#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)_py_examples_updated}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$ROOT_DIR/runs/$RUN_ID}"
RUN_PREFLIGHT="${RUN_PREFLIGHT:-1}"

export RUN_ID
export OUTPUT_ROOT

if [ "$RUN_PREFLIGHT" != "0" ]; then
  "$ROOT_DIR/scripts/check_py_examples_updated_setup.sh"
fi

"$ROOT_DIR/scripts/run_py_examples_updated.sh"

OPENHANDS_OUTPUT_JSONL="$(find "$OUTPUT_ROOT/infer" -type f -name output.jsonl | sort | tail -n 1)"

if [ -z "$OPENHANDS_OUTPUT_JSONL" ]; then
  echo "Could not find output.jsonl under $OUTPUT_ROOT/infer" >&2
  exit 1
fi

"$ROOT_DIR/scripts/run_py_examples_updated_live_eval.sh" "$OPENHANDS_OUTPUT_JSONL"

echo "Pipeline complete under $OUTPUT_ROOT"
