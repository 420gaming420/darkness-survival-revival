# Darkness Survival (Revival)
This is a hex edit patcher project that "revives" the abandoned android game **Darkness Survival (2016)**, whose servers have been offline since ~2021.

**Notice:** No game content or code is in this project — only modding scripts and tools. The latest version of the game apk "v1.1.29" is required and not included. There are NO game files or assets in this repo.

## Patcher Proof

https://github.com/user-attachments/assets/7d6ba17d-c86a-431c-aa72-27ba416fc654

Be aware that since this is an ARM32 game, it only runs on devices compatible with ARM32. For the android studio AVD, you have to use Android 11 x86_64 (not x86), as shown in the video as that version contains an ARM32 translation library for backwards compatability.

## What Works

Without the patch, the game does not work: app start → stuck on connecting to the server → could not connect → infinite retry loop

With the "revival" patch, the game is fully playable from launch through one complete playthrough: title screen → main menu → tutorial prologue → gameplay → death → scoreboard → main menu again. Core offline features work:

- Movement, combat, inventory, hunger/tiredness mechanics
- In-game ad rewards (Slate of Illusion → watch ad → instant item reward, no ad shown)

## What's Broken (Server-Dependent)

These features expect a server response that never arrives:

| Issue | Severity | Status |
|---|---|---|
| No saved progress | HIGH | Game "works" but many gameplay mechanics do not |
| Game over scoreboard freeze | HIGH | Forces you to close the app in order to get back to the main menu |
| Craft recipes and runes | HIGH | Exists but broken |
| Box of Memories empty after game over | MEDIUM | Hypothesis: server didn't send reward data |
| Ankh resurrection bugged (0x20202020 count) | MEDIUM | Hypothesis: resurrection packet never sent |
| Ancient Coins stuck at 10 | MEDIUM | Not earned on game over |
| IAP crash on tap (`IabHelper was disposed`) | LOW | Stubbed, low priority |
| Free common box does nothing | LOW | Reward delivery expects server confirm |

