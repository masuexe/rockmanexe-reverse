#!/usr/bin/env python3
"""Compare real mGBA function execution with a proposed input-update model.

Uses a disposable ROM copy and SDL input events; preserves personal saves.
Requires Linux, cc, SDL2 headers, and the ordinary mGBA SDL debugger.
Outputs debugger transcript and snapshots to a new working directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pty
import re
import select
import struct
import subprocess
import time


def model(before, hardware):
    result = bytearray(before)
    phase = before[0x13] + 1
    if phase > 4:
        phase = 0
    result[0x13] = phase
    previous = struct.unpack_from('<H', before)[0]
    current = (~hardware) & 0xffff
    repeat = current & previous
    for bit in range(10):
        if repeat & (1 << bit):
            count = before[8 + bit]
            if count < 16:
                count += 1
                result[8 + bit] = count
                if count != 1:
                    repeat &= ~(1 << bit)
            elif phase != 0:
                repeat &= ~(1 << bit)
        else:
            result[8 + bit] = 0
    struct.pack_into('<4H', result, 0, current, current & ~previous, repeat, previous)
    return bytes(result)


class Debugger:
    def __init__(self, command, env, transcript):
        self.master, slave = pty.openpty()
        self.process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave, env=env)
        os.close(slave)
        self.transcript = transcript

    def prompt(self):
        output = b''
        deadline = time.monotonic() + 20
        while not output.endswith(b'> '):
            if time.monotonic() > deadline:
                raise TimeoutError(output.decode(errors='replace'))
            if select.select([self.master], [], [], 0.2)[0]:
                chunk = os.read(self.master, 65536)
                if not chunk:
                    raise RuntimeError('Debugger closed')
                output += chunk
        text = output.decode(errors='replace').replace('\r', '')
        self.transcript.write(text)
        self.transcript.flush()
        return text

    def command(self, text):
        os.write(self.master, (text + '\n').encode())
        return self.prompt()

    def read(self, size, address):
        text = self.command(f'r/{size} 0x{address:08x}')
        return int(re.search(r'\n\s*0x([0-9A-Fa-f]+)\s*\n', text)[1], 16)

    def snapshot(self, address):
        text = self.command(f'x/1 0x{address:08x} 20')
        values = []
        for line in text.splitlines():
            if re.match(r'^0x[0-9A-Fa-f]+:', line):
                values.extend(int(value, 16) for value in line.split(':', 1)[1].split())
        if len(values) != 20:
            raise ValueError(text)
        return bytes(values)

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        os.close(self.master)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, default=Path(os.environ.get(
        'EXE_REVERSE_LOCAL_DIR', '/home/harp/projects/exe-reverse')) / 'roms/exe6f.gba')
    parser.add_argument('--work-dir', type=Path, required=True, help='New disposable output directory')
    parser.add_argument('--mgba', default='/usr/games/mgba')
    args = parser.parse_args()
    data = args.rom.read_bytes()
    digest = hashlib.sha1(data).hexdigest()
    if digest != 'd1ce0ecc8e241a716274b9fb1b6eb07fb42dd166':
        raise ValueError('Requires the verified Japanese EXE6F baseline ROM')
    args.work_dir.mkdir(parents=True, exist_ok=False)
    rom = args.work_dir.resolve() / 'exe6f.gba'
    rom.write_bytes(data)
    library = rom.parent / 'input-events.so'
    subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror', '-o', str(library),
                    str(Path(__file__).with_name('mgba-input-events.c')), '-ldl'], check=True)
    keyfile = rom.parent / 'keys.txt'
    keyfile.write_text('0\n')
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
               XDG_CONFIG_HOME=str(rom.parent / 'config'), LD_PRELOAD=str(library),
               EXE6_INPUT_MASK_FILE=str(keyfile))
    scenarios = [('none', 0, 3), ('A-held', 1, 26), ('release-A', 0, 3),
                 ('A+B', 3, 4), ('release-AB', 0, 3), ('R', 256, 4),
                 ('release-R', 0, 3), ('L', 512, 4), ('release-L', 0, 3)]
    samples = []
    with (rom.parent / 'debugger.txt').open('w') as transcript:
        debugger = Debugger([args.mgba, '-d', str(rom)], env, transcript)
        try:
            debugger.prompt()
            debugger.command('break/t 0x080003E4')
            debugger.command('break/t 0x080003F8')
            debugger.command('break/t 0x08000448')
            debugger.command('continue')
            address = debugger.read(4, 0x020093B4)
            for label, wanted, count in scenarios:
                keyfile.write_text(f'{wanted}\n')
                for _ in range(count):
                    before = debugger.snapshot(address)
                    cached_hardware = debugger.read(2, 0x04000130)
                    read_text = debugger.command('continue')
                    if 'at 0x080003F8' not in read_text:
                        raise RuntimeError(read_text)
                    # Capture the CPU's actual ldrh result. Debugger peeks of
                    # KEYINPUT can lag the frontend input by one CPU read.
                    hardware = int(re.search(r'r4: ([0-9A-Fa-f]+)', read_text)[1], 16)
                    exit_text = debugger.command('continue')
                    if 'at 0x08000448' not in exit_text:
                        raise RuntimeError(exit_text)
                    after = debugger.snapshot(address)
                    expected = model(before, hardware)
                    sample = dict(index=len(samples), scenario=label, requested_keys=wanted,
                                  hardware=hardware, debugger_keyinput=cached_hardware,
                                  keys=(~hardware) & 1023,
                                  before=before.hex(), after=after.hex(), expected=expected.hex(),
                                  matches=after == expected)
                    samples.append(sample)
                    if after != expected:
                        raise AssertionError(sample)
                    entry_text = debugger.command('continue')
                    if 'at 0x080003E4' not in entry_text:
                        raise RuntimeError(entry_text)
        finally:
            debugger.close()
            report = dict(rom_sha1=digest, structure_address=hex(address) if 'address' in locals() else None,
                          samples=samples, matched=sum(s['matches'] for s in samples))
            (rom.parent / 'snapshots.json').write_text(json.dumps(report, indent=2) + '\n')
    observed = {sample['keys'] for sample in samples}
    if not {0, 1, 3, 256, 512}.issubset(observed):
        raise AssertionError(f'SDL input scenarios incomplete: {observed}')
    a_samples = [bytes.fromhex(s['after']) for s in samples if s['keys'] == 1 and s['scenario'] == 'A-held']
    if not any(a[8] == 16 and (a[4] & 1) for a in a_samples):
        raise AssertionError('A hold did not reach a saturated repeat event')
    if not any(a[8] == 16 and not (a[4] & 1) for a in a_samples):
        raise AssertionError('A hold did not cover suppressed saturated repeat frames')
    for key, offset in [(256, 0x10), (512, 0x11)]:
        if not any(s['keys'] == key and bytes.fromhex(s['after'])[offset] > 0 for s in samples):
            raise AssertionError(f'Missing shoulder counter coverage for {key:#x}')
    print(f"Matched {len(samples)} snapshots; keys {sorted(observed)}; structure {address:#010x}")


if __name__ == '__main__':
    main()
