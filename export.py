#!/usr/bin/env python3
"""Thin entry point for bulk function export.

Pure RPC wrapper — all work done by the background server.
Zero pyghidra/JVM code in this file.

Usage:
    python3 export.py _ZN7UILayer10networkingEv           # single func
    python3 export.py --all                                # all funcs
    python3 export.py --reachable                          # mainLoop-reachable only
    python3 export.py --stale                              # re-export stale funcs
    python3 export.py --depth 0                            # only depth level N
"""

import json
import os
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Known total — one function always fails to export.
TOTAL_FUNCTIONS = 23949


def _count_c_files(decompiled_dir: Path) -> int:
    """Count .c files in the versioned decompiled directory (recursive)."""
    if not decompiled_dir.exists():
        return 0
    return sum(1 for f in decompiled_dir.rglob("*.c") if f.is_file())


def _show_progress(decompiled_dir: Path, total: int):
    """Show progress by counting .c files on disk. Prints at each 10% mark."""
    count = _count_c_files(decompiled_dir)
    pct = (count / total * 100) if total > 0 else 0
    print(f"\r  {count}/{total} functions exported ({pct:.0f}%)", end="", flush=True)


def main():
    from src.logic.config import cfg
    cfg.binary_path  # validates binary exists before proceeding

    from src.ui.cli import parse_export_args

    args = parse_export_args()

    if args.debug:
        print(f"[DEBUG] Mode: query={args.query} all={args.all} reachable={args.reachable} stale={args.stale}")

    # All work goes through the server — zero pyghidra in this file.
    from src.ui.server.client import rpc as server_rpc
    from src.logic.paths import decompiled_dir as _get_decompiled

    if args.query and not args.all and not args.reachable and not args.stale:
        # Single func export
        result = server_rpc("export_single", {"query": args.query})
        name = result["name"]
        addr = result["address"]
        elapsed = result["elapsed"]
        depth = result["depth"]
        err = result.get("error")
        print(f"[*] {name} @ {addr}")
        print(f"[  OK] Exported in {elapsed:.2f}s (depth {depth})")
        if err:
            print(f"[  ERR] {err}")
        return

    if args.benchmark:
        # Benchmark mode: sample N functions and report per-step timing.
        from src.ui.server.client import _ensure_server
        _ensure_server()

        count = args.benchmark
        mode = "all"
        result = server_rpc("export_benchmark", {"count": count, "mode": mode})

        print(f"\n[*] Benchmark: {result['count']} functions (mode: {result['mode']})", flush=True)
        print("=" * 120, flush=True)

        step_names = ["find_function", "make_filename", "decompile", "format_c",
                       "assembly", "cfg", "refs", "write", "total"]
        header = f"{'FUNC':<45} {'TOTAL':>7} {'DECOMPILE':>9} {'FORMAT_C':>9} {'ASM':>7} {'CFG':>7} {'REFS':>7} {'MAKE_FN':>9} {'FIND_FN':>9} {'WRITE':>7}"
        print(header, flush=True)
        print("-" * 120, flush=True)

        all_timings: dict[str, list[float]] = {s: [] for s in step_names}
        for r in result["results"]:
            t = r.get("timings", {})
            name_short = r["name"][:44]
            total = t.get("total", 0)
            print(f"{name_short:<45} {total:>7.3f} {t.get('decompile', 0):>9.3f} {t.get('format_c', 0):>9.3f} "
                  f"{t.get('assembly', 0):>7.3f} {t.get('cfg', 0):>7.3f} {t.get('refs', 0):>7.3f} "
                  f"{t.get('make_filename', 0):>9.3f} {t.get('find_function', 0):>9.3f} {t.get('write', 0):>7.3f}",
                  flush=True)
            for s in step_names:
                all_timings[s].append(t.get(s, 0))

        def _stats(vals: list[float]) -> tuple[float, float, float, float, float]:
            """Return (avg, min, max, p90, p95)."""
            if not vals:
                return 0.0, 0.0, 0.0, 0.0, 0.0
            s = sorted(vals)
            n = len(s)
            avg = sum(s) / n
            mn, mx = s[0], s[-1]
            p90 = s[int(n * 0.9)] if n > 1 else mx
            p95 = s[int(n * 0.95)] if n > 1 else mx
            return avg, mn, mx, p90, p95

        print("\n" + "=" * 120, flush=True)
        print("SUMMARY", flush=True)
        print("-" * 120, flush=True)
        print(f"{'Step':<15} {'AVG':>8} {'MIN':>8} {'MAX':>8} {'P90':>8} {'P95':>8}", flush=True)
        print("-" * 120, flush=True)
        for s in step_names:
            avg, mn, mx, p90, p95 = _stats(all_timings[s])
            print(f"{s:<15} {avg:>8.3f} {mn:>8.3f} {mx:>8.3f} {p90:>8.3f} {p95:>8.3f}", flush=True)

        avg_total, _, _, _, p95_total = _stats(all_timings["total"])
        estimated_mins = avg_total * TOTAL_FUNCTIONS / 60
        p95_mins = p95_total * TOTAL_FUNCTIONS / 60
        print("\n" + "=" * 120, flush=True)
        print(f"PROJECTION ({TOTAL_FUNCTIONS} functions)", flush=True)
        print(f"  Estimated total:  {estimated_mins:.0f} min  ({avg_total:.3f}s avg × {TOTAL_FUNCTIONS})", flush=True)
        print(f"  Estimated at p95: {p95_mins:.0f} min  ({p95_total:.3f}s × {TOTAL_FUNCTIONS})", flush=True)
        print("=" * 120, flush=True)
        return

    mode = "all"
    if args.reachable:
        mode = "reachable"
    elif args.stale:
        mode = "stale"

    decompiled_base = _get_decompiled()

    def _find_latest_versioned_dir():
        """Find the latest versioned decompiled folder."""
        dirs = sorted(d for d in decompiled_base.iterdir() if d.is_dir() and len(d.name) == 8)
        return dirs[-1] if dirs else None

    print("[*] Running full binary export, this will take some time...", flush=True)
    print("    Watching progress by counting .c files on disk.", flush=True)

    # Ensure server is up exactly once (don't re-spawn in the retry loop).
    from src.ui.server.client import _ensure_server
    _ensure_server()

    t0 = time.time()
    last_pct = -1
    result = None
    last_io = 0.0
    IO_INTERVAL = 5.0  # seconds between recursive disk scans

    # Step 1: Fire off the export RPC (returns immediately with "accepted").
    try:
        server_rpc("export_all" if mode == "all" else f"export_{mode}", {"mode": mode})
    except Exception:
        pass  # Server may have been interrupted; we'll count files instead.

    # Step 2: Poll /progress for completion, counting .c files on disk periodically.
    import urllib.request as _urllib
    while True:
        elapsed = time.time() - t0
        versioned_dir = _find_latest_versioned_dir()

        # Count files on disk every IO_INTERVAL seconds to avoid excessive I/O.
        if versioned_dir and (time.time() - last_io) >= IO_INTERVAL:
            count = _count_c_files(versioned_dir)
            pct = (count / TOTAL_FUNCTIONS * 100) if TOTAL_FUNCTIONS > 0 else 0
            new_pct = int(pct)
            if new_pct != last_pct and new_pct in (0, 10, 20, 40, 60, 80, 100):
                print(f"\r  {count}/{TOTAL_FUNCTIONS} functions exported ({pct:.0f}%) — {elapsed:.0f}s elapsed", end="", flush=True)
                last_pct = new_pct
            last_io = time.time()

        # Check if export is done via /progress endpoint.
        try:
            resp = _urllib.urlopen(f"http://127.0.0.1:{os.environ.get('GHIDRA_SERVER_PORT', '18960')}/progress", timeout=3)
            prog = json.loads(resp.read().decode())
            # Only break when export has completed (has 'exported'/'total' keys).
            # During export, export_status only has {"status": "running"} — keep polling.
            es = prog.get("export_status")
            if es and "exported" in es and "total" in es:
                result = es
                break
        except Exception:
            pass

        time.sleep(2)

    # Print final state.
    versioned_dir = _find_latest_versioned_dir()
    count = _count_c_files(versioned_dir) if versioned_dir else 0
    pct = (count / TOTAL_FUNCTIONS * 100) if TOTAL_FUNCTIONS > 0 else 0
    elapsed = time.time() - t0
    print(f"\r  {count}/{TOTAL_FUNCTIONS} functions exported ({pct:.0f}%) — {elapsed:.0f}s elapsed")
    if result:
        e = result.get("exported", count)
        t = result.get("total", TOTAL_FUNCTIONS)
        er = result.get("errors", 0)
    else:
        e = count
        t = TOTAL_FUNCTIONS
        er = t - count


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrupted — sending interrupt to server...")
        from src.ui.server.client import shutdown
        shutdown()
        print("[*] Server interrupted. Exiting.")
