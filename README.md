# Python OpenHands

This repository contains a Python-focused OpenHands benchmark setup built around `MopenHands/evaluation/benchmarks/swe_bench/run_infer.py`.

As of March 9, 2026, the Python path and runtime flow in this repo has been checked against Xin's intended setup:

- OpenHands runtime starts in `/openhands/code`
- the target repo path comes from the dataset `working_dir`
- Python datasets in this repo use `/testbed`
- the benchmark uses instance-specific base images such as `repoenv_py1:<instance>_linux`

## Verified Behavior

- `run_infer.py` now prefers `working_dir` from the dataset instead of assuming `/workspace/<repo>__<commit>`.
- The prompt clearly distinguishes OpenHands code at `/openhands/code` from the repo to patch at `/testbed`.
- Runtime initialization and completion both `cd` into the dataset-provided repo path.
- `instance_swe_entry.sh` reads `working_dir`, so `/testbed` and `/testbed2` are both supported.
- Python-specific runtime issues that blocked patch attempts were fixed:
  - malformed reproduce scripts created with literal `\\n`
  - accidental removal of valid Python source files during patch cleanup
  - malformed `str_replace_editor` arguments such as `new_str=`

## Setup

1. Clone the repository.

```bash
git clone https://github.com/nunu0404/Python_OpenHands.git
cd Python_OpenHands
```

2. Install `MopenHands` dependencies.

```bash
cd MopenHands
poetry env use python3.12
poetry install
cp config.template.toml config.toml
```

`MopenHands` currently requires Python 3.12. If Poetry selects Python 3.13 or another version on your machine, point it to a Python 3.12 interpreter before running `poetry install`.

3. Edit `MopenHands/config.toml` with your LLM credentials.

Example:

```toml
[llm.eval]
model = "openai/gpt-4o-mini"
base_url = "https://api.openai.com/v1"
api_key = "sk-..."
temperature = 0.0
```

4. Export the benchmark environment variables.

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
export USE_INSTANCE_IMAGE=true
export LANGUAGE=python
```

## Datasets

- `Python_examples.jsonl`
  - 6 Python instances
  - uses verified base images
  - sets `working_dir` to `/testbed`
- `Python_examples_faker2279.jsonl`
  - single-instance quick test
  - also uses `/testbed`

## Run A Quick Test

From `Python_OpenHands/MopenHands`:

```bash
poetry run python evaluation/benchmarks/swe_bench/run_infer.py \
  --dataset ../Python_examples_faker2279.jsonl \
  --split train \
  --config-file config.toml \
  --llm-config eval \
  --agent-cls CodeActAgent \
  --max-iterations 30 \
  --eval-num-workers 1 \
  --eval-note faker2279
```

## Run The Full Python Set

From `Python_OpenHands/MopenHands`:

```bash
poetry run python evaluation/benchmarks/swe_bench/run_infer.py \
  --dataset ../Python_examples.jsonl \
  --split train \
  --config-file config.toml \
  --llm-config eval \
  --agent-cls CodeActAgent \
  --max-iterations 30 \
  --eval-num-workers 1 \
  --eval-note python-full
```

## Logs And Outputs

- OpenHands evaluation output is written under the `--eval-output-dir` you pass to `run_infer.py`.
- Per-instance controller logs are written under `infer_logs/` inside that evaluation output directory.
- The generated patch is stored in `output.jsonl` as `test_result.git_patch`.

## Manual Docker Check

If you want to inspect the target repo manually, use the dataset image and enter `/testbed`:

```bash
docker run -it --rm \
  -w /testbed \
  crpi-sa60h0lyaf80r3a1.cn-shenzhen.personal.cr.aliyuncs.com/xinzhou1997_env/repoenv_py1:joke2k__faker-2279_linux \
  /bin/bash
```

Inside the container:

```bash
pwd
python -V
pytest -rA 2>&1 | tee test-output.log
```

This manual check is only for environment inspection. During benchmark runs, OpenHands itself decides how to reproduce and patch the issue.

## Docker Images

The dataset currently points to instance-specific Python base images of the form:

```text
crpi-sa60h0lyaf80r3a1.cn-shenzhen.personal.cr.aliyuncs.com/xinzhou1997_env/repoenv_py1:<instance_id>_linux
```

These are the images verified in this repo's Python flow, not `*_runtime` tags used directly as dataset inputs.

## Notes

- The path fix ensures the benchmark follows Xin's intended separation between OpenHands code and the target repo.
- The Python 3-instance validation run confirmed the intended runtime flow: instance image selection, `TARGET_REPO_DIR=/testbed`, `cd /testbed`, and patch collection all executed without the old path mismatch.
- This does not guarantee benchmark success. Agent quality and patch quality remain a separate problem.

See [QUICKSTART.md](./QUICKSTART.md) for a shorter single-instance example.
