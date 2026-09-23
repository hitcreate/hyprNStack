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
4. Trial: enable on ONE workspace via `layoutopt:nstack-*`, instant rollback.
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
load, register, activate `nStack`, master+stack tiling, `setstackcount 3` -> 3 columns,
no crash, parent session untouched.
