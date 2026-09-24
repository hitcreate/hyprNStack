# hyprNStack

> **Hyprland 0.56 fork / INCIDENT-146:** Do not copy a new `.so` over a path
> already loaded by Hyprland, then unload it. That sequence crashed the live
> compositor. Build and stage with
> `python3 scripts/stage_plugin.py nstackLayoutPlugin.so EXISTING_DIRECTORY`;
> it gives each binary an immutable, SHA-256-addressed path. Test load and
> upgrade in disposable nested compositors (`tests/containment.py`,
> `tests/upgrade_nested.py`) before choosing a new path for the next login.
> This fork registers the lowercase `nstack` layout. For the Lua config on
> Hyprland 0.56, use `hl.plugin.load("/absolute/immutable/path.so")` and
> `hl.workspace_rule({workspace="2", layout="nstack"})`; leave global layout
> `dwindle`. Do not hot-swap a live plugin or claim an untested rollback.

This plugin is a modified version of Hyprland's Master layout. 

The primary change is that it allows an arbitrary number of non-master 'stacks'. This can be changed dynamically per-workspace.

The layout is sort of a combination of XMonad's 'MultiColumns' and Hyprland's Master layout.

# Configuration
Default values are meant to produce a similar experience to the existing Master layout.
```
plugin {
  nstack {
    layout {
      orientation=left
      new_on_top=0
      new_is_master=1
      no_gaps_when_only=0
      special_scale_factor=0.8
      inherit_fullscreen=1
      stacks=2
      center_single_master=0
      mfact=0.5
      single_mfact=0.5
    }
  }
}
```

### Configuration variable differences in comparison to Master Layout
*  `stacks` The number of *total* stacks, including the master.
*  `mfact` If this is set to 0 the master is the same size as the stacks. So if there is one master and 2 stacks they are all 1/3rd of the screen width(or height). Master and 3 stacks they are all 1/4th etc.
*  `single_mfact` The size of a single centered master window, when center_single_master is set.  
* `center_single_master` When there is a single window on the screen it is centered instead of taking up the entire monitor. This replaces the existing `always_center_master` and has slightly different behavior.

### Workspace layout options
All configuration variables are also usable as workspace rule layout options. Just prefix the setting name with 'nstack-'
`workspace=2,layoutopt:nstack-stacks:2,layoutopt:nstack-single_mfact:0.85`

# Dispatchers

Two new dispatchers
 * `resetsplits` Reset all the window splits to default sizes.
 * `setstackcount` Change the number of stacks for the current workspace. Windows will be re-tiled to fit the new stack count.

Two new-ish orientations
 * `orientationhcenter` Master is horizontally centered with stacks to the left and right. 
 * `orientationvcenter` Master is vertically centered with stacks on the top and bottom. 
 * `orientationcenter` An alias for `orientationhcenter`
 

# Installing

## Hyprland 0.56 / Omarchy Lua configuration (this fork)

Hyprland plugins must match the installed Hyprland version. The upstream
`hyprpm.toml` pins stop at 0.54; **do not install the upstream repository or
use its old `cp` + `exec-once` instructions for this 0.56 fork**.

1. Build against the installed headers: `make all` (check that
   `pkg-config --modversion hyprland` reports the version you are running).
2. Create a staging directory, then stage the binary there:
   ```sh
   mkdir -p "$HOME/.local/share/hyprNStack/builds"
   python3 scripts/stage_plugin.py nstackLayoutPlugin.so "$HOME/.local/share/hyprNStack/builds"
   ```
   The printed file path contains its SHA-256. A rebuild gets a *different*
   path; the script refuses to overwrite an existing one.
3. Run `tests/containment.py` and `tests/upgrade_nested.py` with the versioned
   binaries in disposable nested Hyprland instances. These tests never load a
   plugin into the parent compositor.
4. **Only after a separately approved live trial**, add the printed absolute
   path to the user's Hyprland Lua config for the *next compositor start*:
   ```lua
   hl.plugin.load("/absolute/path/to/nstackLayoutPlugin-<sha256>.so")
   hl.workspace_rule({ workspace = "2", layout = "nstack" })
   ```
   Keep the global layout `dwindle`. A future update means selecting a new
   immutable path at a later compositor start, not copying over the active
   path or hot-unloading the running layout.

# TODO
- [ ] Improve mouse resizing of stacks
- [X] Improve drag and drop rearranging of windows in and between stacks
- [X] Allow resizing of single master window
