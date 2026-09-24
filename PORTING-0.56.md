# Porting hyprNStack to Hyprland 0.56.x

Upstream `zakk4223/hyprNStack` is pinned to **0.54.x** (last commit 2026-03-29, "0.54.x pins").
Host is **Hyprland 0.56.2-2** (Arch), headers at `/usr/include/hyprland/src`, exported; `pkg-config hyprland` -> 0.56.2.

`make all` against 0.56.2 fails with **29 errors across 6 clusters**. The fork exists to carry these.

## Build
```
make            # needs: pkg-config --cflags pixman-1 libdrm hyprland
```
Fork: https://github.com/hitcreate/hyprNStack  (branch `hyprland-0.56`)

## Error clusters

### C1 — fullscreen API moved out of CCompositor  (6 sites: 702,703,958,975,1038,1111)
`g_pCompositor->setWindowFullscreenInternal(PWINDOW, FSMODE_NONE)` no longer exists.
- 0.56: `Fullscreen::CFullscreenController` (`managers/fullscreen/FullscreenController.hpp`).
  - `setFullscreenMode(window, internal, client, layoutAware)`
  - `setWindowFullscreenModeInternal(window, mode, layoutAware)`
  - `setWindowFullscreenModeClient(window, mode, layoutAware)`
- `FSMODE_NONE` -> `Fullscreen::FSMODE_NONE` (`enum eFullscreenMode`, `FullscreenController.hpp:12`).
- Need the live controller accessor from CCompositor / global (confirm from source).

### C2 — ITarget::fullscreenMode removed  (702)
Mode now lives in `FullscreenHandler` / `FullscreenController::SFullscreenMode` (`{internal,client}`).
`target->fullscreenMode` -> `controller->getFullscreenModes(target)`.

### C3 — configStringToInt removed  (124,130,136,142,148)
Not in public headers. Likely replaced by `Config::` value/parse helpers
(`config/values/`, `config/shared/`). Confirm from source.

### C4 — g_pConfigManager gone  (52)
`config/ConfigManager.hpp` now opens `namespace Config {`. Global rename; find new accessor.

### C5 — CCompositor navigation helpers gone  (799,808,841)
`getWindowInDirection`, `getMonitorInDirection`, `warpCursorTo` are absent from `Compositor.hpp`
and the whole installed include tree. Need 0.56 replacement (layout/target navigation or
`g_pCompositor->vectorToWindow*`). Confirm from source.

### C6 — CVarList2 + layoutMsg signature  (848-855, hpp:91, 1068)
- `CVarList2` -> `Hyprutils::String::CVarList2` (qualify or `using`).
- `layoutMsg` covariant return type changed vs base `ITiledAlgorithm` — align signature.
- 1068: `std::string{...}` brace-init no longer matches ctors.

## Method
1. Fetch Hyprland v0.56.2 source; grep the real definitions for each cluster.
2. Patch cluster-by-cluster; rebuild.
3. Containment: load ONLY into an isolated/nested Hyprland instance (reuse the
   `smart-resize`/hypr-minimize isolated-test pattern, CHG-171/232). Never live first.
4. Trial: stage an immutable, content-addressed `.so`; activate it from Lua
   config on a **fresh compositor session** for one workspace only, after a
   nested startup test. Do not promise an instant hot-unload rollback.
5. Record CHG; register in CMDB; carry in `omarchy-custom` manifest; add a
   rebuild-check because every Hyprland bump breaks the .so.

## Runtime finding (not caught by the compiler)

The first "compiles clean" port still **SEGV'd the moment a window mapped**:
`applyWorkspaceLayoutOptions` dereferenced a null pointer from
`HyprlandAPI::getConfigValue(...)->getDataStaticPtr()`.

Cause: on 0.56, `addConfigValue`/`getConfigValue` are `[[deprecated]]` and **no
longer register plugin config values** — so `getConfigValue` returns nullptr.
`hyprctl getoption plugin:nstack:layout:*` said "no such option".

Fix: register every value with `addConfigValueV2(PHANDLE, SP<Config::Values::IValue>)`
(`CStringValue`/`CIntValue`/`CFloatValue`) kept in `globals.hpp`, and read via
`->value()`. Versions compile either way — only a runtime/containment test catches this.

Verified by `tests/containment.py` in a nested Hyprland instance (CONTAINMENT_PASS):
load, register, activate `nstack`, master+stack tiling, `setstackcount 3` -> 3 columns,
no crash, parent session untouched.

## INCIDENT-146: live update/unload crash and corrected procedure

During the first live trial (CHG-452) an agent ran `cp new.so loaded-path.so` and
then `hyprctl plugin unload loaded-path.so`. The live compositor crashed inside
`CPluginSystem::unloadPlugin -> dlsym/ld-linux`. Overwriting the in-use ELF path
is the leading mechanism; the coredump proves the crash occurred during unload,
not the precise loader failure. A safe-mode restart also crashed during
Aquamarine teardown. The trial rule and live plugin were removed; the current
desktop runs dwindle with no plugin loaded.

**Never replace a loaded plugin file. Never hot-swap versions in the user's
desktop.** Stage each build at a unique, content-addressed path with
`python3 scripts/stage_plugin.py nstackLayoutPlugin.so EXISTING_DIRECTORY`.
The script uses an atomic no-clobber link, verifies SHA-256, and refuses a
modified file at an existing hash path. A new version is selected in Lua config
for the *next compositor start*, not by unloading the old one in a live session.
Before any future live opt-in, run both nested tests:

```
python3 -m unittest discover -s tests -p 'test_stage_plugin.py'
python3 tests/containment.py nstackLayoutPlugin.so
python3 tests/upgrade_nested.py OLD.so NEW.so
```

`upgrade_nested.py` proves untouched-file unload with mapped windows and then
starts a second nested compositor from the new immutable path. It asserts a
fresh workspace 2 uses `nstack` while the global layout stays `dwindle`. It
does not claim that a hot-loaded plugin will change an already-created
workspace. See INCIDENT-146 in the shared incident register for impact and
the recovery evidence. No further live trial is authorised by these tests.
