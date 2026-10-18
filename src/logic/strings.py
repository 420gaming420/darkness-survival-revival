"""Text data string resolution from textdata_en.dat.

Loads the textdata EN dat file into a dict mapping integer IDs to strings.
All callers get a frozen view — read-only access.
"""

from pathlib import Path


def load_textdata(path: Path) -> dict[int, str]:
    """Load and parse textdata_en.dat into an ID→string dictionary.

    The .dat file has a 4-byte LUT header at offset 0x04, each entry is a
    4-byte little-endian offset into the string region at 0x2E90. Strings
    are null-terminated UTF-8/ASCII.

    Args:
        path: Path to the .dat file (e.g. textdata_en.dat).

    Returns:
        Dict mapping integer IDs to decoded strings.
    """
    data = path.read_bytes()
    lut_start = 0x04
    string_region = 0x2E90
    textdata: dict[int, str] = {}

    num_entries = (0x2E8C - lut_start) // 4 + 1
    for i in range(num_entries):
        off = lut_start + i * 4
        if off + 4 > len(data):
            break
        lut_val = int.from_bytes(data[off:off + 4], "little")
        abs_pos = string_region + lut_val
        try:
            null_pos = data.index(b"\x00", abs_pos)
        except ValueError:
            null_pos = len(data)
        textdata[i] = data[abs_pos:null_pos].decode("utf-8", errors="replace")

    return textdata


def resolve_string(textdata: dict[int, str], gid: int) -> str | None:
    """Resolve a single gettext ID to its string, or None if not found."""
    if 0 <= gid < len(textdata) and textdata[gid]:
        return textdata[gid]
    return None
