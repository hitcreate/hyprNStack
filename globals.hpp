#pragma once

#include <bit>
#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/config/values/types/StringValue.hpp>
#include <hyprland/src/config/values/types/IntValue.hpp>
#include <hyprland/src/config/values/types/FloatValue.hpp>

inline HANDLE PHANDLE = nullptr;

// Hyprland 0.56: Hyprlang::addConfigValue/getConfigValue are deprecated and no
// longer register plugin values (they read back nullptr -> SEGV). Register with
// addConfigValueV2 and keep the SP for reading via ->value().
inline SP<Config::Values::CStringValue> g_pCfgOrientation;
inline SP<Config::Values::CIntValue>    g_pCfgNewOnTop;
inline SP<Config::Values::CIntValue>    g_pCfgNewIsMaster;
inline SP<Config::Values::CIntValue>    g_pCfgNoGapsWhenOnly;
inline SP<Config::Values::CFloatValue>  g_pCfgSpecialScaleFactor;
inline SP<Config::Values::CIntValue>    g_pCfgInheritFullscreen;
inline SP<Config::Values::CIntValue>    g_pCfgStacks;
inline SP<Config::Values::CIntValue>    g_pCfgCenterSingleMaster;
inline SP<Config::Values::CFloatValue>  g_pCfgMfact;
inline SP<Config::Values::CFloatValue>  g_pCfgSingleMfact;
