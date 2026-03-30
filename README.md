# Python OpenHands: Complete Installation and Python Evaluation Guide

This repository is the Python counterpart to Harry's Java setup. It is prepared so that Xin's original spreadsheet file `py_examples_updated.xlsx` can be used directly with OpenHands and then evaluated with SWE-bench-Live.

The intended end-to-end path is:

```text
py_examples_updated.xlsx
-> OpenHands inference
-> output.jsonl
-> preds.json
-> SWE-bench-Live evaluation
```

As of March 30, 2026, that full path was re-checked on this machine with a real run:

- the spreadsheet loaded directly
- the dataset `docker_image` field was used directly
- OpenHands produced a non-empty patch
- SWE-bench-Live consumed that patch and finished evaluation successfully

That means the environment and scripts in this repository are wired correctly. A run may still fail benchmark correctness, but the pipeline itself is ready.

## Step 1: Clone the Repository

```bash
git clone https://github.com/nunu0404/Python_OpenHands.git
cd Python_OpenHands
```

## Step 2: Prepare Python 3.12 and Poetry

`MopenHands` in this repository is expected to run with Python 3.12.

If you already have Python 3.12 and Poetry, continue to Step 3.

If not, install them first with the package manager you prefer, then confirm:

```bash
python3.12 --version
poetry --version
```

## Step 3: Install OpenHands Dependencies

```bash
cd MopenHands
poetry env use python3.12
poetry install
cd ..
```

## Step 4: Create the OpenHands Config File

Copy the repository template into the actual OpenHands config location:

```bash
cp config.toml.template MopenHands/config.toml
```

Then edit `MopenHands/config.toml`.

This repository includes two useful config names:

- `[llm.eval]`
- `[llm.gpt-5-mini-ca]`

`gpt-5-mini-ca` is the config name Xin asked for. In the template it maps to `openai/gpt-5-mini`. Set the `base_url` and `api_key` to the provider you actually use in your environment.

Minimal example:

```toml
[llm.gpt-5-mini-ca]
model = "openai/gpt-5-mini"
base_url = "https://api.openai.com/v1"
api_key = "YOUR_API_KEY_HERE"
temperature = 0.0
```

If you want a known working fallback for local smoke tests in this repo, you can also use `[llm.eval]`.

## Step 5: Confirm Docker Works

Both OpenHands and SWE-bench-Live require Docker.

For rootless Docker on Linux, use:

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
docker run --rm hello-world
```

If `hello-world` fails, fix Docker before running the benchmark.

## Step 6: Understand the Dataset Input

The file Xin provided is already included in this repository:

```text
py_examples_updated.xlsx
```

This file is used directly by OpenHands in this repository. No manual conversion is required for inference.

The spreadsheet currently contains 3 Python instances:

- `joke2k__faker-2309`
- `joke2k__faker-2279`
- `aws-cloudformation__cfn-lint-3377`

Each row also contains a `docker_image` field, and this repository is configured to use that field directly when `USE_INSTANCE_IMAGE=true`.

## Step 7: Run the Full Pipeline

From the repository root, run:

```bash
LLM_CONFIG=gpt-5-mini-ca ./scripts/run_py_examples_updated_pipeline.sh
```

This wrapper performs all required stages:

1. runs OpenHands on `py_examples_updated.xlsx`
2. finds the generated `output.jsonl`
3. converts the spreadsheet to local JSONL for live evaluation
4. converts `output.jsonl` to `preds.json`
5. prepares the local SWE-bench-Live harness
6. runs SWE-bench-Live evaluation

By default, all outputs are written under:

```text
runs/<UTC timestamp>_py_examples_updated/
```

## Step 8: Run a Fast Single-Instance Smoke Test

If you want to verify the pipeline before launching all 3 instances, run:

```bash
export SKIP_IDS="joke2k__faker-2309,aws-cloudformation__cfn-lint-3377"
export INSTANCE_IDS=joke2k__faker-2279
LLM_CONFIG=eval MAX_ITERATIONS=10 ./scripts/run_py_examples_updated_pipeline.sh
```

Notes:

- `SKIP_IDS` is used by OpenHands inference
- `INSTANCE_IDS` is used by SWE-bench-Live evaluation
- `MAX_ITERATIONS=10` is just for a fast smoke test

For the real run, remove those filters and increase iterations as needed.

## Step 9: Run OpenHands Only

If you want to run only the OpenHands stage first:

```bash
LLM_CONFIG=gpt-5-mini-ca ./scripts/run_py_examples_updated.sh
```

This script writes `output.jsonl` under `runs/<run_id>/infer/.../output.jsonl`.

## Step 10: Run SWE-bench-Live Only

If you already have `output.jsonl`, run only the live evaluation stage:

```bash
./scripts/run_py_examples_updated_live_eval.sh \
  /absolute/path/to/output.jsonl
