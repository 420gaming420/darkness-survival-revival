# Offline Mode Patch — First Playtest Report

**Date:** 2026-07-01  
**Session:** Post-sendPacket-noop patch, first real gameplay run  
**Build:** Darkness_Survival.apk + hex patches A/B/C/D + sendPacket no-op (`d7d44e4`)

---

## TL;DR

The `sendPacket()` no-op patch (commit `d7d44e4`) worked. The infinite "Connecting to Server" loading screen is dead. I can launch, play the tutorial prologue, die, reach the main menu, and start a new game. But several game-over/post-game features are broken because they expect server responses: scoreboard freezes, Box of Memories is empty (never spawned), Ankh resurrection is bugged (instant death on use), and tapping an IAP coin option crashes with `IabHelper was disposed of`.

---

## What Worked 🎉

### Launch → Main Menu → Tutorial Prologue
- **"Connecting to Server" loading screen: GONE.** This was the #1 blocker. The `sendPacket()` no-op at `0x3d04c0` (`movs r0,#0 / bx lr`) replaced `push {r3,r4,r5,lr} / ldr r5,[pc,#8]` and now returns immediately. Combined with patches B/C/D (getGameNetState→2, getNetworkStatus→-1, getResult→1), the connection state machine completes without ever opening a TCP socket or showing the loading screen.
- **Tutorial prologue:** Played through all tutorial steps — movement, skip turn, inventory, combat, hunger, craft recipes, runes, Box of Memories (empty but navigable), new game prompt. Each step auto-advanced correctly.
- **Main menu:** After closing the empty Box of Memories popup, the actual main menu appeared with 5 buttons: Craft Recipes, Runes, Box of Memories, Achievements, Store. Main menu tutorial worked — hand animation pointing at each button, tap to advance.
- **Runes & Crafting tutorials:** Both work offline. All runes and crafting recipes are locked but accessible. No server dependency.
- **Slate of Illusion ad reward:** Found a "Slate of Illusion" (gameobj_statue_illusion / gameobj_sign01) mid-game. Tapped Yes on the ad prompt → message box closed instantly → received "Round Shield". The smali stubbing for Unity Ads (`isUnityAdsAvailable()` → true, `presentUnityAds()` → instant reward) works perfectly. Zero network traffic.
- **Progress persistence:** Die → exit → restart → title screen shows actual main menu (not the frozen game-over screen). Progress saved correctly.

### Unexpected Finds
- **10 Ancient Coins** — Coins never increment, permanently stuck at 10 coins.
- **538,976,288 Ankh (Resurrection) items** — this is... a lot. You normally get ~1 per week of regular gameplay. The player character instant-dies again when using one, and dies permanently on second use. Root cause TBD — possibly tied to the progress not getting a packet from the server, resulting in a garbage 0x20202020 value for the item.

---

## What's Broken 🐛

### 1. Game Over / Scoreboard Freeze (HIGH)
**Symptom:** After dying intentionally, the "Your Adventure Record" scoreboard appears showing:
- Level: 1
- Previous max reached: B2F / Reached: B1F
- Newly Identified Secrets (2%): Items, Creatures (Spider: 1 defeated), Dungeon Objects (Slate of Illusion)

Tapping anything does nothing. Android back-swipe does nothing. Must force-close the app and restart. On restart the main menu appears correctly.

**Hypothesis:** The scoreboard tries to send data to the server or waits for a server response that never comes. Possibly calls `sendPacket()` which now returns no-op, but something else (a timer callback or event listener) keeps calling `openConnectingServer` or blocks on a state change that never happens. Could also be related to the jumptable dispatcher in `networking()` — after game over, a packet type is set but the handler doesn't complete because it expects server confirmation.

**Likely code path:** Game over → `GameNet::prepareUpdateProgressInfo` or similar → `UILayer::sendPacket` (now no-op) → scoreboard UI shown → `networking()` keeps running each tick → some condition never becomes true → UI stays frozen.

### 2. Box of Memories is Empty (MEDIUM)
**Symptom:** "New runes are available" screen shows locked rune icons. "New craft recipes are available" shows locked item icons. Tapping anything does nothing. The X button closes it and proceeds to the main menu tutorials.

After returning to the main menu, the Box of Memories button exists but tapping it opens an "Open the Box of Memories" screen that is empty — no box to open.

**Hypothesis:** In the original game, you get a Box of Memories after each game over as a reward (similar to gacha/loot box). The box data comes from the server in a post-game packet. Since we never connect, `getProgressInfo()` parses an empty/default progress packet, so all runes and recipes show as "newly unlocked" but are actually locked. The Box of Memories is never spawned because the server would have included it in the response.

**Fix approach:** Either:
- Patch the scoreboard to spawn a default Box of Memories locally (find where the server sets `box_of_memories` flag in ProgressInfo, set it directly)
- Or patch the Box of Memories handler to show an empty/placeholder screen with "No memories yet" instead of freezing

### 3. Ankh Resurrection Bugged (MEDIUM)
**Symptom:** Player has 538,976,288 Ankh items. After dying, a message box appears: "Resurrect with Ankh or 600 Ancient Coins." Tapping the Ankh option causes the character to instantly die again without taking damage. Tapping Ankh again makes the character stay dead permanently.