See [summaries/patch/OFFLINE_PATCH_PLAYTEST.md](https://github.com/420gaming420/darkness-survival-revival/blob/dev/summaries/patch/OFFLINE_PATCH_PLAYTEST.md) for the full playtest report.

## Quick Start

```bash
# One-command pipeline: unpack → patch binary → patch smali → repack → deploy to device
./run.sh
```

This reads `GAME_APK` from `.env` (defaults to `Darkness_Survival.apk`).

## Scripts

| Script | Purpose |
|---|---|
| `./run.sh` | Full pipeline: decompile → mod-binary → mod-smali → compile → deploy |
| `./1-import.sh <apk>` | Decompile APK to `project/`, enable debug mode, generate keystore (if missing) |
| `./mod-binary.sh` | Apply 5 hex patches to `libcocos2dcpp.so` (offline mode connection bypass) |
| `./mod-smali.sh` | Stub ad SDK calls in `NativeWrapperActivity.smali` for instant rewards |
| `./2-compile.sh` | Recompile + sign `project/` → `project.apk` |
| `./3-re-apply.sh` | Compile → backup saves → uninstall → install → restore saves → launch on device |
| `./save-backup.sh` | Back up all `gamedata*.dat` files from device to `sources/saves/*.bak` |
| `./save-restore.sh` | Restore saved games to device (launches app, stops, restores, relaunches) |

### `.env`

Copy `.env.example` to `.env` and configure the APK path (and optionally the ghidra install path):

```bash
GAME_APK=Darkness_Survival.apk
```

If absent, `run.sh` defaults to `Darkness_Survival.apk` in the current directory.

## Hex Patches Applied

Five byte-level patches to `libcocos2dcpp.so` that bypass all connection requirements:

| Patch | Function | Offset | Change |
|---|---|---|---|
| A | `UILayer::networking()` | `0x3c1608` | `beq.n` → `bne.n` (skip loading screen when state==CONNECTING) |
| B | `GameNet::getGameNetState()` | `0x3d5d00` | Always return `2` (CONNECTING) |
| C | `GameNet::getNetworkStatus()` | `0x3d5d04` | Always return `-1` (0xff, passes all status checks) |
| D | `GameNet::getResult()` | `0x3d5e98` | Always return `1` (SUCCESS) |
| E | `UILayer::sendPacket()` | `0x3c04c0` | No-op — return immediately, eliminates "Connecting to Server" screen |

See [summaries/patch/REPRODUCE_HEX_PATCH.md](https://github.com/420gaming420/darkness-survival-revival/blob/dev/summaries/patch/REPRODUCE_HEX_PATCH.md) for full technical details.

The patches are idempotent — re-running `run.sh` on an already-patched file skips silently.

## Decompiled Reference

All ~24K functions can be exported into `./decompiled/` via the Ghidra background server:

> I have been using ghidra v12.1 for this project, newer versions have not been tested and may or may not work.
> The binary `project/lib/armeabi/libcocos2dcpp.so` must exist before running any Python tool. Run `./1-import.sh` first to extract it from the APK. All tools (`server.py`, `decompile.py`, `export.py`, `jvm.py`, `patcher.py`) will exit with a clear error if the game binary or ghidra is missing.

```bash
python3 decompile.py <function_name_or_address>    # decompile a function
python3 decompile.py <name> --cfg                  # with control flow graph
python3 decompile.py <name> --asm                  # with interleaved assembly
python3 export.py --all                            # export all functions
python3 patcher.py --show <function>               # inspect + patch preview
```

See [AGENTS.md](https://github.com/420gaming420/darkness-survival-revival/blob/dev/AGENTS.md) for the full tool reference.

## How It Works

The game was designed to constantly talk to an online server, many actions would first try to connect to the server.

The offline patch makes the game think it's always connected:

1. **`sendPacket()`** — the main bottleneck. Every network action went through it. Patched: returns immediately, no loading screen, no TCP connect.
2. **`getGameNetState()`** — controls whether the loading screen is shown. Patched: always says "connecting".
3. **`getNetworkStatus()`** — monitored the TCP socket. Patched: always returns "alive but idle".
4. **`getResult()`** — tells the game whether connection succeeded. Patched: always says "success".
5. **`networking()`** — the connection state machine. One condition flipped so the loading screen hides correctly.

Together, these 5 changes (4–8 bytes each) make the entire game work offline with zero network traffic.

## Requirements

- Android device or AVD with USB debugging enabled
- `apktool` installed
- `adb` in PATH (`$ANDROID_HOME/platform-tools/adb`)
- Java/JDK for keytool and jarsigner

## Notes

- All scripts are tested and idempotent where applicable
- The `project/` directory is regenerated from the APK on each `./run.sh` run if missing
- Save data persists across reinstallations via `./save-backup.sh` / `./save-restore.sh`
- The `mykeystore.jks` file is generated once and reused on subsequent runs

## AI Disclosure

This project was developed with [opencode](https://github.com/anomalyco/opencode/releases) using a locally hosted [llama.cpp server](https://github.com/ggml-org/llama.cpp) as the provider with 256k context size running Qwen3.5 35B quantized at 4-bit GGUF, later upgraded to Qwen3.6 35B [Myric/KAT-Coder-V2.5-Dev-MTP-APEX-GGUF](https://huggingface.co/Myric/KAT-Coder-V2.5-Dev-MTP-APEX-GGUF) i-quality version.

This repo may contain inaccuracies, hallucinated logic, or suboptimal patterns introduced by the model. Scripts were manually reviewed and tested by a human operator, and the offline mode patch has been verified to work in practice. Contributions and pull requests fixing bugs or making improvements are welcome.

## Unlicense

This is free and unencumbered software released into the public domain.
