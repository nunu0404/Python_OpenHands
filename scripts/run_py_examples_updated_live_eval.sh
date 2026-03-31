#!/usr/bin/env bash

set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "Usage: $0 /absolute/path/to/output.jsonl" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/common.sh"

LIVE_DIR="${LIVE_DIR:-$ROOT_DIR/SWE-bench-Live-main}"
LIVE_VENV_DIR="${LIVE_VENV_DIR:-$LIVE_DIR/.venv}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)_py_examples_updated}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT_DIR/runs/$RUN_ID}"
OPENHANDS_OUTPUT_JSONL="$1"
DATASET_XLSX="${DATASET_XLSX:-$ROOT_DIR/py_examples_updated.xlsx}"
DATASET_JSONL="${DATASET_JSONL:-$OUTPUT_ROOT/py_examples_updated.from_xlsx.jsonl}"
PREDS_JSON="${PREDS_JSON:-$OUTPUT_ROOT/preds.json}"
LIVE_OUTPUT_DIR="${LIVE_OUTPUT_DIR:-$OUTPUT_ROOT/live_eval}"
PLATFORM="${PLATFORM:-linux}"
SPLIT="${SPLIT:-train}"
LIVE_WORKERS="${LIVE_WORKERS:-1}"
OVERWRITE="${OVERWRITE:-1}"

mkdir -p "$OUTPUT_ROOT"

if [ ! -f "$OPENHANDS_OUTPUT_JSONL" ]; then
  echo "Missing OpenHands output: $OPENHANDS_OUTPUT_JSONL" >&2
  exit 1
fi

if [[ "$DATASET_XLSX" != /* ]]; then
  DATASET_XLSX="$ROOT_DIR/$DATASET_XLSX"
fi

cd "$ROOT_DIR"
project_python "$ROOT_DIR/scripts/xlsx_to_jsonl.py" \
  "$DATASET_XLSX" \
  "$DATASET_JSONL"
project_python "$ROOT_DIR/evaluation/benchmarks/swe_bench/scripts/live/convert_to_live_eval.py" \
  --output_jsonl "$OPENHANDS_OUTPUT_JSONL" \
  --output_json "$PREDS_JSON" \
  --include_model_name

"$ROOT_DIR/scripts/prepare_swe_bench_live.sh"

LIVE_PYTHON="${LIVE_PYTHON:-$LIVE_VENV_DIR/bin/python}"
if [ ! -x "$LIVE_PYTHON" ]; then
  echo "Missing SWE-bench-Live interpreter: $LIVE_PYTHON" >&2
  exit 1
fi

export DOCKER_HOST="${DOCKER_HOST:-unix:///run/user/$(id -u)/docker.sock}"
export PYTHONPATH="$LIVE_DIR:$LIVE_DIR/launch${PYTHONPATH:+:$PYTHONPATH}"
instance_args=()

if [ -n "${INSTANCE_IDS:-}" ]; then
  read -r -a instance_id_array <<< "${INSTANCE_IDS//,/ }"
  instance_args+=(--instance_ids "${instance_id_array[@]}")
fi

"$LIVE_PYTHON" -m evaluation.evaluation \
  --dataset "$DATASET_JSONL" \
  --split "$SPLIT" \
  --platform "$PLATFORM" \
  --patch_dir "$PREDS_JSON" \
  --output_dir "$LIVE_OUTPUT_DIR" \
  --workers "$LIVE_WORKERS" \
  --overwrite "$OVERWRITE" \
  "${instance_args[@]}"

echo "Predictions JSON: $PREDS_JSON"
echo "Live eval output: $LIVE_OUTPUT_DIR"
