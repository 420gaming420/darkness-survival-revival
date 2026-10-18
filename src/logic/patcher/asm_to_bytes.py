"""Assembly string to bytes converter for the patcher tool.

Uses Ghidra's assembler API (WildSleighAssembler or Assemblers) to convert
assembly strings like "movs r1, #0xff" into raw byte arrays that can be
applied in-memory to the binary.

Two assembler approaches are tried in sequence:
1. WildSleighAssemblerBuilder + no-arg AssemblySelector — respects existing instruction length
2. Assemblers.getAssembler(Program) — simpler but may produce longer encodings

Both use assembleLine(address, assembly_string) which returns byte[].
"""

from __future__ import annotations


def asm_to_bytes(ghidra_addr: int, assembly_string: str) -> list[int]:
    """Convert an assembly string to raw bytes using Ghidra's assembler.

    Tries WildSleighAssembler first (respects instruction length), falls back
    to Assemblers.getAssembler(Program) which always works but may produce
    longer ARM encodings for Thumb instructions.

    Args:
        ghidra_addr: Ghidra address where the instruction will be written.
        assembly_string: Assembly instruction string, e.g. "movs r1, #0xff".

    Returns:
        List of byte values (0-255).

    Raises:
        RuntimeError: If neither assembler can parse the string.
    """
    from src.logic.server.state_lifecycle import get_fpa, get_program

    fpa = get_fpa()
    prog = get_program()

    # Try WildSleighAssembler first (better for Thumb instructions)
    result = _try_wild_sleigh(fpa, prog, ghidra_addr, assembly_string)
    if result is not None:
        return result

    # Fall back to Assemblers.getAssembler(Program)
    return _try_assemblers_get_assembler(fpa, prog, ghidra_addr, assembly_string)


def _try_wild_sleigh(fpa, prog, ghidra_addr: int, assembly_string: str) -> list[int] | None:
    """Try WildSleighAssemblerBuilder with no-arg AssemblySelector.

    Returns bytes or None if it fails.
    """
    import jpype
    from jpype import java

    try:
        # Create a default (no-op) AssemblySelector via reflection
        JavaAsmSel = java.lang.Class.forName('ghidra.app.plugin.assembler.AssemblySelector')
        selector = JavaAsmSel.getDeclaredConstructors()[0].newInstance()

        # Build WildSleighAssembler
        JavaWSABuilder = java.lang.Class.forName('ghidra.asm.wild.WildSleighAssemblerBuilder')
        ctor = JavaWSABuilder.getDeclaredConstructors()[0]
        builder = ctor.newInstance(prog.getLanguage())
        assembler = builder.getAssembler(selector, prog)

        # Use fillMask() to constrain the assembler to produce a 2-byte Thumb
        # instruction instead of defaulting to 4-byte ARM encoding.
        from ghidra.program.model.address import Address as JavaAddr
        ctx = assembler.getContextAt(fpa.toAddr(ghidra_addr))
        pb = ctx.fillMask()
        JavaAsm = assembler.getClass()
        # assembleLine(addr, string, AssemblyPatternBlock) — fillMask returns this type.
        method_with_mask = JavaAsm.getMethod('assembleLine', JavaAddr, java.lang.String,
                                             java.lang.Class.forName(
                                                 'ghidra.app.plugin.assembler.sleigh.sem.AssemblyPatternBlock'
                                             ))
        result = method_with_mask.invoke(assembler, fpa.toAddr(ghidra_addr), assembly_string, pb)

        # Convert Java byte[] to Python list[int] (unsigned)
        return [b if b >= 0 else b + 256 for b in result]
    except Exception:
        return None


def _try_assemblers_get_assembler(fpa, prog, ghidra_addr: int, assembly_string: str) -> list[int]:
    """Try Assemblers.getAssembler(Program).

    This always works for simple instructions but may produce 4-byte ARM
    encodings instead of 2-byte Thumb.

    Returns bytes as list[int] (unsigned).

    Raises:
        RuntimeError: If the assembler cannot parse the string.
    """
    import jpype
    from jpype import java
    from ghidra.program.model.address import Address as JavaAddr

    try:
        JavaAssemblers = java.lang.Class.forName('ghidra.app.plugin.assembler.Assemblers')
        method = JavaAssemblers.getMethod(
            'getAssembler',
            java.lang.Class.forName('ghidra.program.model.listing.Program'),
        )
        assembler = method.invoke(None, prog)

        # Use fillMask() to constrain the assembler to produce a 2-byte Thumb instruction.
        ctx = assembler.getContextAt(fpa.toAddr(ghidra_addr))
        pb = ctx.fillMask()
        JavaAsm = assembler.getClass()
        method_with_mask = JavaAsm.getMethod('assembleLine', JavaAddr, java.lang.String,
                                             java.lang.Class.forName(
                                                 'ghidra.app.plugin.assembler.sleigh.sem.AssemblyPatternBlock'
                                             ))
        result = method_with_mask.invoke(assembler, fpa.toAddr(ghidra_addr), assembly_string, pb)

        return [b if b >= 0 else b + 256 for b in result]
    except Exception as e:
        raise RuntimeError(
            f"Could not assemble '{assembly_string}' at {hex(ghidra_addr)}: {e}"
        ) from e
