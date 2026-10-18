# Cocos2d-x v3.9 Build Setup Summary

## Environment

- **OS:** Debian (trixie), Linux
- **Cocos2d-x version:** 3.9 (tag `cocos2d-x-3.9`, branch `restore`)
- **Python:** 2.7.18
- **CMake:** 3.31.6
- **g++:** 14.2.0
- **Target:** Android ARM32 EABI5 (`libcocos2dcpp.so`)
- **Output:** `HelloWorld/proj.android/obj/local/armeabi/libcocos2dcpp.so`

## Step-by-Step

### 1. Install system dependencies

All packages available in Debian trixie repos:

```bash
apt-get --yes install libglew-dev libglfw3-dev libxmu-dev libglu1-mesa-dev \
  libzip-dev libgtk-3-dev libgl2ps-dev
```

Already installed: `libx11-dev`, `libxi-dev`, `libssl-dev`, `libfreetype-dev`,
`libpng-dev`, `libcurl4-openssl-dev`, `libfontconfig-dev`, `libsqlite3-dev`.

### 2. Fix submodule URLs (git:// -> https://)

All submodules used `git://` (port 9418), which didn't work.
Updated each submodule URL to `https://` and checked out the commit recorded in HEAD:

```bash
git config submodule.plugin.url https://github.com/cocos2d-x/plugin-x.git
git config submodule.tools/cocos2d-console.url https://github.com/cocos2d/cocos2d-console.git
git config submodule.tools/bindings-generator.url https://github.com/cocos2d/bindings-generator.git
git config submodule."tests/cpp-tests/Resources/ccs-res".url https://github.com/dumganhar/ccs-res.git
git config submodule.web.url https://github.com/cocos2d/cocos2d-html5.git
git submodule update --init --force plugin
git submodule update --init --force tools/cocos2d-console
git submodule update --init --force tools/bindings-generator
git submodule update --init --force tests/cpp-tests/Resources/ccs-res
git submodule update --init --force web
```

Recorded commits (v3.9 HEAD):

| Submodule | Commit |
|---|---|
| `plugin` | `4b68a78` |
| `tools/cocos2d-console` | `5089eb3` |
| `tools/bindings-generator` | `2318a15` |
| `tests/cpp-tests/Resources/ccs-res` | `6361298` |
| `web` | `9f65531` |

### 3. Download external dependencies

```bash
python2 download-deps.py
```

Downloads `v3-deps-75.zip` (~119MB) and extracts prebuilt libraries into `external/`.

### 4. Install Android NDK

```bash
apt install google-android-ndk-r10e-installer
```

Installed to `/usr/lib/android-sdk/ndk/10.4`.

### 5. Install Android SDK (API 24)

Downloaded `android-24` (x86-24_r19) and placed in `~/Android/Sdk/platforms/android-24/`.

### 6. Run setup.py

```bash
python setup.py --ndkroot=/usr/lib/android-sdk/ndk/10.4 --androidsdkroot=~/Android/Sdk
```

**Note:** `setup.py` validates `ANDROID_SDK_ROOT` by checking for `tools/android` which was removed in SDK Tools r25 (2016). Created a stub at `~/Android/Sdk/tools/android` to pass the check.

Add the environment variables to `~/.bashrc` or .env:

```bash
export NDK_ROOT=/usr/lib/android-sdk/ndk/10.4
export ANDROID_SDK_ROOT=~/Android/Sdk
export COCOS_CONSOLE_ROOT=~/GIT/cocos2d-x/tools/cocos2d-console/bin
export COCOS_TEMPLATES_ROOT=~/GIT/cocos2d-x/templates
```

### 7. Create project and build

```bash
source ~/.bashrc
python ~/GIT/cocos2d-x/tools/cocos2d-console/bin/cocos.py \
  new HelloWorld -p com.hello.test -l cpp -d ~/GIT/Projects/coco-game
python ~/GIT/cocos2d-x/tools/cocos2d-console/bin/cocos.py \
  compile -p android -s ~/GIT/Projects/coco-game/HelloWorld -m release
```

### 8. Verify output

```bash
file HelloWorld/proj.android/obj/local/armeabi/libcocos2dcpp.so
```

```
ELF 32-bit LSB shared object, ARM, EABI5 version 1 (SYSV), dynamically linked,
interpreter /system/bin/linker, with debug_info, not stripped
```

## Key Gotchas

1. **Submodule URLs** — All used `git://` which is often blocked. Switched all to `https://`.
2. **`/usr/bin/python` missing** — System had only `python3` and `python` via pyenv. Used `python` explicitly.
3. **SDK validation** — `setup.py` checks for `tools/android` (deprecated since SDK Tools r25). Stub file created.
4. **NDK r10e is old** — Produces `armeabi` (v5TE ABI) not `armeabi-v7a`. This is expected for NDK r10e.
5. **`download-deps.py` EOFError** — Non-interactive mode can't answer "save zip file?" prompt. Harmless, deps already extracted.
