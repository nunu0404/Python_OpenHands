# Quick Start: Xin's Python Spreadsheet

This is the shortest verified path for `py_examples_updated.xlsx`.

## 1. Install OpenHands

```bash
git clone https://github.com/nunu0404/Python_OpenHands.git
cd Python_OpenHands/MopenHands
python3.12 --version
poetry env use python3.12
poetry install
cd ..
cp config.toml.template MopenHands/config.toml
```

Edit `MopenHands/config.toml` and fill in either `[llm.eval]` or `[llm.gpt-5-mini-ca]`.

## 2. Check Docker

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
docker run --rm hello-world
```

## 3. Run The Full Pipeline

```bash
LLM_CONFIG=gpt-5-mini-ca ./scripts/run_py_examples_updated_pipeline.sh
```

This runs:

- OpenHands on `py_examples_updated.xlsx`
- patch conversion
- SWE-bench-Live evaluation

## 4. Fast Single-Instance Smoke Test

```bash
export SKIP_IDS="joke2k__faker-2309,aws-cloudformation__cfn-lint-3377"
export INSTANCE_IDS=joke2k__faker-2279
LLM_CONFIG=eval MAX_ITERATIONS=10 ./scripts/run_py_examples_updated_pipeline.sh
```

Use [README.md](./README.md) for the separate-stage commands and output file locations.
