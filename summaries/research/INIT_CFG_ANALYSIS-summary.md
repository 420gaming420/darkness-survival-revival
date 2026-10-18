# Darkness Survival — Init Flow & State Machine CFG Analysis

## 1. Initialization Chain (Depth -1)
*Entry points execute before the main loop starts.*

1.  **`cocos_android_app_init` (0x36cb64)**: JNI entry. Allocates `AppDelegate` singleton (`operator new(4)`).
2.  **`AppDelegate::applicationDidFinishLaunching` (0x3ed7b8)**:
    *   **IAP Setup**: Fires-and-forget calls to `UIStorePopup::requestIAPLocalPrices()` for 5 medal tiers.
    *   **Localization**: Loads `textdata_<lang>.dat`. Fallback to "en" if load fails. Sets `TextDataManager` language.
    *   **Framework Init**: Creates `GLViewImpl` (non-returning). Hides debug stats (`director[0xc5] = 0`).
    *   **Scene Setup**: Gets `GameScene` singleton, runs it via `Director::runWithScene()`.
3.  **`GameScene::getInstance()` (0x39bb20)**:
    *   On first call: Seeds RNG (`srand48(time(NULL))`) and loads sprite frames (`maptile1.plist`). Sets global init flag `DAT_00b5f818`.
4.  **`Director::runWithScene()` (0x4e4d38)**: Sets active scene to `GameScene`, enters infinite `mainLoop()`.
5.  **`nativeInit` (0x3eebb8)**: Called on OpenGL surface recreation. Re-initializes GL state if not already done; dispatches `event_renderer_recreated`.
6.  **`UILayer::openConnectingServer()` (0x3d0418)**: Creates/activates `UIConnectingServer` popup (z-order 10000) with a 10s timeout if not already visible (`this + 0x6b0 == 0`).

## 2. Game Loop Architecture (Depth 0–2)

### Core Loop (`mainLoop`, 0x4e6a9c, Depth 0)
*   **Normal Frame**: Calls `Director::drawScene()`.
*   **Cleanup**: Clears AutoreleasePool after draw.
*   **States**: Handles `PURGE` (exit) and `RESTART` states via flags at `this[0x14]` and `this[0x15]`.

### Frame Processing (`drawScene`, 0x4e6978, Depth 1)
1.  **Timing**: Calculates delta time.
2.  **Events**: Dispatches `PRE_UPDATE`/`POST_UPDATE`.
3.  **Scheduler Update**: **Critical Path**. Fires registered callbacks, specifically `UILayer::onTimer()` every ~3 seconds (drives networking).
4.  **Physics/Navigation** (`stepPhysicsAndNavigation`, Depth 2):
    *   Moves actors based on pending actions.
    *   Calls `GameRuntime::progressAct()`.
5.  **Rendering**: Clears buffers, renders scene, updates FOV, renders UI/HUD, swaps buffers.

### Turn Processing (`progressAct`, 0x397840)
*   **Guard**: Checks `isAnimating` flag (`this[0x1fc05]`) and `turn in progress` flag (`this[0x1fbf8]`).
*   **Actor Iteration**: Loops through all actors in turn order. Each actor calls its AI (`actor->ai()`).
    *   Tracks longest action duration for animation pacing.
    *   Breaks after player acts if `isNewCommandNeeded`.
*   **Post-Player Logic**:
    *   Clears pending command if new one needed.
    *   Calls `UILayer::animateTurnPass()` (triggers monster spawns on adjacent undiscovered tiles).
    *   Executes player's queued action (`player->act()`).
    *   Applies buffs if no action taken.
    *   Checks actor status (dead/alive); recursively calls `progressAct` if conditions changed.

## 3. Connection State Machine (`UILayer::networking`, 0x3d15e4)
*Called every ~3s via `onTimer`.*

### Patched Behavior (Patches A/B/C/D)
*   `getGameNetState()` always returns **2** (CONNECTING).
*   `getNetworkStatus()` always returns **-1** (0xff).
*   `getResult()` always returns **1** (SUCCESS).

### Execution Flow
1.  **UI Phase**: Always calls `openConnectingServer()` to ensure loading screen is visible (`state == 2` and status check logic).
2.  **Status Check**:
    *   Status `-1` is not disconnected (-5), so skips reconnection.
    *   Status `-1` satisfies timeout condition (`-3 < -1`), calls `openConnectingServer()` again.
