# AGENTS.md — Work Journal & Memory Diary

---

## WORK JOURNAL

### Project Overview
- **Game:** Darkness Survival (`Darkness_Survival.apk`) — old ARM32 abandonware Android game
- **Package name:** `com.zeroplusplus.rpg1`
- **Main activity:** `com.zeroplusplus.rpg1.RPG1`
- **Engine:** Cocos2d-x (native lib: `cocos2dcpp`)
- **Version:** 1.1.29, minSdk 10 (Android 2.3.7), targetSdk 28 (Android 9)
- **Status:** Server is dead, game is unplayable online. Goal: implement offline mode patch for singleplayer.
- **Status:** All patches applied. Game launches to main menu, plays tutorial prologue, completes one full playthrough (gameplay → death → scoreboard → main menu again). Core loop is functional offline. Remaining issues: game over scoreboard freeze, empty Box of Memories, Ankh resurrection bugged, IAP crash on tap (see `summaries/patch/OFFLINE_PATCH_PLAYTEST.md` for full details).

### Editing AGENTS.md
- **Never edit `AGENTS.md` directly** — each edit triggers a full session reload (10+ min wait).
- Always copy to `AGENTS-edit.md` first, make all edits there, then do: `[rm AGENTS.md && mv AGENTS-edit.md AGENTS.md && git commit]` as a single command.

