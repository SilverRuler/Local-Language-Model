# exo 설치 및 클러스터 구축 매뉴얼

> 작성 기준: M1 MacBook Air (RAM 16GB), macOS 기준
> exo-explore/exo 공식 저장소(main 브랜치) 기준

---

## 1. 사전 준비물

| 항목 | 용도 |
|---|---|
| Xcode | Metal ToolChain 제공 (MLX 컴파일에 필요) |
| Homebrew | 패키지 관리 |
| uv | Python 의존성 관리 및 실행 |
| node | 대시보드(Svelte) 빌드 |
| rust (nightly) | Rust 바인딩 빌드 |
| macmon (pinned fork) | Apple Silicon 하드웨어 모니터링 |

Xcode는 App Store에서 미리 설치해 둘 것. (Metal ToolChain이 없으면 MLX 컴파일 단계에서 실패함)

---

## 2. 설치 절차

### 2-1. Homebrew 설치

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2-2. uv, node 설치

```bash
brew install uv node
```

### 2-3. Rust 설치 (nightly 필수)

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup toolchain install nightly
```

### 2-4. macmon 설치 (Homebrew 버전 대신 pinned fork 사용)

> Homebrew의 `macmon 0.6.1`은 Apple M5에서 크래시가 발생하는 이슈가 있어, 공식 저장소는 특정 커밋의 fork를 cargo로 직접 설치할 것을 권장함.

```bash
cargo install --git https://github.com/vladkens/macmon \
  --rev a1cd06b6cc0d5e61db24fd8832e74cd992097a7d \
  macmon \
  --force
```

### 2-5. 저장소 클론

```bash
git clone https://github.com/exo-explore/exo
cd exo
```

### 2-6. 대시보드 빌드

```bash
cd dashboard && npm install && npm run build && cd ..
```

### 2-7. exo 실행

```bash
uv run exo
```

- 대시보드/API: `http://localhost:52415/`
- 첫 실행 시 `.venv` 생성 + mlx 등 의존성(약 200MB 내외) 다운로드로 인해 수 분 소요될 수 있음. **진행률 표시가 안 뜨므로 멈춘 것처럼 보이지만 정상 동작인 경우가 많음** (3번 트러블슈팅 참고).

---

## 3. 트러블슈팅 (실제 겪었던 사례)

### 증상: `uv run exo` 실행 후 터미널에 한참 동안 아무 출력이 없음

**원인**: mlx 라이브러리(`libmlx.so`, 200MB+) 다운로드 중이나, 진행률 표시줄이 없어 멈춘 것처럼 보임. 네트워크 순단 등으로 `uv`가 임시 디렉토리를 바꿔가며 재시도하는 경우도 있음 (`.tmpXXXXXX` 폴더명이 바뀜).

**확인 방법**:

```bash
# 1) 프로세스가 살아있는지, 뭘 하고 있는지 확인
ps -o pid,stat,%cpu,%mem,command -p <PID>

# 2) 네트워크 연결 확인 (실시간 다운로드 트래픽 확인에 가장 유용)
nettop -p <PID>

# 3) 파일 핸들 확인 (다운로드 중인 파일 경로 확인)
lsof -p <PID> -i
```

`nettop`에서 `bytes_in`이 계속 증가하고 있으면 정상 다운로드 중이므로 그냥 기다리면 됨. `STAT`이 `S+`(대기)인 것도 네트워크 I/O 대기 시 정상.

**주의**: `watch -n 2 'ls -la <임시파일경로>'` 같은 방식으로 특정 임시 파일 하나만 지켜보면, `uv`가 재시도하며 임시 폴더명을 바꾼 경우 옛날 파일을 보고 있는 것이라 크기가 안 늘어나는 것처럼 보일 수 있음. `nettop`으로 프로세스 전체 트래픽을 보는 게 더 정확함.

### 증상: `Ctrl+C`로 끊고 재실행했는데도 반응 없음

깨진 `.venv`가 남아있을 가능성. 정리 후 재시도:

```bash
rm -rf .venv
uv cache clean
uv run -v exo   # verbose로 실행해서 어디서 멈추는지 확인
```

---

## 4. 추후 애플 실리콘 기기 추가 시 클러스터 연동 방법

