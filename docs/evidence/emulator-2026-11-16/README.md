# Evidence — one end-to-end run on an Android emulator

This folder is the record of a real run, kept next to a repository whose `out/` is not
committed. Nothing here was typed by hand: every file is what the tool wrote.

## What was run

| Step | Command | Output kept here |
|---|---|---|
| Install the APK, launch it, drive two screens, measure | `./scripts/run_flow.sh com.bobek.metronome emulator-5554` | `run-log.txt`, `scene-01-launch.jpg`, `scene-02-result.jpg`, `recording.mp4` |
| Frame window for the measured step | `dumpsys gfxinfo … framestats`, inside the same Airtest run | `perf-framestats.txt` |
| Cumulative counters for the same process | `dumpsys gfxinfo com.bobek.metronome` | `perf-summary.txt` |
| Audio bank off the device | `scripts/collect_audio.sh` (inside the APK + `/sdcard/Android/data`) | `audio/` — 12 WAV files |
| Gate | `python3 -m qa html …` over the files above | `report.html` |

Device: `emulator-5554`, Android 13 (Google APIs image, x86_64), 1080×2340, **swiftshader
software GL** — a container GPU, not a phone GPU. App: `com.bobek.metronome` 1.4.3, GPL-3.0,
3.1 MB; the APK is downloaded at run time and is not redistributed here.

## Result of this run

```
120 frames, budget 16.67 ms:  p50 23.56 ms · p90 26.87 ms · p99 29.12 ms
FAILING:  jank_pct_under_budget  89.167 %  limit   5.000 %
FAILING:  p90_frame_ms           26.865 ms limit  16.000 ms
PASSING:  p99_frame_ms           29.119 ms limit  34.000 ms
FAILING:  jank_pct_from_device    5.510 %  limit   5.000 %   (272 frames, 15 janky)
PASSING:  audio 12 files · silent 0 · clipped 0 · unreadable 0 · too short 0
```

`report.html` shows the same numbers with the limit marked on each bar. The gate exits `1`.
The two screenshots differ (`md5` 12f3bb97… and aa443eef…), so the swipe sequence did move
the screen — unlike the first attempt, where both snapshots were byte-identical and the
frame window was an idle screen.

## What this run does not prove

- **Not a phone.** No real GPU, no thermal behaviour, no vendor skin. These frame numbers are
  what a container does, and they say nothing about a device in a player's hand.
- **Not a slot build.** The APK is a metronome, chosen to keep the repository free of other
  people's game code. The gate checks the shape of the measurement, not a game's maths.
- **Not a game engine, and that is the bigger limit.** Two open-source games were driven on the
  same emulator first: `org.andstatus.game2048` reported **2** frames and
  `com.agateau.burgerparty` **10**, while both were animating. `dumpsys gfxinfo` only sees the
  hardware-accelerated View pipeline, and GL titles (Unity, libGDX, most slot builds) draw
  outside it. For those the frame source is `dumpsys SurfaceFlinger --latency <layer>`, which
  this repository does not implement yet.
- **Not a full session.** 120 frames in one window, on one emulator, on one app. A release
  decision needs several scenes, several devices, and one run per build.
- **The summary is not the window.** `perf-summary.txt` is cumulative for the process since it
  started (272 frames); the perf checks are computed from the 120-frame window in
  `perf-framestats.txt`. The two percentages are not comparable.
