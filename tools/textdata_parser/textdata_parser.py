#!/usr/bin/env python3
"""textdata_parser - Parse Darkness Survival textdata_en.dat.

Extracts all null-terminated strings from the game's English text data file,
using the Relative Offset Pointer Table (LUT) to resolve each string's address.

Format: ARM:LE:32:v5 Android APK extraction.
  - Bytes 0x00-0x03: Header offset (uint32 LE) — indicates LUT region size
  - Bytes 0x04-0x2E8C: LUT entries (uint32 LE each) — offset from string region start
  - Bytes 0x2E90+: String data (null-terminated UTF-8/ASCII)

The last LUT entry (0x2E8C) is ignored as it points past the final string.
"""

import argparse
import json
import struct
import sys
from pathlib import Path


# Constants
LUT_START = 0x04
LUT_END = 0x2E8C
STRING_REGION = 0x2E88 + 8  # Header value (0x2E88) + 8 = 0x2E90
SKIP_LAST_ENTRY = True


def load_dat(path: str) -> bytes:
    """Read the .dat file as raw bytes.

    Args:
        path: Filesystem path to the .dat file.

    Returns:
        Raw file contents as bytes.

    Raises:
        FileNotFoundError: If the file does not exist.
        PermissionError: If the file cannot be read.
    """
    return Path(path).read_bytes()


def parse_lut(data: bytes) -> list[dict]:
    """Walk the LUT and extract each null-terminated string.

    Each LUT entry is a 4-byte little-endian uint32 representing an offset
    from the start of the string region (0x2E90). The value at each offset
    is a null-terminated string.

    Args:
        data: Raw file contents.

    Returns:
        List of dicts, each containing:
            index_addr: File offset of the LUT entry itself (hex string).
            string_addr: Absolute file offset of the string (hex string).
            stripped_offset: Offset from string region start (hex string).
            hex_data: Hex representation of the string bytes (without null).
            ascii_data: Decoded string content.
            byte_count: Length of the string in bytes.
    """
    entries = []
    num_entries = (LUT_END - LUT_START) // 4 + 1

    for i in range(num_entries):
        off = LUT_START + i * 4

        # Skip the last LUT entry
        if SKIP_LAST_ENTRY and off == LUT_END:
            continue

        lut_val = struct.unpack_from('<I', data, off)[0]
        abs_pos = STRING_REGION + lut_val

        # Find null terminator
        null_pos = data.index(b'\x00', abs_pos)
        raw_bytes = data[abs_pos:null_pos]

        entry = {
            'index_addr': f'{off:08x}',
            'string_addr': f'{abs_pos:08x}',
            'stripped_offset': f'{lut_val:08x}',
            'hex_data': raw_bytes.hex(),
            'ascii_data': raw_bytes.decode('utf-8', errors='replace'),
            'byte_count': len(raw_bytes),
        }
        entries.append(entry)

    return entries


def format_md_table(entries: list[dict]) -> str:
    """Format entries as a Markdown table.

    Args:
        entries: Parsed LUT entries.

    Returns:
        Markdown table as a string.
    """
    header = '| INDEX_ADDR | STRING_ADDR | HEX_DATA | ASCII_DATA | BYTES |'
    sep = '|---|---|---|---|---|'

    rows = []
    for e in entries:
        row = '| {} | {} | {} | {} | {} |'.format(
            e['index_addr'],
            e['string_addr'],
            e['hex_data'],
            e['ascii_data'],
            '{} bytes'.format(e['byte_count']),
        )
        rows.append(row)

    return header + '\n' + sep + '\n' + '\n'.join(rows) + '\n'


def write_md(entries: list[dict], path: str) -> None:
    """Write the Markdown hexdump table to file.

    Args:
        entries: Parsed LUT entries.
        path: Output file path.
    """
    md = format_md_table(entries)
    Path(path).write_text(md, encoding='utf-8')
    print(f'[+] Written {len(entries)} entries to {path}')


def write_json(entries: list[dict], path: str) -> None:
    """Write structured JSON output to file.

    Args:
        entries: Parsed LUT entries.
        path: Output file path.
    """
    # Header comment
    output = {
        '_header': 'textdata_en.dat parsed strings',
        '_count': len(entries),
        'strings': entries,
    }
    Path(path).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'[+] Written {len(entries)} entries to {path}')


def validate(entries: list[dict]) -> bool:
    """Validate known string addresses against expected content.

    Args:
        entries: Parsed LUT entries.

    Returns:
        True if all validations pass.
    """
    checks = [
        ('00000004', '00002e90', 'Accuracy :<CF3F300FF> High<CFFFFFFFF>'),
        ('00000fa0', None, "It's very hard substance, but easy to process, so commonly used to manufacture weapons."),
        ('00001f40', None, 'Weight Stone'),
        ('00002e88', None, 'Privacy Policy'),
    ]

    all_pass = True
    for idx, exp_abs, exp_str in checks:
        found = None
        for e in entries:
            if e['index_addr'] == idx:
                found = e
                break

        if not found:
            print(f'  [FAIL] {idx}: not found in LUT')
            all_pass = False
            continue

        if exp_abs and found['string_addr'].lower() != exp_abs:
            print(f'  [FAIL] {idx}: expected string_addr {exp_abs}, got {found["string_addr"]}')
            all_pass = False
            continue

        if found['ascii_data'] != exp_str:
            print(f'  [FAIL] {idx}: expected "{exp_str}", got "{found["ascii_data"]}"')
            all_pass = False
            continue

        print(f'  [OK]   {idx} -> {found["string_addr"]}: "{exp_str}"')

    return all_pass


def main():
    parser = argparse.ArgumentParser(
        description='Parse Darkness Survival textdata_en.dat'
    )
    parser.add_argument(
        'input',
        nargs='?',
        default='textdata_en.dat',
        help='Input .dat file (default: textdata_en.dat)',
    )
    args = parser.parse_args()

    print(f'[*] Loading {args.input}...')
    data = load_dat(args.input)
    print(f'[*] File size: {len(data):,} bytes')

    print('[*] Parsing LUT...')
    entries = parse_lut(data)
    print(f'[*] Found {len(entries)} strings')

    print('[*] Validating...')
    if not validate(entries):
        print('[!] Validation FAILED')
        sys.exit(1)
    print('[+] All validations passed')

    md_path = args.input.replace('.dat', '_parsed.md')
    json_path = args.input.replace('.dat', '_parsed.json')

    write_md(entries, md_path)
    write_json(entries, json_path)

    print(f'[*] Done. {len(entries)} strings extracted.')


if __name__ == '__main__':
    main()
