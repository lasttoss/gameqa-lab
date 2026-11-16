#!/usr/bin/env bash
# Build a short mp4 from the scene checkpoints, for runs where the device could not
# be recorded (Airtest needs an ffmpeg binary to record; this script finds one).
#   ./scripts/make_video.sh out/shot_*.jpg out/walkthrough.mp4
set -euo pipefail
[ "$#" -ge 2 ] || { echo "usage: make_video.sh <shot.jpg...> <out.mp4>" >&2; exit 2; }
out="${*: -1}"
set -- "${@:1:$#-1}"

ffmpeg_bin="$(command -v ffmpeg || true)"
if [ -z "$ffmpeg_bin" ]; then
  ffmpeg_bin="$(python3 -c 'import imageio_ffmpeg, sys; sys.stdout.write(imageio_ffmpeg.get_ffmpeg_exe())' 2>/dev/null || true)"
fi
[ -n "$ffmpeg_bin" ] || { echo "no ffmpeg: apt install ffmpeg, or pip install imageio-ffmpeg" >&2; exit 2; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
i=0
for shot in "$@"; do
  printf -v name '%s/frame-%03d.jpg' "$tmp" "$i"
  cp "$shot" "$name"
  i=$((i+1))
done
"$ffmpeg_bin" -hide_banner -loglevel error -y -framerate 1 -i "$tmp/frame-%03d.jpg" \
  -vf "scale=1280:-2:flags=lanczos,format=yuv420p" -r 25 "$out"
echo "wrote $out from $i shots"
