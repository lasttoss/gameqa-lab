import copy
import unittest
from pathlib import Path

from qa import gate
from qa.gfxinfo import parse_framestats
from qa.rtp import measure, read_rounds

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


class GateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = gate.load_config(ROOT / "config.json")
        self.frames = parse_framestats((FIXTURES / "gfxinfo_framestats.txt").read_text(encoding="utf-8"))
        self.sim = measure(read_rounds(FIXTURES / "simulation.csv"))

    def test_committed_config_passes(self) -> None:
        checks = gate.check_frames(self.frames, self.cfg) + gate.check_simulation(self.sim, self.cfg)
        self.assertTrue(all(c.passed for c in checks), [c.name for c in checks if not c.passed])

    def test_tightening_the_jank_limit_fails(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["perf"]["max_jank_pct"] = 1.0
        checks = gate.check_frames(self.frames, cfg)
        self.assertFalse(all(c.passed for c in checks))

    def test_shifting_the_rtp_window_fails(self) -> None:
        cfg = copy.deepcopy(self.cfg)
        cfg["simulation"]["rtp_min"] = 0.97
        cfg["simulation"]["rtp_max"] = 0.99
        checks = gate.check_simulation(self.sim, cfg)
        self.assertFalse(all(c.passed for c in checks))


if __name__ == "__main__":
    unittest.main()
