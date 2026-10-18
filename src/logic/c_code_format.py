"""Single-line decompiled C code → indented multi-line formatting.

Splits at { } ; to get statements, then reassembles with proper
indentation for readable output.
"""

from __future__ import annotations


def format_c_code(ccode: str) -> list[str]:
    """Format single-line decompiled C code into indented multi-line.

    Splits at { } ; to get statements, then reassembles with proper indentation.

    Args:
        ccode: Single-line Clang C code from the decompiler.

    Returns:
        List of formatted lines ready for output or annotation.
    """
    raw_parts = []
    buf = ""
    for ch in ccode:
        if ch == "{":
            stripped = buf.strip()
            if stripped:
                raw_parts.append(("stmt", stripped))
            raw_parts.append(("open_brace"))
            buf = ""
        elif ch == "}":
            stripped = buf.strip()
            if stripped:
                raw_parts.append(("stmt", stripped))
            raw_parts.append(("close_brace"))
            buf = ""
        elif ch == ";":
            stripped = buf.strip()
            if stripped:
                raw_parts.append(("stmt", stripped))
            buf = ""
        else:
            buf += ch

    trailing = buf.strip()
    if trailing:
        raw_parts.append(("stmt", trailing))

    lines, indent = [], 0
    for tok in raw_parts:
        ttype = tok[0]
        if ttype == "open_brace":
            lines.append(" " * (indent * 4) + "{")
            indent += 1
        elif ttype == "close_brace":
            indent = max(0, indent - 1)
            lines.append(" " * (indent * 4) + "}")
        elif ttype == "stmt":
            content = tok[1]
            lb = tb = 0
            temp = content
            while temp.startswith("{"):
                lb += 1
                temp = temp[1:].lstrip()
            while temp.endswith("}"):
                tb += 1
                temp = temp[:-1].rstrip()
            for _ in range(lb):
                lines.append(" " * (indent * 4) + "{")
                indent += 1
            if temp:
                lines.append(" " * (indent * 4) + temp)
            for _ in range(tb):
                indent = max(0, indent - 1)
                lines.append(" " * (indent * 4) + "}")

    return lines
