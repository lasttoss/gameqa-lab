"""Audio assets pulled off the device, checked without third-party libraries.

The point of an audio gate is not "does a file exist" but "is this clip audible, and
is it damaged". Both are measurable from the samples, so no ffmpeg and no listening
test is required — but the RIFF variants matter more than they look:

* PCM 8-bit is **unsigned**, 16/32-bit are signed;
* plenty of shipped assets are **IEEE float 32** (`WAVE_FORMAT_IEEE_FLOAT`), which
  Python's `wave` module refuses outright;
* Unity and FMOD exports often use `WAVE_FORMAT_EXTENSIBLE`, which carries the real
  format in a sub-format GUID.

All three cases appeared while testing real APKs, so the parser reads the RIFF chunks
itself. Anything it cannot decode is counted, never judged.
"""
from __future__ import annotations

import array
import math
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

AUDIO_SUFFIXES = {".wav", ".ogg", ".mp3", ".m4a", ".aac", ".flac"}

PCM = 1
IEEE_FLOAT = 3
EXTENSIBLE = 0xFFFE


@dataclass(frozen=True)
class Clip:
    path: Path
    duration_ms: float | None
    sample_rate: int | None
    channels: int | None
    rms_db: float | None
    peak: float | None
    decodable: bool
    encoding: str = "unknown"
    full_scale_ratio: float | None = None     # fraction of samples pinned at the rail
    longest_run: int = 0                      # longest unbroken rail run

    @property
    def clipping(self) -> bool:
        """A normalised master is loud, not clipped.

        Peak alone cannot tell them apart: a track normalised to -0.01 dBFS reads
        peak=0.999 and is clean. Clipping is a *shape*: three or more consecutive
        samples pinned at the rail. One sample at the rail is quantisation, not a
        clipped waveform — measured against a real slot APK, where 4 of 7 clips
        touched the rail but only 3 held it for a run.
        """
        return self.longest_run >= 3


def _read_chunks(blob: bytes) -> tuple[tuple[int, int, int, int], bytes] | None:
    """Return ((format, channels, rate, bits), data) from a RIFF/WAVE file."""
    if len(blob) < 12 or blob[0:4] != b"RIFF" or blob[8:12] != b"WAVE":
        return None

    fmt: tuple[int, int, int, int] | None = None
    data: bytes | None = None
    offset = 12
    while offset + 8 <= len(blob):
        name = blob[offset:offset + 4]
        (size,) = struct.unpack_from("<I", blob, offset + 4)
        body = blob[offset + 8:offset + 8 + size]
        if name == b"fmt " and len(body) >= 16:
            audio_format, channels, rate, _, _, bits = struct.unpack_from("<HHIIHH", body, 0)
            if audio_format == EXTENSIBLE and len(body) >= 26:
                (audio_format,) = struct.unpack_from("<H", body, 24)
            fmt = (audio_format, channels, rate, bits)
        elif name == b"data":
            data = body
        offset += 8 + size + (size & 1)                  # chunks are word aligned
        if fmt and data is not None:
            break
    if not fmt or not data:
        return None
    return fmt, data


def _samples(data: bytes, audio_format: int, bits: int) -> tuple[list[float], str, float] | None:
    """Decode to floats in [-1, 1] plus the rail threshold used for clipping.

    The threshold is in the same normalised units as the samples, so a float clip is
    compared against 1.0 and a 16-bit clip against 32767/32768. Mixing the two scales
    made every float clip look like it was pinned at the ceiling.
    """
    if audio_format == IEEE_FLOAT and bits == 32:
        floats = array.array("f")
        floats.frombytes(data[: len(data) - len(data) % 4])
        if sys.byteorder == "big":
            floats.byteswap()
        return floats.tolist(), "float32", 1.0 - 1e-6

    if audio_format != PCM:
        return None

    if bits == 8:
        raw = array.array("B")
        raw.frombytes(data)
        return [(value - 128) / 128.0 for value in raw], "pcm8", 127 / 128
    if bits == 16:
        raw = array.array("h")
        raw.frombytes(data[: len(data) - len(data) % 2])
        if sys.byteorder == "big":
            raw.byteswap()
        return [value / 32768.0 for value in raw], "pcm16", 32767 / 32768
    if bits == 32:
        raw = array.array("i")
        raw.frombytes(data[: len(data) - len(data) % 4])
        if sys.byteorder == "big":
            raw.byteswap()
        return [value / 2147483648.0 for value in raw], "pcm32", 2147483647 / 2147483648
    return None



MP3_BITRATE_TABLE = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
MP3_RATES = {0: 44100, 1: 48000, 2: 32000}


