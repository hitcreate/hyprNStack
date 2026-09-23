#include "globals.hpp"
#include <hyprland/src/config/ConfigManager.hpp>
#include <hyprland/src/desktop/DesktopTypes.hpp>
#include <hyprland/src/desktop/Workspace.hpp>
#include "nstackLayout.hpp"
#include <unistd.h>
#include <thread>
// Methods
inline std::unique_ptr<Layout::Tiled::CHyprNstackAlgorithm> g_pNstackLayout;

// Do NOT change this function.
APICALL EXPORT std::string PLUGIN_API_VERSION() {
    return HYPRLAND_API_VERSION;
}

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    PHANDLE = handle;

    g_pCfgOrientation       = makeShared<Config::Values::CStringValue>("plugin:nstack:layout:orientation", "Nstack layout orientation", std::string{"left"});
    g_pCfgNewOnTop          = makeShared<Config::Values::CIntValue>("plugin:nstack:layout:new_on_top", "New window on top", 0);
    g_pCfgNewIsMaster       = makeShared<Config::Values::CIntValue>("plugin:nstack:layout:new_is_master", "New window is master", 1);
    g_pCfgNoGapsWhenOnly    = makeShared<Config::Values::CIntValue>("plugin:nstack:layout:no_gaps_when_only", "No gaps when only one window", 0);
    g_pCfgSpecialScaleFactor = makeShared<Config::Values::CFloatValue>("plugin:nstack:layout:special_scale_factor", "Special workspace scale factor", 0.8f);
    g_pCfgInheritFullscreen = makeShared<Config::Values::CIntValue>("plugin:nstack:layout:inherit_fullscreen", "Inherit fullscreen", 1);
    g_pCfgStacks            = makeShared<Config::Values::CIntValue>("plugin:nstack:layout:stacks", "Number of stacks", 2);
    g_pCfgCenterSingleMaster = makeShared<Config::Values::CIntValue>("plugin:nstack:layout:center_single_master", "Center a single master", 0);
    g_pCfgMfact             = makeShared<Config::Values::CFloatValue>("plugin:nstack:layout:mfact", "Master factor", 0.5f);
    g_pCfgSingleMfact       = makeShared<Config::Values::CFloatValue>("plugin:nstack:layout:single_mfact", "Single master factor", 0.5f);
    HyprlandAPI::addConfigValueV2(PHANDLE, g_pCfgOrientation);
    HyprlandAPI::addConfigValueV2(PHANDLE, g_pCfgNewOnTop);
    HyprlandAPI::addConfigValueV2(PHANDLE, g_pCfgNewIsMaster);
    HyprlandAPI::addConfigValueV2(PHANDLE, g_pCfgNoGapsWhenOnly);
    HyprlandAPI::addConfigValueV2(PHANDLE, g_pCfgSpecialScaleFactor);
    HyprlandAPI::addConfigValueV2(PHANDLE, g_pCfgInheritFullscreen);
    HyprlandAPI::addConfigValueV2(PHANDLE, g_pCfgStacks);
    HyprlandAPI::addConfigValueV2(PHANDLE, g_pCfgCenterSingleMaster);
    HyprlandAPI::addConfigValueV2(PHANDLE, g_pCfgMfact);
    HyprlandAPI::addConfigValueV2(PHANDLE, g_pCfgSingleMfact);
    g_pNstackLayout  = std::make_unique<Layout::Tiled::CHyprNstackAlgorithm>();
	  if (!HyprlandAPI::addTiledAlgo(PHANDLE, "nStack", &typeid(Layout::Tiled::CHyprNstackAlgorithm), [] { return makeUnique<Layout::Tiled::CHyprNstackAlgorithm>(); })) {
			HyprlandAPI::addNotification(PHANDLE, "[hyprgollum] addTiledAlgo failed! Can't proceed.", CHyprColor{1.0, 0.2, 0.2, 1.0}, 5000);
    }
    HyprlandAPI::reloadConfig();

    return {"hyprNStack", "Plugin for column layout", "Zakk", "1.0"};
}

APICALL EXPORT void PLUGIN_EXIT() {
    HyprlandAPI::invokeHyprctlCommand("seterror", "disable");
}
