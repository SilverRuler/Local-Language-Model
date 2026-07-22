# 라즈베리파이 4B 2대 클러스터링 PoC 정리

## 0. 목적

맥미니 4대로 대형 LLM(GPT OSS 120B 등)을 클러스터 구동하는 사례를 보고, 실제 구매 전 저비용으로
"분산 추론 클러스터링 자체가 동작하는가"를 검증하기 위한 선행 테스트.
- 하드웨어: Raspberry Pi 4B (8GB RAM) 2대
- 목표: 모델 자체의 실사용성이 아니라, RPC 기반 레이어 분산 메커니즘의 동작 여부 확인
- 네트워크: 자택 공유기 192.168.3.X 사설망, 두 기기 동등 위치

| 노드 | 역할 | IP |
|---|---|---|
| SR1-21 | 메인 노드 (모델 로드 및 추론 실행) | 192.168.3.21 |
| SR2-22 | 워커 노드 (RPC 서버, 레이어 연산 분담) | 192.168.3.22 |

---

## 1. 라즈비언 OS 세팅

두 기기 모두 Raspberry Pi OS 64비트 기본 설치, IP 고정 등은 사전 완료된 상태로 진행.
(OS 설치 및 IP 세팅은 본 문서 범위 밖)

---

## 2. llama.cpp 설치

### 2-1. 공통 패키지 설치 (양쪽 노드)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git cmake build-essential libcurl4-openssl-dev
```

### 2-2. 클론 및 빌드 (양쪽 노드)

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DGGML_RPC=ON
cmake --build build --config Release -j4
```

- `-DGGML_RPC=ON` 플래그 없이 빌드하면 RPC 관련 바이너리가 생성되지 않으므로 필수.
- `-j4`는 라즈베리파이 4B의 코어 수(4개)에 맞춘 병렬 빌드 옵션.

### 2-3. 빌드 산출물 확인

```bash
ls build/bin/ | grep -E "rpc-server|llama-cli"
```

⚠️ **주의**: 사용 버전(build b10089)에서는 RPC 서버 바이너리 이름이 `rpc-server`가 아니라
**`ggml-rpc-server`** 였음. 버전에 따라 이름이 다를 수 있으니 반드시 `ls`로 실제 파일명 확인 필요.

### 2-4. 클론 실패 시 트러블슈팅

`git clone` 도중 `fatal: could not open '.git/objects/pack/tmp_pack_XXXXX' for reading` 에러가
발생하는 경우, 대부분 디스크(SD카드) 용량 부족이 원인.

```bash
df -h          # 남은 용량 확인
rm -rf llama.cpp
git clone https://github.com/ggml-org/llama.cpp   # 재시도
```

---

## 3. 모델 다운로드 방법

테스트용 소형 모델로 **Qwen3-1.7B, Q4_K_M 양자화**를 사용.
(SLM을 파이에서 실사용할 목적이 아니라, 8GB RAM 안에서 부담 없이 분산 여부를 확인하기 위한 선택)

### 3-1. 주의 — 스플릿 파일 vs 단일 파일

일부 GGUF 리포는 모델을 여러 조각(`00001-of-00002.gguf`, `00002-of-00002.gguf`)으로 나눠 올려두는데,
이 경우 별도 병합 작업(`llama-gguf-split`)이 필요하므로 번거로움.
**병합이 끝난 단일 파일(`qwen3-1.7b-q4_k_m.gguf`, 약 1.28GB)**을 받는 것이 간단.

### 3-2. 다운로드 (SR1, 메인 노드에서만)

```bash
cd ~/llama.cpp
mkdir -p models
wget -O models/qwen3-1.7b-q4_k_m.gguf \
  https://huggingface.co/enacimie/Qwen3-1.7B-Q4_K_M-GGUF/resolve/main/qwen3-1.7b-q4_k_m.gguf
```

다운로드 확인:
```bash
ls -lh models/qwen3-1.7b-q4_k_m.gguf   # 약 1.28GB 확인
```

`models` 폴더는 반드시 `llama.cpp` 디렉토리 **안쪽**에 위치해야 이후 상대경로(`models/...`) 명령이 정상 동작함.
바깥에 받았다면:
```bash
mv models llama.cpp/
```

---

## 4. RPC 연결 방법

### 4-1. 워커 노드(SR2)에서 RPC 서버 실행

세션이 끊겨도 유지되도록 tmux 사용 권장.

```bash
cd ~/llama.cpp
tmux new -s rpc
./build/bin/ggml-rpc-server -H 0.0.0.0 -p 50052
```

- `-H 0.0.0.0`: 모든 인터페이스에서 수신 대기
- `-p 50052`: RPC 포트

tmux 세션에서 빠져나오려면 `Ctrl+B` 후 `D` (세션은 유지된 채 백그라운드로 전환).
재접속: `tmux attach -t rpc`

### 4-2. 검증 결과 (참고)

`Accepted client connection` / `Client connection closed` 로그가 짧게 반복되는 것은
초기 핸드셰이크(메타데이터 교환) 과정에서 나타나는 정상 동작이며, 실제 연산 실패를 의미하지 않음.
분산 연산이 실제로 일어나는지는 로그보다 **워커 노드의 자원 사용량(htop/Netdata)**으로 확인하는 것이 확실함.

---

## 5. 모델 로드 방법 (메인 노드에서 클러스터 추론 실행)

```bash
cd ~/llama.cpp
./build/bin/llama-cli \
  -m models/qwen3-1.7b-q4_k_m.gguf \
  --rpc 192.168.3.22:50052 \
  -ngl 99 \
  -p "안녕"
```

