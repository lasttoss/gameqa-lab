#!/usr/bin/env bash
# Run the Airtest flow and produce the two artefacts a reviewer opens:
#   out/airtest-report/log.html   steps, screenshots, one row per action
#   out/airtest-report/run.mp4    screen recording of the same run
#
# Two choices worth knowing:
#   * log.html comes from `airtest report`, not from `airtest run` — run only writes
#     log.txt + screenshots;
#   * the recording comes from `adb shell screenrecord`, which is on every device,
#     instead of Airtest's own recorder, which needs an ffmpeg binary on PATH.
set -euo pipefail
pkg="${1:?usage: run_flow.sh <package> [serial]}"
serial="${2:-}"
[ -n "$serial" ] && A=(-s "$serial") || A=()
swipes="${SMOKE_SWIPES:-6}"

# Absolute paths: `airtest report` resolves --outfile inside a directory it
# creates from the script name, so a relative path lands one level too deep.
log_dir="$(pwd)/out/airtest"
target="$(pwd)/out/airtest-report"
rm -rf "$log_dir" "$target"
mkdir -p "$log_dir" "$target"

echo "[1/4] launch the app under test"
adb "${A[@]}" shell monkey -p "$pkg" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 || true
sleep 2

echo "[2/4] record the screen while the flow runs"
adb "${A[@]}" shell screenrecord --bit-rate 4000000 --time-limit 180 /sdcard/qa-run.mp4 &
recorder=$!
sleep 2

SLOT_PACKAGE="$pkg" SMOKE_SWIPES="$swipes" airtest run flows/slot_smoke.py \
  --device "Android:///${serial}" --log "$log_dir"

echo "[3/4] stop the recording and pull it"
wait "$recorder" 2>/dev/null || true
adb "${A[@]}" pull /sdcard/qa-run.mp4 "$target/run.mp4" >/dev/null
adb "${A[@]}" shell rm -f /sdcard/qa-run.mp4

log_root="$(dirname "$(find "$log_dir" -name log.txt -print -quit)")"
echo "[4/4] airtest report (with the video attached) -> $target/log.html"
airtest report flows/slot_smoke.py --log_root "$log_root" --outfile "$target/log.html" \
  --lang en --record "$target/run.mp4" --export "$target"

echo
ls -lh "$target" | sed 's/^/  /'
echo "open: $target/log.html"
