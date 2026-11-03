"""Filename prefix generation for exported function files.

Creates filenames from address and function name:
``{hex_address}_{func_name}.{ext}``

Prefers the full mangled C++ Label symbol name over the demangled
Function name so that exported files are globally unique and searchable.
For extremely long mangled names (e.g. templated functors), truncates
to fit within filesystem path length limits while preserving uniqueness
via a short hex suffix.

The symbol table lookup is cached per-call via a thread-local cache
populated by ``build_symbol_cache()`` — called once before the export
loop. Without the cache, this function iterates ~329K symbols per call.
"""

from __future__ import annotations

import hashlib
import threading


def build_symbol_cache(fpa, prog) -> dict[int, str]:
    """Build a one-time address→mangled-name lookup table.

    Iterates the symbol table once and returns a dict mapping
    integer addresses to the mangled Label name (preferred) or the
    demangled Function name as fallback.

    Call this ONCE before the export loop, then pass the result to
    ``make_filename`` via the ``symbol_cache`` parameter.

    Args:
        fpa: FlatProgramAPI from the open Ghidra session.
        prog: ProgramDB from the open Ghidra session.

    Returns:
        Dict mapping int address → str filename name.
    """
    from ghidra.program.model.symbol import SymbolType
    sym_label = SymbolType.LABEL

    cache: dict[int, str] = {}
    try:
        for s in prog.symbolTable.getAllSymbols(True):
            try:
                addr_int = int(str(s.address), 16)
            except Exception:
                continue
            if s.symbolType == sym_label:
                # Labels (mangled names) always win over Function symbols.
                cache[addr_int] = s.name
            elif addr_int not in cache:
                cache[addr_int] = s.name
    except Exception:
        pass
    return cache


def make_filename(
    entry_addr: int,
    func_name: str,
    fpa=None,
    prog=None,
    symbol_cache: dict[int, str] | None = None,
) -> str:
    """Create filename prefix from address and function name.

    Format: {hex_address_without_0x}_{func_name}

    If a pre-built ``symbol_cache`` is provided, uses O(1) dict lookup
    instead of scanning all symbols. Build the cache once with
    ``build_symbol_cache()`` before the export loop.

    Args:
        entry_addr: Function entry address.
        func_name: Function name (demangled, as returned by Ghidra).
        fpa: FlatProgramAPI (optional — used for address conversion).
        prog: ProgramDB (optional — used to look up mangled Label symbol).
        symbol_cache: Pre-built address→name cache from build_symbol_cache().

    Returns:
        Filename prefix string (no extension).
    """
    try:
        name = symbol_cache.get(entry_addr)
        if name:
            prefix = f"{hex(entry_addr)[2:].lower()}-{name}"
            # Truncate extremely long names to fit filesystem limits.
            # Max filename length is 255 bytes; account for category dir
            # (up to ~100 chars) + extension (e.g. .c, .asm.txt, .cfg.txt,
            # .ref.txt = max 10 chars). Use 120 chars for the name portion.
            if len(prefix) > 120:
                short = hashlib.sha256(name.encode()).hexdigest()[:8]
                prefix = f"{hex(entry_addr)[2:].lower()}-{name[:80]}-{short}"
            return prefix
    except Exception:
        pass
    prefix = f"{hex(entry_addr)[2:].lower()}-{func_name}"
    if len(prefix) > 120:
        short = hashlib.sha256(func_name.encode()).hexdigest()[:8]
        prefix = f"{hex(entry_addr)[2:].lower()}-{func_name[:80]}-{short}"
    return prefix
