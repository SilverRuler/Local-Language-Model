# WSL2에 OpenClaw 네이티브(Docker 미사용) 설치 가이드

> 도커 기반 OpenClaw에서 경로 문제로 스트레스 받아서 WSL2 네이티브 설치로 전환하며 겪은 시행착오 전체 기록.
> 다음에 재설치할 때는 이 문서 순서대로만 따라가면 됨.

---

## 0. 왜 네이티브인가

Docker 방식은 볼륨 마운트/경로 매핑 문제가 계속 발생. OpenClaw는 Node.js 기반이라 컨테이너 레이어 없이 WSL2 Ubuntu에 직접 설치해도 전혀 문제 없음. 상시 구동은 pm2나 systemd로 대체 가능.

---

## 1. 사전 준비 — WSL2 & systemd

```bash
lsb_release -a
```

systemd가 꺼져 있으면 나중에 서비스 등록이 번거로우므로 미리 켜둔다.

```bash
sudo tee /etc/wsl.conf > /dev/null << 'EOF'
[boot]
systemd=true
[automount]
enabled=true
options="metadata,umask=22,fmask=11"
[network]
generateResolvConf=true
EOF
```

PowerShell에서:
```powershell
wsl --shutdown
```
이후 Ubuntu 재실행.

---

## 2. Node.js 22+ 설치 (nvm)

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install 22
nvm alias default 22
node --version
```

---

## 3. OpenClaw 설치

둘 중 하나:

```bash
# 방식 A: 공식 인스톨러 스크립트
curl -fsSL https://openclaw.ai/install.sh | bash

