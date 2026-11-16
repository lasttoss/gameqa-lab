# gameqa-lab

Three checks a slot build has to survive before someone calls it releasable, written
so that the numbers are reproducible and the gate can actually close.

| what | why it is not a screenshot test | runs in CI |
|---|---|---|
| frame time | per-frame duration from `dumpsys gfxinfo … framestats`, not a histogram guess | yes (recorded fixtures) |
| slot maths | RTP, hit frequency, volatility and a 95% interval from one row per round | yes (designed fixture) |
| device flow | Airtest taps, `device().shell()` measures, both in the same run | no — needs a device |

## Verify in 60 seconds

```bash
git clone https://github.com/lasttoss/gameqa-lab && cd gameqa-lab
make test            # 15 tests, no device, no network, no API keys
make demo            # 11 checks against the recorded fixtures → gate=armed failed=0
make guard           # tightens two limits and asserts the gate turns red
make fixtures-check  # the fixtures are what the generator produces
```

`make demo` prints one block and exits 0. `make guard` prints
`RESULT guard=armed baseline=PASS tightened=FAIL failed_checks=...` and exits 0 only
when the tightened limits really do fail — a check that cannot fail is decoration.
If a number in this README stops matching the output, that is a bug in the README,
not in the code.

## What is measured, and what is not

The three fixture files under `tests/fixtures/` are **generated**, not captured from
a phone: `tools/gen_fixtures.py` builds them from a fixed seed. So:

* the RTP figure (0.9537) is a **design decision** baked into
  `HIT_DISTRIBUTION`, and the parser is proven to recover it — that is a parser
  test, not a statement about any real game;
* the frame times are **synthetic** (240 frames, ~9 ms typical, a long frame every
  37th frame), which proves the percentile and jank arithmetic, not the smoothness
  of a build;
* nothing here has been run against a production slot game, and there is no audio
  check yet. `flows/slot_smoke.py` returns exit **3** when no device is attached,
  because "no device" must never look like "passed".

## The artefacts a reviewer actually opens

Airtest writes the run log; this repo does not re-implement it.

```bash
./scripts/run_flow.sh com.example.slot        # run + recording + report
```

| file | who writes it | what is in it |
|---|---|---|
| `out/airtest-report/log.html` | `airtest report` | one row per action, the screenshot after it, and the gate result |
| `out/airtest-report/*.mp4` | `airtest run --recording` | the same run, recorded |
| `out/airtest-report/` (whole dir) | `--export` | self-contained: images and video travel with the html |

`airtest run` only writes `log.txt` + screenshots; `log.html` comes from a second
command, `airtest report --log_root <dir> --outfile log.html --export <dir>`. Both
lines are in `scripts/run_flow.sh`, verified against airtest 1.4.3 source.

Separately, `python -m qa html out/report.html` renders the **gate** as one file —
value, limit, and a bar per check. That one answers "does this build pass", the
Airtest log answers "what did the tester see". Two questions, two files.

## Commands

```bash
python -m qa demo                              # all gates on the fixtures
python -m qa perf out/gfxinfo_framestats.txt   # per-frame gate
python -m qa perf out/gfxinfo_summary.txt --summary
python -m qa sim  out/simulation.csv           # slot maths gate
./scripts/collect.sh com.example.slot          # pull both artefacts from a device
python flows/slot_smoke.py --package com.example.slot   # Airtest flow + measurement + report
./scripts/make_video.sh out/shot_*.jpg out/walkthrough.mp4   # video without a device recorder
```

Thresholds live in `config.json`, not in Python, so a QA lead can move a release
gate without a code review:

```json
{"perf": {"budget_ms": 16.67, "max_jank_pct": 5.0, "max_p90_ms": 16.0, "max_p99_ms": 34.0},
 "simulation": {"rtp_min": 0.945, "rtp_max": 0.965, "hit_frequency_min": 0.20,
                "hit_frequency_max": 0.35, "max_win_multiplier": 5000.0}}
```

## Layout

```
qa/gfxinfo.py   parsers for the summary block and for framestats CSV
qa/rtp.py       per-round rollup: RTP, hit frequency, volatility, 95% interval
qa/gate.py      measurements -> checks, limits read from config.json
qa/report.py    one aligned block of text + exit code
flows/          Airtest flow; measures inside the same run via device().shell()
scripts/        collect the two artefacts from a device
tools/          fixture generator (deterministic) and the guard that proves the gate
tests/          15 unit tests over the fixtures
```

## Status

Python 3.11 and 3.12, no third-party dependency for the unit suite. Airtest is
needed only for `flows/`, and is pinned in `requirements-device.txt`.