- `--rpc <워커IP>:<포트>`: 원격 RPC 서버 지정
- `-ngl 99`: 원래 GPU 오프로드 레이어 수 옵션이나, RPC 컨텍스트에서는 원격 노드로 넘길 레이어 수로 동작

### 5-1. 검증 완료 사항

- SR1에서 프롬프트 실행 시 SR2의 `ggml-rpc-server` 프로세스 CPU 사용률이 약 90%까지 튀고,
  Load average가 순간적으로 1.5 수준까지 상승하는 것을 htop으로 직접 확인.
- 이는 SR2가 실제로 텐서 연산(레이어 분산 처리)에 참여했다는 명확한 증거.
- **결론: 라즈베리파이 4B 2대 간 llama.cpp RPC 기반 분산 추론은 정상 동작함 (PoC 성공).**

### 5-2. 참고 — 프로세스 중복 확인

동일 포트로 서버를 여러 번 실행했을 경우 좀비 프로세스가 남을 수 있으므로 점검 습관 권장:
```bash
ps aux | grep rpc-server
```

---

## 6. Netdata 연동 방법 (자원 모니터링 대시보드)

### 6-0. exo 시도 및 포기 사유 (참고)

당초 맥미니 클러스터 유튜브 영상에서 본 것과 유사한 대시보드를 위해 **exo** 설치를 시도했으나,
exo의 핵심 모듈(`exo-rs`, Rust/PyO3 바인딩)이 Linux aarch64(라즈베리파이)용 사전 빌드 wheel을
PyPI에 제공하지 않아 `pip install`이 실패함. 공식 설치는 Rust nightly 툴체인 + Node.js 빌드가
필요한 무거운 절차이고, 커뮤니티에서도 라즈베리파이 단독 클러스터에서 인식 오류(0 TFLOPS) 사례가
보고된 바 있어 **exo는 포기하고 Netdata로 대체**함.

### 6-1. 설치 (양쪽 노드 모두)

```bash
wget -O /tmp/netdata-kickstart.sh https://get.netdata.cloud/kickstart.sh
sh /tmp/netdata-kickstart.sh
```

설치 중 클라우드 연동 여부를 묻는 경우, 로컬 대시보드만 사용할 것이므로 skip.

### 6-2. 개별 대시보드 확인

```
http://192.168.3.21:19999
http://192.168.3.22:19999
```

### 6-3. Parent-Child 구조 설정 (SR1을 parent, SR2를 child로 통합)

**API 키 생성 (아무 노드에서나 1회)**
```bash
uuidgen
```

**Parent(SR1) 설정**
```bash
cd /etc/netdata
sudo ./edit-config stream.conf
```
파일 끝에 추가:
```ini
[여기에 생성한 API 키]
    enabled = yes
    allow from = *
```

**Child(SR2) 설정**
```bash
cd /etc/netdata
sudo ./edit-config stream.conf
```
`[stream]` 섹션에 입력:
```ini
[stream]
    enabled = yes
    destination = 192.168.3.21:19999
    api key = 여기에 동일한 API 키
```

**양쪽 재시작**
```bash
sudo systemctl restart netdata
```

### 6-4. 연동 확인

브라우저에서 parent 주소(`http://192.168.3.21:19999`) 접속 후,
사이드바에 SR2-22 노드가 표시되는지 확인. **화면이 이전 그대로 보인다면 브라우저 강력 새로고침
(`Ctrl+Shift+R`) 먼저 시도** — 실제로 이 문제가 캐시 때문이었음.

API로 직접 확인하는 방법(로그 파일보다 확실):
```bash
curl -s http://192.168.3.21:19999/api/v1/info | grep -i mirrored
```
`mirrored_hosts`에 두 노드 이름이 모두 뜨면 연동 성공.

### 6-5. 연동 결과 (참고)

두 노드 연동 후 total 노드 수 1 → 2, 합산 연산력 지표가 약 3600 → 7200 수준으로 증가한 것을 확인.
Netdata 로그는 `journalctl`이 아니라 `/var/log/netdata/` 내 파일(`access.log`, `aclk.log`, `debug.log`)에
남는 구조였음 (설치 버전에 따라 상이할 수 있음).

---

## 7. 재부팅 후 매번 해야 하는 작업 정리

| 항목 | 재부팅 후 필요 여부 | 비고 |
|---|---|---|
| Netdata | 불필요 | systemd 자동 기동, parent-child 연동도 설정 파일 기반으로 자동 유지 |
| SR2 RPC 서버 | **수동 필요** | `tmux new -s rpc` → `./build/bin/ggml-rpc-server -H 0.0.0.0 -p 50052` |
| SR1 모델 로드 | **수동 필요** | `./build/bin/llama-cli -m models/qwen3-1.7b-q4_k_m.gguf --rpc 192.168.3.22:50052 -ngl 99` |

---

## 8. 최종 결론

- **llama.cpp RPC 기반 레이어 분산 클러스터링은 라즈베리파이 4B 2대 환경에서 정상 동작함을 실측 검증 완료.**
- 검증 방법: SR1에서 추론 실행 시 SR2의 CPU 부하 급증 및 Load average 상승을 Netdata/htop으로 직접 확인.
- exo는 ARM(aarch64) 환경에서 Rust 바인딩 사전 빌드 wheel 부재로 설치 불가 → Netdata로 모니터링 대체.
- 이 PoC 결과를 근거로, 맥미니 등 상위 하드웨어로 확장 시 동일한 RPC 분산 메커니즘이 적용 가능하다는
  개념적 확신은 얻었으나, 네트워크 대역폭(라즈베리파이 기가비트 vs 맥미니 Thunderbolt)과 연산력
  (Cortex-A72 vs Apple Silicon) 차이로 인해 체감 속도까지 동일하게 재현될 것이라 단정할 수는 없음.
