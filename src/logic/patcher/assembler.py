"""Sleigh assembly/disassembly wrapper using Ghidra's language.parse API.

Provides functions to parse raw bytes into Sleigh instruction prototypes
and extract mnemonic strings for display. Each Thumb instruction is 2 bytes.

Uses the cached Ghidra project's language/processor for accurate disassembly.
"""

from __future__ import annotations

from pathlib import Path

from src.logic.ghidra import GhidraSession
from src.logic.paths import ghidra_project_dir


def _get_context_and_lang(session, target_addr: int):
    """Get a reference instruction context and language from the session.

    Args:
        session: Open GhidraSession.
        target_addr: File offset of target address (used to find any function nearby).

    Returns:
        Tuple of (SleighLanguage, InstructionContext).
    """
    fpa = session.fpa
    prog = session.program
    lang = prog.language

    # Find any instruction in the function containing target_addr to get a context
    func = fpa.getFunctionAt(fpa.toAddr(target_addr))
    if func is None:
        # Fall back to entry point area
        for f in prog.functionManager.getFunctions(True):
            body = f.body
            if body.contains(fpa.toAddr(target_addr)):
                func = f
                break

    if func is None:
        # Last resort: use the first function's instruction as context reference
        for f in prog.functionManager.getFunctions(True):
            instrs = list(f.body)
            if instrs:
                func = f
                break

    ctx = list(prog.listing.getInstructions(func.body, True))[0].getInstructionContext()
    return lang, ctx


def parse_instruction(lang, ctx, addr, raw_bytes: bytes):
    """Parse raw bytes into a SleighInstructionPrototype.

    Args:
        lang: SleighLanguage from the session.
        ctx: InstructionContext reference from an existing instruction.
        addr: Address where these bytes will be written (for address-dependent parsing).
        raw_bytes: Raw bytes to parse (2 bytes for Thumb, 4 for ARM).

    Returns:
        SleighInstructionPrototype object, or None if parsing fails.
    """
    from ghidra.program.model.mem import ByteMemBufferImpl

    buf = ByteMemBufferImpl(addr, raw_bytes, True)
    return lang.parse(buf, ctx, True)


def get_mnemonic(proto) -> str:
    """Extract mnemonic string from a SleighInstructionPrototype.

    Args:
        proto: SleighInstructionPrototype from parse_instruction().

    Returns:
        Mnemonic string (e.g., 'movs', 'bx', 'ldr').
    """
    if proto is None:
        return "??"
    
    # SleighInstructionPrototype stores mnemonic in the ConstructState
    cs = proto.rootState
    if cs is not None:
        try:
            mnem = cs.mnemonic
            if mnem and str(mnem).strip():
                return str(mnem).strip()
        except Exception:
            pass
    
    # Fallback: check for mnemonic attribute directly
    for attr in dir(proto):
        if 'mnemonic' in attr.lower():
            try:
                val = getattr(proto, attr)
                if val and str(val).strip():
                    return str(val).strip()
            except Exception:
                pass
    
    return "??"


def get_instruction_length(proto) -> int:
    """Get the instruction length in bytes from a prototype.

    Args:
        proto: SleighInstructionPrototype from parse_instruction().

    Returns:
        Instruction length in bytes (2 for Thumb, 4 for ARM).
    """
    if proto is None:
        return 2
    return getattr(proto, 'length', 2)


def disassemble_range(lang, ctx, addr, raw_bytes: bytes) -> list[dict]:
    """Disassemble a range of bytes into individual instructions.

    Iterates through the byte range, parsing each instruction sequentially
    based on its length from the prototype.

    Args:
        lang: SleighLanguage from the session.
        ctx: InstructionContext reference.
        addr: Starting address.
        raw_bytes: All bytes in the range.

    Returns:
        List of dicts with keys: addr, mnemonic, hex_bytes (space-separated), length
    """
    from ghidra.program.flatapi import FlatProgramAPI
    
    fpa = FlatProgramAPI(lang.program) if hasattr(lang, 'program') else None
    
    results = []
    offset = 0
    while offset < len(raw_bytes):
        chunk = raw_bytes[offset:]
        proto = parse_instruction(lang, ctx, addr + offset, chunk)
        instr_len = get_instruction_length(proto) or 2
        if instr_len < 1:
            instr_len = 2
        
        mnem = get_mnemonic(proto)
        hex_str = " ".join(f"{b:02x}" for b in raw_bytes[offset:offset + instr_len])
        
        results.append({
            "addr": addr + offset,
            "mnemonic": mnem,
            "hex_bytes": hex_str,
            "length": instr_len,
        })
        offset += instr_len
    
    return results
