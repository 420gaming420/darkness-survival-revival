"""Ghidra-aware binary patching with Sleigh re-assembly.

Applies patches to disk, opens a Ghidra session, clears code units at each
patch range, writes bytes to memory, parses each 2-byte Thumb word as an
instruction via Sleigh, and creates instructions in the listing.
"""

from __future__ import annotations

from pathlib import Path

from src.logic.patcher.core import Patch, _to_jbyte


def apply_patches_with_ghidra(
    patches: list[Patch],
    session,
    binary: Path | None = None,
) -> list[tuple[int, str]]:
    """Apply patches to the binary on disk, re-import, and re-assemble in Ghidra.

    This is the full pipeline: write bytes to disk, open Ghidra session,
    clear code units at each patch range, write bytes to memory, parse each
    2-byte Thumb word as an instruction, and create instructions in the listing.

    Args:
        patches: List of Patch objects to apply.
        session: Open GhidraSession (will be used for re-assembly).
        binary: Path to the binary file on disk.

    Returns:
        List of (entry_addr_int, func_name) tuples for all affected functions.
    """
    from src.logic.patcher_apply import find_affected_functions
    from src.logic.paths import ghidra_to_file_offset

    bin_path = binary or __import__("src.logic.paths", fromlist=["binary_path"]).binary_path()
    fpa = session.fpa
    prog = session.program
    lang = prog.language
    listing = prog.listing
    mem = prog.getMemory()

    # Step 1: Apply patches to disk (convert Ghidra addresses to file offsets)
    data = bytearray(bin_path.read_bytes())
    for patch in patches:
        file_offset = ghidra_to_file_offset(patch.offset)
        new_bytes = list(patch.bytes)
        for i, b in enumerate(new_bytes):
            data[file_offset + i] = b & 0xff
    bin_path.write_bytes(bytes(data))

    # Step 2: Get a reference context from any existing instruction, or parse one.
    all_funcs = list(prog.functionManager.getFunctions(True))
    ctx = None

    # First try to find an existing instruction with a context
    for f in all_funcs:
        instrs = list(prog.listing.getInstructions(f.body, True))
        if instrs:
            ctx = instrs[0].getInstructionContext()
            break

    # If no instructions exist (headless -noanalysis), create a ProgramProcessorContext
    # that works for both lang.parse() and listing.createInstruction().
    if ctx is None:
        from ghidra.program.model.lang import ProgramProcessorContext as _PPC
        ctx = _PPC(prog.programContext, fpa.toAddr(0))

    if ctx is None:
        raise RuntimeError("Could not find any instruction to get context from")

    # Step 2b-3: For each patch, ensure function body covers the range, then apply bytes.
    for patch in patches:
        patch_addr = fpa.toAddr(patch.offset)
        func = None
        for f in all_funcs:
            if f.body.contains(patch_addr):
                func = f
                break

        if func is None:
            nearest_func = None
            for f in all_funcs:
                f_end = int(str(f.body.maxAddress), 16)
                if f_end <= patch.offset:
                    nearest_func = f
                else:
                    break

        tid = prog.startTransaction(f"patch {patch.name or hex(patch.offset)}")
        try:
            if func is None and nearest_func is not None:
                from ghidra.program.model.address import AddressSet
                addr_set = AddressSet(nearest_func.body)
                addr_set.addRange(
                    fpa.toAddr(patch.offset),
                    fpa.toAddr(patch.offset + len(patch.bytes) - 1),
                )
                nearest_func.setBody(addr_set)

            offset = patch.offset
            length = len(patch.bytes)
            start_addr = fpa.toAddr(offset)
            end_addr = fpa.toAddr(offset + length)

            # Clear existing code units in range
            listing.clearCodeUnits(start_addr, end_addr, False)

            # Write each byte to memory (signed Java bytes)
            for i in range(length):
                mem.setByte(fpa.toAddr(offset + i), _to_jbyte(patch.bytes[i]))

            # Re-parse the entire patched range so Sleigh can correctly handle
            # 4-byte Thumb2 instructions. Iterate all resulting instructions and
            # create them in the listing.
            from ghidra.program.model.mem import ByteMemBufferImpl

            all_bytes = bytes(patch.bytes)
            padded = bytearray()
            for i in range(0, len(all_bytes), 2):
                chunk = all_bytes[i:i+2]
                padded.extend(chunk)
                if len(chunk) < 2:
                    padded.append(0x00)
                padded.extend(b'\x00\x00')

            pos = 0
            while pos < len(all_bytes):
                instr_addr = fpa.toAddr(offset + pos)
                chunk_start = pos
                chunk_end = min(pos + 4, len(padded))
                parse_chunk = bytes(padded[chunk_start:chunk_end])
                buf = ByteMemBufferImpl(instr_addr, parse_chunk, True)
                proto = lang.parse(buf, ctx, True)

                if proto is not None:
                    instr_len = getattr(proto, 'length', 2) or 2
                    avail = min(instr_len, len(all_bytes) - pos)
                    if avail < 1:
                        avail = 2

                    if instr_len > avail:
                        padded_actual = bytearray(all_bytes[pos:])
                        while len(padded_actual) < instr_len:
                            padded_actual.append(0x00)
                        actual_buf = ByteMemBufferImpl(instr_addr, bytes(padded_actual), True)
                        create_len = instr_len
                    else:
                        actual = all_bytes[pos:pos + avail]
                        actual_buf = ByteMemBufferImpl(instr_addr, actual, True)
                        create_len = avail

                    listing.createInstruction(instr_addr, proto, actual_buf, ctx, create_len)
                    pos += create_len
                else:
                    nop_bytes = b'\xc0\x46'
                    nop_buf = ByteMemBufferImpl(
                        instr_addr, nop_bytes[:len(all_bytes) - pos], True
                    )
                    listing.createInstruction(
                        instr_addr, None, nop_buf, ctx, min(2, len(all_bytes) - pos)
                    )
                    pos += 2

            prog.endTransaction(tid, True)
        except Exception:
            prog.endTransaction(tid, False)
            raise

    # Step 4: Find all affected functions
    return find_affected_functions(fpa, patches)
