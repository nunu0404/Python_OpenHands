# OpenHands & SWE-bench Benchmark Repository

This repository contains the source code and results for running the SWE-bench (Python) benchmark using OpenHands.
It follows a structure where the core OpenHands engine and the MopenHands benchmark scripts are integrated.

---

## 🚀 How to Reproduce (Step-by-Step Guide)

Follow these steps to reproduce the benchmark execution from scratch.

### Step 0: Prerequisites

**System Requirements:**
- Python 3.11 or higher
- Docker installed and running
- Linux/macOS (for Rootless Docker)
- OpenAI API key or compatible LLM API endpoint

**Docker Setup:**
```bash
# Verify Docker installation
docker --version

# For shared servers, use Rootless Docker
# Check your Docker socket path
ls /run/user/$(id -u)/docker.sock
```

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/nunu0404/Python_OpenHands.git
cd Python_OpenHands
```

---

### Step 2: Install Dependencies

Install required Python packages:

```bash
# Option 1: Using pip
pip install -e .

# Option 2: Using poetry (if available)
poetry install
```

---

### Step 3: Configure API Key

Create your configuration file from the template:

```bash
# Copy template
cp config.toml.template config.toml

# Edit with your API key
nano config.toml  # or use your preferred editor
```

**config.toml example:**
```toml
[llm.eval]
model = "openai/gpt-4o"
base_url = "https://api.openai.com/v1"
api_key = "sk-your-actual-api-key-here"
temperature = 0.0
```

> **Note:** The `config.toml` file is gitignored to protect your API key. Never commit it to Git.

---

### Step 4: Configure Environment Variables

Set up the necessary environment variables:

```bash
# 1. Add current directory to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 2. Set Docker Host (for Rootless Docker)
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"

# 3. Configure benchmark settings
export LANGUAGE=python
export USE_INSTANCE_IMAGE=true
```

---

### Step 5: Execute the Benchmark

Run the benchmark using `nohup` to keep it running in the background:

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

---

### Step 6: Monitor Progress


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
- **`Python_examples.jsonl`**: Benchmark Dataset (6 instances)
- **`Java_examples.jsonl`**: Java Benchmark Dataset (optional)
- **`config.toml.template`**: Configuration template (copy to `config.toml`)
- **`results/`**: Benchmark execution results
- **`logs/`**: Evaluation logs (gitignored)

---

## 📊 Evaluation with SWE-bench-Live

To verify patches using SWE-bench-Live framework:

### Install SWE-bench-Live
```bash
git clone https://github.com/microsoft/SWE-bench-Live.git
cd SWE-bench-Live && pip install -e .
```

### Run Evaluation
```bash
DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock" \
python -m evaluation.evaluation \
  --dataset ../Python_examples.jsonl \
  --platform linux \
  --patch_dir ../results/output.jsonl \
  --output_dir ../logs/swe_bench_eval \
  --workers 2 \
  --overwrite 1
```

---

## 📈 Results

### Benchmark Statistics
- **Dataset**: 6 Python instances
- **Patch Application**: 3/5 successful (60%)
- **Test Pass Rate**: 0/6 (0%)

### Key Findings
- OpenHands successfully generated patches for all instances
- Patch format issues resolved using `data_format.py` filter
- Generated code requires further refinement for test passage

See `results/output.jsonl` for detailed results.

---

