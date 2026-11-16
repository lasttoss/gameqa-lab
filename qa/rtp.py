"""Slot simulation invariants.

A slot build is only reviewable if the numbers coming out of the simulator match
the maths the paytable promises. This module reads one row per round and returns
measured values; deciding pass/fail is left to `qa.gate`.

Input CSV columns (extra columns are ignored):
    round_id,bet,win

Both `bet` and `win` are the same unit (credits or minor currency units).
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SimulationStats:
    rounds: int
    total_bet: float
    total_win: float
    rtp: float
    hit_frequency: float
    volatility: float
    max_win_multiplier: float
    bad_rows: int


def read_rounds(path: Path) -> list[tuple[int, float, float]]:
    rows: list[tuple[int, float, float]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = {"round_id", "bet", "win"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
        for row in reader:
            rows.append((int(row["round_id"]), float(row["bet"]), float(row["win"])))
    if not rows:
        raise ValueError(f"{path.name}: no rounds")
    return rows


def measure(rows: list[tuple[int, float, float]]) -> SimulationStats:
    if not rows:
        raise ValueError("no rounds to measure")
    bad = sum(1 for _, bet, win in rows if bet <= 0 or win < 0)
    total_bet = sum(bet for _, bet, _ in rows)
    total_win = sum(win for _, _, win in rows)
    if total_bet <= 0:
        raise ValueError("total bet is zero; cannot compute RTP")
    returns = [win / bet for _, bet, win in rows]
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / max(len(returns) - 1, 1)
    hits = sum(1 for r in returns if r > 0)
    max_multiplier = max(returns)
    return SimulationStats(
        rounds=len(rows),
        total_bet=total_bet,
        total_win=total_win,
        rtp=total_win / total_bet,
        hit_frequency=hits / len(rows),
        volatility=math.sqrt(variance),
        max_win_multiplier=max_multiplier,
        bad_rows=bad,
    )


def confidence_interval(stats: SimulationStats, z: float = 1.96) -> tuple[float, float]:
    """Normal approximation for RTP standard error, in return units."""
    if stats.rounds < 2:
        return (stats.rtp, stats.rtp)
    stderr = stats.volatility / math.sqrt(stats.rounds)
    return (stats.rtp - z * stderr, stats.rtp + z * stderr)
