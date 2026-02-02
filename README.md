# OpenHands & SWE-bench Benchmark Repository

This repository contains the source code and results for running the SWE-bench (Python) benchmark using OpenHands.
It follows a structure where the core OpenHands engine and the MopenHands benchmark scripts are integrated.

---

## 🚀 How to Reproduce (Step-by-Step Guide)

Follow these steps faithfully to reproduce the benchmark execution using `Python_examples.jsonl`.

### Step 1: Clone the Repository

Clone this repository to your local machine.

```bash
git clone https://github.com/nunu0404/Python_OpenHands.git
cd Python_OpenHands
```

### Step 2: Configure Environment Variables

Set up the necessary environment variables for OpenHands and Docker.
*Note: Ensure you are using Rootless Docker if on a shared server.*

```bash
# 1. Add current directory to PYTHONPATH so OpenHands modules can be found
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 2. Set Docker Host (Check your user ID with `id -u`)
# Example: unix:///run/user/1005/docker.sock
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
```

### Step 3: Configure Benchmark Settings

Export the language and image settings required for the python benchmark.

```bash
export LANGUAGE=python
export USE_INSTANCE_IMAGE=true
```

### Step 4: Execute the Benchmark

Run the `run_infer.py` script using `nohup` to keep it running in the background.
We use the provided `Python_examples.jsonl` dataset.

```bash
nohup python3 MopenHands/evaluation/benchmarks/swe_bench/run_infer.py \
  --dataset Python_examples.jsonl \
  --split train \
  --config-file config.toml \
  --llm-config eval \
  --agent-cls CodeActAgent \
  --max-iterations 30 \
  > run_infer_python_reproduce.log 2>&1 &
```

### Step 5: Monitor Progress

Check the log file to see the progress of the benchmark.

```bash
tail -f run_infer_python_reproduce.log
```

### Step 6: Verify Results

Once completed, check the results in the `results/` directory.

- **Summary File**: `results/output.jsonl` (Contains pass/fail status)
- **Detailed Logs**: `results/infer_logs/` (Per-instance execution logs)

---

## 📂 Repository Structure

- **`openhands/`**: Core OpenHands Engine (v1.2.1)
- **`MopenHands/`**: Benchmark Scripts (contains `run_infer.py`)
- **`logs/`**: Execution Logs
- **`results/`**: Benchmark Results
- **`Python_examples.jsonl`**: Benchmark Dataset
