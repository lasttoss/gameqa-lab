# Example APK for a device-free dry run

A real slot machine, free, open source, no money involved — so the pipeline can be
exercised end to end on a laptop without touching any client's build.

| field | value |
|---|---|
| app | Tuty Fruty Slot for Android |
| package | `eu.veldsoft.tuty.fruty.slot` |
| author | Velbazhd Software LLC, (c) 2008-2026 |
| licence | GPL-3.0-only |
| nature | play-for-fun slot machine, five reels, **no gambling** (ad-supported) |
| source | https://f-droid.org/en/packages/eu.veldsoft.tuty.fruty.slot/ |
| apk | https://f-droid.org/repo/eu.veldsoft.tuty.fruty.slot_5.apk (647 KB) |

## Dry run without a device

```bash
curl -LO https://f-droid.org/repo/eu.veldsoft.tuty.fruty.slot_5.apk
python - <<'PY'
import pathlib, zipfile
out = pathlib.Path("out/example-audio"); out.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile("eu.veldsoft.tuty.fruty.slot_5.apk") as apk:
    for name in apk.namelist():
        if name.lower().endswith(".wav"):
            (out / pathlib.Path(name).name).write_bytes(apk.read(name))
PY
python -m qa audio out/example-audio
```

With a device or emulator, the same build gives the full path:

```bash
adb install eu.veldsoft.tuty.fruty.slot_5.apk
./scripts/collect_audio.sh eu.veldsoft.tuty.fruty.slot
./scripts/run_flow.sh eu.veldsoft.tuty.fruty.slot      # log.html + recording
```

## What the first run found

7 WAV, all 11025 Hz mono 8-bit. `qa/audio.py` flagged 3 of 7 as clipped:

```
9x.wav   447 ms  rms -10.2 dB  12.5%…  run 13 samples at the rail
II.wav   154 ms  rms  -5.7 dB  12.5%   run  6
zZ.wav    79 ms  rms  -6.8 dB   7.8%   run  4
```

Two corrections came out of running against this file, both worth keeping in mind
for any real build:

1. **8-bit WAV is unsigned** (centred on 128). Reading it as signed bytes made every
   clip look like noise around zero and produced a "peak 1.000, all 7 clipped" report
   that was pure artefact. The decoder now converts per width.
2. **Peak alone cannot identify clipping.** These clips are normalised near full
   scale; what separates a loud master from a clipped one is three or more
   *consecutive* samples pinned at the rail. The check counts runs, not peaks.

Neither bug would have shown up on the generated fixtures — the fixture clips are
16-bit and clean. That is the argument for exercising the gate on a real file early.
