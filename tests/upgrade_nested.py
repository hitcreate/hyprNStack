#!/usr/bin/env python3
"""Exercise immutable plugin unload/reload in a disposable nested Hyprland.

The parent compositor is used only to start the nested window. Every plugin,
layout, and window operation targets the new instance signature explicitly.
"""

import json
import os
import pathlib
import shlex
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.stage_plugin import digest, stage  # noqa: E402


def command(args, env, ok=True):
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=20)
    if ok and result.returncode != 0:
        raise AssertionError((args, result.returncode, result.stdout, result.stderr))
    return result


def hypr(env, *args, ok=True):
    return command(["hyprctl", *args], env, ok=ok)


def json_query(env, key):
    return json.loads(hypr(env, "-j", key).stdout)


def wait_until(condition, seconds=20):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        value = condition()
        if value:
            return value
        time.sleep(0.15)
    raise AssertionError("nested Hyprland condition timed out")


def dispatch(env, expression):
    result = hypr(env, "dispatch", expression)
    assert result.stdout.strip() == "ok", result.stdout


def launch_window(env, number):
    before = len(json_query(env, "clients"))
    cmd = f"alacritty --class nstack-upgrade-test --title NSTACK-UPGRADE-{number} -e sleep 300"
    dispatch(env, "hl.dsp.exec_cmd(" + json.dumps(cmd) + ")")
    wait_until(lambda: len(json_query(env, "clients")) == before + 1)


def is_alive(parent, instance):
    return any(i["instance"] == instance for i in json_query(parent, "instances"))


def spawn_nested(parent, root, config, label):
    before = {i["instance"] for i in json_query(parent, "instances")}
    launch = (
        "env -u HYPRLAND_INSTANCE_SIGNATURE "
        f"XDG_STATE_HOME={shlex.quote(str(root / (label + '-state')))} "
        f"Hyprland -c {shlex.quote(str(config))} "
        f">{shlex.quote(str(root / (label + '-compositor.log')))} 2>&1"
    )
    dispatch(
        parent,
        "hl.dsp.exec_cmd("
        + json.dumps(launch)
        + ', {float=true,workspace="special:nstack-upgrade-test silent"})',
    )
    instance = wait_until(
        lambda: next(
            (i for i in json_query(parent, "instances") if i["instance"] not in before),
            None,
        )
    )
    assert instance["instance"] != parent["HYPRLAND_INSTANCE_SIGNATURE"]
    nested = dict(
        parent,
        HYPRLAND_INSTANCE_SIGNATURE=instance["instance"],
        WAYLAND_DISPLAY=instance["wl_socket"],
        XDG_STATE_HOME=str(root / (label + "-state")),
    )
    print("NESTED", label, instance["instance"], flush=True)
    return nested, instance


