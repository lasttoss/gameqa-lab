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

from airtest.core.api import G, auto_setup, device, log, shell, sleep, snapshot, touch

PACKAGE = os.environ.get("SLOT_PACKAGE", "com.example.slot")
OUT = Path(os.environ.get("SLOT_OUT", "out"))
ROOT = Path(__file__).resolve().parent.parent

if not G.DEVICE_LIST:                      # allows `python flows/slot_smoke.py` too
    auto_setup(__file__)

OUT.mkdir(parents=True, exist_ok=True)
dev = device()


def read_framestats(tag: str) -> Path:
    """Reset, wait for the scene to settle, read per-frame data, keep it."""
    shell("dumpsys gfxinfo %s" % PACKAGE)
    sleep(1.0)
    raw = dev.shell("dumpsys gfxinfo %s framestats" % PACKAGE)
    target = OUT / f"framestats_{tag}.txt"
    target.write_text(raw if isinstance(raw, str) else str(raw), encoding="utf-8")
    log("framestats: %s" % target.name, desc="measured %s" % tag)
    return target


log("package: %s" % PACKAGE, desc="target")
snapshot(filename=str(OUT / "01_launch.jpg"), msg="launch")
# Replace with the real selector for the build under test:
# touch(Template(str(ROOT / "assets" / "btn_spin.png")))
sleep(1.0)

open_stats = read_framestats("base_game")

log("spin", desc="action")
sleep(1.0)
snapshot(filename=str(OUT / "02_result.jpg"), msg="result screen")
result_stats = read_framestats("result")

report = subprocess.run(
    [sys.executable, "-m", "qa", "perf", str(open_stats)],
    cwd=ROOT, capture_output=True, text=True,
)
print(report.stdout or report.stderr)
log("gate base_game: exit %s" % report.returncode, desc="gate", snapshot=False)
print("framestats: %s, %s" % (open_stats, result_stats))
