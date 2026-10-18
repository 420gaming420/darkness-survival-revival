#!/usr/bin/env python3
"""Add a newline after every '00' hex byte in a hex string file."""

import sys
from pathlib import Path


def process_hex_file(input_path: str, output_path: str) -> None:
    """Read a hex string from input_path, split on '00', write each segment to output_path.

    Args:
        input_path: Path to the input hex string file.
        output_path: Path to write the processed output.
    """
    hex_data = Path(input_path).read_text().strip()
    result = hex_data.replace("00", "00\n")
    if result.endswith("\n"):
        result = result[:-1]
    Path(output_path).write_text(result + "\n")
    print(f"Done. Output written to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python string_newlines.py <input_hex_file> <output_file>")
        sys.exit(1)
    process_hex_file(sys.argv[1], sys.argv[2])
