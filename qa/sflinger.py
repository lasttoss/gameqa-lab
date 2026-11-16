# -*- coding: utf-8 -*-
"""Frame pacing for surfaces that `dumpsys gfxinfo` cannot see.

`gfxinfo … framestats` only records the hardware-accelerated **View** pipeline. A Unity,
libGDX or any GL title draws into a surface that never appears there — measured on this
machine, `org.andstatus.game2048` reported 2 frames and `com.agateau.burgerparty` 10 while
both were animating. For those titles the compositor still knows every frame, and
`dumpsys SurfaceFlinger --latency <layer>` hands over the last 128 of them:

    line 1              refresh period, in nanoseconds
    every line after     desiredPresentNs <tab> actualPresentNs <tab> frameReadyNs

Rows still in flight carry the int64 max in the present columns; they are not frames yet
and are dropped, never counted as fast ones. The layer name comes from
`dumpsys SurfaceFlinger --list`.

What the three columns mean here:

* ``actual - desired`` is **lateness** — how far behind its target vsync a frame landed.
  A steady 60 Hz app shows a constant one-to-two frame offset, so a big number here is
  normal and says nothing about smoothness.
* ``actual[i] - actual[i-1]`` is the **realised interval** — what the player's eye gets.
  One vsync means 60 fps; two vsyncs mean a dropped frame.
* so the gate counts a **dropped frame** as an interval longer than 1.5 refresh periods,
  which is the only definition that does not call a stable 60 Hz app janky.
"""
from __future__ import annotations

from dataclasses import dataclass

_NS_PER_MS = 1_000_000.0
PENDING = (1 << 63) - 1


@dataclass(frozen=True)
class Frame:
    desired_ns: int
    actual_ns: int
    ready_ns: int


@dataclass(frozen=True)
class Latency:
    refresh_ns: int
    frames: tuple[Frame, ...]

    @property
    def refresh_ms(self) -> float:
        return self.refresh_ns / _NS_PER_MS


@dataclass(frozen=True)
class SfStats:
    """Interval statistics for one surface: what the compositor actually presented."""

    count: int
    refresh_ms: float
    intervals_ms: tuple[float, ...]
    dropped: int

    @property
    def dropped_pct(self) -> float:
        return 100.0 * self.dropped / len(self.intervals_ms) if self.intervals_ms else 0.0

    def percentile(self, pct: float) -> float:
        if not self.intervals_ms:
            return 0.0
        ordered = sorted(self.intervals_ms)
        if len(ordered) == 1:
            return ordered[0]
        rank = (len(ordered) - 1) * (pct / 100.0)
        low = int(rank)
        high = min(low + 1, len(ordered) - 1)
        weight = rank - low
        return ordered[low] * (1 - weight) + ordered[high] * weight

    @property
    def fps(self) -> float:
        mean = sum(self.intervals_ms) / len(self.intervals_ms) if self.intervals_ms else 0.0
        return 1000.0 / mean if mean else 0.0


def parse_latency(text: str) -> Latency:
    """Parse the block `dumpsys SurfaceFlinger --latency <layer>` prints."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("empty latency dump")
    try:
        refresh_ns = int(lines[0].strip())
    except ValueError as exc:
        raise ValueError(f"first line is not a refresh period: {lines[0]!r}") from exc

    frames: list[Frame] = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            desired, actual, ready = (int(part) for part in parts)
        except ValueError:
            continue
        if PENDING in (desired, actual, ready):
            continue
        if actual < desired or ready > actual:
            continue  # impossible ordering: not a frame this device presented
        frames.append(Frame(desired, actual, ready))
    return Latency(refresh_ns=refresh_ns, frames=tuple(frames))


def intervals_ms(latency: Latency) -> tuple[float, ...]:
    """Time between consecutive presents — the interval a player sees."""
    actual = [frame.actual_ns for frame in latency.frames]
    return tuple((actual[i] - actual[i - 1]) / _NS_PER_MS for i in range(1, len(actual)))


def lateness_ms(latency: Latency) -> tuple[float, ...]:
    """How far behind its target vsync each frame landed. A constant offset is normal."""
    return tuple((frame.actual_ns - frame.desired_ns) / _NS_PER_MS for frame in latency.frames)


def stats(latency: Latency, drop_ratio: float = 1.5) -> SfStats:
    """Interval statistics; a frame is dropped when it misses a whole vsync slot."""
    intervals = intervals_ms(latency)
    threshold = drop_ratio * latency.refresh_ms
    dropped = sum(1 for value in intervals if value > threshold)
    return SfStats(count=len(latency.frames), refresh_ms=latency.refresh_ms,
                   intervals_ms=intervals, dropped=dropped)
