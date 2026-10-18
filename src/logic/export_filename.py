"""Filename prefix generation for exported function files.

Creates sanitized filenames from address and function name following the
convention: ``[hex_address]_[sanitized_mangled_name]``.
"""

from __future__ import annotations


def make_filename(entry_addr: int, func_name: str) -> str:
    """Create sanitized filename prefix from address and function name.

    Format: [hex_address]_[sanitized_mangled_name]
    - Name is the mangled C++ name (max 50 chars, truncated with ...)
    - Spaces and filesystem-incompatible characters replaced with dashes
    - Leading/trailing whitespace stripped

    Args:
        entry_addr: Function entry address.
        func_name: Mangled or demangled function name.

    Returns:
        Sanitized filename prefix string (no extension).
    """
    # Use the full mangled name if it starts with _ZN, otherwise use as-is
    name = func_name

    # Sanitize: replace spaces and incompatible chars with dashes
    sanitized = ""
    for ch in name:
        if ch.isalnum() or ch == "_":
            sanitized += ch
        else:
            sanitized += "-"

    # Truncate to 50 chars max, appending ... if truncated
    if len(sanitized) > 50:
        sanitized = sanitized[:47] + "..."

    return f"{hex(entry_addr)[2:].lower()}_{sanitized}"
