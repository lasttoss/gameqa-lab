"""Regenerate the recorded fixtures deterministically.

    python tools/gen_fixtures.py            # write files
    python tools/gen_fixtures.py --check    # fail if files differ (used by CI)

The simulation fixture uses a fixed seed so that `--check` is stable: the same
seed must always produce the same bytes, or the numbers in the README are lies.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
SEED = 20261116
ROUNDS = 6000


# Designed hit distribution. 1560 hits out of 6000 rounds (26%), and the
# multiplier sum is 5722, so RTP = 5722 / 6000 = 0.9537. Hand-built instead of
# sampled: a slot fixture is only reviewable if its RTP is a design decision.
HIT_DISTRIBUTION: tuple[tuple[float, int], ...] = (
    (1, 500), (2, 441), (3, 300), (5, 150), (8, 80), (12, 50), (20, 20), (50, 17), (100, 2),
)


def _design_multipliers(hits: int) -> list[float]:
    values: list[float] = []
    for multiplier, count in HIT_DISTRIBUTION:
        values.extend([float(multiplier)] * count)
    if len(values) != hits:
        raise ValueError(f"distribution has {len(values)} hits, expected {hits}")
    return sorted(values)


def simulation_csv() -> str:
    """6000 rounds, 26% hits, RTP designed to 0.957."""
    rng = random.Random(SEED)
    hit_rate = 0.26
    bet = 100
    target_rtp = 0.957
    hits = int(round(ROUNDS * hit_rate))
    multipliers = _design_multipliers(hits)
    rng.shuffle(multipliers)
    hit_positions = set(rng.sample(range(ROUNDS), hits))
    lines = ["round_id,bet,win"]
    cursor = 0
    for index in range(ROUNDS):
        if index in hit_positions:
            win = int(bet * multipliers[cursor])
            cursor += 1
        else:
            win = 0
        lines.append(f"{index + 1},{bet},{win}")
    return "\n".join(lines) + "\n"


def framestats() -> str:
    """A framestats block: 240 frames, most under a 60 Hz budget, a few over."""
    rng = random.Random(SEED + 1)
    header = (
        "Flags,IntendedVsync,Vsync,OldestInputEvent,NewestInputEvent,HandleInputStart,"
        "AnimationStart,PerformTraversalsStart,DrawStart,SyncQueued,SyncStart,IssueDrawCommandsStart,"
        "SwapBuffers,FrameCompleted,DequeueBufferDuration,QueueBufferDuration,GpuCompleted"
    )
    rows = []
    vsync = 1_000_000_000_000
    for index in range(240):
        intended = vsync + index * 16_666_667
        duration_ns = int(rng.gauss(8_500_000, 2_500_000))
        if index % 37 == 0:                  # a long frame every ~0.6 s of animation
            duration_ns = int(rng.uniform(19_000_000, 27_000_000))
        duration_ns = max(duration_ns, 3_000_000)
        completed = intended + duration_ns
        rows.append(
            f"0,{intended},{intended + 1000},0,0,{intended + 200000},{intended + 400000},"
            f"{intended + 900000},{intended + 1200000},{intended + 1500000},{intended + 1600000},"
            f"{intended + 1700000},{completed - 400000},{completed},300000,200000,{completed + 1000}"
        )
    return "Graphics info for pid 4242 [com.example.slot]\n\n---PROFILEDATA---\n" + header + "\n" + "\n".join(rows) + "\n---PROFILEDATA---\n"


def summary() -> str:
    return """Applications Graphics Acceleration Info:
Uptime: 240000 Realtime: 240000

** Graphics info for pid 4242 [com.example.slot] **

Stats since: 88765432109ns
Total frames rendered: 1245
Janky frames: 52 (4.18%)
Janky frames (legacy): 52 (4.18%)
50th percentile: 5ms
90th percentile: 15ms
95th percentile: 19ms
99th percentile: 32ms
Number Missed Vsync: 9
Number High input latency: 0
Number Slow UI thread: 12
Number Slow bitmap uploads: 1
Number Slow issue draw commands: 3
Number Frame deadline missed: 52
HISTOGRAM: 5ms=612 6ms=210 7ms=118 8ms=74 9ms=44 10ms=31 11ms=22 12ms=16 13ms=12 14ms=9 15ms=7 16ms=5 17ms=4 20ms=3 25ms=2 30ms=2 40ms=1 50ms=1 100ms=0
"""


FILES = {
    "simulation.csv": simulation_csv,
    "gfxinfo_framestats.txt": framestats,
    "gfxinfo_summary.txt": summary,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify committed fixtures match the generator")
    args = parser.parse_args()
    FIXTURES.mkdir(parents=True, exist_ok=True)
    drift = []
    for name, builder in FILES.items():
        path = FIXTURES / name
        content = builder()
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                drift.append(name)
        else:
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
    if args.check:
        if drift:
            print(f"FIXTURE DRIFT: {', '.join(drift)}", file=sys.stderr)
            return 1
        print("fixtures reproducible: 3/3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
