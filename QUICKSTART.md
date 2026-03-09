# Quick Start: `joke2k__faker-2279`

This is the shortest verified path for a single Python instance.

## 1. Install

```bash
git clone https://github.com/nunu0404/Python_OpenHands.git
cd Python_OpenHands/MopenHands
poetry env use python3.12
poetry install
cp config.template.toml config.toml
```

Add your LLM credentials to `config.toml`.

`MopenHands` requires Python 3.12. If Poetry picks Python 3.13 on your host, switch it to a Python 3.12 interpreter first.

## 2. Export Runtime Settings

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
export USE_INSTANCE_IMAGE=true
export LANGUAGE=python
```

## 3. Optional Manual Environment Check

The verified base image for `faker-2279` is:

```text
crpi-sa60h0lyaf80r3a1.cn-shenzhen.personal.cr.aliyuncs.com/xinzhou1997_env/repoenv_py1:joke2k__faker-2279_linux
```

You can inspect it manually:

```bash
docker run -it --rm \
  -w /testbed \
  crpi-sa60h0lyaf80r3a1.cn-shenzhen.personal.cr.aliyuncs.com/xinzhou1997_env/repoenv_py1:joke2k__faker-2279_linux \
  /bin/bash
```

Then inside the container:

```bash
pwd
python -V
pytest -rA 2>&1 | tee test-output.log
```

The target repo should be at `/testbed`.

## 4. Run OpenHands

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

## 5. What This Repo Now Assumes

- OpenHands runtime code lives under `/openhands/code`
- the repo to patch comes from dataset `working_dir`
- for Python quick tests here, that path is `/testbed`
- the dataset uses the base image tag, not a `*_runtime` tag as the dataset input

For the full 6-instance Python run, use [README.md](./README.md).
