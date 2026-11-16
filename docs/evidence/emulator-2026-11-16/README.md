# Evidence — one end-to-end run on an Android emulator

This folder is the record of a real run, kept next to a repository whose `out/` is
not committed. Nothing here was typed by hand: every file is what the tool wrote.

## What was run

| Step | Command | Output kept here |
|---|---|---|
| Install the APK, drive the screen, measure | `airtest run flows/slot_smoke.py --device Android:///emulator-5554 --log out/airtest` | `run-log.txt`, `scene-01-launch.jpg`, `recording.mp4` |
| Frame window for the measured step | `dumpsys gfxinfo` inside the same Airtest run | `perf-framestats.txt` |
| Audio bank off the device | `scripts/collect_audio.sh` (APK + `/sdcard/Android/data`) | `audio/` — 12 WAV files |
| Gate | `python3 -m qa html …` over the files above | `report.html` |

Device: `emulator-5554`, Android 13, 1080×2340, **swiftshader software GL** — a container
GPU, not a phone GPU.

## Result of this run

```
FAILING:  jank_pct_under_budget 98.333 %  limit 5.000 %   120 frames, budget 16.67 ms
FAILING:  p90_frame_ms          69.795 ms limit 16.000 ms
FAILING:  p99_frame_ms          83.476 ms limit 34.000 ms
PASSING:  audio_files 12 · silent 0 · clipped 0 · unreadable 0 · too short 0
```

`report.html` shows the same numbers with the limit marked on each bar. The gate exits
`1`, which is the correct outcome: software rasterisation cannot hold a 60 Hz budget.

## What this run does not prove

- **Not a phone.** No real GPU, no thermal behaviour, no vendor skin. The frame numbers
  are an upper bound on a container, and they say nothing about a device in a player's hand.
- **Not a slot build.** The APK is a plain metronome, chosen to keep the repository free
  of other people's game code. The gate checks the shape of the measurement, not a game's maths.
- **Not a game engine, and that is the bigger limit.** Two open-source games were tried on the same
  emulator first: `org.andstatus.game2048` reported **2** frames and `com.agateau.burgerparty`
  **10**, while both were animating — `dumpsys gfxinfo` only sees the View pipeline, and GL titles
  (Unity, libGDX, most slot builds) draw outside it. That is why the recorded run is a View-based
  app: a real game would have produced a near-empty file, and an empty file read as a pass is the
  exact failure this repository exists to prevent.
- **Not a full session.** 120 frames and one measured window. A release decision needs
  several scenes, several devices, and a run per build.
- **`perf-summary-scroll.txt` is a separate capture.** It is a 307-frame summary taken while
  swiping the same screen, kept as raw device output. It is not the window the perf checks
  above are computed from, so the two percentages are not comparable.
- **One screenshot, not two.** The flow captured a second snapshot at the "result" step, and
  it is byte-identical to the first: the action did not change the screen. That is why only
  `scene-01-launch.jpg` is kept, and why the frame window is best read as an idle screen.
