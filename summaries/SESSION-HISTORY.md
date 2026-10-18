# Session History Archive — Darkness Survival APK Patcher

Old/superseded session summaries from `AGENTS-edit.md` / `AGENTS.md`. These sessions are historical record; their key findings have been folded into the current Work Journal and Memory Diary.

---

## Sessions 1–5: from 2026-06-04 to 2026-06-09

### Session 1: Environment Setup & Symbol Comparison
- Compared target binary vs cpp-tests reference (19,334 common symbols = 83.9% match)
- Address mapping: `VMA = Ghidra_offset + 0xc53c0000`
- Discovered event strings: `"__connection_fail"` at `.rodata` file offset **0x797c03**, `"___ongcli___`" at `.rodata` file offset **0x7968b1**

### Session 2: Ghidra Decompilation & String Resolution
- Decompiled 8 key functions via pyghidra with correct address mapping (dispatchCustomEvent, UILayer::networking, closeConnectingServer, TextDataManager::getText, UIMessageBox::create, PopupManager::openPopup, GameNet::disconnect)
- Built initial string ID → text mapping from textdata_en.dat (IDs 2222–2700)

### Session 3: Hex Patches Applied (from cfg-explorer)
- Four patches applied to binary at `game/Darkness_Survival/lib/armeabi/libcocos2dcpp.so`
- Patch A (networking): `[0x01, 0xd1]` at 0x3c1608; Patch B (getGameNetState): `[0x02, 0x20, 0x70, 0x47]` at 0x3d5d00
- Patch C (getNetworkStatus): `[0xff, 0x20, 0x70, 0x47]` at 0x3d5d04; Patch D (getResult): `[0x01, 0x20, 0x70, 0x47, 0xc0, 0x46]` at 0x3d5e98

### Session 4: getText() Decoder Script & Markdown Documentation
- Created `decode_gettext.py` for string ID lookup; generated `app_init_flow.md`, `retry_button_deep_dive.md`

### Session 5: Thumb Mode Disassembly & Patch C Fix
- Critical discovery: binary uses THUMB (2-byte) instructions, NOT ARM (4-byte). Byte ordering is low-byte-first.

---

## Sessions from 2026-06-12

### Project Setup & Tooling
- Set up APK modding environment; created `1-import.sh`, `2-compile.sh`, `3-re-apply.sh`
- `3-re-apply.sh` handles compile → uninstall → install → launch → logcat cycle
- Fixed logcat filtering to use `adb logcat --pid=<PID>`; silenced jarsigner output

### Smali Log Injection & Workflow Fix
- Added custom `Log.i("RPG1", "...")` smoke test to `RPG1.smali`
- Bug: two separate `invoke-static {v0}, Log.i(...)` each with 1 arg → VerifyError. Fix: combine into `const-string v0` + `const-string v1` + single `invoke-static {v0, v1}`
- Changed fallback logcat to use `-d` flag (dump-and-exit)

### Jadx Deep Analysis & Debug Logging
- JADX analysis (`summaries/jadx-analysis.md`, 692 lines): explored Google Play Services, server connection, Vungle, Unity Ads code
- Both `onSignInFailed()` and `onSignInSucceeded()` call same native `onGameServiceLogin()` — native differentiates via `isSignedIn()` state
- Enabled debug logging across 20 smali files (6 BuildConfig.DEBUG, 5 game/SDK flags, 7 support library flags, 2 additional SDK flags)

---

## Sessions from 2026-06-13

### Sign-In Bypass Patches & Crash Fixes
- Applied all three sign-in bypass patches: `GameHelper.isSignedIn()` always true, `BaseGameActivity.onStart()` no-op, `BaseGameActivity.isSignedIn()` always true
- FacebookSdk crash fix: register overlap in `<clinit>` — used v5 for isDebugEnabled, increased `.locals 5 → 6`
- IabHelper crash fixes: `enableDebugLogging` skip disposed check + .locals fix; `startSetup()` replaced with no-op success
- Result: game launches to main menu, sign-in bypass works, GPGS popup gone. Still shows "Failed to connect to server" error box (native C++ UI), Retry loops infinitely

