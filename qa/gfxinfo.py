"""Parsers for `adb shell dumpsys gfxinfo`.

Two sources are supported:

* the summary block (every Android version) - totals, janky count, percentiles;
* `framestats` CSV (API 23+) - one row per frame, which is the only way to get
  a real per-frame duration instead of a histogram bucket.

Both parsers are pure functions over text so they can be tested without a device.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_NS_PER_MS = 1_000_000.0


@dataclass(frozen=True)
class FrameStats:
    """Per-frame durations in milliseconds, plus derived percentiles."""

    durations_ms: tuple[float, ...]

    @property
    def count(self) -> int:
        return len(self.durations_ms)

    def percentile(self, pct: float) -> float:
        if not self.durations_ms:
            return 0.0
        ordered = sorted(self.durations_ms)
        if len(ordered) == 1:
            return ordered[0]
        rank = (len(ordered) - 1) * (pct / 100.0)
        low = int(rank)
        high = min(low + 1, len(ordered) - 1)
        weight = rank - low
        return ordered[low] * (1 - weight) + ordered[high] * weight

    def jank_pct(self, budget_ms: float) -> float:
        if not self.durations_ms:
            return 0.0
        janky = sum(1 for d in self.durations_ms if d > budget_ms)
        return 100.0 * janky / len(self.durations_ms)


@dataclass(frozen=True)
class SummaryStats:
    """The numbers `dumpsys gfxinfo` prints before the histogram."""

    total_frames: int
    janky_frames: int
    jank_pct: float
    p50_ms: float | None
    p90_ms: float | None
    p95_ms: float | None
    p99_ms: float | None


def parse_framestats(text: str) -> FrameStats:
    """Parse the CSV that follows `dumpsys gfxinfo <pkg> framestats`.

    Frame duration is FRAME_COMPLETED - INTENDED_VSYNC. Rows are skipped when the
    two columns are missing or the marker pair is not present.
    """
    rows = _framestats_rows(text)
    if not rows:
        raise ValueError("no PROFILEDATA block found; run `dumpsys gfxinfo <pkg> framestats`")
    header, body = rows
    try:
        i_vsync = header.index("IntendedVsync")
        i_done = header.index("FrameCompleted")
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError("framestats header is missing IntendedVsync/FrameCompleted") from exc
    durations: list[float] = []
    for row in body:
        if len(row) != len(header):
            continue
        try:
            start = int(row[i_vsync])
            end = int(row[i_done])
        except ValueError:
            continue
        if end <= start:
            continue
        durations.append((end - start) / _NS_PER_MS)
    if not durations:
        raise ValueError("framestats had no usable rows")
    return FrameStats(tuple(durations))


def _framestats_rows(text: str) -> tuple[list[str], list[list[str]]] | None:
    blocks = text.split("---PROFILEDATA---")
    if len(blocks) < 3:
        return None
    inner = blocks[1].strip("\n").splitlines()
    inner = [line for line in inner if line.strip()]
    if len(inner) < 2:
        return None
    header = [cell.strip() for cell in inner[0].split(",")]
    body = [[cell.strip() for cell in line.split(",")] for line in inner[1:]]
    return header, body


_PCT_RE = re.compile(r"(\d+)(?:st|nd|rd|th) percentile:\s*(\d+)\s*ms", re.IGNORECASE)
_JANK_RE = re.compile(r"Janky frames:\s*(\d+)\s*\(([\d.]+)%\)")
_TOTAL_RE = re.compile(r"Total frames rendered:\s*(\d+)")


def parse_summary(text: str) -> SummaryStats:
    """Parse the summary block. Raises ValueError when it is not a gfxinfo dump."""
    total_match = _TOTAL_RE.search(text)
    if not total_match:
        raise ValueError("not a gfxinfo dump: 'Total frames rendered' not found")
    jank_match = _JANK_RE.search(text)
    percentiles = {int(m.group(1)): float(m.group(2)) for m in _PCT_RE.finditer(text)}
    return SummaryStats(
        total_frames=int(total_match.group(1)),
        janky_frames=int(jank_match.group(1)) if jank_match else 0,
        jank_pct=float(jank_match.group(2)) if jank_match else 0.0,
        p50_ms=percentiles.get(50),
        p90_ms=percentiles.get(90),
        p95_ms=percentiles.get(95),
        p99_ms=percentiles.get(99),
    )
