# Evidence — a GL game, measured through the compositor

The `emulator-2026-11-16/` folder next door measures a View-based app, because
`dumpsys gfxinfo` cannot see anything else. This folder does the opposite: a real OpenGL
game, whose frames only exist in the compositor.

## Why this folder has to exist

`dumpsys gfxinfo … framestats` records the hardware-accelerated **View** pipeline. A GL
game draws into a `SurfaceView` and never appears there. Measured on the same emulator:

```
com.agateau.burgerparty   gfxinfo framestats  →   10 frames   (screen visibly animating)
                          SurfaceFlinger      →  127 frames   (this folder)
```

A gate fed the first number would have read "ten frames, all fine" out of a surface it
could not see. That is why `python -m qa sf` exists.

## What was run

```bash
# level 1-1 already started through the UI, game animating
SMOKE_SOURCE=sf SMOKE_SWIPES=0 ./scripts/run_flow.sh com.agateau.burgerparty emulator-5554
```

| file | what it is |
|---|---|
| `latency-window.txt` | raw output of `dumpsys SurfaceFlinger --latency '<layer>'` (128 lines) |
| `scene-01-gameplay.jpg`, `scene-02-gameplay.jpg` | the two snapshots the flow took; `md5` differs |
| `run-log.txt` | Airtest's own log, path rewritten to be portable |
| `recording.mp4` | first 20 s of the run, re-encoded |
| `report.html` | the gate, rendered from `latency-window.txt` only |

Layer: `SurfaceView[com.agateau.burgerparty/com.agateau.burgerparty.MainActivity](BLAST)`.
App: `com.agateau.burgerparty` 1.4.6, GPL-2.0, 8.4 MB, F-Droid; not redistributed here.
Device: `emulator-5554`, Android 13 (Google APIs, x86_64), 1080×2340, **swiftshader** — a
container GPU, not a phone GPU.

## Result of this run

```
127 frames · refresh 16.67 ms · 20.5 fps
p50 49.61 ms · p90 65.55 ms · p99 83.85 ms
dropped 120 intervals (95.24 %), where a dropped frame is an interval over 1.5 refresh slots
PASS sf_frames · FAIL sf_dropped_pct · FAIL sf_p99_interval_ms
```

The gate exits `1`. On software rendering a GL game is expected to miss most vsyncs; the
run proves the path from the compositor to the exit code, not the game's smoothness.

## Definitions worth arguing about

- **lateness** (`actualPresent − desiredPresent`) is not a defect. A steady 60 Hz app shows
  a constant one-to-two frame offset forever; gating on it would call every healthy build
  broken. It is printed for context and never gated.
- **interval** (`actualPresent[i] − actualPresent[i−1]`) is what the player sees. One vsync
  is 60 fps, two vsyncs is a dropped frame — so the check is `interval > 1.5 × refresh`,
  and the limit lives in `config.json` as `sf_max_dropped_pct`.
- **the buffer is 128 frames.** This is a short window by construction, not a session.

## What this run does not prove

- **Not a phone.** Software GL in a container; a real device would show different numbers in
  both directions.
- **Not a slot build.** Burger Party is a puzzle game, picked because it is GPL, small, and
  openly downloadable. Nothing here speaks about a game's maths — that is the `sim` gate.
- **Presentation, not GPU cost.** The compositor says when a frame appeared, not how long the
  GPU spent on it. For shader or fill-rate work the source has to be a GPU profiler.
- **One window, one scene.** 127 frames of one level. A release decision needs several
  scenes, several devices, and a run per build.