### Native C++ Decompilation & i18n Deobfuscation
- Ghidra installed at `./tools/ghidra/` with pyghidra 3.1.0
- Text data files: `textdata_en.dat` and `textdata_ko.dat`, 2978 strings each, null-terminated UTF-8/ASCII
- `TextDataManager::getText(int)` at ~0x3bb428: simple LUT lookup from textdata_en.dat
- i18n deobfuscation approach ("Rosetta Stone"): cross-reference `getText(#)` calls in decompiled functions with actual `.dat` strings
- Detailed mappings found for Player::updateHunger, Player::updateTiredness, ActorSprite HP display, UIRest results, player stats headers, UITutorial steps, Item names/descriptions, recipe upgrades

### Native C++ Decompilation & i18n Deobfuscation (continued)
- Capstone disassembly of `UIInventory::updateDetailStat` at 0x3c8640: 784 bytes, 363 instructions, Thumb mode. 40 function calls, only one named
- Ghidra decompilation fully annotated with 23/28 getText() calls resolved; remaining 5 use runtime-computed global data addresses
- Key finding: getText() uses mangled `_ZN15TextDataManager7getTextEi(0xNNN)` for HEX IDs (NOT decimal `\d+`)

### Actor::addBuff Decompilation
- `_ZN5Actor7addBuffEiiiii` at 0x36f2f8: adds buff to Actor, contains duplicate checks, water condition, buff stack time, UI icon display, special cases for buff types 0x1c/0x43/0x13/0x1b
- 0 getText() calls — pure logic/timer management

---

## Sessions from 2026-06-14

### Decompiler Tool v1
- Created `tools/decompile_func.py` combining Ghidra DecompInterface + Capstone + getText() deobfuscation
- Segfaults as standalone script; works in inline heredoc scripts
- `_UNK_` global data resolution partially works but some addresses contain computed values

### Decompiler Tool v1 (scrapped) → Auto-Annotate Script
- Scrapped `tools/decompile_func.py`; created `tools/auto_annotate.py` as replacement
- Two-pass annotation: variable assignment strings + getText call annotations with all possible strings
- Tested on 3 functions; idempotent — skips already-annotated lines

### Google Play Games Popup Bypass & Log.d Crash Fix
- Patched `GameHelper.smali` `beginUserInitiatedSignIn()` for instant sign-in success (commit `55f44c2`)
- Log.d crash fix: `invoke-static {v0}, Log.d(...)` with 1 arg → fixed to `{v0, v0}`

---

## Sessions from 2026-06-15

### Ad SDKs Fully Removed + Stubbed
- Stubbed `isUnityAdsAvailable()` and `presentUnityAds()` in `NativeWrapperActivity.smali`
- Deleted entire Unity Ads package (`com/unity3d/ads/`, ~40+ files) and Vungle package (`com/vungle/`, ~100+ files)
- All references cleaned from NativeWrapperActivity.smali
- Result: zero network traffic from ad SDKs, instant rewards

### Server Connection Blocker Identified
- Root cause: native C++ calls `GameNet::connectGameServer()` to dead server after sign-in succeeds
- JNI bridge: both `onSignInFailed()` and `onSignInSucceeded()` call same native `onGameServiceLogin()`

---

## Sessions from 2026-06-16

### Cached Ghidra Project & Decompiler Tooling
- Persistent Ghidra project at `tools/ghidra/project/ds_offline/` with full analysis cached on disk
- pyghidra vs GUI comparison for dispatchCustomEvent: GUI produces better type resolution (all analysis plugins enabled)
- PyGhidra API notes: segfault as standalone script, import ordering critical, `open_program()` deprecated, `DecompInterface` uses `.dispose()`
- New scripts: `tools/import-ghidra.sh`, `tools/decompile_cached.py` (syntax bug on line 68)

---

## Sessions from 2026-06-17

### Single Fast Decompiler Tool & Cached Ghidra Project
- **Created `decompile.py`** (replaces `./tools/decompile`): single Python entry point using pre-analyzed `ds_offline` Ghidra project. Supports mangled C++ names, demangled/partial names, hex addresses. Shows Levenshtein-similar function names on typo.
- **Created `export.py`** (replaces `./tools/export_func`): exports each function as 4 files (.c, .asm.txt, .cfg.txt, .ref.txt), organized by CFG depth from mainLoop (0x4e6a9c). Supports `--all`, `--reachable`, `--stale`, `--depth N`.
- **Ghidra cached project:** `tools/ghidra/project/ds_offline/` — binary imported, all 10 ARM32 system libs linked (~304/306 external symbols resolved), complete analyze done in GUI.
- **Address mapping:** File offset = Ghidra address (direct). VMA = file_offset + 0xc53d0000.

