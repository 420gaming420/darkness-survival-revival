"""Export all 4 output files for a single decompiled function.

Each function gets .c, .asm.txt, .cfg.txt, and .ref.txt files in a depth-
based subdirectory under decompiled/. Uses a shared DecompInterface instance
for efficiency across multiple calls.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from src.logic.cfg_format import format_cfg_output
from src.logic.callgraph_format import format_full_refs
from src.logic.decompiler import annotate_lines, build_addr_c_code
from src.logic.disassembly import format_asm_with_c, get_instructions
from src.logic.export_filename import make_filename


def export_single_function(
    fpa,
    prog,
    di,
    textdata,
    entry_addr: int,
    func_name: str,
    depth: int,
    decompiled_dir: Path,
    benchmark: bool = False,
) -> tuple[bool, float, str, dict]:
    """Export all 4 output files for a single function.

    Args:
        fpa: FlatProgramAPI from open session.
        prog: ProgramDB from open session.
        di: DecompInterface (already configured, shared across calls).
        textdata: Loaded textdata dictionary.
        entry_addr: Function entry address.
        func_name: Function name.
        depth: BFS depth level for output directory.
        decompiled_dir: Root output directory.
        benchmark: If True, return per-step timing breakdown.

    Returns:
        (success, elapsed_seconds, error_message, timing_dict)
        timing_dict keys: decompile, format_c, assembly, cfg, refs, total
    """
    t0 = time.time()
    addr_prefix = make_filename(entry_addr, func_name)
    out_dir = decompiled_dir / str(depth)
    os.makedirs(out_dir, exist_ok=True)

    timings: dict[str, float] = {}

    try:
        func = fpa.getFunctionAt(fpa.toAddr(hex(entry_addr)))
    except Exception as e:
        elapsed = time.time() - t0
        return False, elapsed, str(e), {}

    if func is None:
        elapsed = time.time() - t0
        return False, elapsed, "no function found", {}

    try:
        # ── Decompile ──
        t_decompile = time.time()
        result = di.decompileFunction(func, 60, None)
        if not result or not result.isValid():
            err = result.getErrorMessage() if result else "no result"
            di.flushCache()
            elapsed = time.time() - t0
            return False, elapsed, f"decompilation failed: {err}", {}

        ccode = result.getDecompiledFunction().c  # already multi-line formatted with proper indentation
        di.flushCache()
        timings["decompile"] = time.time() - t_decompile

        # ── Format & annotate C code ──
        t_format = time.time()
        lines = ccode.split('\n')
        annotated, found_count = annotate_lines(lines, textdata)
        annotated_code = "\n".join(annotated)

        # ── Build addr→C code mapping (for assembly interleaving) ──
        addr_c_code = build_addr_c_code(result)
        timings["format_c"] = time.time() - t_format

        # ── Assembly ──
        t_asm = time.time()
        all_instrs = get_instructions(fpa, func)
        timings["assembly"] = time.time() - t_asm

        # ── CFG ──
        t_cfg = time.time()
        from src.logic.cfg import get_cfg_blocks

        fn_blocks, cond_branches = get_cfg_blocks(fpa, func)
        timings["cfg"] = time.time() - t_cfg

        # ── Call references ──
        t_ref = time.time()
        from src.logic.callgraph import get_call_refs

        call_refs_to, call_refs_from = get_call_refs(fpa, func)
        timings["refs"] = time.time() - t_ref

        c_file = out_dir / f"{addr_prefix}.c"
        asm_file = out_dir / f"{addr_prefix}.asm.txt"
        cfg_file = out_dir / f"{addr_prefix}.cfg.txt"
        ref_file = out_dir / f"{addr_prefix}.ref.txt"

        # ── Write .c file ──
        with open(c_file, "w") as f:
            f.write(f"/* {func_name} */\n")
            f.write(f"/* Entry: {hex(entry_addr)} */\n\n")
            f.write(annotated_code)
            if found_count > 0:
                f.write(f"\n// Annotated {found_count} getText() call(s)\n")

        # ── Write .asm.txt file ──
        asm_text = format_asm_with_c(all_instrs, addr_c_code)
        with open(asm_file, "w") as f:
            f.write(asm_text)

        # ── Write .cfg.txt file ──
        cfg_text = format_cfg_output(func_name, entry_addr, fn_blocks, cond_branches)
        with open(cfg_file, "w") as f:
            f.write(cfg_text)

        # ── Write .ref.txt file ──
        ref_text = format_full_refs(func_name, entry_addr, call_refs_to, call_refs_from, fpa)
        with open(ref_file, "w") as f:
            f.write(ref_text)

        timings["total"] = time.time() - t0
        return True, timings["total"], "", timings if benchmark else {}

    except Exception as e:
        elapsed = time.time() - t0
        return False, elapsed, str(e), {}
