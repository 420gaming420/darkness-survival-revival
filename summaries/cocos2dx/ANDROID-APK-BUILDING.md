# Building and Deploying a Cocos2d-x Android APK for ARM Devices

This is a complete walkthrough of building a **cocos2d-x v3.9** Android APK from the `cpp-empty-test` Hello World project, deploying it to an Android tablet via ADB. It covers every step — from native compilation with NDK to Gradle packaging and installation.

---

## Architecture Overview

A Cocos2d-x Android app has two parts:

1. **Native C++ code** — the game engine + your game logic, compiled to a `.so` shared library (ARM32 `armeabi`)
2. **Java wrapper** — the Android activity that loads the `.so` and bridges Android ↔ native via JNI

The final APK bundles both together:
```
CppEmptyTest-debug.apk
├── lib/armeabi/libcpp_empty_test.so   ← your C++ game + engine
├── classes.dex                        ← Java bytecode (AppActivity)
├── assets/                            ← game resources (images, fonts, etc.)
├── res/                               ← Android UI resources (icons, themes)
└── AndroidManifest.xml                ← app metadata
```

---

## Prerequisites
First clone and cd to the game engine source code

```bash
git clone https://github.com/cocos2d/cocos2d-x.git
cd cocos2d-x

# Then switch to the cocos2d-x-3.9 tag (the same version our target game uses)
# Make a new branch off off the cocos2d-x-3.9 tag called "dev" or whatever name you want to give it and switch to the new branch.
```
### Required Dependencies
This is an old game engine so you need to install "legacy" ~2015 era versions of these tools.

- **ADB and the Android SDK**: installed at `~/Android/Sdk`, with API 10+ available.
The latest version of android studio SHOULD work fine as you can still install previous versions of the SDK/NDK in it.

- **NDK**: r10e or 10.4
- **Java**: JDK 8 (required — Gradle 2.4 does not support Java 9+)

You may need to add a 3rd party repository to your /etc/apt/sources.d/ in order to install these specific versions.

Read summaries/cocos2dx/COCOS-2D-SETUP.md for a full guide on dependency setup.

### Verify your setup

```bash
# Check NDK exists
ls /usr/lib/android-sdk/ndk/10.4/ndk-build

# Check SDK is available
ls ~/Android/Sdk/platforms/

# Check Java 8 is installed
/usr/lib/jvm/java-8-openjdk-amd64/bin/java -version

# Check ADB works (device connected)
adb devices
```

---

## Step 1: Build the native `.so` with NDK

The first step is compiling the C++ code into an ARM32 shared library using `ndk-build`:

```bash
/usr/lib/android-sdk/ndk/10.4/ndk-build \
  -C ~/GIT/cocos2d-x/tests/cpp-empty-test/proj.android \
  NDK_MODULE_PATH=~/GIT/cocos2d-x:~/GIT/cocos2d-x/cocos:~/GIT/cocos2d-x/external \
  NDK_TOOLCHAIN_VERSION=4.9
```

### What each argument does:

