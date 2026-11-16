"""Turn measurements into pass/fail checks.

Thresholds live in config.json, not in code, so a QA lead can tighten a release
gate without touching Python.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from qa.gfxinfo import FrameStats, SummaryStats
from qa.rtp import SimulationStats


@dataclass(frozen=True)
class Check:
    name: str
    value: float
    limit: float
    passed: bool
    detail: str = ""

    def line(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        return f"{mark}  {self.name:<34} {self.value:>10.2f}  limit {self.limit:.2f}  {self.detail}"


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_frames(stats: FrameStats, cfg: dict) -> list[Check]:
    perf = cfg["perf"]
    jank = stats.jank_pct(perf["budget_ms"])
    return [
        Check("jank_pct_under_budget", jank, perf["max_jank_pct"], jank <= perf["max_jank_pct"],
              f"{stats.count} frames, budget {perf['budget_ms']} ms"),
        Check("p90_frame_ms", stats.percentile(90), perf["max_p90_ms"],
              stats.percentile(90) <= perf["max_p90_ms"]),
        Check("p99_frame_ms", stats.percentile(99), perf["max_p99_ms"],
              stats.percentile(99) <= perf["max_p99_ms"]),
    ]


def check_summary(stats: SummaryStats, cfg: dict) -> list[Check]:
    perf = cfg["perf"]
    checks = [
        Check("jank_pct_from_device", stats.jank_pct, perf["max_jank_pct"],
              stats.jank_pct <= perf["max_jank_pct"],
              f"{stats.total_frames} frames, {stats.janky_frames} janky"),
    ]
    if stats.p90_ms is not None:
        checks.append(Check("p90_frame_ms", stats.p90_ms, perf["max_p90_ms"],
                            stats.p90_ms <= perf["max_p90_ms"]))
    if stats.p99_ms is not None:
        checks.append(Check("p99_frame_ms", stats.p99_ms, perf["max_p99_ms"],
                            stats.p99_ms <= perf["max_p99_ms"]))
    return checks


def check_simulation(stats: SimulationStats, cfg: dict) -> list[Check]:
    sim = cfg["simulation"]
    low, high = sim["rtp_min"], sim["rtp_max"]
    checks = [
        Check("rtp_in_range", stats.rtp, high, low <= stats.rtp <= high,
              f"expected {low:.4f}-{high:.4f}"),
        Check("hit_frequency_low", stats.hit_frequency, sim["hit_frequency_min"],
              stats.hit_frequency >= sim["hit_frequency_min"]),
        Check("hit_frequency_high", stats.hit_frequency, sim["hit_frequency_max"],
              stats.hit_frequency <= sim["hit_frequency_max"]),
        Check("max_win_multiplier", stats.max_win_multiplier, sim["max_win_multiplier"],
              stats.max_win_multiplier <= sim["max_win_multiplier"]),
        Check("bad_rows", float(stats.bad_rows), 0.0, stats.bad_rows == 0,
              f"{stats.rounds} rounds"),
    ]
    return checks
