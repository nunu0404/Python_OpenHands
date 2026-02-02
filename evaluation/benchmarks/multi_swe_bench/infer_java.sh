#!/bin/bash

# Configuration
export AGENT="CodeActAgent"
export LLM_CONFIG="eval"
export MAX_ITER=30
export LANGUAGE="java"
export EVAL_LIMIT=3
export NUM_WORKERS=1
export USE_INSTANCE_IMAGE="true" # Use instance-specific Docker images

# Force model name with provider for Litellm
export LLM_MODEL="openai/gpt-4o"
# Dataset path - SWE-bench-Live MultiLang
export DATASET="/home/seongminju/openhands/OpenHands-main/evaluation/benchmarks/multi_swe_bench/processed_java_dataset.jsonl"
export SPLIT="train" # Local json loading usually defaults to 'train' split 

# Set PYTHONPATH to include current directory
export PYTHONPATH="${PYTHONPATH:+${PYTHONPATH}:}$(pwd)"

# Use Rootless Docker (required for non-root users)
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"

# GPU Configuration
export CUDA_VISIBLE_DEVICES=1

# Run evaluation
poetry run python3 evaluation/benchmarks/multi_swe_bench/run_infer.py \
  --agent-cls $AGENT \
  --llm-config $LLM_CONFIG \
  --max-iter $MAX_ITER \
  --eval-n-limit $EVAL_LIMIT \
  --eval-num-workers $NUM_WORKERS \
  --dataset $DATASET \
  --split $SPLIT
