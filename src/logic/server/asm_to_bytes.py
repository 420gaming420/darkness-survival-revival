"""RPC handler for assembly-to-bytes conversion.

Provides 'asm_to_bytes' method that converts an assembly string to raw bytes
using Ghidra's assembler API (WildSleighAssembler or Assemblers).
"""

from __future__ import annotations


def handle_asm_to_bytes(params: dict) -> dict:
    """Handle 'asm_to_bytes' RPC method.

    Converts an assembly string to raw bytes using Ghidra's assembler.
    Tries WildSleighAssembler first, falls back to Assemblers.getAssembler.

    Args:
        params: Request params with 'address' (int, Ghidra addr) and
                'assembly' (str, assembly instruction string).

    Returns:
        Dict with 'bytes' (list[int]) or 'error' (str) on failure.
    """
    from src.logic.patcher.asm_to_bytes import asm_to_bytes as _asm_to_bytes

    address = params["address"]
    assembly = params["assembly"]

    try:
        bytes_list = _asm_to_bytes(address, assembly)
        return {"bytes": bytes_list}
    except Exception as e:
        return {"error": str(e)}
