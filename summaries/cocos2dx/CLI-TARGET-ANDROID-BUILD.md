# CLI Target — Android APK with Random Greeting Game Logic

This covers building cli-target (a "random greeting" game) as both an x86 32-bit Linux binary and an ARM32 Android APK, then deploying it to a device to verify logcat output.

---

## Step 1: Install 32-bit development libraries

All packages needed for x86 (32-bit) Cocos2d-x builds:

```bash
apt install -y \
  libglew2.2:i386 libglew-dev:i386 \
  libglfw3:i386 libglfw3-dev:i386 \
  libxmu-dev:i386 libglu1-mesa-dev:i386 \
  libzip-dev:i386 libgl2ps-dev:i386 \
  libfreetype-dev:i386 libpng-dev:i386 libjpeg-dev:i386 libtiff-dev:i386 \
  libcurl4-openssl-dev:i386 libfontconfig1-dev:i386 \
  libwebp-dev:i386 libopenal-dev:i386 libvorbis-dev:i386 libmpg123-dev:i386 \
  libgtk-3-dev:i386 \
  libchipmunk-dev:i386
```

**Note:** `libev-dev:i386` and `libwebsockets-dev:i386` may conflict with existing packages. Fix with:
```bash
dpkg -i --force-overwrite /var/cache/apt/archives/libev-dev_1%3a4.33-2.1+b1_i386.deb /var/cache/apt/archives/libwebsockets-dev_4.3.5-1+deb13u1_i386.deb
```

---

## Step 2: Create cli-target project structure

The project lives at `tests/cli-target/` alongside the existing cpp-empty-test and cli-test projects.

### Directory layout:
```
tests/cli-target/
├── Classes/
│   ├── AppDelegate.h        # Header with AppDelegate class
│   ├── AppDelegate.cpp      # Game logic (random greetings)
│   └── AppMacros.h          # Design resolution config
├── Resources/               # (empty, no resources needed for CLI)
├── proj.linux/
│   └── main.cpp             # Entry point: calls Application::run()
├── proj.android-studio/     # Copied from cpp-empty-test, modified below
│   ├── app/
│   │   ├── AndroidManifest.xml
│   │   ├── build.gradle
│   │   ├── settings.gradle (parent)
│   │   ├── src/org/cocos2dx/cli_target/AppActivity.java
│   │   └── jni/
│   │       ├── Android.mk
│   │       └── Application.mk
│   ├── build.gradle
│   ├── settings.gradle
│   ├── local.properties
│   └── gradlew (wrapper)
├── CMakeLists.txt           # Copied from cpp-empty-test, APP_NAME changed
└── build_x86/               # Build output directory (x86 32-bit)
```

### Key source files:

**`Classes/AppDelegate.h`** — Minimal header with AppDelegate extending `cocos2d::Application`:
```cpp
class AppDelegate : private cocos2d::Application {
public:
    AppDelegate();
    virtual ~AppDelegate();
    virtual void initGLContextAttrs();
    virtual bool applicationDidFinishLaunching();
    virtual void applicationDidEnterBackground();
    virtual void applicationWillEnterForeground();
};
```

**`Classes/AppDelegate.cpp` — Game logic with conditional `__android_log_print`/`printf` for both Android logcat and Linux terminal output:
- Conditionally includes `<android/log.h>` only on `__ANDROID__`, defines LOGI/LOGD macros that map to `__android_log_print()` on Android and `printf()` on Linux
- Contains an array of 10 greeting strings (Hello!, Hi there!, Howdy!, Salutations!, etc.)
- Uses `srand(time(nullptr))` + `rand() % max`) for random selection
- Registers a scheduler callback that prints greetings each frame
- Calls `Director::getInstance()->end()` after 15 frames to exit cleanly
- Each LOGI call is paired with an equivalent `printf()` so the same output appears in both Android logcat and Linux terminal

**`proj.linux/main.cpp`** — Standard Cocos2d-x entry point:
```cpp
int main(int argc, char **argv) {
    AppDelegate app;
    return Application::getInstance()->run();
}
```

---

## Step 3: Configure proj.android-studio (Android build)

### AndroidManifest.xml changes:
```xml
<!-- Package name -->
package="org.cocos2dx.cli_target"

<!-- Library name (MUST match the .so filename without lib/ prefix) -->
<meta-data android:name="android.app.lib_name"
           android:value="cli_target" />
```

### build.gradle changes:
```groovy
defaultConfig {
    applicationId "org.cocos2dx.cli_target"
}
```

### settings.gradle changes:
```groovy
include ':CliTarget'
project(':CliTarget').projectDir = new File(settingsDir, 'app')
```

### jni/Android.mk changes:
```makefile
LOCAL_MODULE := cli_target_shared
LOCAL_MODULE_FILENAME := libcli_target
LOCAL_SRC_FILES := main.cpp ../../../Classes/AppDelegate.cpp
# Note: NO HelloWorldScene.cpp — only AppDelegate.cpp
```

