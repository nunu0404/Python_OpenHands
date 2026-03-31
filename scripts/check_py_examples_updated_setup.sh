#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/common.sh"

DATASET_PATH="${DATASET_PATH:-$ROOT_DIR/py_examples_updated.xlsx}"
CONFIG_FILE="${CONFIG_FILE:-$ROOT_DIR/config.toml}"
LLM_CONFIG="${LLM_CONFIG:-eval}"
LIVE_DIR="${LIVE_DIR:-$ROOT_DIR/SWE-bench-Live-main}"
CHECK_IMAGE_MANIFESTS="${CHECK_IMAGE_MANIFESTS:-1}"
DOCKER_SMOKE_TEST="${DOCKER_SMOKE_TEST:-0}"

if [[ "$DATASET_PATH" != /* ]]; then
  DATASET_PATH="$ROOT_DIR/$DATASET_PATH"
fi

if [[ "$CONFIG_FILE" != /* ]]; then
  CONFIG_FILE="$ROOT_DIR/$CONFIG_FILE"
fi

export DOCKER_HOST="${DOCKER_HOST:-unix:///run/user/$(id -u)/docker.sock}"

inspect_docker_image() {
  local image="$1"

  if docker buildx version >/dev/null 2>&1; then
    docker buildx imagetools inspect "$image" >/dev/null
    return
  fi

  docker manifest inspect "$image" >/dev/null
}

echo "[1/5] Validating Python environment"
project_python - "$DATASET_PATH" "$CONFIG_FILE" "$LLM_CONFIG" <<'PY'
from pathlib import Path
import sys

import pandas as pd
import tomllib

dataset_path = Path(sys.argv[1])
config_path = Path(sys.argv[2])
llm_config = sys.argv[3]

if not ((3, 12) <= sys.version_info[:2] < (3, 14)):
    raise SystemExit(f"Python 3.12 or 3.13 is required, found {sys.version.split()[0]}")

if not dataset_path.is_file():
    raise SystemExit(f"Missing dataset: {dataset_path}")

dataframe = pd.read_excel(dataset_path, engine="openpyxl")
required_columns = {"instance_id", "base_commit", "repo", "docker_image"}
missing = sorted(required_columns - set(dataframe.columns))
if missing:
    raise SystemExit(f"Dataset is missing required columns: {', '.join(missing)}")

if not config_path.is_file():
    raise SystemExit(f"Missing config file: {config_path}")

with config_path.open("rb") as handle:
    config = tomllib.load(handle)

llm_section = config.get("llm", {})
if llm_config == "llm":
    target = llm_section
else:
    target = llm_section.get(llm_config)

if not isinstance(target, dict) or not target.get("model") or not target.get("api_key"):
    raise SystemExit(
        f"Config file does not contain a usable [llm.{llm_config}] section in {config_path}"
    )

if str(target["api_key"]).strip() == "YOUR_API_KEY_HERE":
    raise SystemExit(f"config.toml still contains the placeholder API key in [llm.{llm_config}]")

images = sorted(
    {
        str(value).strip()
        for value in dataframe["docker_image"].tolist()
        if str(value).strip() and str(value).strip().lower() != "nan"
    }
)

print(f"Dataset rows: {len(dataframe)}")
print(f"Unique docker images in dataset: {len(images)}")
for image in images:
    print(image)
PY

echo "[2/5] Validating Docker access"
docker version >/dev/null
docker info >/dev/null

if [ "$DOCKER_SMOKE_TEST" = "1" ]; then
  echo "[3/5] Running Docker smoke test"
  docker run --rm hello-world >/dev/null
else
  echo "[3/5] Skipping Docker smoke test (set DOCKER_SMOKE_TEST=1 to enable)"
fi

if [ "$CHECK_IMAGE_MANIFESTS" = "1" ]; then
  echo "[4/5] Checking dataset docker images"
  mapfile -t docker_images < <(project_python - "$DATASET_PATH" <<'PY'
from pathlib import Path
import sys

import pandas as pd

dataset_path = Path(sys.argv[1])
dataframe = pd.read_excel(dataset_path, engine="openpyxl")
images = sorted(
    {
        str(value).strip()
        for value in dataframe["docker_image"].tolist()
        if str(value).strip() and str(value).strip().lower() != "nan"
    }
)
for image in images:
    print(image)
PY
  )

  for image in "${docker_images[@]}"; do
    inspect_docker_image "$image"
    echo "Verified image: $image"
  done
else
  echo "[4/5] Skipping docker image manifest checks"
fi

echo "[5/5] Checking SWE-bench-Live checkout"
if [ ! -d "$LIVE_DIR" ]; then
  echo "Missing SWE-bench-Live checkout: $LIVE_DIR" >&2
  echo "Clone https://github.com/microsoft/SWE-bench-Live.git into that path before live evaluation." >&2
  exit 1
fi

echo "Preflight checks passed."
