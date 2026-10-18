"""JSON-RPC request dispatcher.

Maps method names to handler functions from the server logic package.
Each handler is a pure function receiving params and returning a dict.
"""

from __future__ import annotations


DISPATCH = {
    "decompile": None,  # set by server module on import
    "export_single": None,
    "export_all": None,
    "export_reachable": None,
    "export_stale": None,
    "patcher_show": None,
    "patcher_preview": None,
    "patcher_apply": None,
    "patcher_undo": None,
    "patcher_export": None,
    "patcher_status": None,
    "status": None,
    "asm_to_bytes": None,
    "execute": None,  # eval arbitrary Python in JVM session
}


def register_handlers(
    handle_decompile,
    handle_export_single,
    handle_export_all,
    handle_patcher_show,
    handle_patcher_preview,
    handle_patcher_apply,
    handle_patcher_undo,
    handle_patcher_export,
    handle_patcher_status,
    handle_status,
    handle_asm_to_bytes,
    handle_execute=None,
) -> None:
    """Register handler functions in the DISPATCH map.

    Called by the HTTP server module after importing all handlers.

    Args:
        handle_decompile: Decompilation handler function.
        handle_export_single: Single-function export handler.
        handle_export_all: Bulk export handler.
        handle_patcher_show: Patcher show handler.
        handle_patcher_preview: Patcher preview handler.
        handle_patcher_apply: Patcher apply handler.
        handle_status: Status query handler.
        handle_asm_to_bytes: Assembly string to bytes converter.
        handle_execute: Arbitrary Python eval in JVM session.
    """
    DISPATCH["decompile"] = handle_decompile
    DISPATCH["export_single"] = handle_export_single
    DISPATCH["export_all"] = handle_export_all
    DISPATCH["export_reachable"] = handle_export_all
    DISPATCH["export_stale"] = handle_export_all
    DISPATCH["patcher_show"] = handle_patcher_show
    DISPATCH["patcher_preview"] = handle_patcher_preview
    DISPATCH["patcher_apply"] = handle_patcher_apply
    DISPATCH["patcher_undo"] = handle_patcher_undo
    DISPATCH["patcher_export"] = handle_patcher_export
    DISPATCH["patcher_status"] = handle_patcher_status
    DISPATCH["status"] = handle_status
    DISPATCH["asm_to_bytes"] = handle_asm_to_bytes
    if handle_execute is not None:
        DISPATCH["execute"] = handle_execute


def execute(method: str, params: dict) -> object:
    """Execute an RPC method by name.

    Args:
        method: Method name (e.g. 'decompile', 'export_all').
        params: Request parameters dict.

    Returns:
        Handler return value.

    Raises:
        ValueError: If method is not registered.
    """
    handler = DISPATCH.get(method)
    if handler is None:
        raise ValueError(f"Unknown method: {method}")
    return handler(params)
