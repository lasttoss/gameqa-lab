import unittest
from pathlib import Path

from qa.gfxinfo import parse_framestats, parse_summary

FIXTURES = Path(__file__).parent / "fixtures"


class FramestatsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.stats = parse_framestats((FIXTURES / "gfxinfo_framestats.txt").read_text(encoding="utf-8"))

    def test_counts_every_row(self) -> None:
        self.assertEqual(self.stats.count, 240)

    def test_percentiles_are_ordered(self) -> None:
        self.assertLessEqual(self.stats.percentile(50), self.stats.percentile(90))
        self.assertLessEqual(self.stats.percentile(90), self.stats.percentile(99))

    def test_jank_counts_only_frames_over_budget(self) -> None:
        self.assertAlmostEqual(self.stats.jank_pct(16.67), 100 * 7 / 240, places=6)

    def test_rejects_text_without_profiledata(self) -> None:
        with self.assertRaises(ValueError):
            parse_framestats("Total frames rendered: 10")


class SummaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.stats = parse_summary((FIXTURES / "gfxinfo_summary.txt").read_text(encoding="utf-8"))

    def test_reads_totals(self) -> None:
        self.assertEqual(self.stats.total_frames, 1245)
        self.assertEqual(self.stats.janky_frames, 52)

    def test_reads_percentiles(self) -> None:
        self.assertEqual(self.stats.p90_ms, 15.0)
        self.assertEqual(self.stats.p99_ms, 32.0)

    def test_rejects_wrong_dump(self) -> None:
        with self.assertRaises(ValueError):
            parse_summary("something else entirely")


if __name__ == "__main__":
    unittest.main()
