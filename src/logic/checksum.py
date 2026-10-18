"""SHA256 checksum helpers for binary change detection.

Provides functions to compute, persist, and compare SHA256 hashes of the
libcocos2dcpp.so binary so that re-import into Ghidra only runs when the
binary on disk has actually changed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


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


def read_stored_checksum(checksum_file: Path) -> str | None:
    """Read stored SHA256 from the checksum file, or None if missing.

    Args:
        checksum_file: Path to the .sha256 file.

    Returns:
        Hex digest string, or None if file doesn't exist or is empty.
    """
    try:
        content = checksum_file.read_text().strip()
        return content if content else None
    except (FileNotFoundError, OSError):
        return None


def write_stored_checksum(checksum_file: Path, sha256_hex: str) -> None:
    """Write SHA256 hex digest to the checksum file.

    Args:
        checksum_file: Path to the .sha256 file.
        sha256_hex: Hex digest string to write.
    """
    checksum_file.write_text(sha256_hex + "\n")
