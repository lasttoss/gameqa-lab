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
            write_wav(path, [32767, 32767, 32767, -32768] * 250)
            clip = inspect(path)
            self.assertTrue(clip.clipping)
            self.assertGreaterEqual(clip.longest_run, 3)

    def test_one_sample_at_the_rail_is_not_clipping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "touching.wav"
            write_wav(path, [32767, 100, -200, 300] * 100)
            self.assertFalse(inspect(path).clipping)

    def test_reads_8bit_unsigned_wav(self) -> None:
        """WAV stores 8-bit samples unsigned, centred on 128 — not signed bytes."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "eight_bit.wav"
            payload = bytes([128, 160, 100, 200, 128, 64, 255, 0] * 50)
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(1)
                handle.setframerate(11025)
                handle.writeframes(payload)
            clip = inspect(path)
            self.assertTrue(clip.decodable)
            self.assertEqual(clip.sample_rate, 11025)
            self.assertLess(clip.peak, 1.05)
            self.assertGreater(clip.rms_db, -30)

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
            self.assertIsNone(clips[0].duration_ms)


def write_float_wav(path: Path, values: list[float], rate: int = 48000) -> None:
    import struct
    body = b"".join(struct.pack("<f", v) for v in values)
    header = b"RIFF" + struct.pack("<I", 36 + len(body)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 3, 1, rate, rate * 4, 4, 32)
    header += b"data" + struct.pack("<I", len(body))
    path.write_bytes(header + body)


class EncodingTest(unittest.TestCase):
    def test_float32_is_decoded_not_skipped(self) -> None:
        """Real APKs ship IEEE-float WAV, which Python's wave module rejects."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "float.wav"
            write_float_wav(path, [0.5] * 4800 + [-0.5] * 4800)
            clip = inspect(path)
            self.assertTrue(clip.decodable)
            self.assertEqual(clip.encoding, "float32")
            self.assertAlmostEqual(clip.duration_ms, 200.0, places=0)
            self.assertFalse(clip.clipping)

    def test_float32_rail_is_one_not_thirty_two_thousand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hot.wav"
            write_float_wav(path, [0.8, 1.0, 1.0, 1.0, 0.7] * 100)
            clip = inspect(path)
            self.assertTrue(clip.clipping)
            self.assertGreaterEqual(clip.longest_run, 3)

    def test_unknown_container_is_inventoried(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weird.wav"
            path.write_bytes(b"RIFF" + b"\x00" * 64)
            self.assertFalse(inspect(path).decodable)


def write_ogg(path: Path, rate: int = 48000, channels: int = 1, granule: int = 96000) -> None:
    """Two pages: an identification header and a last page with the granule position."""
    import struct

    id_body = b"\x01vorbis" + struct.pack("<I", 0) + bytes([channels]) + struct.pack("<I", rate) + b"\x00" * 8
    page1 = (b"OggS" + bytes([0, 0x02]) + struct.pack("<q", 0) + struct.pack("<III", 1, 0, 0)
             + bytes([1, len(id_body)]) + id_body)
    page2 = (b"OggS" + bytes([0, 0x04]) + struct.pack("<q", granule) + struct.pack("<III", 1, 1, 0)
             + bytes([1, 8]) + b"\x00" * 8)
    path.write_bytes(page1 + page2)


def write_mp3(path: Path, kbps_index: int = 9, payload: int = 32000) -> None:
    """ID3v2 tag then one valid MPEG1 Layer III frame header at 128 kbps."""
    import struct

    id3 = b"ID3\x03\x00\x00" + bytes([0, 0, 0, 0])
    header = 0xFFE00000 | (3 << 19) | (1 << 17) | (kbps_index << 12) | (0 << 10)
    path.write_bytes(id3 + struct.pack(">I", header) + b"\x00" * payload)


class CompressedTest(unittest.TestCase):
    def test_ogg_duration_comes_from_the_granule_position(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tick.ogg"
            write_ogg(path, rate=48000, granule=96000)
            clip = inspect(path)
            self.assertEqual(clip.encoding, "ogg/vorbis")
            self.assertEqual(clip.sample_rate, 48000)
            self.assertAlmostEqual(clip.duration_ms, 2000.0, places=0)
            self.assertFalse(clip.decodable)      # header known, waveform not measured
            self.assertIsNone(clip.rms_db)

    def test_mp3_duration_is_labelled_an_estimate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "theme.mp3"
            write_mp3(path, payload=32000)
            clip = inspect(path)
            self.assertEqual(clip.encoding, "mp3/estimated")
            self.assertEqual(clip.sample_rate, 44100)
            self.assertAlmostEqual(clip.duration_ms, 2000.0, delta=80)

    def test_garbage_with_audio_suffix_is_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.ogg"
            path.write_bytes(b"not an ogg stream")
            clip = inspect(path)
            self.assertIsNone(clip.duration_ms)
            self.assertEqual(clip.encoding, "unreadable")


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

    def test_header_only_compressed_file_is_not_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            write_ogg(Path(tmp) / "ok.ogg")
            checks = {c.name: c for c in gate.check_audio(inventory(Path(tmp)), self.cfg)}
            self.assertTrue(checks["audio_unreadable"].passed)
            self.assertIn("header-only", checks["audio_files"].detail)

    def test_unreadable_file_fails_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "bad.ogg").write_bytes(b"junk")
            checks = {c.name: c for c in gate.check_audio(inventory(Path(tmp)), self.cfg)}
            self.assertFalse(checks["audio_unreadable"].passed)

    def test_raising_the_floor_fails_a_real_clip(self) -> None:
        strict = dict(self.cfg)
        strict["audio"] = {**self.cfg["audio"], "min_rms_db": -3.0}
        checks = gate.check_audio(self.clips, strict)
        self.assertFalse(all(c.passed for c in checks))


if __name__ == "__main__":
    unittest.main()
