import unittest
from pathlib import Path

from qa.rtp import confidence_interval, measure, read_rounds

FIXTURES = Path(__file__).parent / "fixtures"


class SimulationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = read_rounds(FIXTURES / "simulation.csv")
        self.stats = measure(self.rows)

    def test_designed_rtp(self) -> None:
        self.assertAlmostEqual(self.stats.rtp, 5722 / 6000, places=6)

    def test_hit_frequency(self) -> None:
        self.assertAlmostEqual(self.stats.hit_frequency, 0.26, places=6)

    def test_no_bad_rows(self) -> None:
        self.assertEqual(self.stats.bad_rows, 0)

    def test_confidence_interval_contains_rtp(self) -> None:
        low, high = confidence_interval(self.stats)
        self.assertLess(low, self.stats.rtp)
        self.assertGreater(high, self.stats.rtp)

    def test_empty_input_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            measure([])


if __name__ == "__main__":
    unittest.main()
