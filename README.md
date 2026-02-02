# OpenHands & SWE-bench Benchmark Repository

이 리포지토리는 OpenHands를 사용하여 SWE-bench (Python/Java) 벤치마크를 실행한 결과와 소스 코드를 포함하고 있습니다.
AI 엔진(`OpenHands-main`)과 벤치마크 실행 스크립트(`MopenHands`)가 분리된 구조를 취하고 있습니다.

## 📂 리포지토리 구조

- **`openhands/`**: OpenHands의 핵심 엔진 (OpenHands v1.2.1 기반)
- **`MopenHands/`**: 벤치마크 실행을 위한 스크립트 모음 (`run_infer.py` 포함)
- **`logs/`**: 벤치마크 실행 전체 로그
- **`results/`**: 벤치마크 최종 결과 (`output.jsonl` 및 상세 로그)
- **`Python_examples.jsonl`**: 테스트에 사용된 Python 문제 데이터셋

---

## 🚀 벤치마크 재현 가이드 (How to Reproduce)

팀원이 이 작업을 그대로 재현하려면 다음 절차를 따르세요.

### 1. 전제 조건 (Prerequisites)
- **Docker**: 실행 중이어야 합니다. (Rootless Docker 권장)
- **Python**: 3.10 이상 버전

### 2. 설치 및 준비 (Setup)

이 리포지토리를 클론(Clone)한 후, 필요한 의존성을 설치하고 환경 변수를 설정합니다.

```bash
# 1. 리포지토리 클론
git clone https://github.com/nunu0404/Python_OpenHands.git
cd Python_OpenHands

# 2. PYTHONPATH 설정 (중요: OpenHands 모듈을 찾기 위함)
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 3. Docker 호스트 설정 (Rootless Docker 사용 시)
# 본인의 Docker 소켓 경로를 확인하세요. (일반적으로 /run/user/{UID}/docker.sock)
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
```

### 3. Python 벤치마크 실행 (Execution)

다음 명령어를 입력하면 벤치마크가 백그라운드에서 실행됩니다.

```bash
# 언어 설정 및 Docker 이미지 사용 설정
export LANGUAGE=python
export USE_INSTANCE_IMAGE=true

# 벤치마크 스크립트 실행
nohup python3 MopenHands/evaluation/benchmarks/swe_bench/run_infer.py \
  --dataset Python_examples.jsonl \
  --split train \
  --config-file config.toml \
  --llm-config eval \
  --agent-cls CodeActAgent \
  --max-iterations 30 \
  > run_infer_python_reproduce.log 2>&1 &
```

### 4. 진행 상황 및 결과 확인

실행 후 다음 명령어로 실시간 로그를 확인할 수 있습니다.

```bash
tail -f run_infer_python_reproduce.log
```

완료된 결과는 `results/` 디렉토리 또는 새로 생성되는 `evaluation/` 디렉토리에서 확인할 수 있습니다.

---

## 🛠️ 주요 수정 사항 (Modifications)

이 리포지토리의 코드는 벤치마크 실행을 위해 다음과 같이 수정되었습니다.

1.  **`MopenHands/.../run_infer.py`**:
    -   Alibaba Cloud Docker Registry 이미지를 사용하도록 경로 수정
    -   `OpenHands-main`의 최신 Config 구조(`AppConfig`)와 호환되도록 Import 구문 수정
    -   Legacy 인자(`codeact_enable_...`)를 최신 인자(`enable_...`)로 변경

2.  **`OpenHands-main/config.toml`**:
    -   GPT-4o 모델(`llm.eval`) 설정을 포함하고 있습니다.

---
**작성자**: nunu0404 & OpenHands Team
