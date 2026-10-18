#!/usr/bin/env python3
"""textdata_generate - Reconstruct a .dat file from parsed JSON.

Reads a textdata_en_parsed.json (or any similarly structured JSON) and
rebuilds a binary .dat file. Works with both unmodified and modified strings.

The script dynamically calculates all offsets from the JSON data, so changing
any string's content or address still produces a valid .dat file.

File layout:
    0x00-0x03  Header (uint32 LE = LUT byte count = num_entries * 4)
    0x04-0x07  First string pointer (offset from string region base)
    ...
    0x04+(N-1)*4  Last string pointer
    0x04+N*4-1    Sentinel (end offset of last string)
    After LUT     String data region (null-terminated strings)

Usage:
    python textdata_generate.py --input textdata_en_parsed.json --output textdata_en_copy.dat
    python textdata_generate.py --input modified.json --output modified.dat
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


def load_json(path: str) -> dict:
    """Load and validate the parsed JSON file.

    Args:
        path: Path to the parsed JSON file.

    Returns:
        Parsed JSON data dict.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the JSON structure is invalid.
    """
    data = json.loads(Path(path).read_text(encoding='utf-8'))

    if 'strings' not in data:
        raise ValueError('JSON is missing "strings" key')

    if not isinstance(data['strings'], list):
        raise ValueError('"strings" must be a list')

    required_keys = {'index_addr', 'string_addr', 'ascii_data', 'byte_count'}
    for i, entry in enumerate(data['strings']):
        missing = required_keys - set(entry.keys())
        if missing:
            raise ValueError(f'Entry {i} is missing keys: {missing}')

    return data


def build_string_region(strings: list[dict]) -> tuple[bytes, int]:
    """Assemble the string data region from all entries.

    Each string is placed at its string_addr offset. The region is sized to
    fit the highest (string_addr + string_length).

    Args:
        strings: List of parsed string entries.

    Returns:
        Tuple of (raw bytes, base offset of string region).

    Raises:
        ValueError: If string_addr is missing or invalid.
    """
    if not strings:
        return (b'', 0)

    sorted_entries = sorted(strings, key=lambda e: int(e['string_addr'], 16))

    base_addr = int(sorted_entries[0]['string_addr'], 16)
    max_offset = 0

    for e in sorted_entries:
        addr = int(e['string_addr'], 16)
        raw = e['ascii_data'].encode('utf-8') + b'\x00'
        end = addr + len(raw)
        if end > max_offset:
            max_offset = end

    region = bytearray(max_offset - base_addr)

    for e in sorted_entries:
        addr = int(e['string_addr'], 16)
        raw = e['ascii_data'].encode('utf-8') + b'\x00'
        rel = addr - base_addr
        region[rel:rel + len(raw)] = raw

    return (bytes(region), base_addr)


def build_lut(strings: list[dict], string_region_base: int) -> tuple[bytes, int]:
    """Build the LUT and sentinel from string entries.

    LUT entries are ordered by index_addr (ascending). Each entry stores the
    stripped offset (string_addr - string_region_base) as a uint32 LE.

    The sentinel is appended after all string pointers. It contains the end
    address (string_addr + byte_count) of the last string, also as a stripped
    offset (uint32 LE).

    Args:
        strings: List of parsed string entries.
        string_region_base: The base offset of the string region.

    Returns:
        Tuple of (LUT bytes including sentinel, total LUT byte count).
    """
    sorted_by_index = sorted(strings, key=lambda e: int(e['index_addr'], 16))
    num_entries = len(sorted_by_index)

    # LUT entries (each string pointer) + 1 sentinel entry
    total_entries = num_entries + 1
    lut = bytearray(total_entries * 4)

    # Write each string pointer
    for i, e in enumerate(sorted_by_index):
        string_addr = int(e['string_addr'], 16)
        stripped = string_addr - string_region_base
        off = i * 4  # LUT entries start at index 0 in the buffer
        struct.pack_into('<I', lut, off, stripped)

    # Sentinel: end of the last string (string_addr + length + 1 for null terminator)
    last_entry = sorted_by_index[-1]
    last_addr = int(last_entry['string_addr'], 16)
    last_len = int(last_entry['byte_count']) + 1  # include null terminator
    sentinel = last_addr + last_len - string_region_base
    struct.pack_into('<I', lut, num_entries * 4, sentinel)

    return (bytes(lut), total_entries * 4)


def build_dat(strings: list[dict]) -> bytes:
    """Reconstruct the complete .dat file.

    Layout:
        0x00-0x03:  Header (uint32 LE = total LUT byte count)
        0x04-0x07:  First string pointer (offset from string region base)
        ...
        After LUT:  String data region

    Args:
        strings: List of parsed string entries.

    Returns:
        Complete .dat file as bytes.
    """
    string_region_bytes, string_region_base = build_string_region(strings)
    lut_bytes, lut_byte_count = build_lut(strings, string_region_base)
    pointer_count = len(strings)

    # Header: size of string pointer section only (excludes sentinel)
    header = struct.pack('<I', pointer_count * 4)

    return header + lut_bytes + string_region_bytes


def main():
    parser = argparse.ArgumentParser(
        description='Reconstruct .dat file from parsed JSON'
    )
    parser.add_argument('--input', required=True, help='Input JSON file')
    parser.add_argument('--output', required=True, help='Output .dat file')
    parser.add_argument(
        '--compare',
        default=None,
        help='Original .dat file to compare against (optional)'
    )
    args = parser.parse_args()

    print(f'[*] Loading {args.input}...')
    data = load_json(args.input)
    strings = data['strings']
    print(f'[*] {len(strings)} strings found')

    print('[*] Reconstructing .dat file...')
    dat_bytes = build_dat(strings)
    Path(args.output).write_bytes(dat_bytes)
    print(f'[+] Written {len(dat_bytes):,} bytes to {args.output}')

    # Verify against original if provided
    if args.compare:
        print('[*] Verifying against original...')
        original = Path(args.compare)
        if not original.exists():
            print(f'[!] Original file not found: {original}')
            sys.exit(1)

        original_bytes = original.read_bytes()

        if len(dat_bytes) != len(original_bytes):
            print(f'[FAIL] Size mismatch: {len(dat_bytes):,} vs {len(original_bytes):,}')
            sys.exit(1)

        if dat_bytes == original_bytes:
            print('[+] Byte-for-byte identical to original')
        else:
            # Find first difference
            for i in range(min(len(dat_bytes), len(original_bytes))):
                if dat_bytes[i] != original_bytes[i]:
                    print(f'[FAIL] First difference at byte {i:#08x}')
                    print(f'  Expected: {original_bytes[i]:02x}')
                    print(f'  Got:      {dat_bytes[i]:02x}')
                    sys.exit(1)

        orig_md5 = hashlib.md5(original_bytes).hexdigest()
        new_md5 = hashlib.md5(dat_bytes).hexdigest()
        print(f'  Original MD5: {orig_md5}')
        print(f'  New MD5:      {new_md5}')
        print(f'  [OK] MD5 match: {orig_md5 == new_md5}')


if __name__ == '__main__':
    main()