### Java source files:
- Must be at `app/src/org/cocos2dx/cli_target/AppActivity.java` (NOT cpp_empty_test/)
- Package declaration must be `package org.cocos2dx.cli_target;`
- **CRITICAL MISTAKE:** If you copy from cpp-empty-test, the Java file will be in `org/cocos2dx/cpp_empty_test/` with package `org.cocos2dx.cpp_empty_test` — this causes `ClassNotFoundException: Didn't find class "org.cocos2dx.cli_target.AppActivity"` at runtime

### local.properties (at proj.android-studio/ root, NOT inside app/):
```
sdk.dir=~/Android/Sdk
```

---

## Step 4: Add to root CMakeLists.txt

In `/sources/cocos2d-x/CMakeLists.txt`, add the subdirectory under `BUILD_CPP_TESTS`:
```cmake
add_subdirectory(tests/cli-target)
```

---

## Step 5: Build x86 (32-bit for local testing)

The key difference from the standard 64-bit build is passing `-m32` to all compiler/linker flags, adding `-Wl,-m,elf_i386` to force the linker to use 32-bit libraries, AND setting `ARCH_DIR="32-bit`) so Cocos2d-x finds the right FMOD prebuilt:

```bash
cd ~/GIT/darkness-survival-revival/sources/cocos2d-x
rm -rf CMakeCache.txt CMakeFiles build_x86
mkdir build_x86 && cd build_x86
cmake .. \
  -DCMAKE_C_FLAGS="-m32" \
  -DCMAKE_CXX_FLAGS="-m32" \
  -DCMAKE_EXE_LINKER_FLAGS="-m32 -Wl,-m,elf_i386" \
  -DARCH_DIR="32-bit"
make cli-target -j$(nproc)
```

**Why `ARCH_DIR="32-bit"`**: Cocos2d-x's `CocosUsePrebuiltLibs.cmake` uses `${ARCH_DIR}` to find prebuilt libraries (e.g., FMOD). The 64-bit path is `external/linux-specific/fmod/prebuilt/64-bit/libfmodex64.so` but the 32-bit path is `external/linux-specific/fmod/prebuilt/32-bit/libfmodex.so`. Without this flag, CMake finds the wrong (64-bit) FMOD library and linking fails with `cannot find -lfmodex64`.

**Why `-Wl,-m,elf_i386`**: On Debian/Ubuntu systems with both 32-bit and 64-bit libraries installed (via `:i386`) packages, the linker will pick 64-bit libraries by default even when `-m32` is passed to the compiler. The `-Wl,-m,elf_i386` flag tells the linker to prefer 32-bit ELF objects, ensuring all linked libraries are actually 32-bit. Without it, you get a 64-bit binary that happened to be compiled with `-m32` flags but links against 64-bit system libs (GL, GLEW, glfw, etc.).

**Output**: `build_x86/bin/cli-target/cli-target` — ELF 32-bit LSB pie executable, Intel i386.

### Test locally:
```bash
cd build_x86/bin/cli-target
timeout 10 ./cli-target
```
Expected output: Prints greeting each frame, exits after 15 frames.

---

## Step 6: Build ARM32 .so for Android

Use ndk-build directly (not Gradle) to produce the `.so` file:

```bash
/usr/lib/android-sdk/ndk/10.4/ndk-build \
  -C ~/GIT/darkness-survival-revival/sources/cocos2d-x/tests/cli-target/proj.android-studio/app/jni \
  NDK_MODULE_PATH=~/GIT/darkness-survival-revival/sources/cocos2d-x:~/GIT/darkness-survival-revival/sources/cocos2d-x/cocos:~/GIT/darkness-survival-revival/sources/cocos2d-x/external \
  NDK_TOOLCHAIN_VERSION=4.9
```

**Output**: `proj.android-studio/app/libs/armeabi/libcli_target.so` — ELF 32-bit LSB shared object, ARM, EABI5 version 1 (SYSV), dynamically linked.

---

## Step 7: Build and install APK

### Copy the .so into Gradle's libs folder:
```bash
mkdir -p proj.android-studio/app/libs/armeabi
cp proj.android-studio/app/libs/armeabi/libcli_target.so proj.android-studio/app/libs/armeabi/
```

### Copy assets (if any):
```bash
mkdir -p proj.android-studio/app/assets
cp -r ../../Resources/* proj.android-studio/app.assets/ 2>/dev/null
```

### Build APK:
```bash
export JAVA_HOME=/opt/jdk8
cd proj.android-studio
bash gradlew :CliTarget:assembleDebug
```

**Output**: `app/build/outputs/apk/CliTarget-debug.apk`

