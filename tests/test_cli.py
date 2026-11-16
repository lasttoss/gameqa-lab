import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from qa import cli

ROOT = Path(__file__).resolve().parent.parent


class ConfigFlagTest(unittest.TestCase):
    def _run(self, args: list[str]) -> int:
        with redirect_stdout(io.StringIO()):
            return cli.main(args)

    def test_committed_config_passes(self) -> None:
        self.assertEqual(self._run(["demo"]), 0)

    def test_config_flag_can_close_the_gate(self) -> None:
        cfg = json.loads((ROOT / "config.json").read_text())
        cfg["perf"]["max_jank_pct"] = 1.0
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "strict.json"
            path.write_text(json.dumps(cfg))
            self.assertEqual(self._run(["demo", "--config", str(path)]), 1)

    def test_unknown_command_is_a_usage_error(self) -> None:
        self.assertEqual(self._run(["nope"]), 2)


if __name__ == "__main__":
    unittest.main()