# 방식 B: npm 전역 설치
npm install -g openclaw@latest
```

---

## 4. 온보딩 — `openclaw` 단독 실행과 헷갈리지 말 것

> ⚠️ **시행착오 #1**: `openclaw` 명령어만 치면 온보딩 마법사가 아니라 바로 TUI(대시보드)가 뜬다. 온보딩은 별도 명령어다.

```bash
openclaw onboard --classic
```

`--classic`을 붙여야 모델/인증, 워크스페이스, 게이트웨이, 채널(텔레그램 등)을 하나씩 물어보는 전체 마법사가 나온다. `--classic` 없이 `openclaw onboard`만 치면 QuickStart/Advanced 선택 화면부터 시작.

기존 설정이 남아있어서 온보딩이 자꾸 스킵된다면:
```bash
cat ~/.openclaw/openclaw.json   # 내용 확인
rm ~/.openclaw/openclaw.json    # 필요시 초기화 후 재실행
openclaw onboard --classic
```

---

## 5. 대시보드 외부 접속 — Gateway Bind 설정

> ⚠️ **시행착오 #2**: 최신 OpenClaw는 `gateway.bind`에 `"0.0.0.0"` 같은 raw IP를 직접 넣는 걸 금지한다(legacy 취급, validation 실패). **named bind mode**를 써야 한다.

`~/.openclaw/openclaw.json` 수정:

```json
{
  "gateway": {
    "bind": "lan",
    "port": 18789,
    "controlui": {
      "allowedOrigins": [
        "https://oc.silverruler.xyz",
        "http://oc.silverruler.xyz",
        "http://152.67.210.39:18789",
        "http://127.0.0.1:18789",
        "http://localhost:18789",
        "http://10.8.0.14:18789",
        "http://172.17.98.249:18789"
      ],
      "allowInsecureAuth": true
    }
  }
}
```

- `bind: "lan"` = `0.0.0.0` 바인딩을 의미하는 모드명.
- `lan`(비loopback) 바인딩은 **인증 설정 없이는 게이트웨이가 시작 자체를 거부**한다 (fail-closed). 토큰 인증이 켜져 있는지 확인할 것.
- **allowedOrigins**: 브라우저로 대시보드 접속 시 origin 체크에 걸린다. 접속할 모든 도메인/IP를 여기 추가해야 함.

재시작:
```bash
openclaw gateway restart
```

확인:
```bash
netstat -tulpn | grep 18789
# tcp  0  0  0.0.0.0:18789  0.0.0.0:*  LISTEN  ...  로 바뀌어야 정상
```

> 참고: WSL2 밖(같은 공유기의 다른 기기 등)에서 접속해야 하는 경우, WSL2 자체 NAT 특성상 Windows 쪽 포트포워딩(`netsh interface portproxy`)이 추가로 필요할 수 있음. 지금 환경은 `lan` bind + allowedOrigins 설정만으로 해결됨.

---

## 6. 디바이스 페어링

대시보드에서 로그인하면 장치 페어링을 요구한다.

```bash
openclaw devices list
openclaw devices approve <id>
```

---

## 7. 텔레그램 채팅이 이상하게 동작하던 문제

### 증상
- 웹 대시보드: 정상 응답.
- 텔레그램: 복잡한 요청(파일 생성+첨부)에서 런타임 컨텍스트 메타데이터가 실제 사용자 발화인 것처럼 세션에 섞여 들어가며 이상한 메타 응답을 반복 출력.
- 이후엔 단순 "안녕하세요"에도 아래 에러 발생:
  ```
  ⚠️ Auto-compaction could not recover this turn. I kept this conversation mapped to the current session.
  Please try again, use /compact, or use /new to start a fresh session.
  To prevent this, increase your compaction buffer by setting
  agents.defaults.compaction.reserveTokensFloor to 20000 or higher in your config.
  ```

### 원인 진단 과정
1. 처음엔 세션 오염(여러 세션 생성)을 의심 → `openclaw sessions list`로 확인.
   - `openclaw sessions clear --chat <id>` 는 존재하지 않는 옵션 (`--chat` 미지원).
   - 세션 정리는 텔레그램 채팅 안에서 `/new` 또는 `/compact`, 혹은 CLI로:
     ```bash
     openclaw sessions cleanup --dry-run --active-key "agent:main:telegram:direct:<chat_id>"
     openclaw sessions cleanup --enforce --active-key "agent:main:telegram:direct:<chat_id>"
     ```
2. `/compact`, `/new`로도 해결 안 됨 → **진짜 원인은 세션 오염이 아니라 compaction 설정 위치 착각**이었음.

### ⚠️ 시행착오 #3 — 잘못된 위치를 고치고 있었음

에러 메시지가 안내한 `agents.defaults.compaction.reserveTokensFloor`는 `models.providers.ollama.models[].params.num_ctx`와 **완전히 다른 위치**의 설정이다. 처음엔 이 둘을 혼동해서 `num_ctx`만 계속 만졌음 (헛수고).

### ⚠️ 시행착오 #4 — num_ctx와 contextWindow 불일치

```json
{
  "id": "gemma4-uncensored:latest",
  "contextWindow": 262144,
  "params": { "num_ctx": 20000 }
}
```

`contextWindow`는 262144로 표시되지만 실제 Ollama 런타임에 넘어가는 `num_ctx`는 20000이었음. OpenClaw는 모델이 26만 토큰을 처리할 수 있다고 믿는데 실제로는 2만 토큰에서 잘리니 auto-compaction이 실패.

**여기서 확인된 특이사항**: `num_ctx`를 8192처럼 낮게 잡으면 오히려 모델이 아예 실행이 안 되고 에러가 남 (원인 불명, Ollama/모델 조합 이슈로 추정). 결국 `num_ctx: 262144`로 크게 잡아두는 게 안정적이어서 그대로 유지.

### 최종 해결

```bash
openclaw config get agents.defaults.compaction
openclaw config set agents.defaults.compaction.reserveTokensFloor 20000
openclaw gateway restart
```

→ 즉시 정상화됨.

---

## 8. 최종 정상 동작 설정 (openclaw.json 핵심 부분 요약)

```json
{
  "gateway": {
    "bind": "lan",
    "port": 18789,
    "controlui": {
      "allowedOrigins": [
        "https://oc.silverruler.xyz",
        "http://oc.silverruler.xyz",
        "http://152.67.210.39:18789",
        "http://127.0.0.1:18789",
        "http://localhost:18789",
        "http://10.8.0.14:18789",
        "http://172.17.98.249:18789"
      ],
      "allowInsecureAuth": true
    }
  },
  "agents": {
    "defaults": {
      "compaction": {
        "mode": "default",
        "reserveTokensFloor": 20000
      }
    }
  },
  "models": {
    "providers": {
      "ollama": {
        "models": [
          {
            "id": "gemma4-uncensored:latest",
            "name": "gemma4-uncensored:latest",
            "reasoning": true,
            "input": ["text"],
            "contextWindow": 262144,
            "maxTokens": 8192,
            "compat": {
              "supportsTools": true,
              "supportsUsageInStreaming": true
            },
            "params": {
              "num_ctx": 262144
            }
          }
        ]
      }
    }
  }
}
```

---

## 9. 재설치 시 순서 요약 (Quick Checklist)

1. `wsl.conf`에 systemd 켜기 → `wsl --shutdown` → 재실행
2. nvm으로 Node 22 설치
3. `curl -fsSL https://openclaw.ai/install.sh | bash` (또는 `npm install -g openclaw@latest`)
4. `openclaw onboard --classic` (⚠️ `openclaw`만 치면 TUI로 바로 감, 온보딩 아님)
5. `openclaw.json`에서 `gateway.bind`를 `"lan"`으로 설정 (⚠️ `"0.0.0.0"` 직접 입력 금지)
6. `gateway.controlui.allowedOrigins`에 접속할 도메인/IP 전부 등록
7. `openclaw gateway restart`
8. 대시보드 로그인 후 `openclaw devices list` → `openclaw devices approve <id>`
9. `agents.defaults.compaction.reserveTokensFloor`를 20000 이상으로 설정 (⚠️ `models.providers.*.models[].params.num_ctx`와 헷갈리지 말 것 — 완전히 다른 키)
10. 로컬 모델(Ollama) 쓸 경우 `num_ctx`를 낮게 잡지 말 것 — 오히려 실행 자체가 안 되는 경우 있었음. 넉넉하게(예: 262144) 잡아두는 게 안정적이었음.
11. `openclaw gateway restart` 후 텔레그램/대시보드 양쪽에서 테스트