### Install and test on device:
```bash
adb uninstall org.cocos2dx.cli_target
adb install -r app/build/outputs/apk/CliTarget-debug.apk
adb logcat -c
adb shell am start -n org.cocos2dx.cli_target/.AppActivity
sleep 6
adb logcat -d | grep "CliTarget"
```

**Expected output** (each run produces different greetings):
```
I CliTarget: === Random Greeting Game ===
I CliTarget: Engine: cocos2d-x v3.9
I CliTarget: Greeting #10: What's up!
I CliTarget: ===========================
I CliTarget: FRAME 1 | Greeting: Welcome!
I CliTarget: FRAME 2 | Greeting: Hello!
...
I CliTarget: === GAME COMPLETE ===
I CliTarget: Total runs: 12
```

---

## Mistakes Made Along the Way (Don't Repeat)

### 1. Wrong Java package / ClassNotFoundException
**Symptom**: `java.lang.ClassNotFoundException: Didn't find class "org.cocos2dx.cli_target.AppActivity"`

**Cause**: Copied proj.android-studio from cpp-empty-test but only changed manifest/package name. The Java source file stayed at `src/org/cocos2dx/cpp_empty_test/AppActivity.java` with package `org.cocos2dx.cpp_empty_test`.

**Fix**: Move the Java file to `src/org/cocos2dx/cli_target/` AND change its package declaration:
```bash
mkdir -p src/org/cocos2dx/cli_target
mv src/org/cocos2dx/cpp_empty_test/* src/org/cocos2dx/cli_target/
rmdir src/org/cocos2dx/cpp_empty_test
sed -i 's/package org.cocos2dx.cpp_empty_test;/package org.cocos2dx.cli_target;/' src/org/cocos2dx/cli_target/AppActivity.java
```

### 2. Wrong library name in AndroidManifest.xml
**Symptom**: `couldn't find "libcpp_empty_test.so"` at runtime (UnsatisfiedLinkError)

**Cause**: Cocos2d-x's `Cocos2dxActivity.onLoadNativeLibraries()` reads `android.app.lib_name` from `<meta-data>` and calls `System.loadLibrary(libName)`. The manifest still had `android:value="cpp_empty_test"`.

**Fix**: Change to `android:value="cli_target"` in AndroidManifest.xml. This must match the `.so` filename: `libcli_target.so` → `cli_target`.

### 3. Missing __android_log_print for logcat output
**Symptom**: App runs but nothing appears in logcat (only printf goes to stdout, not logcat on Android)

**Cause**: Used only `printf()` which outputs to the process's stdout, not Android's log system. On Android, native code must use `__android_log_print()` to appear in `adb logcat`.

**Fix**: Include `<android/log.h>` and define LOGI/LOGD macros:
```cpp
#include <android/log.h>
#define LOG_TAG "CliTarget"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
```
Use `LOGI()` for Android logcat AND keep `printf()` as a fallback for Linux testing.

### 4. Wrong schedule() signature
**Symptom**: Compile error about argument count mismatch

**Cause**: Used wrong overload of `Scheduler::schedule()`. The `ccSchedulerFunc` typedef is `std::function<void(float)>` (just `dt`, no `void* userData`). The correct 5-arg signature is `(callback, target, interval, paused, key)`.

**Fix**:
```cpp
director->getScheduler()->schedule(
    [this](float dt) { ... },  // No void* parameter
    this,                       // Non-null target (nullptr fails assertion)
    0.0f,
    false,
    "greetingLoop"
);
```

### 5. FMOD library mismatch with -m32
**Symptom**: `cannot find -lfmodex64: No such file or directory` when building with `-m32`

**Cause**: Cocos2d-x's `CocosUsePrebuiltLibs.cmake` uses `ARCH_DIR` to find prebuilt libraries. Default is `"64-bit"` which points to `libfmodex64.so`. With `-m32`, we need the 32-bit path (`libfmodex.so`).

**Fix**: Pass `-DARCH_DIR="32-bit"` to cmake configuration.

### 6. Forgetting about CMake cache
**Symptom**: Old cached values persist (wrong FMOD library, wrong ARCH_DIR)

**Cause**: CMake caches `FMODEX_LIBRARIES`, `ARCH_DIR`, etc. from previous runs. Simply re-running cmake with different flags doesn't override cached values.

**Fix**: Always clean before rebuilding:
```bash
rm -rf CMakeCache.txt CMakeFiles build_x86
```

### 7. Using `nullptr` as scheduler target
**Symptom**: `Assert failed: Argument target must be non-nullptr`

**Cause**: The `ccSchedulerFunc` overload requires a non-null target pointer. Passing `nullptr` triggers an assertion in `CCScheduler::schedule()`.

**Fix**: Use `this` as the target instead of `nullptr`.

### 8. Building only .so without building full APK
**Symptom**: App crashes because Java layer can't find the `.so`

