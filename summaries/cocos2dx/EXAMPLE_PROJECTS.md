# Cocos2d-x Example Projects for Android Studio

## Overview

The cocos2d-x repository at `~/GIT/cocos2d-x` contains pre-made example projects with full Android build support. Each project supports **two Android build systems**:

- **`proj.android/`** — Ant-based build (older, uses `Android.mk` + `Application.mk` + `build.xml`)
- **`proj.android-studio/`** — Gradle/Android Studio build (newer, uses `build.gradle` + `settings.gradle` + `app/` module)

---

## 1. TEMPLATES (Primary HelloWorld Examples)

These are the core project templates — the best starting point for a "Hello World" app.

### 1a. C++ Template — `cpp-template-default`
- **Location**: `cocos2d-x/templates/cpp-template-default/`
- **Language**: C++
- **Android Studio**: `proj.android-studio/` (full Gradle build)
- **App ID**: `org.cocos2dx.hellocpp`
- **Other platforms**: iOS, Mac, Linux, Windows (Win10/Win32/Win8.1)

### 1b. Lua Template — `lua-template-default`
- **Language**: Lua (with C++ runtime)
- **Android Studio**: `lua-template-default/frameworks/runtime-src/proj.android-studio/`
- **App ID**: `org.cocos2dx.hellolua`

### 1c. JavaScript Template — `js-template-default`
- **Language**: JavaScript (C++ runtime)
- **Android Studio**: `js-template-default/frameworks/runtime-src/proj.android-studio/`
- **App ID**: `org.cocos2dx.hellojavascript`

### 1d. JavaScript Runtime Template — `js-template-runtime`
- **Language**: JavaScript with full runtime (C++ bindings)
- **Android Studio**: `js-template-runtime/frameworks/runtime-src/proj.android-studio/`
- **App ID**: `org.cocos2dx.hellojavascript`

### 1e. Lua Runtime Template — `lua-template-runtime`
- **Language**: Lua with full runtime
- **Android Studio**: `lua-template-runtime/frameworks/runtime-src/proj.android-studio/`

---

## 2. TESTS / DEMO PROJECTS

Functional demo/test projects with full Android build support.

### 2a. C++ Empty Test — `cpp-empty-test`
- **Location**: `cocos2d-x/tests/cpp-empty-test/`
- **Language**: C++
- **Android Studio**: `proj.android-studio/`
- **App ID**: `org.cocos2dx.cpp_empty_test`
- **Description**: Minimal "Hello World" with scene setup

### 2b. C++ Tests (Comprehensive Demo) — `cpp-tests`
- **Location**: `cocos2d-x/tests/cpp-tests/`
- **Language**: C++
- **Android Studio**: `proj.android-studio/`
- **App ID**: `org.cocos2dx.cpp_tests`
- **Description**: 80+ test categories covering every cocos2d-x feature (Actions, Physics, UI, CocosStudio, Spine, Particle3D, Terrain, NavMesh, etc.)

### 2c. Performance Tests — `performance-tests`
- **Location**: `cocos2d-x/tests/performance-tests/`
- **Language**: C++
- **Android Studio**: `proj.android-studio/`

### 2d. Game Controller Test (C++) — `game-controller-test`
- **Location**: `cocos2d-x/tests/game-controller-test/`
- **Language**: C++
- **Android Studio**: `proj.android-studio/`

### 2e–h. JS/Lua Test Suites
- `tests/js-tests/` — JS test suite (App ID: `org.cocos2dx.js_tests`)
- `tests/lua-empty-test/` — Minimal Lua demo
- `tests/lua-game-controller-test/` — Lua game controller test
- `tests/lua-tests/` — Lua test suite

---

## 3. PLUGIN SAMPLES

### 3a. HelloPlugins (C++ Plugin Sample)
- **Location**: `cocos2d-x/plugin/samples/HelloPlugins/`
- **Language**: C++
- **Android (Ant only)**: `proj.android/` (no Gradle support)

### 3b. HelloPluginsLua (Lua Plugin Sample)
- **Location**: `cocos2d-x/plugin/samples/HelloPluginsLua/`
- **Language**: Lua
- **Android (Ant only)**: `frameworks/runtime-src/proj.android/`

---

## Summary Table

| Project | Language | `proj.android` (Ant) | `proj.android-studio` (Gradle) | Description |
|---|---|---|---|---|
| `templates/cpp-template-default` | C++ | Yes | **Yes** | C++ "Hello World" template |
| `templates/lua-template-default` | Lua | Yes | **Yes** | Lua "Hello World" template |
| `templates/js-template-default` | JS | Yes | **Yes** | JS "Hello World" template |
| `templates/js-template-runtime` | JS | Yes | **Yes** | JS full-runtime template |
| `templates/lua-template-runtime` | Lua | Yes | **Yes** | Lua full-runtime template |
| `tests/cpp-empty-test` | C++ | Yes | **Yes** | Minimal C++ demo |
| `tests/cpp-tests` | C++ | Yes | **Yes** | Comprehensive C++ feature demo (80+ tests) |
| `tests/performance-tests` | C++ | Yes | **Yes** | Performance benchmark |
| `tests/game-controller-test` | C++ | Yes | **Yes** | Game controller test |
| `tests/js-tests` | JS | Yes | **Yes** | JS test suite |
| `tests/lua-empty-test` | Lua | Yes | **Yes** | Minimal Lua demo |
| `tests/lua-game-controller-test` | Lua | Yes | **Yes** | Lua game controller test |
| `tests/lua-tests` | Lua | Yes | **Yes** | Lua test suite |
| `plugin/samples/HelloPlugins` | C++ | Yes | No | Plugin integration demo |
| `plugin/samples/HelloPluginsLua` | Lua | Yes | No | Plugin integration demo (Lua) |

**14 of 17 projects support Android Studio (Gradle) builds.**

---

## Recommended for Android Studio

For the simplest "click the green arrow" experience, use:

1. **`templates/cpp-template-default/proj.android-studio/`** — Clean C++ Hello World
2. **`tests/cpp-tests/proj.android-studio/`** — Full feature demo with 80+ tests

### How to open in Android Studio

```bash
# For the C++ Hello World template:
cocos2d-x/templates/cpp-template-default/proj.android-studio/

# For the comprehensive C++ tests:
cocos2d-x/tests/cpp-tests/proj.android-studio/
```

Open the `proj.android-studio/` directory as a project in Android Studio, select your Android Virtual Device (AVD), and click the green Run arrow.