def _ogg_info(blob: bytes) -> tuple[float | None, int | None, int | None, str] | None:
    """Duration from the granule position of the last page. Reads headers only.

    Compressed assets are most of a real bank, and `wave` cannot touch them. Refusing
    to report anything about them leaves the reviewer blind; reporting a duration from
    the container is honest as long as it is not called a waveform measurement.
    """
    if not blob.startswith(b"OggS"):
        return None
    offset = 0
    rate = channels = None
    last_granule = None
    while offset + 27 <= len(blob) and blob[offset:offset + 4] == b"OggS":
        (granule,) = struct.unpack_from("<q", blob, offset + 6)
        segments = blob[offset + 26]
        table = blob[offset + 27:offset + 27 + segments]
        body_start = offset + 27 + segments
        body_len = sum(table)
        body = blob[body_start:body_start + body_len]
        if body[:7] == b"\x01vorbis" and len(body) >= 16:
            channels = body[11]
            (rate,) = struct.unpack_from("<I", body, 12)
        if granule >= 0:
            last_granule = granule
        offset = body_start + body_len
    if rate is None:
        return (None, None, None, "ogg/unknown-codec")
    duration = 1000.0 * last_granule / rate if last_granule else None
    return (duration, rate, channels, "ogg/vorbis")


def _mp3_info(blob: bytes) -> tuple[float | None, int | None, int | None, str] | None:
    """Duration estimated from the bitrate — labelled as an estimate, not a measurement."""
    start = 0
    if blob.startswith(b"ID3") and len(blob) >= 10:
        size = (blob[6] << 21) | (blob[7] << 14) | (blob[8] << 7) | blob[9]
        start = 10 + size
    index = start
    limit = min(len(blob) - 4, start + 65536)
    while index < limit:
        if blob[index] == 0xFF and (blob[index + 1] & 0xE0) == 0xE0:
            break
        index += 1
    else:
        return None
    header = struct.unpack_from(">I", blob, index)[0]
    version = (header >> 19) & 0x03
    layer = (header >> 17) & 0x03
    bitrate_index = (header >> 12) & 0x0F
    rate_index = (header >> 10) & 0x03
    if version != 3 or layer != 1 or not 0 < bitrate_index < len(MP3_BITRATE_TABLE) or rate_index == 3:
        return None
    bitrate = MP3_BITRATE_TABLE[bitrate_index] * 1000
    rate = MP3_RATES[rate_index]
    channels = 1 if ((header >> 6) & 0x03) == 3 else 2
    duration = 1000.0 * (len(blob) - index) * 8 / bitrate
    return (duration, rate, channels, "mp3/estimated")


def inspect(path: Path) -> Clip:
    """Decode a WAV and measure it. Anything else is inventoried, not judged."""
    try:
        blob = path.read_bytes()
    except OSError:
        return Clip(path, None, None, None, None, None, decodable=False)

    chunks = _read_chunks(blob)
    if chunks is None:
        suffix = path.suffix.lower()
        header = _ogg_info(blob) if suffix == ".ogg" else _mp3_info(blob) if suffix == ".mp3" else None
        if header is None:
            return Clip(path, None, None, None, None, None, decodable=False, encoding="unreadable")
        duration, rate, channels, encoding = header
        return Clip(path, duration, rate, channels, None, None, decodable=False, encoding=encoding)

    (audio_format, channels, rate, bits), data = chunks
    decoded = _samples(data, audio_format, bits)
    if decoded is None:
        return Clip(path, 0.0, rate, channels, None, None, decodable=False,
                    encoding=f"riff/fmt{audio_format}-{bits}bit")

    values, encoding, rail = decoded
    if not values:
        return Clip(path, 0.0, rate, channels, None, None, decodable=False, encoding=encoding)

    peak = max(abs(v) for v in values)
    mean_square = sum(v * v for v in values) / len(values)
    rms_db = 20 * math.log10(math.sqrt(mean_square)) if mean_square > 0 else -math.inf

    at_rail = 0
    longest = current = 0
    for value in values:
        if abs(value) >= rail:                            # rail is already normalised
            at_rail += 1
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    return Clip(
        path=path,
        duration_ms=1000.0 * len(values) / (rate * max(channels, 1)),
        sample_rate=rate,
        channels=channels,
        rms_db=rms_db,
        peak=peak,
        decodable=True,
        encoding=encoding,
        full_scale_ratio=at_rail / len(values),
        longest_run=longest,
    )


def inventory(directory: Path) -> list[Clip]:
    files = sorted(p for p in directory.rglob("*") if p.suffix.lower() in AUDIO_SUFFIXES)
    return [inspect(p) for p in files]
