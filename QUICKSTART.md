# Quick Start: Xin's Python Spreadsheet

This is the shortest verified path for running Xin's original `py_examples_updated.xlsx` file.

## 1. Install

```bash
git clone https://github.com/nunu0404/Python_OpenHands.git
cd Python_OpenHands/MopenHands
python3.12 --version
poetry env use python3.12
poetry install
cp config.template.toml config.toml
```

Add your LLM credentials to `config.toml`.

`MopenHands` requires Python 3.12. If `python3.12` is not on your host `PATH`, install Python 3.12 first and replace `python3.12` above with the full path to that interpreter.

## 2. Export Runtime Settings

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
export USE_INSTANCE_IMAGE=true
export LANGUAGE=python
```

## 3. Dataset

The original spreadsheet is included at the repository root:

```text
../py_examples_updated.xlsx
```

It contains these three Python instances:

- `joke2k__faker-2309`
- `joke2k__faker-2279`
- `aws-cloudformation__cfn-lint-3377`

## 4. Run OpenHands

From `Python_OpenHands/MopenHands`:

```bash
poetry run python evaluation/benchmarks/swe_bench/run_infer.py \
  --dataset ../py_examples_updated.xlsx \
  --split train \
  --config-file config.toml \
  --llm-config eval \
  --agent-cls CodeActAgent \
  --max-iterations 30 \
  --eval-num-workers 1 \
  --eval-note py-excel
```

## 5. What This Repo Now Assumes

- OpenHands runtime code lives under `/openhands/code`
- the repo to patch comes from dataset `working_dir`
- for Python quick tests here, that path is `/testbed`
- the spreadsheet uses the base image tag, not a `*_runtime` tag as the dataset input
- `run_infer.py` reconstructs the issue text from `PR_Title` and `PR_Body` when `problem_statement` is absent

For the extended JSONL dataset and manual Docker checks, use [README.md](./README.md).
