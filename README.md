# Python OpenHands Reproduction Guide

This repository is set up to run `py_examples_updated.xlsx` through OpenHands, convert the generated patches, and evaluate them with SWE-bench-Live.

The verified path is:

1. Install the root OpenHands repository with the `evaluation` dependency group.
2. Keep your LLM config in the repository-root `config.toml`.
3. Run the wrapper scripts in `scripts/`.

`MopenHands/` is still used for the spreadsheet-aware `run_infer.py`, but the Python environment is now always the repository-root OpenHands environment. That removes the broken mixed-install path that previously came from `cd MopenHands && poetry run ...`.

## Prerequisites

- Python `3.12` or `3.13`
- Docker with access to `unix:///run/user/$(id -u)/docker.sock`
- A working LLM API config in `config.toml`
- A checkout of SWE-bench-Live at `./SWE-bench-Live-main`

## 1. Clone And Install

```bash
git clone https://github.com/nunu0404/Python_OpenHands.git
cd Python_OpenHands
python3 --version  # must be 3.12.x or 3.13.x
poetry env use python3
poetry install --with evaluation
```

The root environment is required because:

- `openhands/` comes from the repository root.
- `py_examples_updated.xlsx` support needs `openpyxl`.
- SWE-bench-Live conversion and evaluation are executed from the same environment.

## 2. Configure The LLM

```bash
cp config.toml.template config.toml
```

Edit `config.toml` and fill in one of the configured sections, for example:

```toml
[llm.eval]
model = "openai/gpt-4o-mini"
base_url = "https://api.openai.com/v1"
api_key = "YOUR_API_KEY_HERE"
temperature = 0.0
```

The wrapper scripts default to `LLM_CONFIG=eval`. You can switch to another section, such as `gpt-5-mini-ca`, by exporting `LLM_CONFIG`.

## 3. Prepare SWE-bench-Live

Clone SWE-bench-Live into the repository root so the wrapper scripts can find it:

```bash
git clone https://github.com/microsoft/SWE-bench-Live.git SWE-bench-Live-main
```

`./scripts/prepare_swe_bench_live.sh` installs SWE-bench-Live and RepoLaunch into an isolated virtual environment at `SWE-bench-Live-main/.venv`. This avoids overwriting the root OpenHands environment after inference.

## 4. Run The Preflight Check

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
./scripts/check_py_examples_updated_setup.sh
```

This verifies:

- `py_examples_updated.xlsx` opens correctly
- `config.toml` contains the requested LLM section
- Docker is reachable
- every `docker_image` embedded in the spreadsheet is resolvable
- `SWE-bench-Live-main` exists

To include a `hello-world` container smoke test:

```bash
DOCKER_SMOKE_TEST=1 ./scripts/check_py_examples_updated_setup.sh
```

## 5. Run Inference

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
LLM_CONFIG=eval ./scripts/run_py_examples_updated.sh
```

Useful overrides:

- `INSTANCE_IDS=joke2k__faker-2279` runs only one instance
- `SKIP_IDS=joke2k__faker-2309,aws-cloudformation__cfn-lint-3377` excludes instances
- `MAX_ITERATIONS=10` reduces agent turns for smoke tests
- `RUN_ID=my_run_name` controls the output directory name

The wrapper prints the exact `output.jsonl` path when the run finishes.

## 6. Run SWE-bench-Live

```bash
./scripts/run_py_examples_updated_live_eval.sh /absolute/path/to/output.jsonl
```

The live-eval wrapper performs these steps:

1. convert `py_examples_updated.xlsx` to JSONL
2. convert OpenHands `output.jsonl` to SWE-bench-Live `preds.json`
3. install SWE-bench-Live and RepoLaunch into `SWE-bench-Live-main/.venv`
4. run `evaluation.evaluation` with the isolated SWE-bench-Live interpreter

## 7. Run The Full Pipeline

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
LLM_CONFIG=eval ./scripts/run_py_examples_updated_pipeline.sh
```

By default the pipeline runs the preflight check first. Set `RUN_PREFLIGHT=0` only if you intentionally want to skip it.

## Outputs

Every run is written under `runs/<RUN_ID>/`.

- Inference artifacts: `runs/<RUN_ID>/infer/`
- OpenHands predictions: `runs/<RUN_ID>/infer/**/output.jsonl`
- Spreadsheet converted to JSONL: `runs/<RUN_ID>/py_examples_updated.from_xlsx.jsonl`
- SWE-bench-Live patch bundle: `runs/<RUN_ID>/preds.json`
- SWE-bench-Live results: `runs/<RUN_ID>/live_eval/`

## Notes

- `py_examples_updated.xlsx` is tracked as a binary file. Do not remove the `.gitattributes` rules for `*.xlsx`.
- The spreadsheet's `docker_image` column is the primary source of truth for runtime images.
- If a row omits `docker_image`, the runner now falls back to the public `swebench/sweb.eval.x86_64.*:latest` convention instead of a user-specific private registry.
