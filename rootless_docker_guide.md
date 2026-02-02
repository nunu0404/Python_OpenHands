# 🐳 Rootless Docker 완벽 가이드

> 이 문서는 Docker를 root 권한 없이 실행하는 "Rootless Docker"에 대해 설명합니다.  
> 초보자도 따라할 수 있도록 개념부터 설정 방법, 현재 시스템 상태까지 상세히 정리했습니다.

---

## 📚 목차
1. [Docker란?](#1-docker란)
2. [Root Docker vs Rootless Docker](#2-root-docker-vs-rootless-docker)
3. [Rootless Docker의 작동 원리](#3-rootless-docker의-작동-원리)
4. [Rootless Docker 설치 및 설정 방법](#4-rootless-docker-설치-및-설정-방법)
5. [현재 시스템 (gpusystem) 설정 분석](#5-현재-시스템-gpusystem-설정-분석)
6. [Rootless Docker 사용법](#6-rootless-docker-사용법)
7. [문제 해결 (Troubleshooting)](#7-문제-해결-troubleshooting)
8. [제한 사항](#8-제한-사항)

---

## 1. Docker란?

Docker는 애플리케이션을 **컨테이너**라는 격리된 환경에서 실행할 수 있게 해주는 플랫폼입니다.

### 핵심 구성 요소
| 구성 요소 | 설명 |
|-----------|------|
| **Docker Daemon** | 백그라운드에서 실행되며, 컨테이너와 이미지를 관리하는 서비스 |
| **Docker Client** | 사용자가 명령어를 입력하는 도구 (`docker run`, `docker ps` 등) |
| **Docker Socket** | Client와 Daemon이 통신하는 Unix 소켓 파일 |
| **컨테이너** | 격리된 환경에서 실행되는 애플리케이션 인스턴스 |
| **이미지** | 컨테이너를 생성하기 위한 읽기 전용 템플릿 |

---

## 2. Root Docker vs Rootless Docker

### 2.1 Root Docker (기본 모드)

전통적으로 Docker는 **root 권한**으로 실행됩니다.

```
┌─────────────────────────────────────────┐
│              호스트 시스템                │
│                                         │
│   ┌─────────────────────────────────┐   │
│   │    Docker Daemon (root 권한)     │   │
│   │    PID: 1234, UID: 0 (root)     │   │
│   └─────────────────────────────────┘   │
│              ▲                          │
│              │ 통신                      │
│              ▼                          │
│   ┌─────────────────────────────────┐   │
│   │  /var/run/docker.sock           │   │
│   │  (root 소유, docker 그룹)        │   │
│   └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

**특징:**
- Docker Daemon이 **UID 0 (root)** 권한으로 실행됨
- 소켓 파일: `/var/run/docker.sock`
- 데이터 저장 위치: `/var/lib/docker`
- 시스템 전역 서비스로 실행 (`systemctl start docker`)

**보안 위험:**
- 컨테이너 내부에서 탈출(escape)하면 **호스트의 root 권한**을 획득할 수 있음
- Docker 그룹에 속한 사용자는 사실상 root와 동등한 권한을 가짐
- 커널 취약점 악용 시 전체 시스템 장악 가능

---

### 2.2 Rootless Docker (루트리스 모드)

Rootless Docker는 Docker Daemon과 컨테이너를 **일반 사용자 권한**으로 실행합니다.

```
┌─────────────────────────────────────────┐
│              호스트 시스템                │
│                                         │
│   ┌─────────────────────────────────┐   │
│   │   Docker Daemon (일반 사용자 권한) │   │
│   │   PID: 5678, UID: 1005          │   │
│   │   (seongminju 사용자로 실행)     │   │
│   └─────────────────────────────────┘   │
│              ▲                          │
│              │ 통신                      │
│              ▼                          │
│   ┌─────────────────────────────────┐   │
│   │  /run/user/1005/docker.sock     │   │
│   │  (사용자 소유)                   │   │
│   └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

**특징:**
- Docker Daemon이 **일반 사용자 UID**로 실행됨
- 소켓 파일: `/run/user/<UID>/docker.sock`
- 데이터 저장 위치: `~/.local/share/docker`
- 사용자별 systemd 서비스로 실행 (`systemctl --user start docker`)

**보안 이점:**
- 컨테이너가 탈출해도 **일반 사용자 권한**만 획득
- 다른 사용자의 컨테이너에 영향을 줄 수 없음
- 시스템 전체에 대한 접근 불가

---

### 2.3 비교 표

| 항목 | Root Docker | Rootless Docker |
|------|-------------|-----------------|
| **Daemon 실행 권한** | root (UID 0) | 일반 사용자 (예: UID 1005) |
| **소켓 경로** | `/var/run/docker.sock` | `/run/user/<UID>/docker.sock` |
| **데이터 저장 경로** | `/var/lib/docker` | `~/.local/share/docker` |
| **서비스 관리** | `systemctl start docker` | `systemctl --user start docker` |
| **포트 바인딩** | 모든 포트 사용 가능 | 1024 이상 포트만 기본 사용 가능 |
| **보안 수준** | 낮음 (root 탈출 위험) | 높음 (사용자 권한으로 제한) |
| **다중 사용자** | 공유 환경에서 위험 | 각 사용자별 독립 실행 가능 |

---

## 3. Rootless Docker의 작동 원리

### 3.1 User Namespace

Rootless Docker의 핵심은 **Linux User Namespace**입니다.

```
┌─────────────────────────────────────────────────────┐
│                    호스트 시스템                      │
│                                                     │
│   실제 UID: 1005 (seongminju)                       │
│   실제 GID: 1007                                    │
│                                                     │
│   ┌─────────────────────────────────────────────┐   │
│   │              User Namespace                 │   │
│   │                                             │   │
│   │   컨테이너 내부:                              │   │
│   │   - UID 0 (root) → 호스트 UID 427680       │   │
│   │   - UID 1       → 호스트 UID 427681       │   │
│   │   - ...                                    │   │
│   │   - UID 65535   → 호스트 UID 493215       │   │
│   │                                             │   │
│   │   ※ 컨테이너 안에서는 root처럼 보이지만,       │   │
│   │     호스트에서는 일반 사용자 권한만 가짐        │   │
│   └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 3.2 subuid/subgid 매핑

`/etc/subuid`와 `/etc/subgid` 파일이 UID/GID 매핑을 정의합니다.

```bash
# /etc/subuid 예시
seongminju:427680:65536
```

이 설정의 의미:
- `seongminju` 사용자가
- `427680`부터 시작하는
- `65536`개의 subordinate UID를 사용할 수 있음

컨테이너 내부 UID 0 → 호스트 UID 427680으로 매핑됨

---

## 4. Rootless Docker 설치 및 설정 방법

### 4.1 사전 요구사항

```bash
# 1. uidmap 패키지 설치 (Ubuntu/Debian)
sudo apt install -y uidmap

# 2. dbus-user-session 설치
sudo apt install -y dbus-user-session

# 3. subuid/subgid 설정 확인
cat /etc/subuid | grep $(whoami)
cat /etc/subgid | grep $(whoami)
# 출력 예: seongminju:427680:65536
# 만약 없으면 관리자에게 추가 요청 필요
```

### 4.2 기존 Root Docker 비활성화 (선택사항)

```bash
# 시스템 전역 Docker 서비스 중지 (관리자 권한 필요)
sudo systemctl disable --now docker.service docker.socket
```

### 4.3 Rootless Docker 설치

```bash
# Docker 설치 스크립트 실행 (root 권한 필요)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Rootless 설정 도구 실행 (일반 사용자로)
dockerd-rootless-setuptool.sh install
```

### 4.4 환경 변수 및 PATH 설정

설치 스크립트가 출력하는 내용을 `~/.bashrc`에 추가:

```bash
# ~/.bashrc에 추가
export PATH=/usr/bin:$PATH
export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock
```

또는 **Docker Context**를 사용하면 환경변수 없이도 사용 가능:

```bash
docker context use rootless
```

### 4.5 Systemd 서비스 활성화

```bash
# 사용자 레벨 systemd 서비스 시작 및 자동 시작 설정
systemctl --user enable docker
systemctl --user start docker

# 로그아웃 후에도 서비스 유지 (선택사항)
sudo loginctl enable-linger $(whoami)
```

---

## 5. 현재 시스템 (gpusystem) 설정 분석

### 5.1 시스템 개요

| 항목 | 값 |
|------|-----|
| **호스트명** | gpusystem |
| **OS** | Ubuntu 22.04.3 LTS |
| **커널** | 5.15.0-163-generic |
| **Docker 버전** | 24.0.2 |
| **현재 사용자** | seongminju |
| **UID/GID** | 1005 / 1007 |
| **CPU** | 96 코어 |
| **메모리** | 503.5 GiB |

### 5.2 Docker Context 설정

```bash
$ docker context ls
NAME         DESCRIPTION                               DOCKER ENDPOINT                     
default      Current DOCKER_HOST based configuration   unix:///var/run/docker.sock         
rootless *   Rootless mode                             unix:///run/user/1005/docker.sock   
```

> ✅ `rootless` context가 활성화되어 있음 (`*` 표시)

### 5.3 Docker Socket 위치

| 모드 | 소켓 경로 |
|------|----------|
| Root Docker | `/var/run/docker.sock` |
| **Rootless Docker (현재)** | `/run/user/1005/docker.sock` |

```bash
$ ls -la /run/user/1005/docker.sock
srw-rw---T 1 seongminju 428678 0 Jan 27 08:05 /run/user/1005/docker.sock
```

### 5.4 subuid/subgid 설정

```bash
$ cat /etc/subuid | grep seongminju
seongminju:427680:65536

$ cat /etc/subgid | grep seongminju
seongminju:427680:65536
```

> ✅ 65,536개의 subordinate UID/GID가 할당됨 (427680 ~ 493215)

### 5.5 Systemd 서비스 상태

```bash
$ systemctl --user status docker
● docker.service - Docker Application Container Engine (Rootless)
     Loaded: loaded (/home/seongminju/.config/systemd/user/docker.service; enabled)
     Active: active (running) since Tue 2026-01-27 08:06:00 UTC
```

서비스 파일 위치: `/home/seongminju/.config/systemd/user/docker.service`

### 5.6 Docker 데이터 저장 위치

```
~/.local/share/docker/
├── buildkit/
├── containers/
├── image/
├── network/
├── overlay2/
├── plugins/
├── runtimes/
├── swarm/
├── tmp/
├── trust/
└── volumes/
```

### 5.7 daemon.json 설정

```bash
$ cat ~/.config/docker/daemon.json
{
  "dns": ["8.8.8.8", "8.8.4.4"]
}
```

> Google Public DNS를 사용하도록 설정됨

### 5.8 현재 컨테이너 상태

```
$ docker info | grep Containers
 Containers: 74
  Running: 11
  Paused: 0
  Stopped: 63
```

---

## 6. Rootless Docker 사용법

### 6.1 기본 명령어

Root Docker와 **명령어는 동일**합니다:

```bash
# 컨테이너 실행
docker run -it ubuntu:22.04 bash

# 이미지 빌드
docker build -t myimage .

# 컨테이너 목록 확인
docker ps -a

# 이미지 목록 확인
docker images
```

### 6.2 DOCKER_HOST 환경변수 사용

스크립트에서 명시적으로 지정할 때:

```bash
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
docker ps
```

### 6.3 Docker Context 사용 (권장)

```bash
# rootless context로 전환
docker context use rootless

# default (root) context로 전환
docker context use default

# 현재 context 확인
docker context show
```

### 6.4 OpenHands에서 사용하기

OpenHands 실행 스크립트 예시 (`infer_java.sh`):

```bash
#!/bin/bash

# Rootless Docker 소켓 설정
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"

# 실행
poetry run python3 evaluation/benchmarks/multi_swe_bench/run_infer.py ...
```

---

## 7. 문제 해결 (Troubleshooting)

### 7.1 "Cannot connect to Docker daemon" 오류

```bash
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
```

**해결 방법:**
```bash
# 1. Rootless Docker 서비스 상태 확인
systemctl --user status docker

# 2. 서비스 시작
systemctl --user start docker

# 3. DOCKER_HOST 환경변수 설정
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"

# 또는 context 전환
docker context use rootless
```

### 7.2 "permission denied" 오류

```bash
permission denied while trying to connect to Docker daemon socket
```

**해결 방법:**
```bash
# 소켓 권한 확인
ls -la /run/user/$(id -u)/docker.sock

# 소켓이 없으면 서비스 재시작
systemctl --user restart docker
```

### 7.3 포트 1024 이하 바인딩 불가

Rootless 모드에서는 기본적으로 1024 이하 포트 사용 불가:

```bash
# 오류 예시
docker: Error response from daemon: driver failed programming external connectivity: 
Error starting userland proxy: listen tcp 0.0.0.0:80: bind: permission denied
```

**해결 방법:**
```bash
# 방법 1: 높은 포트 사용
docker run -p 8080:80 nginx

# 방법 2: net.ipv4.ip_unprivileged_port_start 설정 (관리자 권한 필요)
sudo sysctl net.ipv4.ip_unprivileged_port_start=80
```

### 7.4 로그아웃 시 Docker 중지됨

```bash
# 로그아웃 후에도 서비스 유지
sudo loginctl enable-linger $(whoami)
```

---

## 8. 제한 사항

### 8.1 Rootless Docker의 한계

| 제한 사항 | 설명 | 해결 방법 |
|-----------|------|----------|
| **포트 제한** | 1024 이하 포트 기본 사용 불가 | 높은 포트 사용 또는 sysctl 설정 |
| **Cgroup 제한** | 일부 리소스 제한 기능 미지원 | 현재 시스템에서 발생하는 WARNING 참조 |
| **네트워크 성능** | slirp4netns 사용으로 약간의 오버헤드 | 대부분의 경우 무시 가능 |
| **호스트 네트워크** | `--network host` 제한적 | Bridge 네트워크 사용 |

### 8.2 현재 시스템의 Warning 메시지

```
WARNING: No cpu cfs quota support
WARNING: No cpu cfs period support
WARNING: No cpu shares support
WARNING: No cpuset support
WARNING: No io.weight support
```

> ⚠️ 이 경고들은 Rootless 모드에서의 Cgroup v2 제한으로 인한 것이며, **일반적인 사용에는 문제없음**

---

## 📝 Quick Reference Card

```bash
# === Rootless Docker 필수 명령어 ===

# 서비스 시작
systemctl --user start docker

# 서비스 상태 확인
systemctl --user status docker

# Context 전환
docker context use rootless

# 현재 Context 확인
docker context ls

# DOCKER_HOST 설정 (스크립트용)
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"

# 소켓 위치 확인
ls -la /run/user/$(id -u)/docker.sock
```

---

## 🔗 참고 자료

- [Docker 공식 문서: Rootless mode](https://docs.docker.com/engine/security/rootless/)
- [Docker 공식 문서: Post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/)
- [Linux User Namespaces 설명](https://man7.org/linux/man-pages/man7/user_namespaces.7.html)

---

> 📅 문서 작성일: 2026-01-27  
> 🖥️ 기준 시스템: gpusystem (Ubuntu 22.04.3 LTS)  
> 🐳 Docker 버전: 24.0.2