### Key Commands / Scripts
| Command | Purpose |
|---|---|
| `./1-import.sh` | Decompile APK, enable debuggable, generate keystore (run once) |
| `./2-compile.sh` | Recompile + sign → project.apk |
| `./3-re-apply.sh` | Full hot-reload cycle: compile → save-backup → uninstall → install → save-restore → logcat |
| `./save-backup.sh` | Back up all gamedata*.dat files from device to sources/saves/*.bak (standalone, any time) |
| `./save-restore.sh` | Restore .bak files to device — launches app 5s, stops, restores each file, relaunches (standalone) |
| `python3 server.py start` | Start the background JVM server in background |
| `python3 server.py stop` | Gracefully shut down the background server |
| `python3 server.py restart` | Stop then start the background server |
| `python3 server.py status` | Show server state, analysis progress, patch info |
| `python3 server.py logs [N]` | Show last N lines of server log (default: 20) |
| `python3 server.py wait` | Block until server finishes initialization |
| `python3 decompile.py <name>` | Decompile a function via background server (see below) |
| `python3 decompile.py <name> --cfg` | Decompile + extract control flow graph |
| `python3 decompile.py <name> --asm` | Decompile + interleaved assembly output |
| `python3 export.py --all` | Export all ~24K functions to ./decompiled/ (run once or after binary patch) |
| `python3 jvm.py "code"` | Send Python code to the running Ghidra server JVM session (single expression mode) |
| `python3 jvm.py` | Interactive REPL — access to fpa, prog, mem, listing, func_mgr |
| `./search <query>` | Recursive grep wrapper, searches entire $PWD including ./decompiled/ (see below) |
| `python3 -c "from src.ui.server.client import shutdown; shutdown()"` | Gracefully stop the background server (alt.) |

### Searching with `./search`

**Primary tool for finding code.** A `grep` wrapper that searches the entire `$PWD` recursively, including `./decompiled/`, `project/smali/`, `jadx-java/`, etc. Fast — no JVM startup, just instant grep.

```bash
# Correct usage:
./search 3c45b4              # bare hex address (matches both "3c45b4" and "0x3c45b4")
./search 3c45b4 --include "*.c"   # filter by filename glob
./search init --include "*.ref.txt"  # find all functions referencing "init"
```

- **Use bare hex** (e.g. `3c45b4`), NOT `0x3c45b4` — the prefix-less form matches both bare addresses and `0x`-prefixed ones in decompiled output, catching more results.
- **Excludes:** `.git/`, `tools/`, `sources/`, `src/`, `summaries/` by default for speed.
- **Shows filenames + line numbers** (fixed from `-l` which suppresses line numbers).
- **Always use the local path** `./search`, not `/path/to/search` or just `search`.
- Avoid `cd` — always use absolute or `./`-prefixed paths.

### JVM Inspector (`jvm.py`)

Interactive Python REPL for sending code to the running Ghidra server's JVM session. Useful for exploring the pyghidra API, testing exports, and ad-hoc debugging without stop/start cycles.

```bash
# Single expression mode:
python3 jvm.py "from ghidra.app.util import exporter; print(dir(exporter))"

# Interactive REPL mode (access to fpa, prog, mem, listing, func_mgr):
python3 jvm.py
jvm> from ghidra.app.util import exporter
jvm> cls = exporter.OriginalFileExporter
```

The `execute` RPC handler (`src/logic/server/execute.py`) runs arbitrary Python code inside the JVM session, injecting `fpa`, `prog`, `mem`, `listing` into the namespace. This is what powers `jvm.py`.

### Decompiling the Native Binary (`libcocos2dcpp.so`)

**All ~24K functions are pre-exported** into `./decompiled/` via `python3 export.py --all`. Each function gets 4 files: `.c`, `.asm.txt`, `.cfg.txt`, `.ref.txt`.

**Background server architecture (since 2026-07-04):**
- `decompile.py`, `export.py`, `patcher.py` are **pure RPC wrappers** — zero pyghidra/JVM code in these files.
- `jvm.py` uses the `execute` RPC handler (`src/logic/server/execute.py`) to run arbitrary Python code inside the JVM session.
- Each tool calls `src.ui.server.client.rpc()` which auto-starts a background server if not running.
- The server (`src/ui/server/core.py`) runs as a single JVM process with JSON-RPC over HTTP on port 18960.
- All analysis (system lib imports + full Ghidra analysis ~15-45 min) happens in a background thread; RPC requests stall/wait until init completes.
- `/progress` endpoint reports real-time analysis status: `GET http://127.0.0.1:18960/progress`.
- Concurrent clients each launch their own server copy; only one survives (EADDRINUSE kills the rest), all converge on the same single JVM.
- No lock files — uses port probing + shared PID file (`src/ghidra_server.pid` for coordination.
- Inactivity timeout: 90 minutes of no requests before auto-shutdown.
- Log file: `src/ghidra_server.log` (verbose always-on logging).

**Usage:** All three tools are instant after first use (server stays alive in background):
```bash
python3 decompile.py dispatchCustomEvent          # instant — server is already running
python3 export.py --all                           # instant — reuses existing server
python3 patcher.py --show sendPacket              # instant — reuses existing server
```

**First use after server stop:** Server auto-starts on first tool call. Initial run includes full analysis (~15-45 min). Subsequent calls are near-instant since the JVM session persists.

**Auto-reimport on checksum mismatch:** All tools detect when the binary differs from stored SHA256 and re-import into the Ghidra project via `analyzeHeadless -overwrite`.

```bash
# Mangled C++ name (preferred — exact match from symbol table):
python3 decompile.py _ZN7cocos2d15EventDispatcher19dispatchCustomEventERKSsPv

# Demangled/partial name (substring search in function names and symbols):
python3 decompile.py dispatchCustomEvent
python3 decompile.py networking

# Hex address:
python3 decompile.py 0x4ea584

# With control flow graph (CFG) — shows all basic blocks and edges:
python3 decompile.py _ZN7UILayer10networkingEv --cfg

# Full export of function(s) as 4 files each, organized by CFG depth from mainLoop:
python3 export.py <name_or_addr>           # single function
python3 export.py --all                    # all ~24K functions
python3 export.py --reachable              # mainLoop-reachable (1,310 funcs)
python3 export.py --stale                  # re-export from export_stale.csv
python3 export.py --depth N                # only depth level N
```

**Output:** formatted C code with `getText(0xNNN)` calls annotated from `textdata_en.dat`. Each resolved string is prefixed with its index (e.g., `gettext(2302); // 2302 = "Full stomach! Full of energy!"`). For variable arguments, all possible strings are shown sorted by ID. If the name isn't found, shows Levenshtein-similar function names for correction.

**CFG mode (`--cfg`)** appends a "CONTROL FLOW GRAPH" section: each block's address range with all outgoing edges and flow types (FALL_THROUGH, CONDITIONAL_JUMP, UNCONDITIONAL_CALL), plus conditional branch summary showing TRUE/FALSE paths per branch point.

The cached project was set up by importing all ARM32 libs from `/home/admin/GIT/darkness-survival-revival/sources/lib/` into the Ghidra GUI (libEGL, libGLESv2, liblog, libc, libm, libstdc++, etc.), then running "complete analyze." This resolves ~304 of 306 external symbols.

**Key decompiled functions already available:** `dispatchCustomEvent` (0x4ea584), `UILayer::networking` (0x3d15e4), `UIInventory::updateDetailStat` (0x3c8640), `Actor::addBuff` (0x36f2f8), `Player::updateHunger` (0x3ac814).

### After Hex-Editing the Binary

When you apply hex patches to `libcocos2dcpp.so`, just run `decompile.py <func>` — it auto-detects checksum mismatch and re-imports. Subsequent runs use cached project (instant). Re-import requires shell timeout of at least 20 minutes.

### Patcher Tool (`patcher.py`)

Custom binary patching tool for quick inline patches with decompiled output comparison. Runs via background server (same JVM session as `decompile.py`/`export.py`). All patches are **in-memory** — they don't write to disk until `--export` is used.

```bash
# Show current state of a function:
python3 patcher.py --show sendPacket
python3 patcher.py --show 0x3d04c0
python3 patcher.py --show _ZN7UILayer10networkingEv

# Preview a patch (dry run, reads binary on disk):
python3 patcher.py -r 0x3d04c0 02207047 --preview

# Apply patch (in-memory, no disk write). Uses mnemonics with DECIMAL immediates (#255 not #ff):
python3 patcher.py -a 0x3ac826 "ble 0x3ac834" -a 0x3ac828 "mov r1,#255"

# Multiple patches at once (Ghidra addresses, not file offsets):
python3 patcher.py -r 0x3d5d00 02207047 -r 0x3d5e98 01207047c046

# Hex bytes format: space-separated or continuous (each pair = one byte)

# Export patched binary to disk (uses Ghidra's OriginalFileExporter — same as GUI "Export as Original File Format")
# Skips decompiled/SHA8 re-export if the versioned folder already exists (saves ~10 min):
python3 patcher.py --export

# Undo last N patches from memory state:
python3 patcher.py --undo 1

# Show current patch state, SHA256s, and history:
python3 patcher.py --status
```

**Key difference from raw `python3 -c` patches:** `patcher.py` uses **Ghidra addresses** (matching `--show` output and objdump), not file offsets. File offset = Ghidra address − 0x10000. The tool handles the conversion internally.

**Patching approach:** Uses `WildSleighAssembler.patchProgram()` which handles writing bytes, clearing code units, parsing new instructions, and setting up fall-throughs in a single call (replaces the old 3-step clear/setByte/parse pipeline).

**Assembly encoding:** Assembler uses `fillMask()` via `AssemblyPatternBlock` to constrain output to 2-byte Thumb instructions instead of defaulting to 4-byte ARM.

**Before/after comparison:** When using `--show` with applied patches, a unified diff of C code lines is shown automatically via `patcher_compare.py`. The compare tool searches recursively through versioned `decompiled/<sha8>/` folders for pre-patch .c files. Uses the stored binary SHA256 (from `*.sha256` file) as the versioned folder key.

**Export:** Uses `ghidra.app.util.exporter.OriginalFileExporter` (same as GUI "Export as Original File Format"). Builds an `AddressSet` of all non-overlay memory blocks, exports to a temp file via Java, reads back via `FileInputStream`. Produces a faithful binary with all patches applied — no corruption, no zero-filled gaps.

**Skip logic:** If `decompiled/<sha8>/` already exists, skips the full re-export entirely (returns immediately). This prevents wasting ~10 minutes on repeated exports of the same binary state.

### Cocos2d-x Engine Entry Point (CRITICAL for native RE)

Every Cocos2d-x Android project follows the same entry pattern:

```
Android loads libcocos2dcpp.so via System.loadLibrary("cocos2dcpp")
  → JNI_OnLoad (javaactivity-android.cpp:53), exports _Z13JNI_OnLoadP7_JavaVMPl at ~0x3deba0
  → cocos_android_app_init (each project's main.cpp), weak symbol, exports _Z22cocos_android_app_initP7_JNIEnv at ~0x35cb64
  → new AppDelegate() → applicationDidFinishLaunching() — initializes Director, GLViewImpl, resource paths, game controller
  → Cocos2dxRenderer.nativeInit (javaactivity-android.cpp:62) — each frame; first call triggers Application::getInstance()->run() (THE INFINITE GAME LOOP)
```

**Source code reference:** `sources/cocos2d-x/cocos/platform/android/javaactivity-android.cpp` contains all JNI bridge functions.
**Address mapping:** File offset = Ghidra address (direct). VMA = file_offset + 0xc53d0000.

### Logcat Best Practices
- Use `adb logcat --pid=<PID> -v threadtime -t 100` to filter by app PID
- Get PID via: `adb shell ps | grep -w 'com\.zeroplusplus\.rpg1' | awk '{print $2}' | head -n1`
- Always clear logcat before launch: `adb logcat -c` (done in 3-re-apply.sh)

### Architecture & Patching Strategy
- **Java entry point:** `com/zeroplusplus/rpg1/RPG1.smali` — main activity
- **Native trigger:** `NativeWrapperActivity.smali` — calls native C++ via JNI; on "Retry" tap: `onSignInFailed()` → `NativeWrapperActivity.onGameServiceLogin()` (a C++ function from libcocos2dcpp.so)
- **All game logic** is in the native `libcocos2dcpp.so` binary (ARM32)
- **JNI layer** handles Android-specific things: Play Store, ad services, etc.

### Hex Patches Applied

**CRITICAL:** The binary uses THUMB (2-byte) instructions, NOT ARM (4-byte). Thumb instruction byte ordering: for a 16-bit Thumb word `0xNNMM`, stored as `[0xMM, 0xNN]` (low byte first). All patch bytes must be written in this order.

#### PATCH A: `networking()` — Change beq.n to bne.n
- **File offset:** `0x3c1608–0x3c1609`
- **Before:** `[0xd0, 0x01]` → `beq.n #0x3c160e`; **After:** `[0x01, 0xd1]` → `bne.n #0x3c160e`

#### PATCH B: `getGameNetState()` — Always return 2 (CONNECTING state)
- **File offset:** `0x3d5d00–0x3d5d03`
- **Before:** `[0x68, 0x00, 0x47, 0x70]`; **After:** `[0x02, 0x20, 0x70, 0x47]` → `movs r0, #2 / bx lr`

#### PATCH C: `getNetworkStatus()` — Always return -1 (0xff)
- **File offset:** `0x3d5d04–0x3d5d07`
- **Before:** original; **After:** `[0xff, 0x20, 0x70, 0x47]` → `movs r0, #0xff / bx lr`

#### PATCH D: `getResult()` — Always return 1 (SUCCESS)
- **File offset:** `0x3d5e98–0x3d5e9d`
- **Before:** `[0x4b, 0x01, 0xc0, 0x56, 0x70, 0x47]`; **After:** `[0x01, 0x20, 0x70, 0x47, 0xc0, 0x46]` → `movs r0, #1 / bx lr / nop`

#### One-liner to apply all patches from scratch:
```bash
python3 -c "
data = open('project/lib/armeabi/libcocos2dcpp.so', 'rb').read()
d = bytearray(data)
d[0x3c1608]=0x01; d[0x3c1609]=0xd1
d[0x3d5d00]=0x02; d[0x3d5d01]=0x20; d[0x3d5d02]=0x70; d[0x3d5d03]=0x47
d[0x3d5d04]=0xff; d[0x3d5d05]=0x20; d[0x3d5d06]=0x70; d[0x3d5d07]=0x47
d[0x3d5e98]=0x01; d[0x3d5e99]=0x20; d[0x3d5e9a]=0x70; d[0x3d5e9b]=0x47; d[0x3d5e9c]=0xc0; d[0x3d5e9d]=0x46
open('project/lib/armeabi/libcocos2dcpp.so', 'wb').write(d)
print('All 4 patches applied.')
"
```

#### PATCH E: `sendPacket()` — No-op
- **Ghidra address:** `0x3d04c0` | **File offset:** `0x3c04c0`
- **Before:** `[0x38, 0xb5, 0x08, 0x4d]` → `push {r3,r4,r5,lr} / ldr r5,[pc,#8]`
- **After:** `[0x02, 0x20, 0x70, 0x47]` → `movs r0,#0 / bx lr`
- Replaces the entire function body with immediate return. Previously: checked if GameNet* was NULL → if so, called `openConnectingServer()` + `connectGameServer()`; if not, called `sendPreparedPacket()`. Now always returns immediately. Eliminates "Connecting to Server" loading screen entirely.

#### Current bugs (post-playtest, see `summaries/OFFLINE_PATCH_PLAYTEST.md`)
1. **Game over / scoreboard freeze** — After dying, the "Your Adventure Record" scoreboard appears but is frozen (tapping/swiping does nothing). Hypothesis: scoreboard handler waits for server response that never comes. Needs patch in scoreboard UI or post-game packet processing.
2. **Box of Memories empty** — Post-game loot box never spawns because server didn't send reward data. `getProgressInfo()` parses empty/default progress packet. Fix: spawn default box locally or make empty state navigable.
3. **Ankh resurrection bugged** — Player sometimes has 538,976,288 Ankh (0x20202020 = uninitialized/zero-filled memory), other times 0 or 5. Tapping Ankh on game over does nothing — it doesn't spend the item. Hypothesis: `prepareResurrection()` sends no-op packet, server never confirms revive, player stays dead. Fix: patch resurrection handler to skip server round-trip and revive locally.
4. **Ancient Coins bugged** — Player permanently has 10 ancient coins. On game over, supposed to earn coins based on gameplay score but it doesn't happen. Tapping locked runes/crafting with coins does nothing (runes are a core game feature). Fix: find where server sends coin rewards in post-game packet and replicate locally, or hardcode a reasonable amount.
5. **IAP crash** — Tapping any ancient coins purchase option crashes with `IabHelper was disposed of`. Low priority (cheat feature). Fix: stub `GoogleIAPActivity.purchaseProductCall` or `IabHelper.launchPurchaseFlow`.
6. **Free common box does nothing** — Tapping free ad box in Store has no effect. Hypothesis: reward delivery expects server confirmation.

**Also still unpatched:** Second `getResult()` call at ~0x3d1746 in `networking()` and global flag `cRam00b60084` at file offset ~`0xb60084`. These may be relevant to the scoreboard freeze.

### Rules & Conventions
- **Never ignore tool call error messages.** If a tool says to use Read first, stop and read it.
- **Never use foreground/interactive commands with Bash** — e.g., `adb logcat` without `-d` or `-t` will block forever
- **Never read binary data directly with the Read tool** — use `xxd`, `strings`, or `objdump` to sanitize
- **Always include a unique "callsign" string in any code changes** so you can verify the change took effect: `adb logcat -d | grep "your-callsign-here"`

---

## MEMORY DIARY

### Session: 2026-07-02 — Save Data Analysis & Backup/Restore Workflow
- **Save file location:** `/data/data/com.zeroplusplus.rpg1/files/gamedata*.dat` — the game uses Cocos2d-x's `FileUtils::getWritablePath()` to store saves in internal app storage. Primary files: `gamedata1.dat` (progress info / player state) and `gamedata5.dat` (world/save data). Additional files (`gamedata2.dat`, `gamedata3.dat`, `gamedata4.dat`) exist conditionally based on game state.
- **File format:** Binary, encrypted with `ZPPCoder::encodeWithKey()` — XOR with 256-entry LUT table keyed by device User ID, plus checksum byte. Each file starts with a 20-byte header (magic number `0xC9B9` + padding), then encrypted body. Device-tied — cannot decrypt on another device without same User ID.
- **Save contents:** Player stats (HP, hunger, tiredness, level, XP, gold), inventory (items, equipment slots), dungeon progress, runes (0x55 entries), recipes, class unlocks, achievements, Ankh count, Ancient Coins. `ProgressInfo::save()` at 0x3b2254 handles writing.
- **Backup method:** `adb shell "run-as com.zeroplusplus.rpg1 ls /data/data/com.zeroplusplus.rpg1/files/ | grep ^gamedata"` to discover files, then each file individually with `adb shell "run-as com.zeroplusplus.rpg1 cat /path/to/file" > local.bak`. Must use `adb shell "run-as ..."` (double-quoted) not `run-as ... sh -c '...'` so commands themselves run as the app user.
- **Restore method:** Push to `/data/local/tmp/`, then `adb shell "run-as com.zeroplusplus.rpg1 dd if=/data/local/tmp/name of=/data/data/.../name bs=4096"`. Must launch app first (5s) so data directory exists, then `am force-stop` before restoring.
- **Critical bug fix:** `adb shell` calls inside a `while read` loop consume the here-string's stdin, causing only the first file to be processed. Fixed by adding `< /dev/null` to each adb call.
- **`save-backup.sh`** — standalone script that discovers all `gamedata*.dat` files and backs each to `sources/saves/*.bak` with byte count verification.
- **`save-restore.sh`** — standalone script that launches app (5s) → stops it → restores each `.bak` file → relaunches. Verifies byte counts on restore.
- **`3-re-apply.sh`** refactored to call `./save-backup.sh` before uninstall and `./save-restore.sh` after install. Can comment out the backup call to reuse the same save state across multiple install cycles without replaying the tutorial.
- **Documentation:** Full analysis in `summaries/research/SAVE_DATA_ANALYSIS.md`.

### Older sessions archived → `summaries/SESSION-HISTORY.md`
Sessions 1–5 (cfg-explorer era) through 2026-07-01 are fully archived there.
