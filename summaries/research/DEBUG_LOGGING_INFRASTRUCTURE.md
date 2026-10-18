# Debug/Logging Infrastructure in Decompiled Binary

## 1. `__android_log_print` Calls (Summary)

| Priority | Tag / Category | Count | Purpose |
|----------|----------------|-------|---------|
| **3 (INFO)** | `"JNI ZEROPP"` | **9** | Game-specific debug: dungeon generation, memory allocation, monster type selection |
| **3 (INFO)** | `"JniHelper"` | **6** | Cocos2d-x JNI bridge: JavaVM init, class loading, method lookup errors |
| **3 (INFO)** | `"CCFileUtils-android.cpp"` | **4** | File I/O: asset manager setup, file read paths/errors |
| **3 (INFO)** | `"cocos2d"` | **2** | Android engine: build version detection |
| **3 (INFO)** | `"cocos_android_app_init"` | **1** | App init entry point marker |
| **6 (ERROR)** | `"cocos2d-x assert"` | **42** | Assert failures across physics, rendering, scene graph, audio |
| **6 (ERROR)** | `"JniHelper"` | **5** | JNI method/class lookup failures |
| **3 (INFO)** | `"cocos2d-x debug info"` | **1** | LuaLog wrapper — forwards Lua print output to logcat |

**Total `__android_log_print` calls: 69** (across the decompiled .c files)
**Total `__android_log_write` calls: 1** (the LuaLog function)

## 2. Key Files with Game-Specific Debug Logging (`"JNI ZEROPP"` tag)

| File | Address | Message |
|------|---------|---------|
| `decompiled/.../36cb64_cocos_android_app_init.c` | `0x36cb64` | `cocos_android_app_init` (entry marker) |
| `decompiled/.../3b1f04_ProgressInfo.c` | `0x3b1f04` | `"not enough memory\n"` (in ProgressInfo constructor, line 46) |
| `decompiled/.../3aa1dc_PathFinder.c` | `0x3aa1dc` | `"not enough memory\n"` (line 31) |
| `decompiled/.../386fdc_generate.c` | `0x386fdc` | `"Unable to place the first room.\n"` (line 174), `"Unable to place more features (placed %d).\n"` (line 193) |
| `decompiled/.../382b28_getAvailableMonsterType.c` | `0x382b28` | `"getAvailableMonsterType" + param_1 + param_2` (line 40) |
| `decompiled/.../38248c_print.c` | `0x38248c` | `"print" + tile data` (line 19) |
| `decompiled/.../3821dc_printSimple.c` | `0x3821dc` | `"printSimple" + tile data` (line 19) |
| `decompiled/.../380efc_printRoom.c` | `0x380efc` | `"printRoom"` per-tile and newline (lines 22, 26) |
| `decompiled/.../380744_getSpecialRoomTemplateIndex.c` | `0x380744` | `"getSpecialRoomTemplateIndex" + params` (line 70) |
| `decompiled/.../36f2f8_addBuff.c` | `0x36f2f8` | `"not enough memory\n"` (line 52) |
| `decompiled/.../36d2bc_onLoad.c` | `0x36d2bc` | `"not enough memory\n"` (line 59) |
| `decompiled/.../37ec44_onLoad.c` | `0x37ec44` | `"not enough memory\n"` (line 30) |

## 3. LuaLog — Console Debug Output Bridge

**File:** `decompiled/.../3edc04_LuaLog.c`
```c
void cocos2d::LuaLog(char *param_1) {
    __android_log_write(3, "cocos2d-x debug info", param_1);
}
```
This is the Cocos2d-x Lua `print()` function — any Lua code calling `print()` will be forwarded to logcat with priority 3 (INFO). This means **Lua scripts in the game can produce debug output**.

## 4. Console System

**File:** `decompiled/.../4e406c_Console.c`

The game includes a full `cocos2d::Console` system with registered commands including:
- `"debugmsg"` — "Whether or not to forward the debug messages on the console. Args: [on | off]" (line 67-69)
- `"config"` — Print the Configuration object
- `"allocator"` — Display allocator diagnostics

This is a Cocos2d-x built-in remote console for debugging. The `debugmsg` command suggests there's a toggleable debug message forwarding system.

## 5. Debug Draw / Visualization Infrastructure (Extensive)

The binary contains **80+ functions** related to debug drawing across multiple subsystems:

