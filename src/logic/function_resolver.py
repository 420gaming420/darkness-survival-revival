"""Function resolution from Ghidra symbol table and function manager.

Provides ``find_function()`` — a 5-tier search strategy that handles:
1. Hex address (0x...)
2. Exact function name match (demangled)
3. Exact symbol name match (mangled C++)
4. Case-insensitive substring against function names
5. Case-insensitive substring against all symbols

Plus ``find_similar()`` for Levenshtein-based typo tolerance.
"""

from __future__ import annotations


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein distance between two strings."""
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[lb]


def find_function(fpa, query: str):
    """Find a function by hex address, exact name, or substring match.

    Tries in order:
    1. Hex address (0x...)
    2. Exact function name match (demangled)
    3. Exact symbol name match (mangled C++)
    4. Case-insensitive substring against function names
    5. Case-insensitive substring against all symbols

    Args:
        fpa: FlatProgramAPI from an open session.
        query: Address, mangled name, or demangled name to search for.

    Returns:
        The Function object, or None if not found.

    Raises:
        ValueError: If not found and similar names can be suggested.
    """
    prog = fpa.currentProgram
    func = None

    # 1. Hex address
    if query.startswith("0x") or query.startswith("0X"):
        try:
            addr = fpa.toAddr(query)
            func = fpa.getFunctionAt(addr)
        except Exception:
            pass

    # 2. Exact function name (demangled)
    if func is None:
        for f in prog.functionManager.getFunctions(True):
            if f.name == query:
                func = f
                break

    # 3. Exact symbol match (mangled C++)
    if func is None:
        for sym in prog.symbolTable.getAllSymbols(True):
            if query == sym.name:
                addr = fpa.toAddr(str(sym.address))
                func = prog.functionManager.getFunctionAt(addr)
                break

    # 4-5. Substring / partial match
    if func is None:
        for f in prog.functionManager.getFunctions(True):
            if query.lower() in f.name.lower():
                func = f
                break

    if func is None:
        for sym in prog.symbolTable.getAllSymbols(True):
            saddr = str(sym.address)
            if saddr.startswith("EXTERNAL:"):
                continue
            if query.lower() in sym.name.lower():
                addr = fpa.toAddr(saddr)
                func = prog.functionManager.getFunctionAt(addr)
                break

    if func is None:
        similar = find_similar(fpa, query)
        if similar:
            raise ValueError(
                f"Could not find function for '{query}'. "
                f"Did you mean: {', '.join(sorted({n for _, n in similar})[:10])}"
            )
        else:
            raise ValueError(f"Could not find function for '{query}'")

    return func


def find_similar(fpa, name: str) -> list[tuple[int, str]]:
    """Find similar function names from function manager and symbol table.

    Args:
        fpa: FlatProgramAPI from an open session.
        name: The query string to find similar names for.

    Returns:
        List of (levenshtein_distance, name) tuples, sorted by distance.
    """
    prog = fpa.currentProgram
    candidates = []
    seen = set()

    for f in prog.functionManager.getFunctions(True):
        fname = f.name
        if fname in seen:
            continue
        dist = _levenshtein(name, fname)
        if 0 < dist < len(name) // 2 + 3:
            candidates.append((dist, fname))
            seen.add(fname)

    for sym in prog.symbolTable.getAllSymbols(True):
        saddr = str(sym.address)
        if saddr.startswith("EXTERNAL:"):
            continue
        fname = sym.name
        if fname in seen:
            continue
        dist = _levenshtein(name, fname)
        if 0 < dist < len(name) // 2 + 3:
            candidates.append((dist, fname))
            seen.add(fname)

    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[:10]