def main(old_source, new_source):
    parent = os.environ.copy()
    live_signature = parent.get("HYPRLAND_INSTANCE_SIGNATURE")
    assert live_signature, "must start from an active Hyprland session"
    assert hypr(parent, "plugin", "list").stdout.strip() == "no plugins loaded", (
        "parent has loaded plugins; stop"
    )

    root = pathlib.Path(tempfile.mkdtemp(prefix="nstack-upgrade-"))
    directory = root / "immutable"
    directory.mkdir()
    old = stage(old_source, directory)
    new = stage(new_source, directory)
    assert old != new, "two distinct builds are required to prove versioned paths"
    old_hash = digest(old)

    config = root / "config.lua"
    config.write_text(
        'hl.config({general={layout="dwindle"},animations={enabled=false}})\n'
        'hl.monitor({output="",mode="1280x720@60",position="auto",scale=1})\n'
    )
    original_clients = {c["address"] for c in json_query(parent, "clients")}
    nested, instance = spawn_nested(parent, root, config, "unload")

    try:
        assert hypr(nested, "plugin", "load", str(old)).stdout.strip() == "ok"
        assert is_alive(parent, instance["instance"])
        assert (
            hypr(
                nested, "eval", 'hl.workspace_rule({workspace="2",layout="nstack"})'
            ).stdout.strip()
            == "ok"
        )
        dispatch(nested, "hl.dsp.focus({workspace=2})")
        for n in range(3):
            launch_window(nested, n)
        assert (
            hypr(nested, "getoption", "general:layout").stdout.splitlines()[0]
            == "str: dwindle"
        )
        assert (
            hypr(nested, "dispatch", 'hl.dsp.layout("setstackcount 3")').stdout.strip()
            == "ok"
        ), "workspace 2 still uses dwindle"
        at_x = {c["at"][0] for c in json_query(nested, "clients")}
        assert len(at_x) == 3, at_x
        print("PASS workspace 2 uses nstack; global layout remains dwindle", flush=True)

        # This is the actual INCIDENT-146 boundary: unload with windows mapped,
        # but never alter the ELF file the dynamic loader still has open.
        result = hypr(nested, "plugin", "unload", str(old), ok=False)
        assert result.returncode == 0 and result.stdout.strip() == "ok", result.stdout
        assert is_alive(parent, instance["instance"]), (
            "nested compositor crashed on untouched-file unload"
        )
        assert digest(old) == old_hash, "loaded library was altered"
        assert hypr(nested, "plugin", "list").stdout.strip() == "no plugins loaded"
        assert len(json_query(nested, "clients")) == 3
        print("PASS untouched plugin unload with mapped windows", flush=True)

    finally:
        if is_alive(parent, instance["instance"]):
            hypr(nested, "dispatch", "hl.dsp.exit()", ok=False)
            wait_until(lambda: not is_alive(parent, instance["instance"]))
        assert hypr(parent, "plugin", "list").stdout.strip() == "no plugins loaded"

    # A new version belongs to a new compositor session. No same-session
    # hot-swap is part of the deployment procedure.
    next_config = root / "next-config.lua"
    next_config.write_text(
        'hl.config({general={layout="dwindle"},animations={enabled=false}})\n'
        'hl.monitor({output="",mode="1280x720@60",position="auto",scale=1})\n'
        + f"hl.plugin.load({json.dumps(str(new))})\n"
        + 'hl.workspace_rule({workspace="2",layout="nstack"})\n'
    )
    next_nested, next_instance = spawn_nested(parent, root, next_config, "startup")
    try:
        wait_until(lambda: "hyprNStack" in hypr(next_nested, "plugin", "list").stdout)
        assert not hypr(next_nested, "configerrors").stdout.strip()
        dispatch(next_nested, "hl.dsp.focus({workspace=2})")
        for n in range(3):
            launch_window(next_nested, n + 3)
        assert (
            hypr(next_nested, "getoption", "general:layout").stdout.splitlines()[0]
            == "str: dwindle"
        )
        result = hypr(
            next_nested, "dispatch", 'hl.dsp.layout("setstackcount 3")', ok=False
        )
        assert result.returncode == 0 and result.stdout.strip() == "ok", result.stdout
        assert len({c["at"][0] for c in json_query(next_nested, "clients")}) == 3
        assert digest(old) == old_hash
        print(
            "PASS fresh compositor starts new version on workspace 2 only", flush=True
        )
    finally:
        if is_alive(parent, next_instance["instance"]):
            hypr(next_nested, "dispatch", "hl.dsp.exit()", ok=False)
            wait_until(lambda: not is_alive(parent, next_instance["instance"]))
        assert hypr(parent, "plugin", "list").stdout.strip() == "no plugins loaded"
        assert original_clients.issubset(
            {c["address"] for c in json_query(parent, "clients")}
        )
        print("PASS parent unchanged", flush=True)

    print("NESTED_UPGRADE_PASS", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: upgrade_nested.py OLD.so NEW.so")
    main(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
