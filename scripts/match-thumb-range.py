#!/usr/bin/env python3
"""Find relocation-shaped Thumb instruction ranges in another ROM.

Masks Thumb-1 BL operands and PC-relative LDR offsets only. Candidate matches
require manual checking of call targets and literal values; this is not a
proof of equivalent behavior. Input ranges must contain instructions only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

BASE = 0x08000000


def instructions(data, address):
    offset = 0
    while offset < len(data):
        word = struct.unpack_from('<H', data, offset)[0]
        if word & 0xf800 == 0xf000 and offset + 4 <= len(data):
            low = struct.unpack_from('<H', data, offset + 2)[0]
            if low & 0xf800 == 0xf800:
                displacement = ((word & 0x7ff) << 12) | ((low & 0x7ff) << 1)
                if displacement & (1 << 22):
                    displacement -= 1 << 23
                yield offset, 4, 'bl', address + offset + 4 + displacement
                offset += 4
                continue
        literal = (((address + offset + 4) & ~3) + (word & 255) * 4) if word & 0xf800 == 0x4800 else None
        yield offset, 2, 'literal' if literal is not None else 'instruction', literal
        offset += 2


def match(source, target, start, end):
    data = source[start - BASE:end - BASE]
    if start % 2 or end % 2 or len(data) != end - start:
        raise ValueError('Invalid instruction range')
    pattern = []
    for offset, size, kind, _ in instructions(data, start):
        # Keep both BL halfwords' opcode bits while masking the displacement.
        pattern.append(b'.[\xf0-\xf7].[\xf8-\xff]' if kind == 'bl' else
                       b'.' + re.escape(data[offset + 1:offset + 2]) if kind == 'literal' else
                       re.escape(data[offset:offset + size]))
    candidates = []
    for hit in re.finditer(b''.join(pattern), target, re.S):
        if hit.start() % 2:
            continue
        address = BASE + hit.start()
        candidate_data = target[hit.start():hit.end()]
        relocations = []
        for left, right in zip(instructions(data, start), instructions(candidate_data, address)):
            offset, _, kind, old = left
            if kind == 'instruction':
                continue
            row = dict(offset=hex(offset), kind=kind, source=hex(old), target=hex(right[3]))
            if kind == 'literal':
                row['source_value'] = hex(struct.unpack_from('<I', source, old - BASE)[0])
                row['target_value'] = hex(struct.unpack_from('<I', target, right[3] - BASE)[0])
            relocations.append(row)
        candidates.append(dict(address=hex(address), end=hex(address + len(data)),
                               sha256=hashlib.sha256(candidate_data).hexdigest(), relocations=relocations))
    return dict(source_start=hex(start), source_end=hex(end),
                source_sha256=hashlib.sha256(data).hexdigest(), candidates=candidates)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('target', type=Path)
    parser.add_argument('start', type=lambda value: int(value, 0))
    parser.add_argument('end', type=lambda value: int(value, 0))
    args = parser.parse_args()
    print(json.dumps(match(args.source.read_bytes(), args.target.read_bytes(), args.start, args.end), indent=2))