| Argument | Purpose |
|---|---|
| `-C <path>` | Change to the project directory before building (where `Android.mk` lives) |
| `NDK_MODULE_PATH=<paths>` | Colon-separated list of directories where NDK can find modules referenced by `$(call import-module,<name>)`. Must include: **repo root** (for `extensions/`, `cocos/`), **cocos/** (for engine modules), **external/** (for third-party libs) |
| `NDK_TOOLCHAIN_VERSION=4.9` | Use GCC 4.9 toolchain (required for this NDK version) |

### Why the `NDK_MODULE_PATH` is so specific

The path resolution is relative to each project's directory structure. The original command from a different workspace used relative paths like `../../../..` which resolved correctly there but **not** here. The key insight:

- `~/GIT/cocos2d-x` — the repo root, where `extensions/Android.mk` and `cocos/Android.mk` live
- `~/GIT/cocos2d-x/cocos` — where engine submodules are found via `import-module`
- `~/GIT/cocos2d-x/external` — third-party libraries

If you get errors like:
```
Cannot find module with tag 'extensions' in import path
```
It means one of those paths is wrong. Each `$(call import-module,<name>)` in any `Android.mk` will search each directory in `NDK_MODULE_PATH` for `<name>/Android.mk`.

### Output

The build produces:
```
proj.android/libs/armeabi/libcpp_empty_test.so
```

This is the ARM32 shared library containing your game logic, compiled on top of the full Cocos2d-x engine. The `armeabi` ABI means ARMv5TE (EABI5) — compatible with all ARM Android devices.

---

## Step 2: Set up the Gradle project structure

The `proj.android-studio/` directory contains the Gradle/Android Studio build system, but it needs a few files populated before it can build an APK.

### 2a. Copy the `.so` into the Gradle app module

Gradle expects native libraries in `app/libs/<abi>/`:

```bash
mkdir -p ~/GIT/cocos2d-x/tests/cpp-empty-test/proj.android-studio/app/libs/armeabi
cp ~/GIT/cocos2d-x/tests/cpp-empty-test/proj.android/libs/armeabi/libcpp_empty_test.so \
   ~/GIT/cocos2d-x/tests/cpp-empty-test/proj.android-studio/app/libs/armeabi/
```

The `app/build.gradle` has this line:
```groovy
jniLibs.srcDir "libs"
```
This tells Gradle to package everything under `app/libs/` into the APK's `lib/` directory.

### 2b. Copy game resources (assets)

The Cocos2d-x engine expects game assets at runtime in the app's **internal files** area, which is provided by the `assets/` directory in an APK:

```bash
mkdir -p ~/GIT/cocos2d-x/tests/cpp-empty-test/proj.android-studio/app/assets
cp -r ~/GIT/cocos2d-x/tests/cpp-empty-test/Resources/* \
      ~/GIT/cocos2d-x/tests/cpp-empty-test/proj.android-studio/app/assets/
```

The `app/build.gradle` has:
```groovy
assets.srcDir "assets"
```

### 2c. Create `local.properties` at the **project root** (NOT in app/)

Gradle needs to know where the Android SDK is. Create this file at the **project root** (`proj.android-studio/`), not inside `app/`:

```bash
echo "sdk.dir=~/Android/Sdk" > ~/GIT/cocos2d-x/tests/cpp-empty-test/proj.android-studio/local.properties
```

> **Common pitfall:** Putting `local.properties` inside `app/` won't work — Gradle looks for it at the project root. If you get:
> ```
> SDK location not found. Define location with sdk.dir in the local.properties file
> ```
> This is why.

---

## Step 3: Build the APK with Gradle

Now everything is in place. Use the Gradle wrapper (not system gradle) to build:

```bash
export JAVA_HOME=/opt/jdk8
cd ~/GIT/cocos2d-x/tests/cpp-empty-test/proj.android-studio
bash gradlew :CppEmptyTest:assembleDebug
```

### Why each part matters:

| Part | Reason |
|---|---|
| `export JAVA_HOME=/opt/jdk8` | Gradle 2.4 (bundled with this project) requires Java 8. The system default is Java 21, which gives: `Could not determine java version from '21.0.11'` |
| `bash gradlew` | The wrapper is a bash script. Running it with `python` causes a syntax error |
| `:CppEmptyTest:assembleDebug` | `:CppEmptyTest` is the app module name (from `settings.gradle`). `assembleDebug` builds an unsigned debug APK. Use `assembleRelease` for a release build |

### What Gradle does:

1. **Compiles Java sources** — `AppActivity.java` from `app/src/`
2. **Bundles Cocos2dx library** — the `:libcocos2dx` module (Java classes from `cocos/platform/android/java/src/`)
3. **Merges assets** — copies game resources from `app/assets/` into the APK
4. **Packages resources** — compiles `res/` (icons, themes, strings) into the APK
5. **Dexes Java code** — converts `.class` files to `.dex` bytecode
6. **Signs with debug key** — creates a debug signature (not needed for ADB sideload)
7. **Zipaligns** — optimizes the APK for memory efficiency

### Output

On success:
```
BUILD SUCCESSFUL
Total time: 15.064 secs
```

The APK is at:
```
app/build/outputs/apk/CppEmptyTest-debug.apk
```

---

## Step 4: Install and run on device

```bash
adb install -r ~/GIT/cocos2d-x/tests/cpp-empty-test/proj.android-studio/app/build/outputs/apk/CppEmptyTest-debug.apk
```

The `-r` flag replaces any existing installation. You should see:
```
Performing Streamed Install
Success
```

Then open **CppEmptyTest** from your device's app launcher. You'll see the Hello World scene — same as the Linux build, but running natively on ARM32 Android.

> **Note:** You may see "This app was made for an older version of Android" — tap OK to dismiss. It's harmless; the app still runs fine.

---

## Project file reference

Here's what each key file does:

| File | Role |
|---|---|
| `proj.android/jni/Android.mk` | NDK build config — lists C++ source files, includes paths, links static libs |
| `proj.android/jni/Application.mk` | NDK toolchain settings (C++11, rtti, ABI) |
| `proj.android-studio/app/build.gradle` | Gradle config — SDK version, source sets, dependencies |
| `proj.android-studio/settings.gradle` | Module references (`:CppEmptyTest`, `:libcocos2dx`) |
| `proj.android-studio/local.properties` | Android SDK path (project root) |
| `app/src/org/cocos2dx/cpp_empty_test/AppActivity.java` | Your app's entry point, extends `Cocos2dxActivity` |
| `app/AndroidManifest.xml` | App metadata — package name, permissions, activity config |
| `app/libs/armeabi/libcpp_empty_test.so` | Native library (you provide this from ndk-build) |
| `app/assets/` | Game resources packaged into APK |

---

## Comparison: Linux vs Android builds

| Aspect | Linux (x86_64) | Android (ARM32) |
|---|---|---|
| Build system | CMake + make | ndk-build + Gradle |
| Output format | Single ELF binary + Resources/ folder | APK with bundled `.so`, assets, Java bytecode |
| Native lib | `bin/cpp-empty-test/cpp-empty-test` (executable) | `app/libs/armeabi/libcpp_empty_test.so` (shared library) |
| Engine linking | Static (`libcocos2d.a`) linked into binary | Static libs built into APK via Gradle |
| Resources | Copied to `bin/cpp-empty-test/Resources/` by CMake post-build step | Copied to `app/assets/`, packaged into APK by Gradle |
| Entry point | `main()` → `Application::run()` | `AppActivity.onCreate()` → JNI → native init |
| Graphics | OpenGL via GLFW + GTK3 | OpenGL ES 2.0 via Android EGL |
| Audio | FMOD (prebuilt `.so`) + OpenAL | CocosDenshion (OpenSL ES) |

---

## Troubleshooting

### "Cannot find module with tag 'extensions' in import path"
Your `NDK_MODULE_PATH` doesn't include the repo root. Make sure the first path resolves to the directory containing `extensions/Android.mk`.

### "SDK location not found"
Put `local.properties` (with `sdk.dir=...`) at the **project root**, not inside `app/`.

### "Could not determine java version from '21.0.11'"
Gradle 2.4 doesn't support Java 9+. Set `JAVA_HOME=/opt/jdk8` before running gradlew.

### Gradle wrapper downloads forever
The wrapper downloads Gradle 2.4 from `services.gradle.org`. If your network is slow or blocking, you can pre-download it:
```bash
mkdir -p ~/.gradle/wrapper/dists/gradle-2.4-all/
# Place the downloaded gradle-2.4-all.zip in that directory
```

### "This app was made for an older version of Android" (on install)
Harmless warning on newer Android versions when the APK targets `minSdkVersion=10`. Tap OK to dismiss.

---

## Summary: Complete command sequence

```bash
# 1. Build native .so
/usr/lib/android-sdk/ndk/10.4/ndk-build \
  -C /path/to/cocos2d-x/tests/cpp-empty-test/proj.android \
  NDK_MODULE_PATH=/path/to/cocos2d-x:/path/to/cocos2d-x/cocos:/path/to/cocos2d-x/external \
  NDK_TOOLCHAIN_VERSION=4.9

# 2. Copy .so into Gradle structure
mkdir -p proj.android-studio/app/libs/armeabi
cp proj.android/libs/armeabi/libcpp_empty_test.so proj.android-studio/app/libs/armeabi/

# 3. Copy game resources
mkdir -p proj.android-studio/app/assets
cp -r ../../Resources/* proj.android-studio/app/assets/

# 4. Create project-level local.properties
echo "sdk.dir=~/Android/Sdk" > proj.android-studio/local.properties

# 5. Build APK
export JAVA_HOME=/opt/jdk8
cd proj.android-studio
bash gradlew :CppEmptyTest:assembleDebug

# 6. Install to device
adb install -r app/build/outputs/apk/CppEmptyTest-debug.apk
```
