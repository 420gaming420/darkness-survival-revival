"""Raw binary file read/write operations.

Provides functions to read, write, and compute SHA256 of the target binary.
All byte values are Python ints (0-256), no signed/unsigned conversion needed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def read_binary(path: Path) -> bytearray:
    """Read entire binary file into a mutable bytearray.

    Args:
        path: Path to the binary file.

    Returns:
        Mutable bytearray of file contents.
    """
    return bytearray(path.read_bytes())


def write_binary(path: Path, data: bytearray | bytes) -> None:
    """Write byte data to the binary file.

    Args:
        path: Path to the binary file.
        data: Bytes or bytearray to write.
    """
    path.write_bytes(bytes(data))


def compute_sha256(path: Path) -> str:
    """Compute SHA256 hex digest of a file.

    Args:
        path: Path to the file.

    Returns:
        Hex digest string.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_bytes(data: bytearray | bytes, offset: int, length: int) -> bytes:
    """Read a slice of bytes from binary data.

    Args:
        data: Binary data (bytearray or bytes).
        offset: Start offset (inclusive).
        length: Number of bytes to read.

    Returns:
        Bytes slice.
    """
    return bytes(data[offset:offset + length])


def write_bytes(data: bytearray, offset: int, new_bytes: bytes | bytearray | list[int]) -> None:
    """Write bytes into binary data at a given offset (in-place).

    Args:
        data: Mutable bytearray of the binary.
        offset: Start offset (inclusive).
        new_bytes: Bytes or list of ints to write.
    """
    if isinstance(new_bytes, list):
        new_bytes = bytes(new_bytes)
    for i, b in enumerate(new_bytes):
        data[offset + i] = b