- **Cocos2d PhysicsWorld:** `PhysicsDebugDraw`, `debugDraw()`, `setDebugDrawEnable()`, `isDebugDrawEnabled()`, `setDebugDrawMask()`
- **Cocos2d NavMesh:** `NavMeshDebugDraw` (15+ functions), `debugDraw()`, `setDebugDrawEnable()`, `isDebugDrawEnabled()`
- **Bullet Physics (btIDebugDraw):** `drawLine`, `drawSphere`, `drawBox`, `drawTriangle`, `drawCapsule`, `drawPlane`, `drawCone`, `drawCylinder`, `drawTransform`, `drawAabb` + many more
- **Spine Animation:** `SkeletonRenderer::drawDebug()`, `setDebugBonesEnabled()`, `getDebugSlotsEnabled()`
- **Cocostudio BoneNode:** `setDebugDrawEnable()`, `getDebugDrawLength/Width/Color()`
- **Physics3DWorld:** `setDebugDrawEnable()`, `isDebugDrawEnabled()`, `Physics3DDebugDrawer`
- **ClightningBoltSprite:** `debugDraw_segWireFrame()`, `debugDraw_segLineAndDot()`, `onDrawDebug()`
- **btCollisionWorld:** `debugDrawWorld()`, `debugDrawObject()`, `setDebugDrawer()`

All of these are **unconditional** — they're always present in the binary, but most are gated behind a bool flag (e.g., `isDebugDrawEnabled`) that is called before each draw call. These are NOT compiled out with `#ifdef`.

## 6. `printf`/`sprintf`/`fprintf` Calls (Non-Logcat)

**287 files** contain at least one `printf`-family call, but these are primarily:
- **libTIFF** library: `sprintf`, `fprintf` for TIFF tag printing and error messages ("Sorry, can not handle images with...")
- **libpng**: `fprintf` for "libpng error:" / "libpng warning:" to stderr
- **zlib/gzip**: `fprintf` for compression format info
- **TextureCache dumpDebugInfo:** `snprintf("TextureCache dumpDebugInfo: %ld textures, for %lu KB (%.2f MB)\n")` at `0x503424`

None of these are game-specific debug output — they're all third-party library error/info reporting.

## 7. Conditional Debug Flags / `#ifdef DEBUG` Style Checks

**No `#ifdef DEBUG`, `#if DEBUG`, or `#ifdef DBG` preprocessor blocks** were found in any `.c` files. This is expected since the decompiled output is post-compiler C (not source), but it means:

- There are **no conditional compilation blocks** visible in the decompiled code
- All debug functions and log calls are **unconditionally compiled in**
- The `"JNI ZEROPP"` logs are gated only by runtime conditions (e.g., "if room placement fails" or "if memory allocation fails"), not by a global debug flag

## 8. Debug Mode / Debug Flag Variables

The search for variables named with debug prefixes (`isDebug`, `debugMode`, `DEBUG_MODE`, `m_debug`, `s_debug`, etc.) found only:
- **`isDebugDrawEnabled()`** methods — these are per-subsystem bool flags (PhysicsWorld, NavMesh, BoneNode) that gate visual debug rendering. These are NOT global debug mode flags.

There is **no global "debug mode" or "debug flag" variable** visible in the decompiled output.

---

## Summary: What Kind of Debug/Logging Infrastructure Exists?

**The original binary had substantial debug logging infrastructure that SURVIVED compilation.** Specifically:

1. **69 `__android_log_print` calls** are present — this is not a stripped-out release build. The game was compiled with `#define LOG_TAG "JNI ZEROPP"` style macros, and the logs were left in for:
   - Dungeon generation (room placement, monster types, features)
   - Memory allocation failures (calloc returns NULL across 5+ functions)
   - JNI bridge state tracking

2. **All logs are priority 3 (INFO), not priority 2 (DEBUG).** This means the Cocos2d-x `CCLOG` macro was likely mapped to INFO level, or the build used `ANDROID_LOG_INFO`. The `"cocos2d-x assert"` calls at priority 6 are error-level assertions.

3. **No conditional debug flag gates** any of the `"JNI ZEROPP") logs. They fire whenever their condition is met (e.g., memory failure, room placement failure). This means they will produce logcat output during normal gameplay when these events occur.

4. **The Lua print bridge (`LuaLog`) and Console system** are fully present and functional — Lua `print()` goes to logcat, and there's a debug message forwarding toggle in the console.

5. **80+ debug draw functions** are all compiled in for visual debugging (physics bodies, navmesh, bones), each gated by a per-subsystem bool flag.

6. **The build appears to be a DEBUG or BETA build**, not a fully stripped production release. A production build would typically:
   - Strip `__android_log_print` calls entirely via `#ifdef NDEBUG` / `CCLOG` macros
   - Remove debug draw functions via `#if CC_ENABLE_STACKABLE_EFFECTS` or similar
   - Remove the Console system

## Practical Implications

The binary retains its full debug logging infrastructure. You can see game state (dungeon generation, memory allocation, JNI status) in logcat by filtering for `"JNI ZEROPP"` or `"cocos2d"`. This is very useful for offline mode debugging — you can watch the dungeon generator run, see when room placement fails, and track memory allocations without needing a server connection.
