"""Formatting for CFG block data.

Provides ``format_cfg_output()`` which formats basic blocks and conditional
branch information into a human-readable string suitable for .cfg.txt output.
"""

from __future__ import annotations


def format_cfg_output(
    func_name: str,
    entry_addr: int,
    blocks: list[dict],
    cond_branches: dict[int, list[tuple[int, str]]]
) -> str:
    """Format CFG data into a human-readable string.

    Args:
        func_name: Function name for header.
        entry_addr: Function entry address.
        blocks: Output from get_cfg_blocks().
        cond_branches: Conditional branch info from get_cfg_blocks().

    Returns:
        Formatted CFG text ready for file output or stdout.
    """
    lines = []
    lines.append(f"/* CFG of {func_name} @ {hex(entry_addr)} */")
    lines.append(f"Total basic blocks: {len(blocks)}")
    lines.append("")

    for block in blocks:
        s_addr = block["addr"]
        targets = block["targets"]
        lines.append(f"[0x{s_addr:x}] ->")
        for d_addr, r_ft in targets:
            lines.append(f"  0x{d_addr:x} {r_ft}")

    if cond_branches:
        lines.append("")
        lines.append("CONDITIONAL BRANCHES:")
        for addr in sorted(cond_branches.keys()):
            lines.append(f"  [0x{addr:x}]:")
            for d_addr, r_ft in cond_branches[addr]:
                if r_ft == "FALL_THROUGH":
                    label = "FALSE (fall-through)"
                elif "JUMP" in r_ft:
                    label = "TRUE  (conditional)"
                else:
                    label = r_ft
                lines.append(f"    {label} -> [0x{d_addr:x}]")

    return "\n".join(lines)
