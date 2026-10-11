#!/usr/bin/env python3
"""Extract SF2 JP Berserk x Shinobi gauge tiles and assemble a 56px HUD core.

SF2 stores loose cockpit tiles, not the SF3 animation/sprite container. The
frame height is assembled from original corners/edge tiles around a 56px core.
The three ready tiles and their flipped copies form a 48-row flow pattern.
Two original-game captures confirm its layout and eight-row downward steps.
"""
import argparse
import hashlib
import json
import pathlib
import struct
try:
    from extract_starforce3_gauge import archive_member, rom_file, write_png
except ImportError:
    from scripts.starforce.extract_starforce3_gauge import archive_member, rom_file, write_png

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
EXPORT_ROOT = PROJECT_ROOT / 'exports' / 'starforce'

RESOURCE = 'datbin/jpn/cockpit_local.bin'
HEIGHT = 56


def decode(raw, palette):
    colors = struct.unpack_from('<16H', palette)
    rgba = [bytes(((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31,
                   ((v >> 10) & 31) * 255 // 31, 255 if i else 0))
            for i, v in enumerate(colors)]
    return [b''.join(rgba[(raw[t * 32 + y * 4 + x // 2] >> (x % 2 * 4)) & 15]
                     for y in range(8) for x in range(8))
            for t in range(len(raw) // 32)]


def tile_blit(canvas, width, tile, x, y, flip=False):
    for row in range(8):
        for col in range(8):
            src = (row * 8 + (7 - col if flip else col)) * 4
            dest = ((y + row) * width + x + col) * 4
            canvas[dest:dest + 4] = tile[src:src + 4]


def frame(tiles, empty):
    # 3-column tile assembly: left lettering/bend, middle, right edge.
    # Edge tile 6 repeats to give seven interior rows (56 pixels).
    result = bytearray(24 * 72 * 4)
    for row, index in enumerate([0, 1, 2, 3, 4, 5, 6, 6, 7]):
        tile_blit(result, 24, tiles[index], 0, row * 8)
    tile_blit(result, 24, tiles[8], 8, 0)
    for row in range(1, 8):
        tile_blit(result, 24, empty, 8, row * 8)
        tile_blit(result, 24, tiles[6], 16, row * 8, True)
    tile_blit(result, 24, tiles[9], 8, 64)
    tile_blit(result, 24, tiles[10], 16, 0)
    tile_blit(result, 24, tiles[7], 16, 64, True)
    return b''.join(result[(y * 24 + 1) * 4:(y * 24 + 21) * 4] for y in range(72))


def filled(base, strip, phase=0):
    result = bytearray(base)
    rows = len(strip) // 32
    for y in range(HEIGHT):
        dest = ((y + 8) * 20 + 7) * 4
        src = ((y + phase) % rows) * 32
        result[dest:dest + 32] = strip[src:src + 32]
    return result


def ready_strip(tiles):
    # Match docs/research/starforce/images/original-frame0.png: tile 2, flipped 2, tile 0, tile 1, flipped 1,
    # flipped 0. Both-axis flips preserve the staggered highlight pattern.
    def flipped(tile):
        return b''.join(tile[i * 4:(i + 1) * 4] for i in range(63, -1, -1))
    return (tiles[2] + flipped(tiles[2]) + tiles[0] + tiles[1]
            + flipped(tiles[1]) + flipped(tiles[0]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=pathlib.Path)
    parser.add_argument('--output', type=pathlib.Path, default=EXPORT_ROOT / 'sf2')
    parser.add_argument('--preview', type=pathlib.Path, default=EXPORT_ROOT / 'sf2' / 'preview.png')
    parser.add_argument('--raw-output', type=pathlib.Path, default=EXPORT_ROOT / 'sf2' / 'source')
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    if rom[:16] != b'RR2_V_VS_S\x00\x00YRVJ':
        raise ValueError('Expected Japanese SF2 Berserk x Shinobi ROM')
    archive = rom_file(rom, RESOURCE)
    members = {i: archive_member(archive, i) for i in (5, 6, 19, 20, 21, 22, 23)}
    expected_sizes = {5: 64, 6: 32, 19: 384, 20: 224, 21: 288, 22: 384, 23: 96}
    if {i: len(raw) for i, raw in members.items()} != expected_sizes:
        raise ValueError('Unsupported SF2 cockpit tile layout')
    border = decode(members[19], members[5])
    progress_tiles = decode(members[21], members[5])
    ready_tiles = decode(members[23], members[6])
    # Original strip runs from white (tile 0) to dark blue (tile 8).
    # Dark blue is the empty background; white is the charging progress.
    base = frame(border, progress_tiles[8])
    progress = progress_tiles[0] * 7
    flow = ready_strip(ready_tiles)
    args.output.mkdir(parents=True, exist_ok=True)
    write_png(args.output / 'WRGEMPTY.png', 20, 72, base)
    write_png(args.output / 'WRGFILL.png', 8, HEIGHT, progress)
    states = [base, filled(base, progress)]
    for i in range(6):
        pixels = filled(base, flow, -i * 8)
        write_png(args.output / f'WRGRD{i:02}.png', 20, 72, pixels)
        states.append(pixels)
    for i in (6, 7):
        (args.output / f'WRGRD{i:02}.png').unlink(missing_ok=True)
    # Preserve raw original gauge/LR tiles as extraction evidence, outside src.
    raw_dir = args.raw_output
    raw_dir.mkdir(parents=True, exist_ok=True)
    for i, raw in members.items():
        (raw_dir / f'cockpit_local_{i:02}.bin').write_bytes(raw)
    args.preview.parent.mkdir(parents=True, exist_ok=True)
    width = len(states) * 20
    preview = bytearray(width * 72 * 4)
    for i, pixels in enumerate(states):
        for y in range(72):
            dest = (y * width + i * 20) * 4
            preview[dest:dest + 80] = pixels[y * 80:(y + 1) * 80]
    write_png(args.preview, width, 72, preview)
    print(json.dumps({'resource': RESOURCE, 'rom_sha256': hashlib.sha256(rom).hexdigest(),
                      'members': {i: hashlib.sha256(raw).hexdigest() for i, raw in members.items()},
                      'canvas': [20, 72], 'fill': [8, HEIGHT], 'files': 8}, indent=2))


if __name__ == '__main__':
    main()
