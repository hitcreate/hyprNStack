#!/usr/bin/env python3
"""Containment test: load the ported hyprNStack .so into a SECOND, nested Hyprland
instance only, and assert it works. Never targets the live/parent compositor.

Exits non-zero if any assertion fails or the nested instance crashes.
Modelled on ~/.local/state/hypr-minimize/native-test/test.py.
"""

import json, os, pathlib, subprocess, sys, tempfile, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.stage_plugin import stage  # noqa: E402

SO = (
    pathlib.Path(sys.argv[1]).resolve()
    if len(sys.argv) > 1
    else pathlib.Path(__file__).resolve().parents[1] / "nstackLayoutPlugin.so"
)
assert SO.exists(), f"missing plugin: {SO}"

OUT = pathlib.Path(tempfile.mkdtemp(prefix="nstack-containment-"))
SO = stage(SO, OUT)  # Never load the mutable build output directly.
LIVE = os.environ["HYPRLAND_INSTANCE_SIGNATURE"]
env = None
instance = None
failures = []


def cmd(*args, e=None):
    r = subprocess.run(args, env=e, capture_output=True, text=True, timeout=20)
    return r.returncode, r.stdout, r.stderr


def ctl(*args, e=None):
    rc, out, err = cmd("hyprctl", *args, e=e)
    assert rc == 0, (args, rc, out, err)
    return out


def q(name, e=None):
    return json.loads(ctl("-j", name, e=e))


def check(name, ok, details=None):
    print(("PASS " if ok else "FAIL ") + name, flush=True)
    if details:
        print("     " + str(details), flush=True)
    if not ok:
        failures.append(name)


def wait(fn, secs=20):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        r = fn()
        if r:
            return r
        time.sleep(0.15)
    raise AssertionError("condition timed out")


config = """hl.config({general={gaps_in=5,gaps_out=10,border_size=2,layout="nstack"},animations={enabled=false},misc={disable_hyprland_logo=true}})
hl.monitor({output="",mode="1280x720@60",position="auto",scale=1})
"""
(OUT / "config.lua").write_text(config)

before = {i["instance"] for i in json.loads(ctl("instances", "-j"))}
parent_before = q("clients")
launch = f"env -u HYPRLAND_INSTANCE_SIGNATURE XDG_STATE_HOME={OUT}/state Hyprland -c {OUT}/config.lua >{OUT}/compositor.log 2>&1"
ctl(
    "dispatch",
    "hl.dsp.exec_cmd("
    + json.dumps(launch)
    + ', {float=true,workspace="special:nstack-containment-test silent"})',
)
inst = wait(
    lambda: next(
        (i for i in json.loads(ctl("instances", "-j")) if i["instance"] not in before),
        None,
    )
)
assert inst["instance"] != LIVE, "refusing to test the parent compositor"
(OUT / "instance.json").write_text(json.dumps(inst))
print("ISOLATED_INSTANCE_STARTED", inst, flush=True)

env = dict(
    os.environ,
    HYPRLAND_INSTANCE_SIGNATURE=inst["instance"],
    WAYLAND_DISPLAY=inst["wl_socket"],
    XDG_STATE_HOME=str(OUT / "state"),
)
q2 = lambda n: q(n, e=env)
ctl2 = lambda *a: ctl(*a, e=env)


def dsp(code):
    out = ctl2("dispatch", code)
    assert "error" not in out.lower(), out
    time.sleep(0.2)


def lmsg(arg):
    """layoutmsg via the 0.56 Lua dispatcher. hyprctl wraps the arg in hl.dispatch(...)."""
    result = cmd(
        "hyprctl",
        "dispatch",
        "hl.dsp.layout(" + json.dumps(arg) + ")",
        e=env,
    )
    assert result[0] == 0 and result[1].strip() == "ok", result
    return result


def clients():
    return q2("clients")


def xy(c):
    a = c["at"]
    x, y = (a[0], a[1]) if isinstance(a, list) else (a["x"], a["y"])
    s = c["size"]
    w, h = (s[0], s[1]) if isinstance(s, list) else (s["width"], s["height"])
    return x, y, w, h


def launch_win(n):
    old = len(clients())
    dsp(
        "hl.dsp.exec_cmd("
        + json.dumps(f"alacritty --class nstack-test --title NSTACK-{n} -e sleep 900")
        + ")"
    )
    wait(lambda: len(clients()) == old + 1)


