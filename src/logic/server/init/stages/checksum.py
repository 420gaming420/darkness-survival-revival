"""SHA256 checksum helpers.

Pure functions for computing and persisting binary hashes.
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


def save_checksum(binary: Path, sha256_hex: str) -> None:
    """Save SHA256 hex digest to the checksum file.

    Args:
        binary: Path to libcocos2dcpp.so (checksum saved as .sha256).
        sha256_hex: Hex digest string to write.
    """
    checksum_file = Path(str(binary) + ".sha256")
    checksum_file.write_text(sha256_hex + "\n")


def needs_reanalysis(binary: Path, ghidra_project_dir: Path, project_name: str) -> bool:
    """Check if the binary has changed and needs re-analysis.

    Args:
        binary: Path to libcocos2dcpp.so.
        ghidra_project_dir: Path to the Ghidra project directory.
        project_name: Name of the Ghidra project.

    Returns:
        True if re-analysis is needed, False if up to date.
    """
    checksum_file = Path(str(binary) + ".sha256")
    current_sha = compute_sha256(binary)
    try:
        stored_sha = checksum_file.read_text().strip()
        return current_sha != stored_sha
    except FileNotFoundError:
        return True
