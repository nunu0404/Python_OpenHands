# Quick Start: `py_examples_updated.xlsx`

This is the shortest reproducible path that matches the current scripts.

## 1. Install The Root Environment

```bash
git clone https://github.com/nunu0404/Python_OpenHands.git
cd Python_OpenHands
python3 --version  # must be 3.12.x or 3.13.x
poetry env use python3
poetry install --with evaluation
cp config.toml.template config.toml
git clone https://github.com/microsoft/SWE-bench-Live.git SWE-bench-Live-main
```

Edit `config.toml` and fill in `[llm.eval]` or another `llm` profile.

## 2. Verify The Setup

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
./scripts/check_py_examples_updated_setup.sh
```

## 3. Fast Single-Instance Smoke Test

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
INSTANCE_IDS=joke2k__faker-2279 MAX_ITERATIONS=10 LLM_CONFIG=eval \
  ./scripts/run_py_examples_updated.sh
```

## 4. Full Pipeline

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
LLM_CONFIG=eval ./scripts/run_py_examples_updated_pipeline.sh
```

## 5. Live Evaluation Only

```bash
./scripts/run_py_examples_updated_live_eval.sh /absolute/path/to/output.jsonl
```

`INSTANCE_IDS` now works for inference filtering, and `SKIP_IDS` remains available for exclusions.
