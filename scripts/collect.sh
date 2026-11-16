#!/usr/bin/env bash
# Collect the two artefacts a perf review needs, from a connected device.
#   ./scripts/collect.sh com.example.slot            # summary + framestats
# Needs: adb on PATH, a device authorised (`adb devices`).
set -euo pipefail
pkg="${1:?usage: collect.sh <package> [serial]}"
serial="${2:-}"
adb_args=()
[ -n "$serial" ] && adb_args=(-s "$serial")
mkdir -p out
adb "${adb_args[@]}" shell dumpsys gfxinfo "$pkg" > out/gfxinfo_summary.txt
adb "${adb_args[@]}" shell dumpsys gfxinfo "$pkg" framestats > out/gfxinfo_framestats.txt
echo "wrote out/gfxinfo_summary.txt and out/gfxinfo_framestats.txt"
python3 -m qa perf out/gfxinfo_framestats.txt
