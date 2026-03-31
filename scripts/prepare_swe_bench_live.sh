#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/common.sh"

LIVE_DIR="${LIVE_DIR:-$ROOT_DIR/SWE-bench-Live-main}"
REPOLAUNCH_DIR="$LIVE_DIR/launch"
LIVE_VENV_DIR="${LIVE_VENV_DIR:-$LIVE_DIR/.venv}"
EXPECTED_LAUNCH_COMMIT="$(
  git -C "$ROOT_DIR" ls-files -s SWE-bench-Live-main/launch 2>/dev/null | awk '$1 == "160000" {print $2; exit}'
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
  if git -C "$REPOLAUNCH_DIR" cat-file -e "${EXPECTED_LAUNCH_COMMIT}^{commit}" 2>/dev/null; then
    git -C "$REPOLAUNCH_DIR" checkout "$EXPECTED_LAUNCH_COMMIT"
  elif git -C "$REPOLAUNCH_DIR" fetch origin "$EXPECTED_LAUNCH_COMMIT" >/dev/null 2>&1; then
    git -C "$REPOLAUNCH_DIR" checkout "$EXPECTED_LAUNCH_COMMIT"
  else
    echo "Warning: could not fetch RepoLaunch commit $EXPECTED_LAUNCH_COMMIT; using current checkout $(git -C "$REPOLAUNCH_DIR" rev-parse HEAD)." >&2
  fi
fi

BASE_PYTHON="$(project_python -c 'import sys; print(sys.executable)')"
if [ ! -x "$LIVE_VENV_DIR/bin/python" ]; then
  "$BASE_PYTHON" -m venv "$LIVE_VENV_DIR"
fi

"$LIVE_VENV_DIR/bin/python" -m pip install -e "$LIVE_DIR" -e "$REPOLAUNCH_DIR"

echo "SWE-bench-Live is ready at $LIVE_DIR"
echo "SWE-bench-Live Python: $LIVE_VENV_DIR/bin/python"
