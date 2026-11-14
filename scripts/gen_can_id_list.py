#!/usr/bin/env python3
"""Generate a C header with CAN frame IDs from a DBC file.

Uses the Eko-Energia cantools fork, so the macro names are exactly the ones
`cantools generate_c_source` produces (e.g. RCD_STATIC_CHARGER1COMMS_FRAME_ID)
and the header can be included next to a generated CAN_DB.h without conflicts.

Usage:
    python scripts/gen_can_id_list.py CAN_DB.dbc can_id_list.h
    python scripts/gen_can_id_list.py CAN2_DB.dbc can2_id_list.h
"""

import argparse
import re
import sys
from pathlib import Path

import cantools
from cantools.database.can.c_source import CodeGenMessage

C_IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def build_header(dbc_path: Path, header_name: str) -> str:
    db = cantools.database.load_file(str(dbc_path), strict=True)

    rows = []
    for message in db.messages:
        name = f'{CodeGenMessage(message).snake_name.upper()}_FRAME_ID'
        # Same value format as the fork's generate_c_source.
        value = f'(0x{message.frame_id:02x}u)'
        kind = 'extended' if message.is_extended_frame else 'standard'
        senders = ', '.join(message.senders) or '-'
        rows.append((message.frame_id, name, value, f'{kind}, sender: {senders}'))

    check(rows, dbc_path)
    rows.sort()

    guard = 'INC_' + re.sub(r'[^A-Za-z0-9]', '_', header_name).upper() + '_'
    width = max(len(name) for _, name, _, _ in rows)

    lines = [
        '/*',
        f' * {header_name}',
        ' *',
        ' * AUTO-GENERATED FILE - DO NOT EDIT BY HAND.',
        f' * Source: Eko-Energia/CAN-DATABASE/{dbc_path.name}',
        ' * Generator: scripts/gen_can_id_list.py (Eko-Energia/cantools fork)',
        ' * Change the DBC instead; this file is regenerated on every merge.',
        ' */',
        '',
        f'#ifndef {guard}',
        f'#define {guard}',
        '',
    ]
    for _, name, value, comment in rows:
        lines.append(f'#define {name:<{width}} {value:<14} /* {comment} */')
    lines += ['', f'#endif /* {guard} */', '']
    return '\n'.join(lines)


def check(rows, dbc_path: Path) -> None:
    errors = []
    seen_ids = {}
    seen_names = set()
    for frame_id, name, _, _ in rows:
        if not C_IDENTIFIER.fullmatch(name):
            errors.append(f'{name}: not a valid C identifier')
        if name in seen_names:
            errors.append(f'{name}: duplicate name')
        if frame_id in seen_ids:
            errors.append(f'ID 0x{frame_id:x} used by both {seen_ids[frame_id]} and {name}')
        seen_names.add(name)
        seen_ids[frame_id] = name
    if not rows:
        errors.append('no frames found')
    if errors:
        sys.exit(f'{dbc_path}:\n  ' + '\n  '.join(errors))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('dbc', type=Path, help='input .dbc file')
    parser.add_argument('header', type=Path, help='output .h file')
    args = parser.parse_args()

    text = build_header(args.dbc, args.header.name)
    args.header.parent.mkdir(parents=True, exist_ok=True)
    args.header.write_text(text, encoding='utf-8', newline='\n')
    print(f'{args.header}: {text.count("_FRAME_ID ")} frames from {args.dbc}')


if __name__ == '__main__':
    main()
