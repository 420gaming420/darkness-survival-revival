# cpp-tests Build Document

## What is cpp-tests?

`cpp-tests` is the comprehensive C++ test/demo project bundled with cocos2d-x. It contains **70+ test scenes** covering every feature of the engine:

- **Physics**: Box2D testbed, Chipmunk, 3D Physics, Physics3D
- **UI Controls**: Buttons, sliders, page views, list views, edit boxes, web views, video players
- **3D**: Sprite3D, terrain, navmesh, lighting, materials, skinning, toon shaders, cube maps
- **Animations**: Spine skeletal animation (spineboy), CocosStudio timeline, armature, particle 3D
- **Tile Maps**: Isometric, orthogonal, hexagonal with collision and scrolling
- **Draw Primitives**: Shapes, lines, meshes, render textures
- **Audio**: Background music, sound effects, audio engine
- **Network**: HTTP client, WebSocket, Socket.IO
- **Effects**: Post-processing, bloom, blur, edge detection, cel shading
- **And 40+ more categories**

It is the most feature-rich sample in the entire cocos2d-x repository.

## Project Structure

```
cocos2d-x/tests/cpp-tests/
├── Classes/                    # C++ source code (AppDelegate, test scenes)
├── Resources/                  # Game assets (images, audio, tilemaps, shaders, 3D models)
├── proj.android/               # Ant-based Android build (older, uses Android.mk)
├── proj.android-studio/        # Gradle/Android Studio build
│   ├── app/                    # Main app module (jni/, assets/, Java wrappers)
│   ├── libcocos2dx/            # cocos2d-x Android library module
│   ├── build.gradle            # Top-level Gradle config (AGP version)
│   ├── settings.gradle         # Module references
│   └── gradle/wrapper/         # Gradle wrapper (2.4)
├── proj.ios_mac/               # Xcode projects
├── proj.win32/                 # Visual Studio project
├── proj.linux/                 # CMake-based Linux build
├── CMakeLists.txt              # Top-level CMake config
└── cocos2d/                    # (created by cocos.py, links to cocos2d-x root)
```

## Build Environment

| Component | Version | Path |
|---|---|---|
| Python | 2.7.18 (cocovenv) | `~/.pyenv/versions/cocovenv` |
| Python | 3.14.3 (projects) | `~/.pyenv/versions/3.14.3` |
| CMake | 3.31.6 | System |
| g++ | 14.2.0 | System (Debian trixie) |
| NDK | r10e (10.4) | `/usr/lib/android-sdk/ndk/10.4` |
| Android SDK | 28.0.2+12 | `~/Android/Sdk` |
| JDK | 8.0_472 | `/opt/jdk8/` |
| Gradle | 2.4 (wrapper) | `~/.gradle/wrapper/dists/gradle-2.4/` |
| AGP (Android Plugin) | 1.3.0 | In `build.gradle` |
| Gradle Wrapper | 2.4 | `gradle-wrapper.properties` |
| Java (system) | 21.0.11 | System default |

## Android Build (armeabi, API 10-22)

### Step 1: Initial `cocos.py` build attempt

**Command:**
```bash
cd builds/
python ~/GIT/cocos2d-x/tools/cocos2d-console/bin/cocos.py \
  compile -p android -s ~/GIT/cocos2d-x/tests/cpp-tests \
  -m release
```

**Why `cd builds/`**: The `builds/` directory contains `.python-version` with `cocovenv`, which activates the Python 2.7 venv required by `cocos.py`. Without it, Python 3 is used and `cocos.py` fails.

**Error 1 — Keystore prompt:**
```
Building apk...
Please input the absolute/relative path of '.keystore' file:
Traceback (most recent is last):
  ...
  ret = raw_input()
EOFError: EOF when reading a line
```
**Fix**: Added keystore config to `proj.android/ant.properties`:
```
key.store=~/.android/debug.keystore
key.alias=androiddebugkey
key.store.password=android
key.alias.password=android
```

**Error 2 — Ant build.xml not found:**
```
BUILD FAILED
~/Android/Sdk/tools/ant/build.xml not found
```
**Cause**: Android SDK Tools r25 (2016) removed ant support. The SDK only has a stub at `tools/android`.