### AGENTS.md Edit Protocol
- Updated editing convention: copy to `AGENTS-edit.md`, edit, then swap back as single command

---

## Sessions from 2026-06-19

### getText() Deobfuscation Fix & CFG Extraction
- Ghidra decompiler now produces **two forms** of getText calls: `TextDataManager::getText(0xNNN)` (hex literal) and `TextDataManager::getText(varName)` (variable + constant propagation). Fixed annotation pipeline with `HEX_LITERAL_RE` pattern, multi-line assignment handling, and index-prefixed string annotations.
- **`--cfg` flag:** extracts control flow graph using `SimpleBlockModel` API. Flow types: FALL_THROUGH, CONDITIONAL_JUMP, UNCONDITIONAL_CALL. Each Python invocation is independent (JVM state NOT shared across invocations).

### Cocos2d-x Engine Entry Point & Source Code Reference
- Entry point confirmed from cpp-tests source code with proof lines
- Symbol verification and source code reference tree documented

---

## Sessions from 2026-06-20

### Binary Checksum Auto-Reimport
- SHA256-based auto-detection: computes current binary SHA256, compares to stored checksum file, re-imports on mismatch, skips on match (fast path). Checksum file at `project/lib/armeabi/libcocos2dcpp.so.sha256` (git-ignored).

---

## Sessions from 2026-06-21

### Full networking() CFG Analysis & Connection Flow Mapping
- **Function:** `_ZN7UILayer10networkingEv` at file offset `0x3d15e4` — 19 basic blocks, 6 conditional branches, 1 indirect call jumptable. All paths mapped (loading screen → error popup → main menu).
- **Connection flow with all 4 patches applied:**
  - **PHASE 1:** Show loading screen + check status (getGameNetState→2, getNetworkStatus→-1, dispatch "__connection_fail", closeConnectingServer, show error popup, disconnect, openConnectingServer AGAIN)
  - **PHASE 2:** Packet type check + jumptable (`__gnu_thumb1_case_uhi`)
  - **PHASE 3 (SUCCESS at LAB_003d1764):** syncServerTime → getProgressInfo → initTutorialButton → disconnect → closeConnectingServer → dispatch "connect" event → **second getResult()** (NOT PATCHED) → if result ≠ 2: openConnectingServer → cRam00b60084 check → FUN_003d22d0
- **Key functions state:** getGameNetState→2 (Patch B), getNetworkStatus→-1/0xff (Patch C), getResult→1 (Patch D, first call only), getPacketType→reads [GameNet+0x200c], ZPPTCPNetwork::status→reads [this+0x1c]
- **JNI bridge:** 8 native methods exported from NativeWrapperActivity: `onGameServiceLogin()`, `fullScreenADCallback()`, `IAPReceiveResultCallback(...)`, `onFBChangeProfile()`, `onFBLogin(I)`, `onUnityAdsCompleted(I)` (line 2429/2440), `setUrlSchemeParamCallback(I)`, `shareFinishedCallback()`
- **Binary insertion approach:** ~12-16 bytes per log call for `mov r0,#4` + `ldr r1,=string_addr` + `bl __android_log_print` + branch back

---

## Sessions from 2026-06-22

### Decompiler Tool Extensions (`--ref`, `--asm`)
- **`--ref` flag:** shows call graph references (callers/callees) using `.referenceType.isCall()` and `getFunctionContaining()`. Tested on dispatchCustomEvent (15 call sites across 12 functions) and networking (1 caller from onTimer).
- **`--asm` flag:** interleaves assembly with decompiled C code. Iterates every instruction in func.body order, showing raw bytes + mnemonic with matching C tokens as `//` comments. Matches Ghidra GUI display exactly.

---

## Sessions from 2026-06-26

### Full Export Tool & Reachability Analysis
- **Reachability from entry points:** JNI_OnLoad (0x3eeba0): 39 reachable, max depth 7; cocos_android_app_init (0x35cb64): 32 reachable, max depth 6; nativeInit (0x3eebb8): 735 reachable, max depth 13; applicationDidFinishLaunching (0x3ed7b8): 150 reachable, max depth 6; **mainLoop (0x4e6a9c): 1,310 reachable, max depth 18** — largest cluster.
- **Function composition:** Of 1,310 from mainLoop: 237 FUN_ (unnamed), 30 template instantiations, ~1,043 named non-template (~422 game-specific).
