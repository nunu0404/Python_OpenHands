#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIVE_DIR="${LIVE_DIR:-$ROOT_DIR/SWE-bench-Live-main}"
LIVE_PYTHON="${LIVE_PYTHON:-python}"
REPOLAUNCH_DIR="$LIVE_DIR/launch"
EXPECTED_LAUNCH_COMMIT="$(
  git -C "$ROOT_DIR" ls-files -s SWE-bench-Live-main/launch 2>/dev/null | awk '{print $2}'
)"

if [ ! -d "$LIVE_DIR" ]; then
  echo "Missing SWE-bench-Live checkout: $LIVE_DIR" >&2
  exit 1
fi

if [ ! -d "$REPOLAUNCH_DIR/launch" ]; then
  rm -rf "$REPOLAUNCH_DIR"
  git clone --depth 1 https://github.com/microsoft/RepoLaunch "$REPOLAUNCH_DIR"
fi

if [ -n "$EXPECTED_LAUNCH_COMMIT" ]; then
  git -C "$REPOLAUNCH_DIR" fetch origin "$EXPECTED_LAUNCH_COMMIT"
  git -C "$REPOLAUNCH_DIR" checkout "$EXPECTED_LAUNCH_COMMIT"
fi

"$LIVE_PYTHON" -m pip install -e "$LIVE_DIR" -e "$REPOLAUNCH_DIR"

echo "SWE-bench-Live is ready at $LIVE_DIR"
