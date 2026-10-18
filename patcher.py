#!/usr/bin/env python3
"""Thin entry point for the patcher tool.

Pure RPC wrapper — all work done by the background server.
Zero pyghidra/JVM code in this file.

Usage:
    python3 patcher.py -r 0x3d5d00 02 20 70 47              # apply patch (in-memory)
    python3 patcher.py -r 0x3d5d00 02 20 70 47 --preview    # dry run
    python3 patcher.py --show _ZN7UILayer10networkingEv      # show current state
    python3 patcher.py -r 0x3d5d00 02 20 70 47 --show getGameNetState  # apply + show
    python3 patcher.py --export                              # write to disk + re-export decompiled/
    python3 patcher.py --undo 1                              # undo last patch
    python3 patcher.py --status                              # show patch state/history
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))


def main():
    from src.logic.config import cfg
    cfg.binary_path  # validates binary exists before proceeding

    from src.ui.cli import print_header
    from src.ui.patcher import parse_patcher_args

    args = parse_patcher_args()

    if args.debug:
        print(f"[DEBUG] Patches: {len(args.patches)}")
        for p in args.patches:
            print(f"[DEBUG]   {p['name']}: offset={hex(p['offset'])} bytes={p['bytes']}")
        print(f"[DEBUG] Preview: {args.preview}")
        print(f"[DEBUG] Show: {args.show_query}")

    # ── --status mode ────────────────────────────────────────────────────────
    if args.status and not args.patches and not args.preview and not args.undo:
        from src.ui.server.client import rpc as server_rpc
        result = server_rpc("patcher_status", {})
        print(f"[*] Current SHA256: {result.get('current_sha256', 'N/A')[:16]}...")
        print(f"[*] Before SHA256:  {result.get('before_sha256', 'N/A')[:16]}..." if result.get('before_sha256') else "[*] Before SHA256:  (none — unpatched)")
        print(f"[*] Patch history:  {result.get('history_count', 0)} patch(es) applied")
        return

    # ── --undo mode ──────────────────────────────────────────────────────────
    if args.undo and not args.patches and not args.preview:
        from src.ui.server.client import rpc as server_rpc
        count = args.undo if isinstance(args.undo, int) else 1
        print_header("UNDO LAST PATCH")
        result = server_rpc("patcher_undo", {"count": count})
        undone = result.get("undone", 0)
        print(f"[*] Undid {undone} patch(es)")
        for detail in result.get("undo_details", []):
            print(f"    Offset: {detail['offset']}")
            print(f"    Restored: {' '.join(f'{b:02x}' for b in detail['restored_to'])}")
            if detail.get('name'):
                print(f"    Name: {detail['name']}")
        affected = result.get("affected", [])
        if affected:
            print(f"\n  Affected {len(affected)} function(s):")
            for entry in affected:
                print(f"    - {entry['name']} @ {entry['address']}")
        return

    # ── --show mode (no patches) ────────────────────────────────────────────
    if args.show_query and not args.patches:
        from src.ui.server.client import rpc as server_rpc
        result = server_rpc("patcher_show", {"query": args.show_query})
        if result.get("error"):
            print(f"[ERROR] {result['error']}")
            sys.exit(1)
        print(f"[*] Found: {result['name']} @ {result['address']}")
        print(result["asm"])

        # Show before/after comparison if available.
        if "before_codelines" in result and "after_codelines" in result:
            from src.logic.server.patcher_compare import format_diff
            diff = format_diff(result["before_codelines"], result["after_codelines"])
            print_header("BEFORE/AFTER COMPARISON")
            print(diff)
        return

    # ── --preview mode (no server needed — just reads binary on disk) ────────
    if args.preview:
        from src.logic.patcher.core import Patch, preview_patches
        from src.logic.paths import binary_path as _bp, ghidra_to_file_offset as _g2fo
        patch_objs = [Patch(**p) for p in args.patches]
        print_header("PATCH PREVIEW (dry run)")
        text = preview_patches(patch_objs, _bp())
        # Patch dataclass uses Ghidra addresses; convert to file offsets for display.
        import re as _re
        output_lines = []
        for line in text.split("\n"):
            if line.startswith("OFFSET 0x") and "length" in line:
                m = _re.search(r'OFFSET (0x[0-9a-f]+)', line)
                if m:
                    ghidra_addr = int(m.group(1), 16)
                    file_off = _g2fo(ghidra_addr)
                    line = f"OFFSET {m.group(1)} (file offset 0x{file_off:x})"
            elif _re.match(r'\s*\[(0x[0-9a-f]+)\]', line):
                m = _re.search(r'(0x[0-9a-f]+)', line)
                if m:
                    ghidra_addr = int(m.group(1), 16)
                    file_off = _g2fo(ghidra_addr)
                    line = line.replace(m.group(1), _re.sub(r'0x[0-9a-f]+', f"{m.group(1)} (file 0x{file_off:x})", line, count=1))
            output_lines.append(line)
        print("\n".join(output_lines))
        return

    # ── --export mode ────────────────────────────────────────────────────────
    if args.export and not args.patches:
        from src.ui.server.client import rpc as server_rpc
        import time as _time
        print_header("EXPORT PATCHED BINARY TO DISK")
        t0 = _time.time()
        result = server_rpc("patcher_export", {})
        elapsed = _time.time() - t0
        print(f"  Written to: {result.get('written_to', 'N/A')}")
        print(f"  SHA256:     {result.get('sha256', 'N/A')[:16]}...")
        print(f"  Exported:   {result.get('exported', 0)}/{result.get('total', 0)} functions to versioned decompiled/ subfolder")
        print(f"  Elapsed:    {elapsed:.1f}s")
        return

    # ── Apply patches ────────────────────────────────────────────────────────
    from src.logic.patcher.core import Patch
    patch_objs = [Patch(**p) for p in args.patches]

    print_header("APPLYING PATCHES (in-memory)")
    from src.logic.paths import ghidra_to_file_offset

    from src.logic.paths import binary_path as _bp
    for p in patch_objs:
        new_hex = " ".join(f"{b:02x}" for b in p.bytes)
        file_off = ghidra_to_file_offset(p.offset)
        orig_data = bytearray(_bp().read_bytes())
        orig_hex = " ".join(f"{b:02x}" for b in orig_data[file_off : file_off + len(p.bytes)])
        print(f"  [{hex(p.offset)}] {orig_hex} -> {new_hex}")

    # Handle --patch-asm patches (convert assembly strings to bytes via server)
    if args.asm_patches:
        from src.ui.server.client import rpc as server_rpc
        for ap in args.asm_patches:
            print(f"\n  Assembling '{ap['asm_string']}' at {hex(ap['offset'])}...")
            asm_result = server_rpc("asm_to_bytes", {
                "address": ap["offset"],
                "assembly": ap["asm_string"],
            })
            if "error" in asm_result:
                print(f"[ERROR] Assembly failed: {asm_result['error']}", file=sys.stderr)
                sys.exit(1)
            byte_list = asm_result["bytes"]
            new_hex = " ".join(f"{b:02x}" for b in byte_list)
            file_off = ghidra_to_file_offset(ap["offset"])
            orig_data = bytearray(_bp().read_bytes())
            orig_hex = " ".join(f"{b:02x}" for b in orig_data[file_off : file_off + len(byte_list)])
            print(f"    {orig_hex} -> {new_hex}")
            patch_objs.append(Patch(offset=ap["offset"], bytes=byte_list, name=ap["name"]))

    # Apply via server (in-memory, no disk write)
    import time as _time
    from src.ui.server.client import rpc as server_rpc

    t0 = _time.time()
    result = server_rpc("patcher_apply", {"patches": [
        {"offset": p.offset, "bytes": p.bytes, "name": p.name} for p in patch_objs
    ]})
    elapsed = _time.time() - t0
    affected = result.get("affected", [])
    patch_id = result.get("patch_id", "?")
    new_sha = result.get("new_sha256", "")
    before_sha = result.get("before_sha256", "")

    if not affected:
        print("  No functions found in the patched ranges.")
        print("  (Patches may be between function boundaries.)")
    else:
        print(f"  Found {len(affected)} affected function(s):")
        for entry in affected:
            print(f"    - {entry['name']} @ {entry['address']}")

    print(f"\n  Patch #{patch_id} applied (SHA256 changed) ({elapsed:.1f}s)")
    if before_sha and new_sha:
        print(f"    Before: {before_sha[:16]}...")
        print(f"    After:  {new_sha[:16]}...")

    # If --show was specified, show after patching + comparison.
    if args.show_query:
        result = server_rpc("patcher_show", {"query": args.show_query})
        print_header("AFTER PATCH")
        if result.get("error"):
            print(f"  {result['error']}")
        else:
            print(result["asm"])

        # Show before/after comparison.
        if "before_codelines" in result and "after_codelines" in result:
            from src.logic.server.patcher_compare import format_diff
            diff = format_diff(result["before_codelines"], result["after_codelines"])
            print_header("BEFORE/AFTER COMPARISON")
            print(diff)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrupted — sending interrupt to server...")
        from src.ui.server.client import shutdown
        shutdown()
        print("[*] Server interrupted. Exiting.")
