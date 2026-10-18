#!/usr/bin/env python3
"""Hex to ASCII converter - runs in a loop accepting hex input."""

import string


def is_valid_hex_char(c: str) -> bool:
    """Check if a character is a valid hex digit."""
    return c in string.hexdigits


def convert_hex_to_ascii(hex_str: str) -> tuple[str, int]:
    """Convert a hex string to ASCII, returning (result, error_count).

    Processes hex pairs from left to right. If a pair of hex digits is
    valid, it is converted to its ASCII character. If a pair is invalid
    or the string has an odd length with a trailing single hex digit,
    that position is replaced with '?' in the output. Non-hex characters
    are also replaced with '?'.

    Args:
        hex_str: The hex string to convert.

    Returns:
        A tuple of (ASCII result string, number of invalid/error positions).
    """
    clean = hex_str.replace(' ', '')
    result = ''
    error_count = 0

    i = 0
    while i < len(clean):
        if i + 1 < len(clean) and is_valid_hex_char(clean[i]) and is_valid_hex_char(clean[i + 1]):
            try:
                result += bytes.fromhex(clean[i:i + 2]).decode('ascii', errors='replace')
                i += 2
            except ValueError:
                result += '?'
                error_count += 1
                i += 1
        else:
            result += '?'
            error_count += 1
            i += 1

    return result, error_count


def main():
    """Run the hex-to-ASCII converter in a loop."""
    print("Hex to ASCII Converter")
    print("Enter hex data to convert (or 'quit' to exit)\n")

    while True:
        user_input = input("Hex: ")

        if user_input.strip().lower() == 'quit':
            break

        if not user_input.strip():
            continue

        ascii_result, errors = convert_hex_to_ascii(user_input)

        if errors > 0:
            print(f"Warning: Invalid hex data. {errors} position(s) could not be converted.\n")

        print(f"ASCII: {ascii_result}\n")


if __name__ == '__main__':
    main()
