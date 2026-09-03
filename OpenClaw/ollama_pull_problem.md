# Ollama Pull 실패 문제 정리 (2026-07-24)

## 증상

`gemma4:e4b` 모델을 `ollama pull` 또는 `ollama run`으로 받으려 할 때 반복적으로 아래 에러 발생:

```
Error: open /mnt/g/ollama/models/blobs/sha256-4c27e0f5b5adf02ac956c7322bd2ee7636fe3f45a8512c9aba5385242cb6e09a-partial-0: permission denied
```

- `qwen3:4b`는 정상적으로 pull 성공
- `sudo rm -rf`로 partial 파일 삭제 후 재시도해도 동일 에러 재현
- `ollama ps`로 실행 중인 모델 없음을 확인해도 동일 에러 재현
- `OLLAMA_MODELS` 환경변수를 클라이언트 명령어 앞에 붙여도 동일 경로(`/mnt/g/...`)로 계속 시도됨

## 원인 조사 과정

1. **환경변수 오해 정정**
   `OLLAMA_MODELS=~/ollama-test ollama pull ...` 형태로 실행해도 소용없었음. `ollama pull`은 실제 다운로드를 수행하는 주체가 아니라, 백그라운드에서 이미 돌고 있는 `ollama serve` 데몬에게 API 요청만 보내는 클라이언트임. 실제 저장 경로는 **서버 프로세스가 기동될 때 가진 환경변수**(`/mnt/g/ollama/models`)를 그대로 따름. 클라이언트 쪽 env var 설정은 서버에 전혀 영향을 주지 않음.

2. **서비스 실행 계정 확인**
   `ps aux` 결과 `ollama serve` 및 `llama-server`가 **`ollama`라는 별도 리눅스 계정**으로 실행 중임을 확인. 사용자는 `base` 계정으로 작업 중이었음.

3. **핵심 원인 특정**
   ```
   sudo -u ollama touch /mnt/g/ollama/models/blobs/test_write
   → touch: cannot touch '...': Permission denied
   ```
   `blobs` 디렉토리 자체의 소유권/권한:
   ```
   drwxr-xr-x 1 base base ... blobs/
   ```
   디렉토리가 `base:base` 소유이며 권한이 `755`(소유자만 쓰기 가능, 그룹·기타는 읽기+실행만 가능)였음. `ollama` 계정은 `base` 그룹에 속해 있지 않아 이 디렉토리에 **새 파일을 생성(write)할 권한이 없었음**.

   반면 디렉토리 내 기존 blob 파일들은 `ollama:ollama` 소유로 되어 있어, 과거 어느 시점엔 `ollama` 계정이 이 디렉토리에 정상적으로 쓸 수 있었던 것으로 추정됨. 이후 디렉토리 자체가 재생성되거나 권한이 리셋되면서(`sudo rm -rf` 또는 다른 경로로 인한 재생성 등) 소유권이 `base:base`, 권한이 `755`로 바뀌었고, 그 시점부터 `ollama` 계정의 새 파일 생성만 조용히 막혀 있었던 것으로 판단됨.

   - **읽기 전용 작업(기존 모델 로드, 추론 실행)**: 문제없이 동작 → 그룹/기타에도 읽기(`r-x`) 권한은 있었기 때문
   - **쓰기 작업(신규 모델 pull)**: 실패 → 그룹/기타 쓰기 권한 없음

4. **참고로 배제된 가설들**
   - `/mnt/g`가 9p(DrvFs) 마운트라는 점 자체(디렉토리 락, 캐시 문제 등)는 추가 조사 결과 직접 원인 아니었음
   - Windows Defender 등 백신의 파일 잠금 가능성도 배제됨 (권한 문제로 최종 확인됨)
   - 실행 중인 모델이 파일을 점유하고 있어서 생기는 충돌 가능성도 배제됨 (`ollama ps` 비어있는 상태에서도 재현됐음)

## 해결 방법

1. `ollama` 계정을 `base` 그룹에 추가:
   ```
   sudo usermod -aG base ollama
   sudo systemctl restart ollama
   ```
2. 디렉토리 권한 보강 (그룹 쓰기 허용):
   ```
   sudo chmod -R 775 /mnt/g/ollama
   ```
3. 위 조치 후 `ollama pull gemma4:e4b` 재시도 → 정상적으로 다운로드 시작됨

## 남은 의문 / 향후 확인 사항

- 디렉토리 소유권이 정확히 언제, 어떤 명령/이벤트로 인해 `base:base`, `755`로 바뀌었는지는 로그 부재로 특정하지 못함. WSL 재시작, Windows 쪽 파일 조작, 혹은 이전 `sudo` 명령 실행 이력 등이 후보로 추정됨.
- `/mnt/g`는 9p(DrvFs) 마운트 특성상 `chmod`가 완전히 반영되지 않는 경우가 있어, 이번 조치로 근본 해결이 안 될 경우 다음 대안 고려:
  - `ollama serve`를 `base` 계정으로 실행하도록 systemd 유닛 수정 (`systemctl edit ollama` → `User=base`, `Group=base`)
  - 모델 저장 경로 자체를 WSL 네이티브 ext4 파티션으로 이전 (`wsl --mount`로 별도 ext4 파티션을 직접 마운트하는 방식이 DrvFs보다 안정적)