exo는 **별도 설정 없이 자동 디바이스 디스커버리**를 지원함. 새 기기에서도 동일하게 2번 설치 절차를 그대로 따라 `uv run exo` (또는 macOS 앱)를 실행하기만 하면, 같은 네트워크상의 기존 기기를 자동으로 찾아서 클러스터를 구성함.

### 4-1. 기본 연동

1. 새 기기에서 2번 설치 절차 동일하게 진행
2. `uv run exo` 실행
3. 같은 LAN(또는 Thunderbolt 직결)에 있으면 대시보드(`http://localhost:52415`)에서 자동으로 두 기기가 하나의 클러스터로 묶여 보임
4. 모델을 불러오면 exo가 기기 토폴로지(리소스, 네트워크 지연/대역폭)를 감안해 자동으로 샤딩 배치를 결정함

### 4-2. 연결 방식별 권장 사항

| 방식 | 특징 |
|---|---|
| Thunderbolt 직결 | 지연시간 가장 낮음. 케이블 하나로 두 맥을 직접 연결 |
| 일반 LAN(Wi-Fi/이더넷) | 동작은 하지만 지연시간이 더 큼 |
| RDMA over Thunderbolt 5 | macOS 26.2 이상 + Thunderbolt 5 지원 기기(M4 Pro Mac mini, M4 Max Mac Studio/MacBook Pro, M3 Ultra Mac Studio)에서만 가능. 지연시간 99% 감소 효과 |

### 4-3. RDMA 활성화 (Thunderbolt 5 기기 구입 시)

1. Mac 종료
2. 전원 버튼 10초 이상 눌러 부팅 메뉴 진입
3. "옵션(Options)" 선택 → 복구 모드 진입
4. 유틸리티 메뉴에서 터미널 열기
5. 아래 명령 실행

```bash
rdma_ctl enable
```

6. 재부팅

**주의사항**:
- 클러스터에 참여하는 모든 기기가 서로 Thunderbolt로 물려 있어야 함
- 케이블은 TB5 지원 케이블이어야 함
- Mac Studio에서는 이더넷 포트 옆 Thunderbolt 5 포트는 RDMA용으로 사용 불가
- 소스 빌드로 실행 시 `tmp/set_rdma_network_config.sh` 스크립트로 Thunderbolt Bridge 비활성화 + RDMA 포트 DHCP 설정 필요
- 모든 기기의 macOS 버전(베타 빌드 번호까지)이 정확히 일치해야 RDMA 포트끼리 서로 탐지 가능

### 4-4. 클러스터 격리 (여러 클러스터를 한 네트워크에서 운용할 경우)

기본적으로 같은 네트워크의 exo 인스턴스는 서로 자동으로 묶이므로, 의도치 않게 다른 클러스터와 섞이는 걸 막고 싶으면 네임스페이스를 지정:

```bash
EXO_LIBP2P_NAMESPACE=my-cluster uv run exo
```

macOS 앱에서는 Advanced 설정에서 동일하게 설정 가능.

### 4-5. 참고: 코디네이터 전용 노드

연산 성능이 낮은 기기(예: 구형 기기)를 네트워킹/오케스트레이션 용도로만 쓰고 싶다면:

```bash
uv run exo --no-worker
```

---

## 5. 자주 쓰는 환경 변수

| 변수 | 설명 |
|---|---|
| `EXO_DEFAULT_MODELS_DIR` | 모델 다운로드/캐시 기본 경로 |
| `EXO_MODELS_DIRS` | 추가 모델 저장 경로 (콜론 구분, 공간 부족 시 순서대로 탐색) |
| `EXO_OFFLINE` | 오프라인 모드 (로컬 모델만 사용) |
| `EXO_LIBP2P_NAMESPACE` | 클러스터 격리용 네임스페이스 |
| `EXO_TRACING_ENABLED` | 분산 트레이싱(성능 분석용) 활성화 |

---

## 6. 참고 링크

- 공식 저장소: https://github.com/exo-explore/exo
- macOS 앱 다운로드: https://assets.exolabs.net/EXO-latest.dmg
- 플랫폼 지원 로드맵: https://github.com/exo-explore/exo/blob/main/PLATFORMS.md
