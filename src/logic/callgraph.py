"""Caller/callee reference extraction from Ghidra's reference manager.

Provides ``get_call_refs()`` which returns raw reference objects for:
- References TO the function (call sites where it is called)
- References FROM the function (what this function calls)

Formatting functions live in ``src.logic.callgraph_format``.
"""

from __future__ import annotations


def get_call_refs(fpa, func) -> tuple[list, list]:
    """Get call references to/from a function.

    Args:
        fpa: FlatProgramAPI from an open session.
        func: The Ghidra Function object.

    Returns:
        (call_refs_to, call_refs_from) where each is a list of raw
        Reference objects filtered to only CALL-type references.
    """
    prog = fpa.currentProgram

    # References TO this function (call sites)
    refs_to = list(prog.referenceManager.getReferencesTo(func.entryPoint))
    call_refs_to = [r for r in refs_to if r.referenceType.isCall()]

    # References FROM this function (calls made)
    refs_from = list(prog.referenceManager.getReferencesFrom(func.entryPoint))
    call_refs_from = [r for r in refs_from if r.referenceType.isCall()]

    return call_refs_to, call_refs_from
