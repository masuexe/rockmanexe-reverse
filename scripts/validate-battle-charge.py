#!/usr/bin/env python3
"""Run Japanese EXE6F battle input/charge functions with synthetic RAM state.

Runs original buffer writer, AI input conversion, charge/request functions,
and initialization dispatchers in ordinary mGBA. Sets registers, object/AI
data, battle actor index, and Navi stats in a disposable emulator; does not
load a save or reproduce an actual battle. Captures requests before reset.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re

OBJECT = 0x0203e000
AI = 0x0203e100
STATS = 0x0203ce00
RETURN = 0x080003e4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, default=Path(os.environ.get(
        'EXE_REVERSE_LOCAL_DIR', '/home/harp/projects/exe-reverse')) / 'roms/exe6f.gba')
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    data = args.rom.read_bytes()
    if hashlib.sha1(data).hexdigest() != 'd1ce0ecc8e241a716274b9fb1b6eb07fb42dd166':
        raise ValueError('Requires the verified Japanese EXE6F ROM')
    args.work_dir.mkdir(parents=True, exist_ok=False)
    root = args.work_dir.resolve()
    rom = root / 'exe6f.gba'
    rom.write_bytes(data)
    spec = importlib.util.spec_from_file_location('input_debugger', Path(__file__).with_name('validate-input-update.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', XDG_CONFIG_HOME=str(root / 'config'))
    # Do not inherit the separate SDL input test's preload hook.
    env.pop('LD_PRELOAD', None)
    records = []
    checks = []
    with (root / 'debugger.txt').open('w') as transcript:
        debugger = module.Debugger(['/usr/games/mgba', '-d', str(rom)], env, transcript)
        try:
            debugger.prompt()
            debugger.command(f'break/t {RETURN:#x}')
            debugger.command('continue')
            battle_state = debugger.read(4, 0x020093B0 + 0x18)

            def write(size, address, value):
                response = debugger.command(f'w/{size} {address:#x} {value:#x}')
                if 'error' in response.lower():
                    raise RuntimeError(response)

            def snapshot(label, returned=None):
                text = debugger.command(f'x/1 {AI:#x} 80')
                values = []
                for line in text.splitlines():
                    if re.match(r'^0x[0-9A-Fa-f]+:', line):
                        values.extend(int(v, 16) for v in line.split(':', 1)[1].split())
                if len(values) != 80:
                    raise ValueError(text)
                row = dict(label=label, ai=bytes(values).hex(), count=values[0x1b],
                           state=values[0x1d], button=values[0x1e],
                           flags=int.from_bytes(bytes(values[0x44:0x48]), 'little'), returned=returned)
                records.append(row)
                return row

            def check(label, actual, expected):
                checks.append(dict(label=label, actual=actual, expected=expected, matches=actual == expected))
                if actual != expected:
                    raise AssertionError(checks[-1])

            def call(address, arg=0, arg1=0):
                for register, value in [('r0', arg), ('r1', arg1), ('r5', OBJECT), ('r7', AI + 0xa0),
                                        ('sp', 0x03007000), ('lr', RETURN + 1), ('pc', address)]:
                    debugger.command(f'w/r {register} {value:#x}')
                response = debugger.command('continue')
                if f'at 0x{RETURN:08X}' not in response:
                    raise RuntimeError(response)
                return int(re.search(r'r0: ([0-9A-Fa-f]+)', response)[1], 16)

            def setup(level=0, power=1):
                # Scratch object/AI allocation and the dedicated battle Navi
                # stats are isolated test state; game execution stays stopped.
                for address, size in [(OBJECT, 0x200), (STATS, 0x64)]:
                    for offset in range(0, size, 4):
                        write(4, address + offset, 0)
                write(4, OBJECT + 0x58, AI)
                write(2, OBJECT + 0x28, 0x1a0)  # MegaMan actor name ID.
                write(4, battle_state + 0xd0, OBJECT)  # First friendly battle actor.
                write(1, battle_state + 0x12, 1)
                write(1, battle_state + 0x13, 1)
                write(1, battle_state + 0x0b, 0)
                for offset in range(0, 16, 4):
                    write(4, 0x02036820 + offset, 0)
                for offset, value in [(0, 2), (5, 255), (6, 0), (7, power), (0x11, 255), (0x48, 16)]:
                    write(1, AI + offset, value)
                write(1, STATS + 3, level)
                write(1, STATS + 1, 2)  # Internal attack level 2 => ordinary damage 3.
                write(1, STATS + 0x0e, 1)  # Avoid emotion-result 5 from zeroed Mood.

            def keys(held, previous):
                old = debugger.read(2, AI + 0x22)
                check('input:previous-low-bits', old & 1023, previous)
                current = held | 0xfc00
                call(0x0800a6be, 0, current)  # Original per-alliance input-buffer writer.
                call(0x080133fc, 0)  # Original buffer-to-player-AI conversion.
                actual = [debugger.read(2, AI + offset) for offset in [0x22, 0x24, 0x26, 0x28]]
                check('input:AI-fields', actual, [current, current & ~old, old & ~current, old])

            for label, level, ticks, threshold, final_state, request in [
                ('short', 0, 9, 100, 0, 1),
                ('almost-full', 0, 99, 100, 1, 1),
                ('full', 0, 101, 100, 2, 2),
                ('fast-full', 4, 61, 60, 2, 2),
            ]:
                setup(level)
                check(label + ':threshold', call(0x08013562, 2), threshold)
                previous = 0
                for tick in range(1, ticks + 1):
                    keys(2, previous)
                    previous = 2
                    call(0x080135c8)
                    before = snapshot(f'{label}:{tick}:input')
                    check(f'{label}:{tick}:held-flags', before['flags'], 0x40000)
                    call(0x080134bc)
                    after = snapshot(f'{label}:{tick}:charge')
                    check(f'{label}:{tick}:count', after['count'], min(tick, threshold))
                    check(f'{label}:{tick}:state', after['state'],
                          0 if tick < 10 else 1 if tick < threshold else 2)
                check(label + ':final-state', after['state'], final_state)
                keys(0, 2)
                call(0x080135c8)
                release = snapshot(label + ':release-input')
                check(label + ':release-request', release['flags'], request)
                call(0x080134bc)
                reset = snapshot(label + ':release-charge')
                check(label + ':reset', [reset['count'], reset['state'], reset['button']], [0, 0, 0])

            setup(power=255)
            keys(2, 0)
            call(0x080135c8)
            row = snapshot('charge-disabled:press')
            check('charge-disabled:press-request', row['flags'], 1)

            setup()
            keys(2, 0)
            write(4, AI + 0x48, 0)  # Charge eligibility bit absent.
            call(0x080135c8)
            call(0x080134bc)
            row = snapshot('charge-ineligible:held')
            check('charge-ineligible:state', [row['flags'], row['count'], row['state']], [0, 0, 0])

            for label, address, action, damage in [
                ('normal-init', 0x08011d74, 0x11, 3),
                ('charged-init', 0x08011db4, 0x16, 30),
            ]:
                setup()
                returned = call(address)
                row = snapshot(label, returned)
                attack_damage = debugger.read(2, AI + 0xa8)
                row['attack_damage'] = attack_damage
                check(label + ':action', returned, action)
                check(label + ':damage', attack_damage, damage)
            for label, address, action, damage in [
                ('normal-init-mood-zero', 0x08011d74, 0x11, 1),
                ('charged-init-mood-zero', 0x08011db4, 0x16, 30),
            ]:
                setup()
                write(1, STATS + 0x0e, 0)
                returned = call(address)
                row = snapshot(label, returned)
                row['attack_damage'] = debugger.read(2, AI + 0xa8)
                check(label + ':action', returned, action)
                check(label + ':damage', row['attack_damage'], damage)
        finally:
            debugger.close()
            (root / 'snapshots.json').write_text(json.dumps(dict(
                mode='synthetic-RAM function execution; not an actual battle',
                rom_sha1=hashlib.sha1(data).hexdigest(), records=records, checks=checks), indent=2) + '\n')
    print(f'Passed {len(checks)} checks; {len(records)} snapshots; original ROM functions, synthetic RAM')


if __name__ == '__main__':
    main()
