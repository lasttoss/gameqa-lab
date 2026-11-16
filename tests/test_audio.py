import array
import math
import tempfile
import unittest
import wave
from pathlib import Path

from qa import gate
from qa.audio import inventory, inspect

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
ROOT = Path(__file__).resolve().parent.parent


def write_wav(path: Path, samples: list[int], rate: int = 22050) -> None:
    buffer = array.array("h", samples)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(buffer.tobytes())


class InspectTest(unittest.TestCase):
    def test_reads_the_generated_clips(self) -> None:
        clip = inspect(FIXTURES / "audio" / "audio_win.wav")
        self.assertTrue(clip.decodable)
        self.assertEqual(clip.sample_rate, 22050)
        self.assertAlmostEqual(clip.duration_ms, 800.0, places=0)
        self.assertLess(clip.peak, 0.999)

    def test_detects_a_clipped_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clipped.wav"
            write_wav(path, [32767, -32768] * 500)
            self.assertTrue(inspect(path).clipping)

    def test_detects_silence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "silent.wav"
            write_wav(path, [0] * 2000)
            self.assertLess(inspect(path).rms_db, -100)

    def test_compressed_file_is_inventoried_not_judged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "music.ogg"
            path.write_bytes(b"OggS" + b"\x00" * 100)
            clip = inspect(path)
            self.assertFalse(clip.decodable)
            self.assertIsNone(clip.rms_db)

    def test_a_directory_of_broken_wav_still_counts_as_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.wav"
            path.write_bytes(b"not a wave file")
            clips = inventory(Path(tmp))
            self.assertEqual(len(clips), 1)
            self.assertFalse(clips[0].decodable)


class AudioGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = gate.load_config(ROOT / "config.json")
        self.clips = inventory(FIXTURES / "audio")

    def test_committed_bank_passes(self) -> None:
        checks = gate.check_audio(self.clips, self.cfg)
        self.assertTrue(all(c.passed for c in checks), [c.name for c in checks if not c.passed])

    def test_a_silent_clip_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_wav(Path(tmp) / "silent.wav", [0] * 2000)
            checks = gate.check_audio(inventory(Path(tmp)), self.cfg)
            failed = [c.name for c in checks if not c.passed]
            self.assertIn("audio_silent_clips", failed)

    def test_raising_the_floor_fails_a_real_clip(self) -> None:
        strict = dict(self.cfg)
        strict["audio"] = {**self.cfg["audio"], "min_rms_db": -3.0}
        checks = gate.check_audio(self.clips, strict)
        self.assertFalse(all(c.passed for c in checks))


if __name__ == "__main__":
    unittest.main()