3.  **Event Dispatch**: Always dispatches `__connection_fail` event to listeners.
4.  **Packet Dispatch**: Reads packet type from `GameNet + 0x200c`. Dispatches via jumptable (offsets 0x3d1694/0x3d1695).
    *   **Key Handlers**:
        *   **Login Response (Type 1)**: Calls `syncServerTime()` and `getProgressInfo()`.
        *   **Other Types**: Progress updates, combat results, etc.

### Data Parsing (`getProgressInfo`, 0x3e5f38)
*   Parses server packet to update `ProgressInfo` singleton:
    *   Static data: Max ground level, current floor, achievements (bitmask), unlocked items/recipes/runes.
    *   Dynamic arrays: Items, spells, etc.
    *   Saves data to disk immediately.

## 4. Menu & Tutorial Flow

### Entry Points (`UIMainmenu`)
*   **`continueGame()`**: Loads `GameData` from disk, initializes dungeon view, closes menu fade, enables search, starts tutorial (step 0).
*   **`newGame(classType)`**: Resets IDs, creates new player data, initializes dungeon, sends `prepareNewGame` packet to server.

### Tutorial System (`UITutorial`)
*   **Controller** (`startTutorial`, 0x3e9d08): Master state machine. Uses bitmask flags in `ProgressInfo` (`testTutorialStep`) to determine next step.
    *   **Auto-Detect (Step 0)**: Checks conditions sequentially (Welcome → Movement → Zoom → Skip Turn → Inventory → Items → Combat → Advanced).
    *   **Item-Based**: Triggers based on specific item types (potions, scrolls, seeds, etc.).
*   **Execution** (`startTutorialTypeSub`, 0x3eb9a0): Maps step ID to message text and highlights relevant UI elements (buttons, tiles).
*   **Progression** (`progressTutorial`, 0x3eaa24): Per-frame animation of tutorial panel. Advances steps based on frame counters or user interaction.
*   **Completion**: Final step (`0x800000`) shows "Are you ready?" and the START button.

### UI States & Popups
*   **Modals**: `UIMainmenuPopup`, `UIStorePopup`, `UIEnding`, `UIMessageBox`, etc.
*   **Interaction**: All popups use `touchEvent()` switch on Button ID (e.g., 5=Exit, 6=Menu/NewGame, 7=Save/Login).
*   **Ending**: `setEndingMenu` hides main buttons, shows credits button. `startEnding` creates `UIEnding` popup.

## 5. Key State Variables & Flags

| Variable/Offset | Type/Location | Purpose |
| :--- | :--- | :--- |
| `DAT_00b5f818` | Global | GameScene initialized flag. |
| `this[0x1fc05]` | GameRuntime | `isAnimating`: Prevents overlapping turns. |
| `this[0x1fbf8]` | GameRuntime | `turn in progress` guard. |
| `this[0x6ac}` | UILayer | `GameNet*` pointer. |
| `this[0x6b0]` | UILayer | `UIConnectingServer*` popup pointer. |
| `this[0x26c]` | UITutorial | Current tutorial step ID (bitmask). |
| `progress.achievements` | ProgressInfo | 85-bit bitmask of completed achievements. |

## 6. Summary of Critical Paths

1.  **Startup**: `cocos_android_app_init` → `AppDelegate::init` → `GameScene::getInstance` → `Director::runWithScene` → `mainLoop`.
2.  **Networking Loop**: `mainLoop` → `drawScene` → `Scheduler::update` → `UILayer::onTimer` → `networking` → `openConnectingServer` + Packet Dispatch.
3.  **Game Start**: `networking` (Login) → `syncServerTime`/`getProgressInfo` → `UIMainmenu::continueGame`/`newGame` → `initializeDungeonView` → `startTutorial(0)`.
4.  **Tutorial Progression**: `startTutorial` checks `ProgressInfo` bitmasks → `startTutorialTypeSub` shows UI → `progressTutorial` animates/advances → repeats until all steps complete.
5.  **Gameplay Tick**: `progressAct` iterates actors → each calls AI → player acts → spawns monsters → updates FOV → repeats.

## 7. Unresolved Areas
*   Full mapping of the packet type jumptable at `0x3d1694/0x3d1695` (only Login/Progress/Combat types are confirmed).
