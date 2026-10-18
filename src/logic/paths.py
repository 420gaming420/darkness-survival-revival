"""Project-relative path resolution — all paths driven by .env config.

No hardcoded filesystem paths. All paths resolve from src/config.py which
loads from .env / environment variables.
"""

from __future__ import annotations

from pathlib import Path
from src.logic.config import cfg


def project_root() -> Path:
    """Return the project root directory."""
    return cfg.project_root


def ghidra_project_dir() -> Path:
    """Return the Ghidra project directory."""
    return cfg.ghidra_project_dir


def binary_path() -> Path:
    """Return the path to the main binary file."""
    return cfg.binary_path


def textdata_en_path() -> Path:
    """Return the path to textdata_en.dat."""
    return cfg.textdata_en_path


def decompiled_dir() -> Path:
    """Return the output directory for exported function files."""
    return cfg.decompiled_dir


# Ghidra loads stripped ELF binaries at image base 0x10000 by default.
# File offsets = Ghidra addresses - 0x10000.
# The user passes Ghidra addresses (matching --show output and objdump),
# and this module converts them to file offsets for raw binary I/O.
GHIDRA_IMAGE_BASE = cfg.ghidra_image_base


def ghidra_to_file_offset(ghidra_addr: int) -> int:
    """Convert a Ghidra address to a file offset in the binary.

    Args:
        ghidra_addr: Address as seen by Ghidra/pyghidra (e.g., 0x3d1608).

    Returns:
        File offset suitable for raw read/write of the binary on disk.
    """
    return ghidra_addr - GHIDRA_IMAGE_BASE
