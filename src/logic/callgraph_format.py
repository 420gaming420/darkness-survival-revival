"""Formatting for call graph references.

Provides ``format_full_refs()`` which combines caller and callee formatting
into a single human-readable string suitable for .ref.txt output files.
"""

from __future__ import annotations


def format_callers(call_refs_to, fpa_obj) -> str:
    """Format call sites (who calls this function) into readable text.

    Groups call sites by containing function to show which functions call
    this one and at what addresses.

    Args:
        call_refs_to: Raw reference objects from get_call_refs().
        fpa_obj: FlatProgramAPI for looking up containing functions.

    Returns:
        Formatted caller list string.
    """
    lines = []
    lines.append("REFERENCES TO (call sites):")

    prog = fpa_obj.currentProgram
    groups: dict[tuple[str, int], list[int]] = {}

    for r in call_refs_to:
        call_addr = r.getFromAddress()
        containing = prog.functionManager.getFunctionContaining(call_addr)
        if containing:
            fname = containing.name
            fentry = int(str(containing.entryPoint), 16)
            caddr = int(str(call_addr), 16)
            key = (fname, fentry)
            if key not in groups:
                groups[key] = []
            groups[key].append(caddr)

    for (fname, fentry) in sorted(groups.keys()):
        sites = groups[(fname, fentry)]
        lines.append("")
        lines.append(f"{fname} @ {hex(fentry)}")
        for caddr in sorted(sites):
            lines.append(f"  bl at [0x{caddr:x}]")

    return "\n".join(lines)


def format_callees(call_refs_from, fpa_obj) -> str:
    """Format call targets (what this function calls) into readable text.

    Args:
        call_refs_from: Raw reference objects from get_call_refs().
        fpa_obj: FlatProgramAPI for looking up callee functions.

    Returns:
        Formatted callee list string.
    """
    lines = []
    lines.append("")
    lines.append("REFERENCES FROM (calls made):")

    prog = fpa_obj.currentProgram
    callee_addrs = set()

    for r in call_refs_from:
        dst_addr = r.getToAddress()
        try:
            callee = prog.functionManager.getFunctionAt(dst_addr)
            cname = callee.name
            centry = int(str(callee.entryPoint), 16)
        except Exception:
            cname = f"FUN_{int(str(dst_addr), 16):x}"
            centry = int(str(dst_addr), 16)

        if centry not in callee_addrs:
            callee_addrs.add(centry)
            lines.append(f"  -> {cname} @ {hex(centry)}")

    return "\n".join(lines)


def format_full_refs(func_name, entry_addr, call_refs_to, call_refs_from, fpa_obj) -> str:
    """Format complete call references (both callers and callees).

    Convenience wrapper around ``format_callers`` + ``format_callees``.

    Args:
        func_name: Function name for header.
        entry_addr: Function entry address.
        call_refs_to: Raw reference objects from get_call_refs().
        call_refs_from: Raw reference objects from get_call_refs().
        fpa_obj: FlatProgramAPI for lookups.

    Returns:
        Complete formatted reference text.
    """
    callers_text = format_callers(call_refs_to, fpa_obj)
    callees_text = format_callees(call_refs_from, fpa_obj)

    header = f"/* References to/from {func_name} @ {hex(entry_addr)} */"
    return "\n".join([header, "", callers_text, callees_text])
