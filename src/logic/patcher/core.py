"""Patch dataclass and preview logic for the binary patcher tool.

Provides the ``Patch`` dataclass (offset + bytes + optional name) and
``preview_patches()`` which shows hex dump of each patch before/after.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path


@dataclasses.dataclass
class Patch:
    """A single memory patch: write bytes at a file offset.

    Attributes:
        offset: File offset (int, not hex string) where bytes are written.
        bytes: New bytes to write (list of ints 0-256 or bytes/bytearray).
        name: Optional human-readable name for this patch.
    """
    offset: int
    bytes: list[int] | bytes | bytearray
    name: str = ""

    def __post_init__(self):
        if isinstance(self.bytes, (bytes, bytearray)):
            self.bytes = list(self.bytes)
        elif isinstance(self.bytes, list):
            self.bytes = [b & 0xff for b in self.bytes]


def _to_jbyte(val: int) -> int:
    """Convert unsigned int (0-255) to Java byte (-128..127)."""
    return val if val < 128 else val - 256


def preview_patches(patches: list[Patch], binary_path: Path) -> str:
    """Preview patches by disassembling affected ranges.

    Reads the current binary, applies each patch in-memory, and returns
    a formatted string showing each patch's hex bytes and disassembly.

    Args:
        patches: List of Patch objects to preview.
        binary_path: Path to the binary file (for reading original bytes).

    Returns:
        Formatted preview string with hex dumps and disassembly info.
    """
    data = bytearray(binary_path.read_bytes())
    lines = []

    for patch in patches:
        offset = patch.offset
        length = len(patch.bytes)
        end = offset + length

        # Original bytes
        orig = data[offset:end]
        orig_hex = " ".join(f"{b:02x}" for b in orig)

        # New bytes
        new = list(patch.bytes)
        new_hex = " ".join(f"{b:02x}" for b in new)

        lines.append(f"OFFSET 0x{offset:x} (length {length} bytes)")
        if patch.name:
            lines.append(f"  NAME: {patch.name}")
        lines.append(f"  ORIGINAL: {orig_hex}")
        lines.append(f"  PATCHED:  {new_hex}")

        # Show each 2-byte Thumb word with disassembly hint
        i = 0
        while i < length:
            word = bytes(new[i:i+2]) if i + 1 < length else bytes([new[i]])
            word_hex = " ".join(f"{b:02x}" for b in word)
            lines.append(f"    [{hex(offset + i)}] {word_hex}")
            i += 2

        lines.append("")

    return "\n".join(lines)
