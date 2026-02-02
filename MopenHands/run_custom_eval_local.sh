#!/bin/bash
set -e

# Define absolute path to dataset
DATASET_PATH="/home/seongminju/openhands/Python_examples.jsonl"
MOPENHANDS_DIR="/home/seongminju/openhands/MopenHands"

# Set DOCKER_HOST for rootless docker (based on docker context)
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"

# Enable instance image usage (we are using local image)
export USE_INSTANCE_IMAGE=true

# Force use of local image prefix
# export EVAL_DOCKER_IMAGE_PREFIX="my-local/"

cd "$MOPENHANDS_DIR"

echo "=========================================="
echo "Starting evaluation with gpt-4o-mini..."
echo "=========================================="

./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
    llm.gpt-4o-mini \
    HEAD \
    CodeActAgent \
    3 \
    30 \
    1 \
    "$DATASET_PATH" \
    python

echo "=========================================="
echo "Starting evaluation with gpt-o1-mini..."
echo "=========================================="

./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
    llm.gpt-o1-mini \
    HEAD \
    CodeActAgent \
    3 \
    30 \
    1 \
    "$DATASET_PATH" \
    python

echo "=========================================="
echo "All evaluations completed."
echo "=========================================="
