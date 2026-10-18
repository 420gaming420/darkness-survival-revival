"""Assembly instruction extraction with C code token mapping.

Provides functions to enumerate all instructions in a function body and
map them to corresponding decompiled C code tokens for interleaved output.
"""

from __future__ import annotations


def get_instructions(fpa, func) -> list[dict]:
    """Get all instructions in a function body with metadata.

    Each instruction includes raw bytes, mnemonic, operands, and address.

    Args:
        fpa: FlatProgramAPI from an open session.
        func: The Ghidra Function object.

    Returns:
        List of dicts with keys: addr, mnemonic, hex_bytes, ops_str
    """
    prog = fpa.currentProgram
    all_instrs = list(prog.listing.getInstructions(func.body, True))

    result = []
    for instr in all_instrs:
        iaddr = int(str(instr.address), 16)
        ctx = instr.instructionContext
        # Use the full disassembly string from instructionContext (e.g. "mov r3,#0xb4")
        # Split it into mnemonic + operands for proper formatting
        full_str = str(ctx).strip()
        parts = full_str.split(None, 1)
        mnemonic = parts[0] if parts else "?"
        ops_str = (" " + parts[1]) if len(parts) > 1 else ""
        hex_bytes = " ".join("{:02x}".format(b & 0xff) for b in instr.bytes)

        result.append({
            "addr": iaddr,
            "mnemonic": mnemonic,
            "hex_bytes": hex_bytes,
            "ops_str": ops_str,
        })

    return result


def format_asm_with_c(
    instructions: list[dict],
    addr_c_code: dict[int, set[str]]
) -> str:
    """Format interleaved assembly + decompiled C code.

    Each instruction is shown with its bytes/mnemonic, followed by any
    matching C code tokens joined into a single // comment line.

    Args:
        instructions: Output from get_instructions().
        addr_c_code: Address → C token mapping from build_addr_c_code().

    Returns:
        Formatted interleaved assembly+C text.
    """
    lines = []
    for instr in instructions:
        iaddr = instr["addr"]
        mnemonic = instr["mnemonic"]
        hex_bytes = instr["hex_bytes"]
        ops_str = instr["ops_str"]

        c_tokens = addr_c_code.get(iaddr, set())
        meaningful = [ct for ct in c_tokens if len(ct) > 3]

        lines.append(f'[{hex(iaddr)}] {hex_bytes.ljust(16)}| {mnemonic}{ops_str}')
        if meaningful:
            joined = " ".join(sorted(meaningful))
            lines.append(f"  // {joined}")

    return "\n".join(lines)