**Hypothesis:** The Ankh resurrection works in two stages:
1. Player taps Ankh → `GameNet::prepareResurrection()` is called → packet sent to server
2. Server responds with "resurrected" state → player revived at full HP

Since `sendPacket()` is now a no-op, the server never receives the resurrection request and never sends back the revive state. The game thinks the Ankh was used (decremented from inventory? or not?) but the player never gets revived, so they stay dead. The 538,976,288 number is suspiciously close to `0x20202020` or similar — possibly an uninitialized/overflow value or a default "max uint32" value that's being used as the Ankh count when the server hasn't synced it yet.

**Likely code path:** Game over → `GameNet::prepareResurrection(gameNet, ankhCount, ...)` → `UILayer::sendPacket()` (no-op) → no response → player stays dead → tapping Ankh again calls `prepareResurrection` again → same result.

**Fix approach:** Patch the resurrection handler to skip the server round-trip and revive the player locally. Find the function that handles the "resurrected" response from the server, or find where the player HP is set on resurrection, and call it directly when the Ankh button is tapped.

### 4. IAP Crash (LOW)
**Symptom:** Tapping any ancient coins purchase option in the Store crashes with:
```
java.lang.IllegalStateException: IabHelper was disposed of, so it cannot be used.
    at com.zeroplusplus.common.google.IabHelper.checkNotDisposed(IabHelper.java:360)
    at ...IabHelper.launchPurchaseFlow(IabHelper.java:435)
    at ...GoogleIAPActivity.purchaseProductCall(GoogleIAPActivity.java:148)
```

**Hypothesis:** The `IabHelper` was initialized but disposed during the initial setup (since Play Services are offline). When the app tries to launch a purchase flow, `checkNotDisposed()` throws. This is expected behavior — we stubbed out all IAP init calls in `NativeWrapperActivity.smali`.

**Fix approach:** Patch `GoogleIAPActivity.purchaseProductCall` or `IabHelper.launchPurchaseFlow` to return immediately without calling `checkNotDisposed()`. Or add a stub that gives the player the coins directly. Low priority since this is a "cheat" feature.

### 5. Free Common Box (AD) Does Nothing (LOW)
**Symptom:** Tapping the free common box in the Store does nothing.

**Hypothesis:** The button calls `presentUnityAds()` which returns true and calls `onUnityAdsCompleted(0)` instantly, but something about the reward delivery expects a server confirmation or an item ID that's not set up correctly for offline mode.

---

## File Offsets & Key Addresses (for future patches)

| Function | Ghidra Addr | File Offset | Role |
|---|---|---|---|
| `UILayer::sendPacket` | 0x3d04c0 | 0x3c04c0 | **PATCHED** → no-op (commit d7d44e4) |
| `UILayer::openConnectingServer` | 0x3d0418 | 0x3c0418 | Shows loading screen overlay |
| `UILayer::networking` | 0x3d15e4 | 0x3c15e4 | Connection state machine (5 openConnectingServer calls) |
| `GameNet::prepareResurrection` | ~0x3e5xxx | ~0x3cxxxx | Build resurrection packet |
| `GameNet::getProgressInfo` | 0x3e5f38 | 0x3c4f38 | Parse progress from server packet |
| `GameNet::prepareUpdateProgressInfo` | ~0x3e6xxx | ~0x3cxxxx | Build post-game update packet |
| `GameNet::getPacketType` | 0x3e5e88 | 0x3c4e88 | Read packet type from [GameNet+0x200c] |
| Jumptable | 0x3d1694/0x3d1695 | 0x3c1694/0x3c1695 | Packet type → handler dispatch |

---

## Next Steps (in priority order)

1. **Game over scoreboard freeze** — find what's blocking the UI after game over. Likely needs a patch in the scoreboard handler or the post-game packet processing chain.
2. **Box of Memories** — either spawn a default box locally or make the "empty" state navigable. This is key to the post-game reward loop.
3. **Ankh resurrection** — find where server sends "resurrected" state and replicate it locally when player taps Ankh. Also investigate why Ankh count is 538,976,288 (likely `progress.ankh` field not initialized properly).
4. **IAP crash** — patch `GoogleIAPActivity.purchaseProductCall` to stub out the purchase flow. Low priority.
5. **Free common box** — make it deliver a default item instead of doing nothing.

---

## Notes on the Ankh Count

538,976,288 = `0x20202020` in hex. That's four copies of ASCII '0' (0x30)... wait, no — `0x20` is space. So it's `SP SP SP SP`. This looks like an uninitialized/zero-filled buffer being interpreted as a 32-bit integer, or possibly the result of `memset(ankh_ptr, 0x20, 4)` followed by a little-endian read. Could also be the default value for an unallocated memory slot that's been zeroed but then had each byte set to 0x20 (space character) by some initialization routine. Either way, it's clearly not a legitimate in-game count and points to the server not having synced this field yet.

---

## Session Recap

This was the first full gameplay session after applying all patches (A/B/C/D + sendPacket no-op). The game is now **playable from launch through one complete playthrough** — title screen → main menu → tutorial prologue → gameplay → death → scoreboard → main menu again. The core loop works. What's broken are the server-dependent features that expect a response after each action: post-game rewards, resurrection, IAP purchases, and loot boxes.

The good news: everything that doesn't require a server round-trip works perfectly. The remaining work is to make the server-dependent features either self-contained or stubbed to return sensible defaults.