```

## Step 11: Direct OpenHands Command

If you want to run the exact OpenHands command without the wrapper, use:

```bash
cd MopenHands
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
export USE_INSTANCE_IMAGE=true
export LANGUAGE=python

poetry run python evaluation/benchmarks/swe_bench/run_infer.py \
  --dataset ../py_examples_updated.xlsx \
  --split train \
  --config-file config.toml \
  --llm-config gpt-5-mini-ca \
  --agent-cls CodeActAgent \
  --max-iterations 30 \
  --eval-num-workers 1 \
  --eval-note py-excel
```

The wrapper scripts in this repository simply automate this plus the live evaluation stage.

## Step 12: Manual Docker Check

If you want to inspect one dataset image manually, use:

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
docker run -it --rm \
  -w /testbed \
  crpi-sa60h0lyaf80r3a1.cn-shenzhen.personal.cr.aliyuncs.com/xinzhou1997_env/repoenv_py1:joke2k__faker-2279_linux \
  /bin/bash
```

Inside the container you can check:

```bash
pwd
python -V
ls /testbed
```

This is only for manual inspection. During benchmark runs, OpenHands handles the runtime automatically.

## Step 13: Helper Scripts in This Repository

The repository now includes these GitHub-facing helper scripts:

- `scripts/run_py_examples_updated.sh`
  - runs OpenHands directly on `py_examples_updated.xlsx`
- `scripts/run_py_examples_updated_live_eval.sh`
  - converts OpenHands output and runs SWE-bench-Live
- `scripts/run_py_examples_updated_pipeline.sh`
  - one-command wrapper for both stages
- `scripts/prepare_swe_bench_live.sh`
  - prepares `SWE-bench-Live-main` and checks out the expected RepoLaunch commit
- `scripts/xlsx_to_jsonl.py`
  - converts the spreadsheet to JSONL for the live evaluation stage

## Step 14: Output Files to Check

After a pipeline run, the main files are:

- `runs/<run_id>/infer/.../output.jsonl`
  - raw OpenHands output with `test_result.git_patch`
- `runs/<run_id>/py_examples_updated.from_xlsx.jsonl`
  - spreadsheet converted for the live harness
- `runs/<run_id>/preds.json`
  - predictions converted to SWE-bench-Live format
- `runs/<run_id>/live_eval/results.json`
  - SWE-bench-Live summary

## Step 15: Important Implementation Notes

This repository was adjusted so that:

- `MopenHands/evaluation/benchmarks/swe_bench/run_infer.py` accepts `.xlsx`
- the dataset `docker_image` field is used directly when present
- the Python repo path comes from the dataset instead of assuming a fixed default
- `py_examples_updated.xlsx` can be used directly without first converting it for OpenHands

For live evaluation, conversion is still needed because SWE-bench-Live expects JSONL or dataset input rather than raw Excel.

## Step 16: Recommended Command for Xin

If Xin wants the single command that best matches the intended workflow in this repository, it is:

```bash
LLM_CONFIG=gpt-5-mini-ca ./scripts/run_py_examples_updated_pipeline.sh
```

If Xin wants to confirm the setup quickly before running all 3 spreadsheet rows, use the smoke test command in Step 8 first.

## Repository Summary

This repository is now organized so that a user can:

1. clone the repo
2. fill in `MopenHands/config.toml`
3. run one command
4. get both OpenHands output and SWE-bench-Live results

That is the Python equivalent of the Java deliverable Harry prepared.
