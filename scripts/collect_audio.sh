#!/usr/bin/env bash
# Pull the audio bank off a device so the gate can read it. Works over network adb:
#   adb connect 192.168.1.50:5555 && ADB_TARGET=192.168.1.50:5555 ./scripts/collect_audio.sh com.example.slot
# Two places matter: the APK (assets baked in) and Android/data/<pkg> (bundles unpacked
# at first run). A slot that ships sound in a downloaded bundle has an empty APK half.
set -euo pipefail
pkg="${1:?usage: collect_audio.sh <package> [out-dir] [serial]}"
out="${2:-out/audio-assets}"
serial="${3:-}"
adb_args=()
[ -n "$serial" ] && adb_args=(-s "$serial")

mkdir -p "$out"

echo "[1/4] apk path"
apk="$(adb "${adb_args[@]}" shell pm path "$pkg" | tr -d '\r' | sed -n 's/^package://p' | head -1)"
if [ -z "$apk" ]; then
  echo "package $pkg not installed on this device" >&2
  exit 2
fi
adb "${adb_args[@]}" pull "$apk" "$out/base.apk" >/dev/null
echo "  $apk -> $out/base.apk"

echo "[2/4] audio entries inside the apk"
python3 - "$out/base.apk" > "$out/apk-audio.txt" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    for name in archive.namelist():
        if name.lower().endswith((".wav", ".ogg", ".mp3", ".m4a", ".aac", ".flac")):
            print(name)
PY
echo "  $(wc -l < "$out/apk-audio.txt") entries"

echo "[2b/4] extract the wav entries so the gate can decode them"
python3 - "$out" <<'PY'
import pathlib, sys, zipfile
out = pathlib.Path(sys.argv[1])
target = out / "apk"
target.mkdir(exist_ok=True)
count = 0
with zipfile.ZipFile(out / "base.apk") as apk:
    for name in apk.namelist():
        if name.lower().endswith(".wav"):
            (target / pathlib.Path(name).name).write_bytes(apk.read(name))
            count += 1
print(f"  extracted {count} wav files from the apk")
PY

echo "[3/4] audio files written after install (bundles, obb, cache)"
adb "${adb_args[@]}" shell \
  "find /sdcard/Android/data/$pkg /sdcard/Android/obb/$pkg -type f 2>/dev/null" \
  | tr -d '\r' | grep -Ei '\.(wav|ogg|mp3|m4a|aac|flac)$' > "$out/runtime-audio.txt" || true
echo "  $(wc -l < "$out/runtime-audio.txt") files"

echo "[4/4] pull the wav files the gate can decode"
n=0
while IFS= read -r remote; do
  [ -z "$remote" ] && continue
  case "$remote" in *.wav|*.WAV) ;; *) continue ;; esac
  adb "${adb_args[@]}" pull "$remote" "$out/" >/dev/null && n=$((n+1))
done < "$out/runtime-audio.txt"
echo "  pulled $n wav files"

python3 -m qa audio "$out"