---

## 10. 알아두면 좋은 명령어 모음

```bash
openclaw sessions list                          # 세션 목록
openclaw sessions cleanup --dry-run --active-key "<key>"   # 특정 세션 정리 미리보기
openclaw sessions cleanup --enforce --active-key "<key>"   # 실제 정리
openclaw doctor                                  # 설정 진단
openclaw doctor --fix                            # 자동 수정
openclaw config get <key.path>                   # 설정 값 확인
openclaw config set <key.path> <value>           # 설정 값 변경
openclaw gateway restart                         # 게이트웨이 재시작
openclaw gateway status                          # 게이트웨이 상태 확인
```

텔레그램 채팅 안에서 바로 쓸 수 있는 명령어:
```
/new       세션 새로 시작
/compact   현재 대화 강제 압축
/model     현재 모델 확인 / 전환
```

---

## 11. 남은 과제 (다음에 할 것)

- 텔레그램 파일 첨부 스킬 활성화 (`openclaw skills list`로 현재 설치된 스킬 확인 필요)
- WSL2 밖(외부 네트워크)에서 안정적으로 접속하려면 `netsh interface portproxy` + Windows 방화벽 규칙 추가 고려 (WSL2 재부팅 시 내부 IP 변경되는 점 주의, Windows 11 mirrored 네트워킹 모드로 회피 가능)
