"""CFG block extraction from Ghidra's instruction flow types.

Derives basic blocks from instruction flow types within a function body.
Each non-FALL_THROUGH instruction marks a block end; its flows and
fallThrough give all outgoing edges.

Formatting lives in ``src.logic.cfg_format``.
"""

from __future__ import annotations


def get_cfg_blocks(fpa, func) -> tuple[list[dict], dict[int, list[tuple[int, str]]]]:
    """Extract CFG blocks and conditional branches for a given function.

    Derives basic blocks from instruction flow types within the function body.
    Each non-FALL_THROUGH instruction marks a block end; its flows and
    fallThrough give all outgoing edges.

    Args:
        fpa: FlatProgramAPI from an open session.
        func: The Ghidra Function object.

    Returns:
        (blocks_list, cond_branches_dict) where:
        - blocks_list: Each entry is {"addr": int, "targets": [(addr, flow_type), ...]}
        - cond_branches_dict: addr -> [(target_addr, flow_type), ...] for conditional branches
    """
    prog = fpa.currentProgram
    body = func.getBody()

    blocks_list: list[dict] = []
    cond_branches: dict[int, list[tuple[int, str]]] = {}

    instrs = list(prog.listing.getInstructions(body, True))
    current_block_addrs: list[int] = []

    for instr in instrs:
        iaddr = int(str(instr.address), 16)
        ft = instr.flowType
        current_block_addrs.append(iaddr)

        if ft != "FALL_THROUGH":
            targets: list[tuple[int, str]] = []
            for flow_addr in instr.flows:
                a = int(str(flow_addr), 16)
                targets.append((a, str(ft)))
            ft_addr = instr.fallThrough
            if ft_addr is not None and body.contains(ft_addr):
                ft_a = int(str(ft_addr), 16)
                if ft_a not in [t[0] for t in targets]:
                    targets.append((ft_a, "FALL_THROUGH"))

            blocks_list.append({"addr": current_block_addrs[0], "targets": targets})

            if any("JUMP" in str(ft) or ft == "CONDITIONAL_JUMP" for _, ft in targets):
                cond_branches[current_block_addrs[0]] = targets

            current_block_addrs = []

    return blocks_list, cond_branches
