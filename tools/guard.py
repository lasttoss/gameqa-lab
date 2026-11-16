"""Prove that the gate closes.

A check that cannot fail is decoration. This script tightens two thresholds,
asserts the gate turns red, and restores nothing (config is read, never written).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qa import gate  # noqa: E402
from qa.gfxinfo import parse_framestats  # noqa: E402
from qa.rtp import measure, read_rounds  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def main() -> int:
    cfg = gate.load_config(ROOT / "config.json")
    frames = parse_framestats((FIXTURES / "gfxinfo_framestats.txt").read_text(encoding="utf-8"))
    sim = measure(read_rounds(FIXTURES / "simulation.csv"))

    baseline = gate.check_frames(frames, cfg) + gate.check_simulation(sim, cfg)
    if not all(c.passed for c in baseline):
        print("RESULT guard=broken reason=baseline_fails", file=sys.stderr)
        return 1

    strict = copy.deepcopy(cfg)
    strict["perf"]["max_jank_pct"] = 0.5
    strict["simulation"]["rtp_min"] = 0.99
    strict["simulation"]["rtp_max"] = 0.995
    tightened = gate.check_frames(frames, strict) + gate.check_simulation(sim, strict)
    failed = [c.name for c in tightened if not c.passed]
    if not failed:
        print("RESULT guard=broken reason=tightened_limits_still_pass", file=sys.stderr)
        return 1

    print(f"RESULT guard=armed baseline=PASS tightened=FAIL failed_checks={','.join(failed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
