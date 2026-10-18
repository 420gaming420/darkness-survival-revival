# C Header Parser — Function-to-Source Mapping

## Functions with Matching Cocos2d-x Source Code

The Cocos2d-x engine source at `sources/cocos2d-x/` contains the implementation for ~80% of functions in `libcocos2dcpp.so`. Here are the confirmed mappings:

### 1. `EventDispatcher::dispatchCustomEvent`
- **Binary:** file offset `0x4ea584`, symbol `_ZN7cocos2d15EventDispatcher19dispatchCustomEventERKSsPv`
- **Header:** `sources/cocos2d-x/cocos/base/CCEventDispatcher.h:178`
  ```cpp
  void dispatchCustomEvent(const std::string &eventName, void *optionalUserData = nullptr);
  ```
- **Implementation:** `sources/cocos2d-x/cocos/base/CCEventDispatcher.cpp:932-937`
  ```cpp
  void EventDispatcher::dispatchCustomEvent(const std::string &eventName, void *optionalUserData) {
      EventCustom ev(eventName);
      ev.setUserData(optionalUserData);
      dispatchEvent(&ev);
  }
  ```
- **Full source:** Yes (header + .cpp)

### 2. `EventDispatcher::dispatchEvent(Event*)`
- **Header:** `sources/cocos2d-x/cocos/base/CCEventDispatcher.h:171`
- **Implementation:** `sources/cocos2d-x/cocos/base/CCEventDispatcher.cpp:891-927`
- **Full source:** Yes (header + .cpp)

### 3. `EventCustom` class
- **Header:** `sources/cocos2d-x/cocos/base/CCEventCustom.h` (entire file, 78 lines)
  ```cpp
  class CC_DLL EventCustom : public Event {
      EventCustom(const std::string& eventName);
      inline void setUserData(void* data) { _userData = data; };
      inline void* getUserData() const { return _userData; };
      inline const std::string& getEventName() const { return _eventName; };
  protected:
      void* _userData;
      std::string _eventName;
  };
  ```
- **Base class:** `sources/cocos2d-x/cocos/base/CCEvent.h` (107 lines)
- **Full source:** Yes (header + base .cpp impl)

### 4. `Application::run()` (Android)
- **Header:** `sources/cocos2d-x/cocos/platform/android/CCApplication-android.h:37`
- **Protocol:** `sources/cocos2d-x/cocos/platform/CCApplicationProtocol.h:82,104`
  ```cpp
  virtual bool applicationDidFinishLaunching() = 0;
  ```
- **Implementation:** `sources/cocos2d-x/cocos/platform/android/CCApplication-android.cpp:65-74`
  ```cpp
  int Application::run() {
      if (!applicationDidFinishLaunching()) return 0;
      return -1;
  }
  ```
- **Full source:** Yes (header + .cpp)

### 5. `Director::getInstance()` / `drawScene()`
- **Header:** `sources/cocos2d-x/cocos/base/CCDirector.h:132`
  ```cpp
  static Director* getInstance();
  ```
- **Implementation:** `sources/cocos2d-x/cocos/base/CCDirector.cpp:95-105, 259-331`
- **Full source:** Yes (header + .cpp)

### 6. JNI Entry Points (`JNI_OnLoad`, `cocos_android_app_init`, `nativeInit`)
- **Implementation:** `sources/cocos2d-x/cocos/platform/android/javaactivity-android.cpp`
  - `JNI_OnLoad` (line 53): sets JavaVM, calls `cocos_android_app_init()`
  - `cocos_android_app_init` (line 46, weak): user-defined, creates AppDelegate
  - `nativeInit` (line 62): creates GLViewImpl, calls `Application::getInstance()->run()` = game loop start
- **Reference:** `sources/cocos2d-x/tests/cpp-tests/proj.android/jni/main.cpp` (cpp-tests project)
- **Full source:** Yes (.cpp only, all inline)

## Functions WITHOUT Matching Cocos2d-x Source

These are game-specific classes defined in Darkness Survival's own C++ code:

| Function | File Offset | Notes |
|----------|-------------|-------|
| `UILayer::networking` | `0x3d15e4` | Inherits from `cocos2d::Layer` (header at `sources/cocos2d-x/cocos/2d/CCLayer.h`) |
| `UILayer::openConnectingServer` | `0x3d0418` | Game-specific UI logic |
| `UILayer::closeConnectingServer` | `0x3d04a0` | Game-specific UI logic |
| `Actor::addBuff` | `0x36f2f8` | Custom game class, no engine equivalent |
| `GameNet::connectGameServer` | `0x3e5e04` | Game-specific networking |
| `GameNet::getGameNetState` | `0x3d5d00` | Game-specific state machine |
| `GameNet::getNetworkStatus` | `0x3d5d04` | Game-specific status |
| `GameNet::getResult` | `0x3d5e98` | Game-specific result |

## Header Files Available for CParser

- **Total headers:** 3,458 `.h` files in `sources/cocos2d-x/`
- **Key engine headers** (resolve types like `EventDispatcher*`, `Director*`, `EventCustom*`):
  - `cocos/base/CCEventDispatcher.h`
  - `cocos/base/CCEvent.h`
  - `cocos/base/CCEventCustom.h`
  - `cocos/base/CCDirector.h`
  - `cocos/platform/android/javaactivity-android.cpp` (all JNI functions)
- **Cocos2d-x Android headers** (platform-specific types):
  - `cocos/platform/android/CCApplication-android.h`
  - `cocos/platform/android/CCStdC-android.h`
  - `cocos/platform/android/CCPlatformDefine-android.h`
  - `cocos/platform/android/jni/Java_org_cocos2dx_lib_Cocos2dxHelper.h`
  - `cocos/platform/android/jni/DPIJni.h`

## CParser Feature Summary

Ghidra's built-in C/C++ Header Parser (`ghidra.app.plugin.core.cparser`) can parse `.h` files and convert them into Ghidra Data Types:
- `struct`/`union` → `Composite` types (fields, bitfields, alignment)
- `enum` → `Enumeration` types
- `typedef` → type aliases
- Function signatures → `FunctionDefinitionDataType`

**API:** `CParserUtils.parseHeaderFiles()` — takes file list, include paths, defines, and a destination DataTypeManager. Returns `CParseResults` with success status and parse messages.

**Expected benefit for this project:** Resolving `undefined4*`, `undefined8*` to proper types like `cocos2d::EventDispatcher*`, `cocos2d::Director*` in decompiled output, making function signatures match the source code exactly.