**Error 3 — Missing `local.properties`:**
```
IOError: [Errno 2] No such file or directory:
  u'~/GIT/cocos2d-x/tests/cpp-tests/proj.android-studio/app/local.properties'
```
**Fix**: Created `local.properties` with `sdk.dir=~/Android/Sdk` in both `app/` and `libcocos2dx/` module directories.

### Step 2: Gradle build (successful)

**Command:**
```bash
export JAVA_HOME=/opt/jdk8
bash gradlew :CppTests:assembleRelease
```

**Working directory**: `cocos2d-x/tests/cpp-tests/proj.android-studio/`

**Why `JAVA_HOME=/opt/jdk8`**: Gradle 2.4 does not support Java 21. Java 8 is required.

**Why `bash gradlew`**: The `gradlew` script is a bash script, not Python. Running it with `python` causes a syntax error.

**Why `:CppTests:assembleRelease`**: The Gradle project uses custom module names (`:CppTests` for the app, `:libcocos2dx` for the library). `assembleRelease` builds the release APK.

**Result**: `app/build/outputs/apk/CppTests-release-unsigned.apk` (119 MB)

### Step 3: Sign the APK

**Command:**
```bash
jarsigner -verbose \
  -keystore ~/.android/debug.keystore \
  -storepass android -keypass android \
  -signedjar ~/GIT/Projects/coco-game/builds/CppTests-release.apk \
  ~/GIT/Projects/coco-game/builds/CppTests-release-unsigned.apk \
  androiddebugkey
```

**Why sign**: The unsigned APK fails to install with `INSTALL_PARSE_FAILED_NO_CERTIFICATES`. Android requires all APKs to be signed.

### Step 4: Install to device

**Command:**
```bash
adb install ~/GIT/Projects/coco-game/builds/CppTests-release.apk
```

**Result**: Successfully installed and running on Android 10 phone.

## Linux Build (x86_64, CMake)

### Step 1: Install dependencies

**Command:**
```bash
sudo apt install -y \
  cmake g++ make \
  libglew-dev libglfw3 libglfw3-dev \
  libxmu-dev libglu1-mesa-dev \
  libzip-dev libgl2ps-dev \
  libfreetype6 libfreetype6-dev \
  libpng-dev libjpeg-dev libtiff-dev \
  libcurl4-openssl-dev libfontconfig1-dev \
  libwebp-dev libwebsockets-dev \
  libopenal-dev libvorbis-dev libmpg123-dev \
  libgtk-3-dev
```

**Why each dependency:**
| Package | Used by |
|---|---|
| `cmake` | Build system |
| `g++`, `make` | C++ compiler and build tool |
| `libglew-dev`, `libglfw3-dev` | OpenGL context creation (Linux headless/server builds) |
| `libxmu-dev`, `libglu1-mesa-dev` | X11/GLU support for Linux desktop |
| `libzip-dev` | Zip file handling |
| `libgl2ps-dev` | PDF/PS rendering |
| `libfreetype6-dev` | Font rendering |
| `libpng-dev`, `libjpeg-dev`, `libtiff-dev` | Image format support |
| `libcurl4-openssl-dev` | HTTP requests (HttpClient, WebSocket) |
| `libfontconfig1-dev` | System font discovery |
| `libwebp-dev` | WebP image support |
| `libwebsockets-dev` | WebSocket support |
| `libopenal-dev` | 3D audio (CocosDenshion) |
| `libvorbis-dev`, `libmpg123-dev` | Audio codec support |
| `libgtk-3-dev` | X11/OpenGL on modern Linux desktop |

### Step 2: Create Linux build directory

**Command:**
```bash
mkdir -p ~/GIT/Projects/coco-game/builds/cpp-tests-linux
cd ~/GIT/Projects/coco-game/builds/cpp-tests-linux
```

### Step 3: Run CMake

**Command:**
```bash
cmake \
  -DCMAKE_BUILD_TYPE=Release \
  -DCOCOS2DX_test_SOURCE_DIR=~/GIT/cocos2d-x/tests/cpp-tests \
  -Dcocos2d_libs_SOURCE_DIR=~/GIT/cocos2d-x \
  -DCOCOS_X_PATH=~/GIT/cocos2d-x \
  -DCMAKE_PREFIX_PATH=/usr/lib/x86_64-linux-gnu \
  ~/GIT/cocos2d-x/tests/cpp-tests/proj.linux
```

