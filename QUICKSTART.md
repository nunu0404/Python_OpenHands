# Quick Start: faker-2279 Instance

This section provides Docker image and dataset for quick testing of the `faker-2279` instance.

## 🐳 Docker Image

```bash
# Pull the pre-built Docker image
docker pull jsm02404/python-faker:2279_runtime

# (Optional) Rename for convenience
docker tag jsm02404/python-faker:2279_runtime python/faker:2279_runtime
```

## 📦 Available Docker Images

All 6 Python instances are available on DockerHub:

| Instance | Docker Image |
|----------|--------------|
| `joke2k__faker-2279` | `jsm02404/python-faker:2279_runtime` |
| `joke2k__faker-2309` | `jsm02404/python-faker:2309_runtime` |
| `cfn-lint-3377` | `jsm02404/python-cfn-lint:3377_runtime` |
| `cfn-lint-3470` | `jsm02404/python-cfn-lint:3470_runtime` |
| `cfn-lint-3561` | `jsm02404/python-cfn-lint:3561_runtime` |
| `cfn-lint-3994` | `jsm02404/python-cfn-lint:3994_runtime` |

## 📋 Dataset Files

| File | Description |
|------|-------------|
| `Python_examples_faker2279.jsonl` | Single instance (faker-2279) for quick testing |
| `Python_examples.jsonl` | All 6 Python instances |

## 🚀 Quick Test

```bash
# 1. Clone this repo
git clone https://github.com/nunu0404/Python_OpenHands.git
cd Python_OpenHands

# 2. Pull Docker image
docker pull jsm02404/python-faker:2279_runtime

# 3. Configure environment and run benchmark
export PYTHONPATH=$PYTHONPATH:$(pwd)

python3 MopenHands/evaluation/benchmarks/swe_bench/run_infer.py \
  --dataset Python_examples_faker2279.jsonl \
  --split train \
  --config-file config.toml \
  --llm-config eval \
  --agent-cls CodeActAgent \
  --max-iterations 30
```

## 📊 faker-2279 Instance Details

| Field | Value |
|-------|-------|
| **Instance ID** | `joke2k__faker-2279` |
| **Repository** | [joke2k/faker](https://github.com/joke2k/faker) |
| **Language** | Python |
| **FAIL_TO_PASS** | 1 test |
| **PASS_TO_PASS** | 2,178 tests |
| **Per-test Commands** | 4,608 |

---

For full installation guide, see the main [README.md](README.md).
