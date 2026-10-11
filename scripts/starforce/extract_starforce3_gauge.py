#!/usr/bin/env python3
"""Extract MMSF3 Custom Gauge from a supplied Red Joker JP Rev 1 ROM.

Standard-library only. Reads Nitro FNT/FAT, the game's offset/size archive,
LZ11, and 4bpp SF sprite layouts. Never redistributes or bundles the ROM.
Format cross-check: https://github.com/brianuuu/BNSpriteEditor (LoadSF).
"""
import argparse
import hashlib
import json
import pathlib
import struct
import zlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
EXPORT_ROOT = PROJECT_ROOT / 'exports' / 'starforce'

RESOURCE = 'datbin/com/btl_cockpit_local.bin'
HEIGHT = 76


def write_png(path, width, height, pixels):
    def chunk(kind, data):
        return (struct.pack('>I', len(data)) + kind + data
                + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))
    scanlines = b''.join(b'\0' + bytes(pixels[y * width * 4:(y + 1) * width * 4])
                        for y in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'
                     + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b''))


def decompress(data):
    if data[0] != 0x11:
        raise ValueError('Expected LZ11 stream')
    size = int.from_bytes(data[1:4], 'little')
    pos, output = 4, bytearray()
    while len(output) < size:
        flags = data[pos]
        pos += 1
        for bit in range(7, -1, -1):
            if len(output) >= size:
                break
            if not flags & (1 << bit):
                output.append(data[pos])
                pos += 1
                continue
            a, b = data[pos:pos + 2]
            pos += 2
            prefix = a >> 4
            if prefix == 0:
                c = data[pos]
                pos += 1
                length = ((a & 15) << 4 | b >> 4) + 17
                distance = ((b & 15) << 8 | c) + 1
            elif prefix == 1:
                c, d = data[pos:pos + 2]
                pos += 2
                length = ((a & 15) << 12 | b << 4 | c >> 4) + 273
                distance = ((c & 15) << 8 | d) + 1
            else:
                length = prefix + 1
                distance = ((a & 15) << 8 | b) + 1
            if distance > len(output) or len(output) + length > size:
                raise ValueError('Invalid LZ11 back-reference')
            for _ in range(length):
                output.append(output[-distance])
    return bytes(output)


def rom_file(rom, wanted):
    fnt_offset, fnt_size, fat_offset = struct.unpack_from('<III', rom, 0x40)
    names = rom[fnt_offset:fnt_offset + fnt_size]

    def walk(directory, prefix):
        pos, file_id, _ = struct.unpack_from('<IHH', names, (directory & 0xfff) * 8)
        while names[pos]:
            length = names[pos]
            pos += 1
            name = names[pos:pos + (length & 127)].decode('ascii')
            pos += length & 127
            path = prefix + name
            if length & 128:
                child = struct.unpack_from('<H', names, pos)[0]
                pos += 2
                yield from walk(child, path + '/')
            else:
                yield path, file_id
                file_id += 1
    for path, file_id in walk(0xf000, ''):
        if path == wanted:
            start, end = struct.unpack_from('<II', rom, fat_offset + file_id * 8)
            return rom[start:end]
    raise ValueError('ROM resource missing: ' + wanted)


def archive_member(archive, index):
    start, size = struct.unpack_from('<II', archive, index * 8)
    end = struct.unpack_from('<I', archive, (index + 1) * 8)[0]
    data = archive[start:end]
    result = decompress(data) if size & 0x80000000 else data[:size]
    if len(result) != size & 0x7fffffff:
        raise ValueError('Archive member size mismatch')
    return result


