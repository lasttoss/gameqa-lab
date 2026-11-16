# -*- coding: utf-8 -*-
"""The compositor path: parse, intervals, and the dropped-frame definition."""
from __future__ import annotations

import unittest
from pathlib import Path

from qa import sflinger

ROOT = Path(__file__).resolve().parent.parent
REAL = ROOT / "tests" / "fixtures" / "sflinger_latency.txt"
PENDING = sflinger.PENDING


def _dump(rows, refresh=16_666_666) -> str:
    lines = [str(refresh)]
    lines += [f"{d}\t{a}\t{r}" for d, a, r in rows]
    return "\n".join(lines) + "\n"


class ParseTest(unittest.TestCase):
    def test_real_capture_parses(self) -> None:
        latency = sflinger.parse_latency(REAL.read_text(encoding="utf-8"))
        self.assertEqual(latency.refresh_ns, 16_666_666)
        self.assertGreaterEqual(len(latency.frames), 100)

    def test_pending_rows_are_not_frames(self) -> None:
        text = _dump([(1, 3, 2), (4, PENDING, PENDING), (7, 9, 8)])
        self.assertEqual(len(sflinger.parse_latency(text).frames), 2)

    def test_impossible_ordering_is_skipped(self) -> None:
        text = _dump([(10, 5, 3), (10, 12, 11)])
        self.assertEqual(len(sflinger.parse_latency(text).frames), 1)

    def test_empty_dump_is_an_error_not_a_pass(self) -> None:
        with self.assertRaises(ValueError):
            sflinger.parse_latency("   \n")

    def test_first_line_must_be_a_refresh_period(self) -> None:
        with self.assertRaises(ValueError):
            sflinger.parse_latency("SurfaceFlinger latency\n1\t2\t3\n")


class IntervalTest(unittest.TestCase):
    def test_one_vsync_per_frame_is_sixty_fps(self) -> None:
        step = 16_666_666
        rows = [(i * step, i * step + 1_000_000, i * step + 500_000) for i in range(61)]
        stats = sflinger.stats(sflinger.parse_latency(_dump(rows)))
        self.assertEqual(stats.count, 61)
        self.assertAlmostEqual(stats.fps, 60.0, places=1)
        self.assertEqual(stats.dropped, 0)

    def test_two_vsyncs_is_a_dropped_frame(self) -> None:
        step = 16_666_666
        rows = [(0, 0, 0), (step, step, step), (3 * step, 3 * step, 3 * step)]
        stats = sflinger.stats(sflinger.parse_latency(_dump(rows)))
        self.assertEqual(stats.dropped, 1)
        self.assertAlmostEqual(stats.dropped_pct, 50.0, places=3)

    def test_lateness_is_not_the_interval(self) -> None:
        # A steady 60 Hz app that is consistently 2 frames behind is smooth, not janky.
        step, offset = 16_666_666, 33_333_332
        rows = [(i * step, i * step + offset, i * step + offset - 1_000_000) for i in range(61)]
        latency = sflinger.parse_latency(_dump(rows))
        self.assertEqual(sflinger.stats(latency).dropped, 0)
        self.assertAlmostEqual(sflinger.lateness_ms(latency)[0], 33.333, places=2)

    def test_single_frame_has_no_interval(self) -> None:
        stats = sflinger.stats(sflinger.parse_latency(_dump([(0, 1, 0)])))
        self.assertEqual(stats.count, 1)
        self.assertEqual(stats.intervals_ms, ())
        self.assertEqual(stats.percentile(99), 0.0)
        self.assertEqual(stats.dropped_pct, 0.0)


class GateTest(unittest.TestCase):
    def test_thresholds_come_from_config(self) -> None:
        from qa import gate
        cfg = gate.load_config(ROOT / "config.json")
        stats = sflinger.stats(sflinger.parse_latency(REAL.read_text(encoding="utf-8")))
        checks = {c.name: c for c in gate.check_sflinger(stats, cfg)}
        self.assertEqual(set(checks), {"sf_frames", "sf_dropped_pct", "sf_p99_interval_ms"})
        self.assertTrue(all(c.passed for c in checks.values()))

    def test_a_starved_surface_fails(self) -> None:
        from qa import gate
        cfg = gate.load_config(ROOT / "config.json")
        step = 16_666_666
        rows = [(i * 3 * step, i * 3 * step + 1, i * 3 * step) for i in range(70)]
        checks = gate.check_sflinger(sflinger.stats(sflinger.parse_latency(_dump(rows))), cfg)
        failed = {c.name for c in checks if not c.passed}
        self.assertIn("sf_dropped_pct", failed)

    def test_too_few_frames_fails_instead_of_passing_quietly(self) -> None:
        from qa import gate
        cfg = gate.load_config(ROOT / "config.json")
        rows = [(0, 1, 0), (16_666_666, 16_666_667, 16_666_666)]
        checks = gate.check_sflinger(sflinger.stats(sflinger.parse_latency(_dump(rows))), cfg)
        self.assertIn("sf_frames", {c.name for c in checks if not c.passed})


if __name__ == "__main__":
    unittest.main()