**Cause**: ndk-build produces only the `.so` file. The APK needs: the `.so` in `app/libs/armeabi/`, assets in `app/assets/`, local.properties, and all Java files properly configured. Gradle packages everything together.

**Fix**: After ndk-build, copy .so to libs/, ensure assets/ exists, set local.properties, then run gradlew.

### 9. `#include <android/log.h>` fails on Linux builds
**Symptom**: `fatal error: android/log.h: No such file or directory` when building cli-target with CMake on Linux.

**Cause**: `<android/log.h>` is part of the Android NDK, not available on Linux. The original code unconditionally includes it.

**Fix**: Wrap the include and LOGI/LOGD macro definitions in `#ifdef __ANDROID__`:
```cpp
#ifdef __ANDROID__
#include <android/log.h>
#define LOG_TAG "CliTarget"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#else
#define LOG_TAG "CliTarget"
#define LOGI(...) printf(__VA_ARGS__)
#endif
```
This allows the same source file to compile on both Android (using `__android_log_print`) and Linux (falling back to `printf`).

### 10. Linker produces 64-bit binary despite `-m32` compiler flags
**Symptom**: Binary reports as `ELF 64-bit LSB pie executable, x86-64` even though compiled with `-m32`. `ldd` shows all 64-bit system libraries.

**Cause**: The `-m32` flag tells the *compiler* to emit 32-bit object files (which it does), but the *linker* (`/usr/bin/c++`) searches the default library paths and finds matching 64-bit `.so` files (libGL.so.1, libGLEW.so.2.2, etc.). The `-m32` flag alone doesn't force the linker to prefer `:i386` libraries.

**Fix**: Add `-Wl,-m,elf_i386` to `CMAKE_EXE_LINKER_FLAGS`. This tells the linker to use the 32-bit ELF emulation (`elf_i386`) which forces it to only accept 32-bit objects and libraries:
```bash
-DCMAKE_EXE_LINKER_FLAGS="-m32 -Wl,-m,elf_i386"
```

### 11. CMake cache prevents clean rebuild
**Symptom**: After changing CMake flags (e.g., adding `-DARCH_DIR="32-bit"` or `-Wl,-m,elf_i386`), the old cached values persist and the build still fails or produces wrong output.

**Cause**: CMake caches `FMODEX_LIBRARIES`, `ARCH_DIR`, `CMAKE_C_FLAGS`, etc. in `CMakeCache.txt`. Simply re-running `cmake` with different flags doesn't override all cached values — especially directory-level caches like `tests/cli-test/CMakeFiles/` and `cocos/CMakeFiles/`.

**Fix**: Always clean everything before rebuilding:
```bash
rm -rf CMakeCache.txt CMakeFiles \
       cocos/CMakeFiles tests/cli-test/CMakeFiles tests/cli-target/CMakeFiles \
       bin/cli-test bin/cli-target build_x86
```

---

## Key Files Reference

| File | Path | Purpose |
|------|------|---------|
| AppDelegate.h | `tests/cli-target/Classes/AppDelegate.h` | Header with class declaration |
| AppDelegate.cpp | `tests/cli-target/Classes/AppDelegate.cpp` | Game logic (random greetings + logcat) |
| AppMacros.h | `tests/cli-target/Classes/AppMacros.h` | Design resolution config |
| main.cpp (Linux) | `tests/cli-target/proj.linux/main.cpp` | Entry point |
| AndroidManifest.xml | `tests/cli-target/proj.android-studio/app/AndroidManifest.xml` | Package name + lib_name metadata |
| build.gradle | `tests/cli-target/proj.android-studio/app/build.gradle` | Application ID |
| AppActivity.java | `tests/cli-target/proj.android-studio/app/src/org/cocos2dx/cli_target/AppActivity.java` | Java activity (extends Cocos2dxActivity) |
| Android.mk | `tests/cli-target/proj.android-studio/app/jni/Android.mk` | NDK build config |
| Application.mk | `tests/cli-target/proj.android-studio/app/jni/Application.mk` | NDK toolchain settings |
| CMakeLists.txt | `tests/cli-target/CMakeLists.txt` | CMake build config for Linux |

## Output Locations

| Build Type | Path |
|------------|------|
| x86 32-bit binary | `build_x86/bin/cli-target/cli-target` (from CMake build dir) |
| ARM32 .so | `tests/cli-target/proj.android-studio/app/libs/armeabi/libcli_target.so` |
| Android APK | `tests/cli-target/proj.android-studio/app/build/outputs/apk/CliTarget-debug.apk` |

> **Note**: The CMakeLists.txt uses `RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"` which places the binary at `build_x86/bin/cli-target/cli-target`, NOT in a root `bin/` directory. Running `file` on it should show `ELF 32-bit LSB pie executable, Intel i386`.