def alive():
    return any(
        i["instance"] == inst["instance"] for i in json.loads(ctl("instances", "-j"))
    )


def ncols():
    return len({xy(c)[0] for c in clients()})


try:
    load_out = ctl2("plugin", "load", str(SO))
    print("plugin load ->", load_out.strip(), flush=True)
    check("plugin load reported ok", "error" not in load_out.lower(), load_out.strip())
    time.sleep(0.5)
    plugins = ctl2("plugin", "list")
    print("plugin list ->", plugins.strip(), flush=True)
    check("plugin is listed", "nstack" in plugins.lower(), plugins.strip())
    check("nested instance alive after plugin load", alive())

    # plugin config values must register (the 0.56 V2 fix)
    opt = ctl2("getoption", "plugin:nstack:layout:stacks").strip()
    check("plugin config values registered", "no such option" not in opt.lower(), opt)
    print("plugin:nstack:layout:stacks ->", opt, flush=True)

    # activate layout
    ctl2("reload")
    time.sleep(0.5)
    if "nstack" not in ctl2("getoption", "general:layout").lower():
        ctl2("keyword", "general:layout", "nstack")
        time.sleep(0.3)
    print("layout ->", ctl2("getoption", "general:layout").strip(), flush=True)
    check("layout is nstack", "nstack" in ctl2("getoption", "general:layout").lower())
    check(
        "no config errors",
        ctl2("configerrors").strip() == "",
        ctl2("configerrors").strip(),
    )
    check("still alive after activation", alive())

    # two windows -> master + stack (two columns)
    dsp("hl.dsp.focus({workspace=1})")
    launch_win(0)
    launch_win(1)
    time.sleep(0.4)
    two = [(c["title"],) + xy(c) for c in clients()]
    check("two windows form master + stack (2 columns)", ncols() == 2, two)

    # dynamic dispatcher: setstackcount 3 -> three columns
    rc, out, err = lmsg("setstackcount 3")
    print(
        "setstackcount 3 rc=%s out=%r err=%r" % (rc, out.strip(), err.strip()),
        flush=True,
    )
    time.sleep(0.5)
    check("instance alive after setstackcount", alive())
    launch_win(2)
    time.sleep(0.5)
    check(
        "setstackcount 3 produces three columns",
        ncols() == 3,
        [(c["title"], xy(c)[0]) for c in clients()],
    )

    # back to 2
    lmsg("setstackcount 2")
    time.sleep(0.6)
    check(
        "setstackcount 2 produces two columns",
        ncols() == 2,
        [(c["title"], xy(c)[0]) for c in clients()],
    )

    lmsg("resetsplits")
    time.sleep(0.3)
    check("resetsplits accepted (alive)", alive())
    lmsg("orientationtop")
    time.sleep(0.4)
    check("orientationtop accepted (alive)", alive())

    log = (OUT / "compositor.log").read_text(errors="ignore")
    crashed = any(
        t in log
        for t in (
            "Segmentation fault",
            "SIGSEGV",
            "Assertion",
            "abort",
            "terminate called",
        )
    )
    check("no crash signatures in compositor log", not crashed)
    check(
        "no config errors at end",
        ctl2("configerrors").strip() == "",
        ctl2("configerrors").strip(),
    )

finally:
    try:
        for c in clients():
            dsp(
                "hl.dsp.window.close({window="
                + json.dumps("address:" + c["address"])
                + "})"
            )
        wait(lambda: not clients(), secs=10)
        dsp("hl.dsp.exit()")
        wait(
            lambda: all(
                i["instance"] != inst["instance"]
                for i in json.loads(ctl("instances", "-j"))
            ),
            secs=10,
        )
        check("nested instance exited cleanly", True)
    except Exception as ex:
        check("nested instance exited cleanly", False, ex)

    parent_now = q("clients")
    check(
        "parent window set unchanged",
        len(parent_now) == len(parent_before),
        f"before={len(parent_before)} after={len(parent_now)}",
    )

if failures:
    print(f"\nCONTAINMENT_FAIL: {len(failures)} failure(s): {failures}", flush=True)
    sys.exit(1)
print("\nCONTAINMENT_PASS", flush=True)