**Why each flag:**
| Flag | Purpose |
|---|---|
| `-DCMAKE_BUILD_TYPE=Release` | Optimized build (no debug symbols, O2/O3 optimization) |
| `-DCOCOS2DX_test_SOURCE_DIR` | Points to the test project root (CMakeLists.txt expects this) |
| `-Dcocos2d_libs_SOURCE_DIR` | Points to the cocos2d-x engine root (where cocos2d library lives) |
| `-DCOCOS_X_PATH` | Points to the engine root for finding headers and resources |
| `-DCMAKE_PREFIX_PATH` | Helps CMake find system libraries in the Debian multiarch path |

### Step 4: Build

**Command:**
```bash
make -j$(nproc)
```

## Android Build (armeabi, release APK) ✅
- **Status**: COMPLETE — APK installed and running on Android 10 phone
- **Output**: `builds/CppTests-release.apk` (signed, 119 MB)
- **ABI**: `armeabi` (ARMv5TE, EABI5) — matches target device
- **Library**: `libcpp_tests.so` — extracted and verified as `ELF 32-bit LSB shared object, ARM, EABI5`
- **Test scenes**: 70+ all working
- **Known issue**: "This app was made for an older version" warning on install (harmless, tap OK to dismiss)

## Linux Build (x86_64) ✅
- **Status**: COMPLETE
- **Dependencies**: All installed via `apt`
- **CMake**: Configured and generated successfully
- **Build**: `make` completed without errors
- **Binary**: `CppTests` built and ready to run
- **Assets**: Copied to build directory for runtime access

## Errors Summary

| # | Error | Cause | Fix |
|---|---|---|---|
| 1 | `pyenv: python: command not found` | Running from wrong directory (not in cocovenv) | Copy `.python-version` to working dir or `cd` to `cocos2d-x/` |
| 2 | `EOFError: EOF when reading a line` | `cocos.py` prompts for keystore in non-interactive mode | Add keystore config to `ant.properties` |
| 3 | `Cannot find .../tools/ant/build.xml` | SDK Tools r25+ removed ant | Use Gradle (`--android-studio`) instead of Ant |
| 4 | `No such file or directory: local.properties` | `android update project` didn't create it | Manually create with `sdk.dir=...` |
| 5 | `Could not determine java version from '21.0.11'` | Gradle 2.4 doesn't support Java 21 | Set `JAVA_HOME=/opt/jdk8` |
| 6 | `SyntaxError: invalid syntax` on `gradlew` | Python tried to run bash script | Use `bash gradlew` instead |
| 7 | `INSTALL_PARSE_FAILED_NO_CERTIFICATES` | APK was unsigned | Sign with `jarsigner` |
| 8 | `Gradle 2.4 is not supported. Minimum is 4.6` | New Android Studio dropped old Gradle | Upgrade AGP to 2.3.0 and Gradle to 4.6 (in progress) |
| 9 | `Gradle version 2.2 is required. Current is 4.6` | AGP 1.3.0 is too old for Gradle 4.6 | Upgrade AGP from 1.3.0 to 2.3.0 |

## Key Files Modified

1. `cocos2d-x/tests/cpp-tests/proj.android/ant.properties` — Added keystore config
2. `cocos2d-x/tests/cpp-tests/proj.android-studio/app/local.properties` — Created with SDK path
3. `cocos2d-x/tests/cpp-tests/proj.android-studio/app/assets/` — Copied from Resources/
4. `cocos2d-x/tests/cpp-tests/proj.android-studio/libcocos2dx/local.properties` — Created with SDK path
5. `cocos2d-x/tests/cpp-tests/proj.android-studio/gradle/wrapper/gradle-wrapper.properties` — Restored to 2.4 after Android Studio upgraded to 4.6

## Key Files to Modify for Android Studio Sync

6. `cocos2d-x/tests/cpp-tests/proj.android-studio/build.gradle` — Change AGP from 1.3.0 to 2.3.0
7. `cocos2d-x/tests/cpp-tests/proj.android-studio/app/build.gradle` — Update compileSdkVersion to 28, buildToolsVersion to 28.0.3
8. `cocos2d-x/tests/cpp-tests/proj.android-studio/cocos/platform/android/libcocos2dx/build.gradle` — Same SDK updates
9. `cocos2d-x/tests/cpp-tests/proj.android-studio/gradle/wrapper/gradle-wrapper.properties` — Change to Gradle 4.6 or 6.5
