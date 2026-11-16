# -*- coding: utf-8 -*-
"""Slot build: smoke path plus the frame window that belongs to it.

Run through Airtest so the run produces its own log:

    ./scripts/run_flow.sh com.example.slot          # run + recording + log.html

Airtest owns the taps and the screenshots, `device().shell()` owns the
measurement, and both land in the same log, so a frame window can be traced back
to the screen it was taken on. Configure with environment variables so the file
stays a plain Airtest script:

    SLOT_PACKAGE   package name under test      (default com.example.slot)
    SLOT_OUT       output directory             (default out)
    SMOKE_SOURCE   "gfxinfo" (View apps) or "sf" (GL games)   (default gfxinfo)
    SMOKE_LAYER    exact SurfaceFlinger layer for SMOKE_SOURCE=sf (default: found by package)
"""
__author__ = "Tran Trung Dung"
__title__ = "Slot build: smoke + measured frame window"
__desc__ = (
    "Launch, spin, result screen. One snapshot per checkpoint and one dumpsys gfxinfo "
    "read per scene, so the log shows which screen each frame window came from."
)

import os
import subprocess
import sys
from pathlib import Path

from airtest.core.api import (
    G, auto_setup, device, log, shell, sleep, snapshot, swipe, touch,
)

PACKAGE = os.environ.get("SLOT_PACKAGE", "com.example.slot")
SOURCE = os.environ.get("SMOKE_SOURCE", "gfxinfo")
LAYER = os.environ.get("SMOKE_LAYER", "")
SWIPES = int(os.environ.get("SMOKE_SWIPES", "0"))
# Absolute: `airtest run` does not keep the caller's working directory, so a relative
# path lands inside the log directory instead of the repo.
OUT = Path(os.environ.get("SLOT_OUT", "out")).resolve()
ROOT = Path(__file__).resolve().parent.parent

if not G.DEVICE_LIST:                      # allows `python flows/slot_smoke.py` too
    auto_setup(__file__)

OUT.mkdir(parents=True, exist_ok=True)
dev = device()


def find_layer() -> str:
    """Pick the compositor layer that belongs to the app under test.

    A GL game draws into a SurfaceView, and that is the layer whose frames are the ones a
    player sees; the activity layer underneath only draws chrome. Preference order is a
    BLAST SurfaceView, any SurfaceView, then the activity itself.
    """
    if LAYER:
        return LAYER
    listing = str(dev.shell("dumpsys SurfaceFlinger --list"))
    names = [line.strip() for line in listing.splitlines() if PACKAGE in line]
    for pick in (
        [n for n in names if n.startswith("SurfaceView[") and "(BLAST)" in n],
        [n for n in names if n.startswith("SurfaceView")],
        [n for n in names if n.startswith(PACKAGE + "/")],
    ):
        if pick:
            return pick[0]
    return "%s/.MainActivity" % PACKAGE


def read_frames(tag: str) -> Path:
    """Read one frame window for the current scene and keep the raw dump.

    gfxinfo only sees the View pipeline; a GL game has to come from the compositor, so the
    source is chosen once, at the top of the run, and printed into the log.
    """
    if SOURCE == "sf":
        layer = find_layer()
        raw = dev.shell("dumpsys SurfaceFlinger --latency '%s'" % layer)
        suffix = "latency"
        log("layer: %s" % layer, desc="compositor layer")
    else:
        shell("dumpsys gfxinfo %s" % PACKAGE)
        sleep(1.0)
        raw = dev.shell("dumpsys gfxinfo %s framestats" % PACKAGE)
        suffix = "framestats"
    target = OUT / f"{suffix}_{tag}.txt"
    target.write_text(raw if isinstance(raw, str) else str(raw), encoding="utf-8")
    log("%s: %s" % (suffix, target.name), desc="measured %s" % tag)
    return target


log("package: %s" % PACKAGE, desc="target")
log("frame source: %s" % SOURCE, desc="source")
snapshot(filename=str(OUT / "01_launch.jpg"), msg="launch")
# Replace with the real selector for the build under test:
# touch(Template(str(ROOT / "assets" / "btn_spin.png")))
sleep(1.0)

if SWIPES:
    # A static screen draws almost nothing: gfxinfo reports a handful of frames and the
    # gate has no distribution to judge. Real interaction is the only way to get one.
    log("interaction: %d swipes" % SWIPES, desc="action")
    for _ in range(SWIPES):
        swipe((0.5, 0.85), (0.5, 0.25))
        sleep(0.3)

open_stats = read_frames("base_game")

log("spin", desc="action")
sleep(1.0)
snapshot(filename=str(OUT / "02_result.jpg"), msg="result screen")
result_stats = read_frames("result")

report = subprocess.run(
    [sys.executable, "-m", "qa", "sf" if SOURCE == "sf" else "perf", str(open_stats)],
    cwd=ROOT, capture_output=True, text=True,
)
print(report.stdout or report.stderr)
log("gate base_game: exit %s" % report.returncode, desc="gate", snapshot=False)
print("frames: %s, %s" % (open_stats, result_stats))
