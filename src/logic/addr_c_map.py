"""Address-to-C-code mapping from decompiler output.

Each p-code token is mapped to its source instruction address, enabling
interleaved assembly+decompiled output. Comment tokens (Ghidra warnings
like "Could not recover jumptable") are excluded so each instruction gets
only the actual C code tokens as a single joined comment line.
"""

from __future__ import annotations


def build_addr_c_code(result) -> dict[int, set[str]]:
    """Build address → C code token mapping from ClangOpToken.minAddress.

    Each p-code token is mapped to its source instruction address, enabling
    interleaved assembly+decompiled output.  Comment tokens (Ghidra warnings
    like "Could not recover jumptable") are excluded so each instruction gets
    only the actual C code tokens as a single joined comment line.

    Args:
        result: DecompilationResult from decompileFunction().

    Returns:
        Dict mapping instruction address → set of meaningful C code tokens.
    """
    from ghidra.app.decompiler import ClangCommentToken, ClangSyntaxToken

    addr_c_code: dict[int, set[str]] = {}
    tokens = list(result.getCCodeMarkup().tokenIterator(False))
    for t in tokens:
        # Skip comment tokens entirely — they are Ghidra warnings split into
        # individual words (e.g. "Could", "not", "recover") that produce the
        # broken multi-line // comments seen at jumptable addresses.
        if isinstance(t, ClangCommentToken):
            continue
        txt = str(t).strip()
        if not txt or txt in ("{", "}", ";", "", "/*", "*/"):
            continue
        min_a = getattr(t, "minAddress", None)
        if min_a and str(min_a) != "None":
            a = int(str(min_a), 16)
            if a not in addr_c_code:
                addr_c_code[a] = set()
            addr_c_code[a].add(txt)
    return addr_c_code
