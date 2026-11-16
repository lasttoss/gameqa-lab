import unittest
from pathlib import Path

from qa import gate, htmlreport
from qa.gfxinfo import parse_framestats
from qa.rtp import measure, read_rounds

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def _checks(rtp_min: float | None = None) -> list[gate.Check]:
    cfg = gate.load_config(ROOT / "config.json")
    if rtp_min is not None:
        cfg["simulation"]["rtp_min"] = rtp_min
    frames = parse_framestats((FIXTURES / "gfxinfo_framestats.txt").read_text(encoding="utf-8"))
    sim = measure(read_rounds(FIXTURES / "simulation.csv"))
    return gate.check_frames(frames, cfg) + gate.check_simulation(sim, cfg)


class HtmlReportTest(unittest.TestCase):
    def _render(self, checks, video=None, shots=()):
        meta = htmlreport.RunMeta(
            title="Slot build gate", source="fixtures", device="not attached",
            video=video, shots=tuple(shots),
        )
        return htmlreport.render(checks, meta, ROOT)

    def test_passing_gate_says_passed(self) -> None:
        page = self._render(_checks())
        self.assertIn("GATE PASSED", page)
        self.assertNotIn("GATE FAILED", page)

    def test_failing_gate_says_failed(self) -> None:
        page = self._render(_checks(rtp_min=0.99))
        self.assertIn("GATE FAILED", page)
        self.assertIn('class="badge fail"', page)

    def test_report_is_self_contained(self) -> None:
        page = self._render(_checks())
        for external in ("http://", "https://", "<script"):
            self.assertNotIn(external, page)

    def test_limit_marker_is_drawn_for_every_check(self) -> None:
        checks = _checks()
        page = self._render(checks)
        self.assertEqual(page.count('<div class="bar">'), len(checks))

    def test_video_is_linked_only_when_the_file_exists(self) -> None:
        missing = ROOT / "out" / "does-not-exist.mp4"
        self.assertNotIn("<video", self._render(_checks(), video=missing))

    def test_footer_states_the_limits_of_the_evidence(self) -> None:
        page = self._render(_checks())
        self.assertIn("audio is not checked yet", page)


if __name__ == "__main__":
    unittest.main()
