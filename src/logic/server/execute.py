"""RPC handler for arbitrary Python execution in the JVM session.

Provides 'execute' method that runs arbitrary Python code inside the
Ghidra server process, giving direct access to FlatProgramAPI, ProgramDB,
and all Ghidra APIs without stop/start cycles.
"""

from __future__ import annotations


def handle_execute(params: dict) -> dict:
    """Handle 'execute' RPC method.

    Runs arbitrary Python code in the JVM session and returns the result
    as a JSON-serializable value (string, list, dict, int, float, bool).

    Injected into the code namespace:
        fpa  - FlatProgramAPI
        prog - ProgramDB

    Args:
        params: Request params with 'code' (str, Python code to execute).

    Returns:
        Dict with 'result' (str) containing the repr() of the result,
        or 'error' (str) if execution failed.
    """
    from src.logic.server.state_lifecycle import get_fpa, get_program

    try:
        code = params["code"]
        # Build namespace with shared state objects injected
        _fpa = get_fpa()
        _prog = get_program()
        _listing = _prog.listing if hasattr(_prog, "listing") else None
        _mem = _prog.getMemory() if _prog is not None else None
        ns = {
            "__builtins__": __builtins__,
            "fpa": _fpa,
            "prog": _prog,
            "mem": _mem,
            "listing": _listing,
        }
        # Try as expression first
        try:
            result = eval(code, ns)
            return {"result": repr(result)}
        except SyntaxError:
            pass
        # Multi-line — use exec
        exec(code, ns)
        for _k in ("output", "_result"):
            if _k in ns:
                return {"result": repr(ns[_k])}
        return {"result": "(exec completed, no output)"}
    except Exception as e:
        import traceback

        return {"error": f"{type(e).__name__}: {e}\n{traceback.format_exc()}"}
