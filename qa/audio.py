"""Audio assets pulled off the device, checked with the standard library.

The point of an audio gate is not "does a file exist" but "is this clip audible and
not clipped". Both are measurable from the PCM samples, so no ffmpeg and no
listening test is required for WAV. Compressed formats are inventoried only —
saying more than that about an .ogg without decoding it would be a guess.
"""
from __future__ import annotations

import array
import math
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

AUDIO_SUFFIXES = {".wav", ".ogg", ".mp3", ".m4a", ".aac", ".flac"}


@dataclass(frozen=True)
class Clip:
    path: Path
    duration_ms: float | None
    sample_rate: int | None
    channels: int | None
    rms_db: float | None
    peak: float | None
    decodable: bool
    full_scale_ratio: float | None = None     # fraction of samples pinned at the rail
    longest_run: int = 0                      # longest unbroken rail run

    @property
    def clipping(self) -> bool:
        """A normalised master is loud, not clipped.

        Peak alone cannot tell them apart: a track normalised to -0.01 dBFS reads
        peak=0.999 and is clean. Clipping is a *shape*: three or more consecutive
        samples pinned at the rail. One sample at the rail is quantisation, not a
        clipped waveform — measured against a real slot APK, where 4 of 7 clips
        touch the rail but only 3 hold it for a run.
        """
        if self.full_scale_ratio is None:
            return False
        return self.longest_run >= 3


def inspect(path: Path) -> Clip:
    """Read a WAV header and its samples. Anything else is inventoried, not judged."""
    try:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            rate = handle.getframerate()
            frames = handle.getnframes()
            raw = handle.readframes(frames)
    except (wave.Error, EOFError, OSError):
        return Clip(path, None, None, None, None, None, decodable=False)

    if not frames or width not in (1, 2, 4):
        return Clip(path, 0.0, rate, channels, None, None, decodable=False)

    # WAV sample encoding depends on the width: 8-bit is UNSIGNED (centred on 128),
    # 16/32-bit are signed little-endian. Reading 8-bit as signed makes a loud clip
    # look like noise around zero, which is exactly the mistake this line prevents.
    if width == 1:
        raw_samples = array.array("B")
        raw_samples.frombytes(raw)
        samples = [value - 128 for value in raw_samples]
        scale, rail = 128.0, 127
    else:
        raw_samples = array.array("h" if width == 2 else "i")
        usable = len(raw) - (len(raw) % raw_samples.itemsize)
        raw_samples.frombytes(raw[:usable])
        if sys.byteorder == "big":
            raw_samples.byteswap()
        samples = raw_samples.tolist()
        scale = float(2 ** (width * 8 - 1))
        rail = int(scale) - 1

    peak = max(abs(s) for s in samples) / scale
    mean_square = sum((s / scale) ** 2 for s in samples) / len(samples)
    rms_db = 20 * math.log10(math.sqrt(mean_square)) if mean_square > 0 else -math.inf

    at_rail = 0
    longest = current = 0
    for sample in samples:
        if abs(sample) >= rail:
            at_rail += 1
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    return Clip(
        path=path,
        duration_ms=1000.0 * frames / rate,
        sample_rate=rate,
        channels=channels,
        rms_db=rms_db,
        peak=peak,
        decodable=True,
        full_scale_ratio=at_rail / len(samples),
        longest_run=longest,
    )


def inventory(directory: Path) -> list[Clip]:
    files = sorted(p for p in directory.rglob("*") if p.suffix.lower() in AUDIO_SUFFIXES)
    return [inspect(p) for p in files]
