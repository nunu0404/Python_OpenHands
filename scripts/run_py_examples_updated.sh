#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOPENHANDS_DIR="$ROOT_DIR/MopenHands"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)_py_examples_updated}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT_DIR/runs/$RUN_ID}"
INFER_OUTPUT_DIR="${INFER_OUTPUT_DIR:-$OUTPUT_ROOT/infer}"
DATASET_PATH="${DATASET_PATH:-$ROOT_DIR/py_examples_updated.xlsx}"
LLM_CONFIG="${LLM_CONFIG:-eval}"
AGENT_CLS="${AGENT_CLS:-CodeActAgent}"
MAX_ITERATIONS="${MAX_ITERATIONS:-30}"
NUM_WORKERS="${NUM_WORKERS:-1}"
EVAL_NOTE="${EVAL_NOTE:-py-excel}"
CONFIG_FILE="${CONFIG_FILE:-config.toml}"

export DOCKER_HOST="${DOCKER_HOST:-unix:///run/user/$(id -u)/docker.sock}"
export USE_INSTANCE_IMAGE="${USE_INSTANCE_IMAGE:-true}"
export LANGUAGE="${LANGUAGE:-python}"

mkdir -p "$OUTPUT_ROOT"

cd "$MOPENHANDS_DIR"
poetry run python evaluation/benchmarks/swe_bench/run_infer.py \
  --dataset "$DATASET_PATH" \
  --split train \
  --config-file "$CONFIG_FILE" \
  --llm-config "$LLM_CONFIG" \
  --agent-cls "$AGENT_CLS" \
  --max-iterations "$MAX_ITERATIONS" \
  --eval-num-workers "$NUM_WORKERS" \
  --eval-output-dir "$INFER_OUTPUT_DIR" \
  --eval-note "$EVAL_NOTE"

OUTPUT_JSONL="$(find "$INFER_OUTPUT_DIR" -type f -name output.jsonl | sort | tail -n 1)"

echo "Run root: $OUTPUT_ROOT"
echo "OpenHands output: $OUTPUT_JSONL"
