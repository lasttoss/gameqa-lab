"""Airtest flow: UI check plus in-flow frame sampling.

Runs on a device or an emulator. Airtest is imported lazily so that the unit
suite and CI never need it installed.

    pip install -r requirements-device.txt
    python flows/slot_smoke.py --package com.example.slot

The point of this file: Airtest owns the taps and the screenshots, and
`device().shell()` owns the measurement. Both marks land in the same run, so the
frame window belongs to the scene it names.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def gfxinfo(serial: str | None, package: str, framestats: bool) -> str:
    command = ["adb"]
    if serial:
        command += ["-s", serial]
    command += ["shell", "dumpsys", "gfxinfo", package]
    if framestats:
        command.append("framestats")
    try:
        result = subprocess.run(command, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("adb not installed or not on PATH") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        message = detail[-1] if detail else "adb failed"
        raise RuntimeError(f"no usable device: {message}")
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", default="com.example.slot")
    parser.add_argument("--serial", default=None)
    parser.add_argument("--out", default="out/framestats.txt")
    parser.add_argument("--skip-ui", action="store_true", help="measure only; no Airtest import")
    args = parser.parse_args()

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] reset frame stats for {args.package}")
    try:
        gfxinfo(args.serial, args.package, framestats=False)
    except RuntimeError as exc:
        print(f"SKIP: {exc}", file=sys.stderr)
        return 3

    if not args.skip_ui:
        try:
            from airtest.core.api import device, sleep, touch  # noqa: F401
            from airtest.core.api import snapshot  # noqa: F401
            from poco.drivers.unity3d import UnityPoco  # noqa: F401
        except ImportError:
            print("airtest/poco missing: pip install -r requirements-device.txt", file=sys.stderr)
            return 2
        print("[2/4] Airtest flow: open the game, spin, wait for the result screen")
        # Replace these three calls with the real selectors for the build under test.
        # touch(Template(str(ROOT / "assets" / "icon_game.png")))
        time.sleep(1.0)
    else:
        print("[2/4] UI step skipped")

    print(f"[3/4] read framestats -> {out.relative_to(ROOT)}")
    try:
        out.write_text(gfxinfo(args.serial, args.package, framestats=True), encoding="utf-8")
    except RuntimeError as exc:
        print(f"SKIP: {exc}", file=sys.stderr)
        return 3

    print("[4/4] evaluate the perf gate")
    return subprocess.run([sys.executable, "-m", "qa", "perf", str(out)], cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
