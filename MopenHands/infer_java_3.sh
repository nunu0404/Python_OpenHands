#!/bin/bash

# MopenHands Java Benchmark - 3 Tasks
# Run from: /home/seongminju/openhands/MopenHands

BASE_SCRIPT="./evaluation/benchmarks/swe_bench/scripts/run_infer.sh"

MODEL_CONFIG="eval"
GIT_VERSION="HEAD"
AGENT_NAME="CodeActAgent"
EVAL_LIMIT="3"
MAX_ITER="30"
NUM_WORKERS="1"
LANGUAGE="java"
DATASET="/home/seongminju/openhands/MopenHands/evaluation/benchmarks/swe_bench/data/java_mopenhands.jsonl"

echo "=============================="
echo "MopenHands Java Benchmark"
echo "Model: $MODEL_CONFIG"
echo "Dataset: $DATASET"
echo "Language: $LANGUAGE"
echo "Eval Limit: $EVAL_LIMIT tasks"
echo "=============================="

$BASE_SCRIPT \
    "$MODEL_CONFIG" \
    "$GIT_VERSION" \
    "$AGENT_NAME" \
    "$EVAL_LIMIT" \
    "$MAX_ITER" \
    "$NUM_WORKERS" \
    "$DATASET" \
    "$LANGUAGE"

echo "Java benchmark completed!"
