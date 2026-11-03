#!/usr/bin/env python3
"""Decode hex float constants found in decompiled code.

Usage:
    python3 decode_float.py 0xbf0ccccd
    python3 decode_float.py 0xbf800000 0x3f800000
    python3 decode_float.py --all  # Show common constants table
"""

import sys
import struct


def decode_hex_float(hex_val):
    """Decode a hex float constant and return human-readable information."""
    # Remove 0x prefix if present
    hex_str = hex_val.replace('0x', '').replace('0X', '')

    try:
        int_val = int(hex_str, 16)
    except ValueError:
        print(f"Error: '{hex_val}' is not a valid hex number")
        return None

    # Interpret as IEEE 754 single-precision float
    float_val = struct.unpack('f', struct.pack('I', int_val))[0]

    return {
        'hex': f'0x{int_val:08x}',
        'float': float_val,
        'approx': approx_value(float_val),
    }


def approx_value(val):
    """Return a human-friendly approximation of the float value."""
    if val == 0.0:
        return '0.0'
    if val == -0.0:
        return '-0.0'
    if val == 1.0:
        return '1.0'
    if val == -1.0:
        return '-1.0'

    # Check for common fractions
    fractions = [
        (0.25, '1/4'),
        (0.5, '1/2'),
        (0.75, '3/4'),
        (0.7, '7/10'),
        (0.666667, '2/3'),
        (0.55, '11/20'),
        (0.333333, '1/3'),
        (0.2, '1/5'),
        (0.1, '1/10'),
        (-0.25, '-1/4'),
        (-0.5, '-1/2'),
        (-0.7, '-7/10'),
        (-0.55, '-11/20'),
    ]

    for exact, frac in fractions:
        if abs(val - exact) < 0.001:
            return frac

    # Round to 2 decimal places
    return f'{val:.2f}'


def print_common_constants():
    """Print a table of common float constants."""
    print("=== Common Float Constants in Games ===\n")
    print(f"{'Value':<12} {'Hex':<12} {'Notes'}")
    print("-" * 50)

    constants = [
        (-10.0, 'large negative'),
        (-5.0, ''),
        (-2.0, ''),
        (-1.5, ''),
        (-1.0, 'one'),
        (-0.75, 'three quarters'),
        (-0.7, 'seven tenths'),
        (-0.666667, 'negative two-thirds'),
        (-0.55, 'negative fifty-five hundredths'),
        (-0.5, 'negative one half'),
        (-0.25, 'negative one quarter'),
        (-0.1, 'negative one tenth'),
        (0.0, 'zero'),
        (0.25, 'one quarter'),
        (0.5, 'one half'),
        (0.7, 'seven tenths'),
        (0.75, 'three quarters'),
        (1.0, 'one'),
        (1.5, 'one and a half'),
        (2.0, 'two'),
        (5.0, 'five'),
        (10.0, 'ten'),
    ]

    for val, note in constants:
        hex_val = struct.unpack('I', struct.pack('f', val))[0]
        approx = approx_value(val)
        print(f"{approx:<12} 0x{hex_val:08x}    {note}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == '--all':
        print_common_constants()
        return

    # Decode each provided hex value
    results = []
    for arg in sys.argv[1:]:
        if arg.startswith('-') and arg != '--all':
            continue
        result = decode_hex_float(arg)
        if result:
            results.append(result)

    # Print results
    print("\n=== Decoded Float Constants ===\n")
    for r in results:
        print(f"{r['hex']}  =  {r['float']:.10f}  (≈ {r['approx']})")

    if len(results) == 1:
        print(f"\nInterpretation: This is the float constant {results[0]['approx']}")
        print("In C/C++ code, this would be written as: {0:.4f}f".format(results[0]['float']))


if __name__ == '__main__':
    main()