def sprite(data, index, palette_index):
    tiles, palettes, _, layouts, _ = struct.unpack_from('<5I', data)
    if struct.unpack_from('<H', data, palettes)[0] != 5:
        raise ValueError('Expected 4bpp sprite')
    count, first = struct.unpack_from('<HH', data, tiles + 8 + index * 4)
    header = struct.unpack_from('<H', data, tiles + 4)[0]
    raw = data[tiles + header + first * 32:tiles + header + (first + count) * 32]
    colors = struct.unpack_from('<16H', data, palettes + 4 + palette_index * 32)
    palette = [((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31,
                ((v >> 10) & 31) * 255 // 31, 255 if i else 0)
               for i, v in enumerate(colors)]
    sizes = (((8, 8), (16, 8), (8, 16)), ((16, 16), (32, 8), (8, 32)),
             ((32, 32), (32, 16), (16, 32)), ((64, 64), (64, 32), (32, 64)))
    pos = layouts + struct.unpack_from('<I', data, layouts + 4 + index * 4)[0]
    objects = []
    while True:
        tile, x, y, size, shape, flip, last, high = data[pos:pos + 8]
        pos += 8
        x = x if x < 128 else x - 256
        y = y if y < 128 else y - 256
        width, height = sizes[size][shape]
        objects.append((tile * 2 + high * 512, x, y, width, height, flip))
        if last:
            break
    left = min(obj[1] for obj in objects)
    top = min(obj[2] for obj in objects)
    width = max(obj[1] + obj[3] for obj in objects) - left
    height = max(obj[2] + obj[4] for obj in objects) - top
    pixels = bytearray(width * height * 4)
    for tile, ox, oy, ow, oh, flip in objects:
        for y in range(oh):
            for x in range(ow):
                sx = ow - 1 - x if flip & 1 else x
                sy = oh - 1 - y if flip & 2 else y
                tile_index = tile + sy // 8 * (ow // 8) + sx // 8
                value = raw[tile_index * 32 + sy % 8 * 4 + sx % 8 // 2] >> (sx % 2 * 4) & 15
                if value:
                    dest = ((oy - top + y) * width + ox - left + x) * 4
                    pixels[dest:dest + 4] = bytes(palette[value])
    return width, height, pixels


def animation(data, index):
    """Return the ROM's (sprite, duration, palette) sequence and loop flag."""
    header = struct.unpack_from('<I', data, 8)[0]
    count = struct.unpack_from('<H', data, header)[0]
    if not 0 <= index < count:
        raise ValueError('Animation index outside sprite header')
    pos = header + struct.unpack_from('<I', data, header + 4 + index * 4)[0]
    frames = []
    while True:
        sprite_index, duration, flags, palette_index = data[pos:pos + 4]
        pos += 4
        if duration == 0:
            raise ValueError('Zero-duration animation frame')
        frames.append((sprite_index, duration, palette_index))
        if flags & 0xc0:
            return frames, bool(flags & 0x40)


def gauge(data, amount, ready_palette=0, frame_index=0):
    # Keep the user's 18x89 body crop. The ready sprites' L/R wings are
    # excluded, but their animated body pixels are decoded unchanged.
    width, _, frame = sprite(data, frame_index, ready_palette)
    crop_left = 34 if frame_index else 2
    result = bytearray(18 * 89 * 4)
    for y in range(89):
        for x in range(18):
            src = (y * width + crop_left + x) * 4
            dest = (y * 18 + x) * 4
            result[dest:dest + 4] = frame[src:src + 4]
    # Ready sprites already contain the original animated fill/highlights.
    if frame_index:
        return result
    # Sprite 17 is the original complete eight-row charging fill tile.
    _, _, fill = sprite(data, 17, ready_palette)
    for y in range(82 - amount, 82):
        for x in range(1, 8):
            dest = (y * 18 + 7 + x) * 4
            src = ((y % 8) * 8 + x) * 4
            result[dest:dest + 4] = fill[src:src + 4]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=pathlib.Path)
    parser.add_argument('--output', type=pathlib.Path, default=EXPORT_ROOT / 'sf3')
    parser.add_argument('--preview', type=pathlib.Path, default=EXPORT_ROOT / 'sf3' / 'preview.png')
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    if rom[:16] != b'RR3_R_JOKER\x00CRRJ':
        raise ValueError('Expected Japanese MMSF3 Red Joker ROM')
    data = archive_member(rom_file(rom, RESOURCE), 3)
    # Verified layout fingerprint: nineteen sprites, twelve animations.
    if len(data) != 19964 or struct.unpack_from('<5I', data) != (20, 19176, 19276, 19404, 1):
        raise ValueError('Unsupported cockpit sprite layout')
    args.output.mkdir(parents=True, exist_ok=True)
    write_png(args.output / 'S3GEMPTY.png', 18, 89, gauge(data, 0))
    # Only the seven-pixel interior, with no border or CUSTOM lettering.
    full = gauge(data, HEIGHT)
    progress = b''.join(full[(y * 18 + 8) * 4:(y * 18 + 15) * 4]
                        for y in range(6, 82))
    write_png(args.output / 'S3GFILL.png', 7, HEIGHT, progress)
    # Remove the old generated per-height composites from previous exports.
    for amount in range(HEIGHT + 1):
        (args.output / f'WRG{amount:03}.png').unlink(missing_ok=True)
    ready_frames, loops = animation(data, 1)
    expected = [(i, 4, 1 if i % 2 else 2) for i in range(1, 9)]
    if ready_frames != expected or not loops:
        raise ValueError('Unsupported ready animation sequence')
    decoded = []
    for i, (frame_index, duration, palette) in enumerate(ready_frames):
        pixels = gauge(data, HEIGHT, palette, frame_index)
        decoded.append(pixels)
        write_png(args.output / f'S3GRD{i:02}.png', 18, 89, pixels)
    # These two approximated ready images are superseded by the ROM sequence.
    for name in ('WRGRDY1.png', 'WRGRDY2.png'):
        (args.output / name).unlink(missing_ok=True)
    states = [gauge(data, 0), gauge(data, 38)] + decoded
    preview_width = 18 * len(states)
    preview = bytearray(preview_width * 89 * 4)
    for i, pixels in enumerate(states):
        for y in range(89):
            dest = (y * preview_width + i * 18) * 4
            preview[dest:dest + 18 * 4] = pixels[y * 18 * 4:(y + 1) * 18 * 4]
    write_png(args.preview, preview_width, 89, preview)
    manifest = {'resource': RESOURCE, 'member': 3, 'rom_sha256': hashlib.sha256(rom).hexdigest(),
                'sprite_sha256': hashlib.sha256(data).hexdigest(), 'fill_height': HEIGHT,
                'canvas': [18, 89], 'fill_canvas': [7, HEIGHT], 'files': 10, 'ready_animation': ready_frames,
                'ready_loops': loops}
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
