"""getText() string annotation via two-pass constant propagation.

Resolves ``TextDataManager::getText(...)`` calls in decompiled C code to
actual game strings from ``textdata_en.dat``. Uses a two-pass approach:
1. Identify all variable names used as getText() arguments (non-literals)
2. Map each variable to the gettext IDs it can hold via literal assignments

Then annotates each line with the resolved string(s).
"""

from __future__ import annotations

import re


# Regex patterns for matching TextDataManager::getText calls and hex literals
_PATTERNS = {
    "demanged": re.compile(r"(TextDataManager::getText\()([^)]+)(\))"),
    "hex_literal": re.compile(r"^0x([0-9a-fA-F]+)$", re.IGNORECASE),
}


def _get_pattern(name: str) -> re.Pattern:
    """Lazy-load and return a compiled regex pattern.

    Args:
        name: One of 'demanged' or 'hex_literal'.

    Returns:
        Compiled regex pattern object.
    """
    return _PATTERNS[name]


def build_var_ids(lines: list[str]) -> dict[str, list[int]]:
    """Two-pass constant propagation for getText() variable resolution.

    Pass 1: Find all variable names used as arguments to TextDataManager::getText().
    Pass 2: Map each variable to the gettext IDs it can hold via literal assignments.

    Args:
        lines: Formatted C code lines from format_c_code().

    Returns:
        Dict mapping variable name to list of possible gettext IDs.
    """
    pattern = _get_pattern("demanged")
    hex_re = _get_pattern("hex_literal")

    # Pass 1: collect variable names used as getText() args (exclude literals)
    text_vars = set()
    for line in lines:
        for m in pattern.finditer(line):
            arg = m.group(2).strip()
            if not hex_re.match(arg) and not re.match(r"^[0-9]+$", arg):
                text_vars.add(arg)

    # Pass 2: map variables to their possible IDs
    var_ids: dict[str, list[int]] = {}
    for line in lines:
        m = re.match(r"\s*(\w+)\s*=\s*(0x[0-9a-fA-F]+)", line)
        if not m:
            m = re.match(r"\s*(\w+)\s*=\s*(\d+)", line)
        if m:
            var_name = m.group(1)
            try:
                gid = int(m.group(2), 16) if m.group(2).startswith("0x") else int(m.group(2))
                if var_name in text_vars and 0 <= gid < 3000:
                    if var_name not in var_ids:
                        var_ids[var_name] = []
                    if gid not in var_ids[var_name]:
                        var_ids[var_name].append(gid)
            except ValueError:
                pass

    return var_ids


def _resolve_hex_literal(hex_str: str, textdata: dict[int, str]):
    """Resolve a hex literal like '0x995' to (gid, string) or None.

    Args:
        hex_str: Hex string like '0x995'.
        textdata: Loaded textdata dictionary.

    Returns:
        Tuple of (gettext_id, string) or None if not found.
    """
    try:
        gid = int(hex_str, 16)
        if gid in textdata and textdata[gid]:
            return gid, textdata[gid]
    except ValueError:
        pass
    return None


def _resolve_decimal_literal(dec_str: str, textdata: dict[int, str]):
    """Resolve a decimal literal like '2223' to (gid, string) or None.

    Args:
        dec_str: Decimal string like '2223'.
        textdata: Loaded textdata dictionary.

    Returns:
        Tuple of (gettext_id, string) or None if not found.
    """
    try:
        gid = int(dec_str)
        if 0 <= gid < len(textdata) and textdata[gid]:
            return gid, textdata[gid]
    except ValueError:
        pass
    return None


def _format_annotation(gid_list: list[int], textdata: dict[int, str]) -> tuple[str | None, str | None]:
    """Format a list of string IDs into the annotation comment.

    Args:
        gid_list: List of gettext IDs.
        textdata: Loaded textdata dictionary.

    Returns:
        (first_string_or_None, comment_string).
        Single result: ('"string"', '; // N = "string"')
        Multiple:       (None, '// (N possible) N1 = "s1", N2 = "s2", ...')
    """
    resolved = []
    for gid in sorted(set(gid_list)):
        if gid in textdata and textdata[gid]:
            resolved.append(textdata[gid])
    if not resolved:
        return None, None

    # Deduplicate preserving order
    seen = set()
    unique = []
    for s in resolved:
        if s not in seen:
            seen.add(s)
            unique.append(s)

    # Build "N = string" pairs preserving sorted order
    pairs = []
    seen_strs = set()
    for gid in sorted(set(gid_list)):
        if gid in textdata and textdata[gid] and textdata[gid] not in seen_strs:
            seen_strs.add(textdata[gid])
            pairs.append((gid, textdata[gid]))

    if len(pairs) == 1:
        gid, s = pairs[0]
        return s, f"; // {gid} = \"{s}\""
    else:
        parts = ", ".join(f"{g} = \"{s}\"" for g, s in pairs)
        return None, f"// ({len(pairs)} possible) " + parts


def annotate_line(line: str, var_ids: dict[str, list[int]], textdata: dict[int, str]) -> str:
    """Annotate a single C code line with getText() string literals.

    Handles both hex/decimal literals and variable references resolved via
    constant propagation from build_var_ids().

    Args:
        line: A single formatted C code line.
        var_ids: Variable → gettext ID mapping from build_var_ids().
        textdata: Loaded textdata dictionary.

    Returns:
        The annotated line, or the original if no getText() found.
    """
    pattern = _get_pattern("demanged")
    m2 = pattern.search(line)
    if not m2:
        return line

    arg = m2.group(2).strip()

    # Hex literal → resolve directly
    hex_re = _get_pattern("hex_literal")
    if hex_re.match(arg):
        result = _resolve_hex_literal(arg, textdata)
        if result:
            gid, s = result
            escaped = s.replace("\\", "\\\\").replace('"', '\\"')
            return line.replace(m2.group(0), f'gettext({gid}); // {gid} = "{escaped}"')
        return line.replace(m2.group(0), f"gettext({int(arg, 16)})")

    # Decimal literal → resolve directly
    if re.match(r"^[0-9]+$", arg):
        result = _resolve_decimal_literal(arg, textdata)
        if result:
            gid, s = result
            escaped = s.replace("\\", "\\\\").replace('"', '\\"')
            return line.replace(m2.group(0), f'gettext({gid}); // {gid} = "{escaped}"')
        return line.replace(m2.group(0), f"gettext({int(arg)})")

    # Variable → look up all possible IDs from constant propagation
    gid_list = var_ids.get(arg, [])
    if gid_list:
        annotation = _format_annotation(gid_list, textdata)
        if annotation[1]:
            first_gid = min(gid_list)
            if annotation[0] is not None:
                new_call = f'gettext({first_gid}); // {first_gid} = "{annotation[0]}"'
            else:
                new_call = f"gettext({first_gid}){annotation[1]}"
            return line.replace(m2.group(0), new_call)

    return line


def annotate_lines(lines: list[str], textdata: dict[int, str]) -> tuple[list[str], int]:
    """Annotate all lines with getText() strings.

    Args:
        lines: Formatted C code lines.
        textdata: Loaded textdata dictionary.

    Returns:
        (annotated_lines, count_of_gettext_calls_found).
    """
    var_ids = build_var_ids(lines)
    annotated = []
    found_count = 0
    pattern = _get_pattern("demanged")

    for line in lines:
        if pattern.search(line):
            found_count += 1
            annotated.append(annotate_line(line, var_ids, textdata))
        else:
            annotated.append(line)

    return annotated, found_count
