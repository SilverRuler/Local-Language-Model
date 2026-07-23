# OpenClaw 완전 운영 가이드

> 이 문서 하나만 보면 처음부터 끝까지 전부 다시 세팅 가능.
> 마지막 업데이트: 2026-07-23
> 서버: `YOUR_ID@10.8.0.14` / 비번: `니비번`

---

## 목차

1. [전제 조건](#1-전제-조건)
2. [처음 설치](#2-처음-설치)
3. [openclaw.json 핵심 설정](#3-openclaw-json-핵심-설정)
4. [docker compose up](#4-docker-compose-up)
5. [대시보드 접속](#5-대시보드-접속)
6. [새 기기 페어링 (pairing required 해결)](#6-새-기기-페어링)
7. [토큰 관리](#7-토큰-관리)
8. [allowedOrigins 추가](#8-allowedorigins-추가)
9. [모델 변경](#9-모델-변경)
10. [텔레그램 봇 설정](#10-텔레그램-봇-설정)
11. [치트시트](#11-치트시트)
12. [트러블슈팅](#12-트러블슈팅)

---

## 1. 전제 조건

| 항목 | 값 |
|------|-----|
| 서버 SSH | `ssh YOUR_ID@10.8.0.14` / pw: `니비번` |
| 대시보드 도메인 | `https://니도메인 SSL/TLS필수` (Cloudflare → origin) |
| 대시보드 포트 | `18789` |
| ollama 서버 | `http://172.17.0.1:11434` |
| docker compose 위치 | `~/openclaw/` |
| openclaw 설정 디렉토리 | `~/.openclaw/` (= `/home/YOUR_ID/.openclaw`) |

> ⚠️ **중요**: 컨테이너가 마운트하는 실제 경로는 `/home/YOUR_ID/.openclaw` 이다.
> `/root/.openclaw` 는 존재하지 않음. 편집할 파일은 항상 `/home/YOUR_ID/.openclaw/openclaw.json`

---

## 2. 처음 설치

### 2-1. git clone (최초 1회)

```bash
ssh YOUR_ID@10.8.0.14
cd ~
git clone <openclaw_repo_url> openclaw
cd openclaw
```

### 2-2. .env 파일 생성

```bash
cd ~/openclaw
cp .env.example .env
```

`.env` 필수 항목:

```env
OPENCLAW_CONFIG_DIR=/home/YOUR_ID/.openclaw
OPENCLAW_WORKSPACE_DIR=/home/YOUR_ID/.openclaw/workspace
OPENCLAW_GATEWAY_PORT=18789
OPENCLAW_BRIDGE_PORT=18790
OPENCLAW_GATEWAY_BIND=lan
OPENCLAW_GATEWAY_TOKEN=<아래에서 생성할 토큰>
OPENCLAW_IMAGE=openclaw:local
```

### 2-3. 게이트웨이 토큰 생성

```bash
NEW_TOKEN=$(openssl rand -hex 32)
echo $NEW_TOKEN   # ← 반드시 메모!
sed -i "s/OPENCLAW_GATEWAY_TOKEN=.*/OPENCLAW_GATEWAY_TOKEN=$NEW_TOKEN/" ~/openclaw/.env
```

### 2-4. docker 이미지 빌드

```bash
cd ~/openclaw
docker build -t openclaw:local .
```

> 이미 `openclaw:local` 이미지 있으면 스킵. `docker images | grep openclaw` 로 확인.

---

## 3. openclaw.json 핵심 설정

**파일 위치: `/home/YOUR_ID/.openclaw/openclaw.json`**

처음 설치 시 존재하지 않으면 생성:

```bash
mkdir -p ~/.openclaw
nano ~/.openclaw/openclaw.json
```

### 완성된 openclaw.json 템플릿

```json
{
  "gateway": {
    "mode": "local",
    "bind": "lan",
    "port": 18789,
    "auth": {
      "mode": "token",
      "token": "<OPENCLAW_GATEWAY_TOKEN 값>"
    },
    "controlUi": {
      "allowedOrigins": [
        "https://oc.silverruler.xyz",
        "http://oc.silverruler.xyz",
        "http://152.67.210.39:18789",
        "http://127.0.0.1:18789",
        "http://localhost:18789",
        "http://10.8.0.14:18789"
      ],
      "allowInsecureAuth": true
    },
    "tailscale": {
      "mode": "off",
      "resetOnExit": false
    }
  },
  "agents": {
    "defaults": {
      "model": "ollama/gemma4-uncensored:latest",
      "workspace": "/home/node/.openclaw/workspace",
      "sandbox": {
        "mode": "off"
      }
    }
  },
  "models": {
    "mode": "merge",
    "providers": {
      "ollama": {
        "YOUR_IDUrl": "http://172.17.0.1:11434",
        "api": "ollama",
        "apiKey": "OLLAMA_API_KEY",
        "models": [
          {
            "id": "gemma4-uncensored:latest",
            "name": "gemma4-uncensored:latest",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 128000,
            "maxTokens": 8192
          }
        ]
      }
    }
  },
  "plugins": {
    "entries": {
      "ollama": { "enabled": true }
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "니토큰",
      "allowFrom": ["*"],
      "dmPolicy": "open",
      "groups": {
        "*": { "requireMention": true }
      }
    }
  },
  "auth": {
    "profiles": {
      "ollama:default": {
        "provider": "ollama",
        "mode": "api_key"
      }
    }
  },
  "tools": {
    "profile": "coding"
  }
}
```

> ⚠️ `gateway.auth.mode`는 반드시 `"token"` 으로 설정.
> `"password"` 로 하면 대시보드 로그인이 안 된다.

---

## 4. docker compose up

```bash
cd ~/openclaw
docker compose up -d
```

### 상태 확인

```bash
docker ps | grep openclaw
docker logs openclaw-openclaw-gateway-1 --tail 20
```

정상 기동 시 로그:

```
[gateway] ready (6 plugins: acpx, browser, device-pair, phone-control, talk-voice, telegram; 1.8s)
[gateway] agent model: ollama/gemma4-uncensored:latest
```

### 컨테이너 내리기

```bash
cd ~/openclaw && docker compose down
```

### 설정 변경 후 재시작

```bash
cd ~/openclaw && docker compose restart openclaw-gateway
# 또는 완전 재시작
docker compose down && docker compose up -d
```

---

## 5. 대시보드 접속

### 접속 URL

```
https://oc.silverruler.xyz
```

### 로그인 토큰 확인

```bash
grep OPENCLAW_GATEWAY_TOKEN ~/openclaw/.env
```

또는:

```bash
docker exec openclaw-openclaw-gateway-1 node dist/index.js dashboard --no-open
# 출력 예: Dashboard URL: http://127.0.0.1:18789/#token=xxxxxxx
```

### URL 해시로 직접 접속 (편한 방법)

```
https://oc.silverruler.xyz/#token=<게이트웨이토큰>
```

---

## 6. 새 기기 페어링

대시보드에서 토큰 입력 후 **"pairing required"** 가 나오면:

### Step 1. 브라우저에서 토큰 입력

`https://oc.silverruler.xyz` → 토큰 입력 → "pairing required" 화면 확인

### Step 2. 서버에서 pending 목록 확인

```bash
docker exec openclaw-openclaw-gateway-1 node dist/index.js devices list \
  --token <게이트웨이토큰> \
  --url ws://127.0.0.1:18789
```

출력 예:

```
Pending (1):
  requestId: 51e3e99a-9c00-427b-8d2f-3d95057b4afa   platform: Win32
```

### Step 3. 승인

```bash
docker exec openclaw-openclaw-gateway-1 node dist/index.js devices approve \
  <requestId> \
  --token <게이트웨이토큰> \
  --url ws://127.0.0.1:18789
```

승인 즉시 브라우저가 자동으로 로그인된다.

### Step 4. 확인

```bash
docker exec openclaw-openclaw-gateway-1 node dist/index.js devices list \
  --token <게이트웨이토큰> \
  --url ws://127.0.0.1:18789
```

Paired 목록에 해당 기기가 나오면 완료.

---

## 7. 토큰 관리

### 게이트웨이 토큰 재발급

```bash
NEW_TOKEN=$(openssl rand -hex 32)
echo "새 토큰: $NEW_TOKEN"

# openclaw.json 업데이트
python3 -c "
import json
path = '/home/YOUR_ID/.openclaw/openclaw.json'
with open(path) as f: d = json.load(f)
d['gateway']['auth']['token'] = '$NEW_TOKEN'
with open(path, 'w') as f: json.dump(d, f, indent=2)
print('완료')
"

# .env 업데이트
sed -i "s/OPENCLAW_GATEWAY_TOKEN=.*/OPENCLAW_GATEWAY_TOKEN=$NEW_TOKEN/" ~/openclaw/.env

# 재시작
cd ~/openclaw && docker compose restart openclaw-gateway
```

### 디바이스 토큰 rotate (기존 기기 토큰만 재발급)

```bash
# deviceId 확인
docker exec openclaw-openclaw-gateway-1 node dist/index.js devices list \
  --token <게이트웨이토큰> --url ws://127.0.0.1:18789

# rotate
docker exec openclaw-openclaw-gateway-1 node dist/index.js devices rotate \
  <deviceId> \
  --role operator \
  --token <게이트웨이토큰> \
  --url ws://127.0.0.1:18789 \
  --json
```

### 모든 디바이스 페어링 완전 초기화

```bash
cd ~/openclaw && docker compose down
echo "{}" > ~/.openclaw/devices/paired.json
echo "{}" > ~/.openclaw/devices/pending.json
cd ~/openclaw && docker compose up -d
```

---

## 8. allowedOrigins 추가

"origin not allowed" 에러 시:

```bash
python3 -c "
import json
path = '/home/YOUR_ID/.openclaw/openclaw.json'
with open(path) as f: d = json.load(f)
origins = d['gateway']['controlUi']['allowedOrigins']
new_origin = 'http://새IP주소:18789'
if new_origin not in origins:
    origins.append(new_origin)
    print('추가됨:', new_origin)
with open(path, 'w') as f: json.dump(d, f, indent=2)
print('현재 목록:', origins)
"
cd ~/openclaw && docker compose restart openclaw-gateway
```

### 현재 등록 확인

```bash
docker exec openclaw-openclaw-gateway-1 \
  node dist/index.js config get gateway.controlUi.allowedOrigins
```

### 서버 IP 변경 시 체크리스트

1. allowedOrigins에 새 IP 추가 (위 방법)
2. `docker compose restart openclaw-gateway`
3. `docker logs openclaw-openclaw-gateway-1 --tail 20` 확인

> ⚠️ Cloudflare 경유 접속 시 브라우저 Origin 헤더는
> `https://oc.silverruler.xyz` 이므로 이것도 목록에 있어야 함.

---

## 9. 모델 변경

### 기본 에이전트 모델 변경

```bash
python3 -c "
import json
path = '/home/YOUR_ID/.openclaw/openclaw.json'
with open(path) as f: d = json.load(f)
d['agents']['defaults']['model'] = 'ollama/새모델명:tag'
with open(path, 'w') as f: json.dump(d, f, indent=2)
print('완료')
"
cd ~/openclaw && docker compose restart openclaw-gateway
```

### 모델 목록에 새 모델 등록

`openclaw.json`의 `models.providers.ollama.models` 배열에 추가:

```json
{
  "id": "새모델:tag",
  "name": "새모델:tag",
  "reasoning": false,
  "input": ["text"],
  "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
  "contextWindow": 128000,
  "maxTokens": 8192
}
```

### ollama 서버 주소 변경

```bash
python3 -c "
import json
path = '/home/YOUR_ID/.openclaw/openclaw.json'
with open(path) as f: d = json.load(f)
d['models']['providers']['ollama']['YOUR_IDUrl'] = 'http://새ollama주소:11434'
with open(path, 'w') as f: json.dump(d, f, indent=2)
"
```

현재 ollama 서버: `http://172.17.0.1:11434`

---

## 10. 텔레그램 봇 설정

### 현재 봇 정보

| 항목 | 값 |
|------|-----|
| 봇 이름 | `@Furen_Notifier_Bot` |
| 봇 토큰 | `니토큰` |
| Chat ID | `1777952457` |

### openclaw.json 채널 설정

```json
"channels": {
  "telegram": {
    "enabled": true,
    "botToken": "<봇토큰>",
    "allowFrom": ["*"],
    "dmPolicy": "open",
    "groups": {
      "*": { "requireMention": true }
    }
  }
}
```

- 특정 유저만 허용: `"allowFrom": ["1777952457"]`
- 모두 허용: `"allowFrom": ["*"]`

### 봇 토큰 유효성 확인

```bash
curl -s "https://api.telegram.org/bot<봇토큰>/getMe"
```

### 테스트 메시지 발송

```bash
curl -s "https://api.telegram.org/bot<봇토큰>/sendMessage" \
  -d "chat_id=<CHAT_ID>&text=테스트"
```

---

## 11. 치트시트

```bash
# ── 기본 관리 ──────────────────────────────────
cd ~/openclaw && docker compose up -d          # 올리기
cd ~/openclaw && docker compose down           # 내리기
cd ~/openclaw && docker compose restart openclaw-gateway  # 재시작
docker ps | grep openclaw                      # 상태
docker logs openclaw-openclaw-gateway-1 --tail 50  # 로그

# ── 토큰/인증 ───────────────────────────────────
grep OPENCLAW_GATEWAY_TOKEN ~/openclaw/.env    # 토큰 확인
docker exec openclaw-openclaw-gateway-1 node dist/index.js dashboard --no-open

# ── 디바이스 페어링 ─────────────────────────────
docker exec openclaw-openclaw-gateway-1 node dist/index.js devices list \
  --token <토큰> --url ws://127.0.0.1:18789

docker exec openclaw-openclaw-gateway-1 node dist/index.js devices approve \
  <requestId> --token <토큰> --url ws://127.0.0.1:18789

docker exec openclaw-openclaw-gateway-1 node dist/index.js devices remove \
  <deviceId> --token <토큰> --url ws://127.0.0.1:18789

# ── 설정 확인/변경 ──────────────────────────────
docker exec openclaw-openclaw-gateway-1 node dist/index.js config get <키>
docker exec openclaw-openclaw-gateway-1 node dist/index.js config set <키> <값>
docker exec openclaw-openclaw-gateway-1 \
  node dist/index.js config get gateway.controlUi.allowedOrigins

# ── 상태/헬스 ───────────────────────────────────
docker exec openclaw-openclaw-gateway-1 node dist/index.js status
docker exec openclaw-openclaw-gateway-1 node dist/index.js health
```

---

## 12. 트러블슈팅

### ❌ origin not allowed

**원인:** 접속 도메인/IP가 `allowedOrigins`에 없음
**해결:** [8. allowedOrigins 추가](#8-allowedorigins-추가) 참고

---

### ❌ pairing required

**원인:** 해당 기기가 아직 approved 상태가 아님
**해결:**
```bash
# pending 확인
docker exec openclaw-openclaw-gateway-1 node dist/index.js devices list \
  --token <토큰> --url ws://127.0.0.1:18789
# 승인
docker exec openclaw-openclaw-gateway-1 node dist/index.js devices approve \
  <requestId> --token <토큰> --url ws://127.0.0.1:18789
```

---

### ❌ too many failed authentication attempts

**원인:** 잘못된 토큰 반복 시도로 rate limit 걸림
**해결 (빠름):** 컨테이너 재시작
```bash
cd ~/openclaw && docker compose restart openclaw-gateway
```
**해결 (완전 초기화):**
```bash
cd ~/openclaw && docker compose down
echo "{}" > ~/.openclaw/devices/paired.json
echo "{}" > ~/.openclaw/devices/pending.json
# 새 토큰 생성 후 openclaw.json + .env 업데이트
cd ~/openclaw && docker compose up -d
```

---

### ❌ connect failed (code 4008)

**원인:** origin은 허용됐지만 토큰이 틀림
**해결:**
```bash
python3 -c "import json; d=json.load(open('/home/YOUR_ID/.openclaw/openclaw.json')); print(d['gateway']['auth']['token'])"
```
출력된 값과 대시보드 입력 토큰 비교.

---

### ❌ 설정 변경이 반영 안 됨

```bash
cd ~/openclaw && docker compose restart openclaw-gateway
```

---

### ❌ 대시보드 화면이 하얗게 뜸

- `gateway.auth.mode`가 `"token"` 인지 확인
- 브라우저 강제 새로고침: `Ctrl+Shift+R`

---

### ❌ ollama 연결 안 됨

```bash
curl http://172.17.0.1:11434/api/tags
```
응답 없으면 ollama 서버 문제.

---

## 부록: 현재 운영 환경 (2026-07-23 기준)

| 항목 | 값 |
|------|-----|
| 서버 IP (VPN) | `10.8.0.14` |
| 외부 IP | `니주소` |
| 대시보드 | `https://oc.silverruler.xyz` |
| 포트 | `18789` (gateway), `18790` (bridge) |
| 기본 모델 | `ollama/gemma4-uncensored:latest` |
| ollama 주소 | `http://172.17.0.1:11434` |
| 텔레그램 봇 | `@Furen_Notifier_Bot` |
| 텔레그램 토큰 | `니토큰` |
| Chat ID | `1777952457` |
| 게이트웨이 토큰 | `니토큰` |

---

## 13. ollama 모델 메모리 상주 (keep_alive)

### 왜 필요한가?

이 서버는 ollama 모델 파일이 **Windows G: 드라이브 (`/mnt/g/`)** 에 있어서  
WSL2를 통한 파일 I/O가 느립니다.

- 모델이 언로드된 상태에서 첫 요청 시 **로딩 50~60초** 소요
- openclaw의 LLM 타임아웃(기본 ~30초)이 먼저 터져서 `LLM request failed` 발생

따라서 openclaw 사용 전에 모델을 미리 메모리에 올려놔야 합니다.

---

### keep_alive 값 설명

| 값 | 의미 |
|----|------|
| `0` | 응답 후 즉시 언로드 |
| `5m` | 마지막 요청 후 5분간 유지 (ollama 기본값) |
| `1h` | 1시간 유지 |
| `-1` | 영구 유지 (ollama 프로세스 종료 전까지) |

---

### 방법 1: 영구 상주 (keep_alive=-1)

재시작 전까지 계속 GPU/RAM에 올려둠. openclaw 상시 운영 시 권장.

```bash
curl -s http://172.17.0.1:11434/api/generate \
  -d '{"model":"gemma4-uncensored:latest","prompt":"","keep_alive":-1,"stream":false}'
```

확인:
```bash
ollama ps
# NAME                        SIZE    PROCESSOR    UNTIL
# gemma4-uncensored:latest    5.6GB   100% GPU     Forever
```

---

### 방법 2: 기본 상주값 (5분, ollama 디폴트)

openclaw가 응답을 받은 후 5분 동안 메모리 유지. 그 이후 자동 언로드.  
다음 요청 시 다시 50~60초 로딩 발생.

```bash
# keep_alive 생략하면 ollama 기본값(5분) 적용
curl -s http://172.17.0.1:11434/api/generate \
  -d '{"model":"gemma4-uncensored:latest","prompt":"","stream":false}'
```

---

### 방법 3: 원하는 시간만큼 유지

```bash
# 1시간 유지
curl -s http://172.17.0.1:11434/api/generate \
  -d '{"model":"gemma4-uncensored:latest","prompt":"","keep_alive":"1h","stream":false}'
```

---

### 모델 즉시 언로드 (메모리 회수)

```bash
# keep_alive=0 으로 강제 언로드
curl -s http://172.17.0.1:11434/api/generate \
  -d '{"model":"gemma4-uncensored:latest","prompt":"","keep_alive":0,"stream":false}'

# 또는 ollama stop 명령
ollama stop gemma4-uncensored:latest
```

---

### WSL2 재시작 후 복구 절차

WSL2(우분투) 재시작하면 ollama 모델이 전부 언로드됩니다.  
openclaw 사용 전에 아래 순서로 복구:

```bash
# 1. docker compose 올리기
cd ~/openclaw && docker compose up -d

# 2. 모델 warm-up (메모리 상주)
curl -s http://172.17.0.1:11434/api/generate \
  -d '{"model":"gemma4-uncensored:latest","prompt":"","keep_alive":-1,"stream":false}'

# 3. 상태 확인
ollama ps
docker ps | grep openclaw
```

> ⚠️ 2번 warm-up은 **50~60초** 소요됩니다. 완료되면 이후 응답은 2~3초.

---

### 빠른 상태 확인 원라이너

```bash
# ollama 로드 상태 + openclaw 컨테이너 상태 한번에
ollama ps && echo "---" && docker ps | grep openclaw
```

---

## 14. 시작 스크립트 (start.sh)

WSL2 재시작 후 openclaw + 모델 warm-up + 텔레그램 알림을 한 번에 처리하는 스크립트.

**파일 위치:** `~/openclaw/start.sh`

### 사용법

```bash
# OpenClaw 전체 시작 (컨테이너 + 모델 warm-up + 텔레그램 알림)
bash ~/openclaw/start.sh
```

### 스크립트 동작 순서

```
[1/4] docker compose up -d
[2/4] 게이트웨이 헬스체크 대기 (최대 30초)
[3/4] 텔레그램 "시작 중..." 알림 발송
      → 모델 warm-up (약 60초 소요)
[4/4] 텔레그램 "✅ OpenClaw is ready!" 알림 발송
```

### 텔레그램으로 오는 알림 예시

```
⏳ OpenClaw 시작 중...
모델 로딩 중입니다. 잠시 기다려주세요. (약 60초)
```
↓ 약 60초 후

```
✅ OpenClaw is ready!

🤖 모델: gemma4-uncensored:latest
🌐 대시보드: https://oc.silverruler.xyz
🖥️ 서버: 172.17.98.249
```

### 스크립트 내용 (수동 재생성 시)

```bash
cat > ~/openclaw/start.sh << 'SCRIPT'
#!/bin/bash
TELEGRAM_TOKEN="니토큰"
CHAT_ID="1777952457"
OLLAMA_URL="http://172.17.0.1:11434"
MODEL="gemma4-uncensored:latest"

tg_send() {
  curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}&text=$1&parse_mode=HTML" > /dev/null
}

echo "[1/4] OpenClaw 컨테이너 시작..."
cd ~/openclaw && docker compose up -d

echo "[2/4] 게이트웨이 준비 대기..."
for i in $(seq 1 30); do
  STATUS=$(curl -s --max-time 2 http://127.0.0.1:18789/healthz 2>/dev/null)
  if echo "$STATUS" | grep -q "ok"; then
    echo "  → 게이트웨이 준비됨 (${i}초)"
    break
  fi
  sleep 1
done

echo "[3/4] 모델 warm-up 중..."
tg_send "⏳ <b>OpenClaw 시작 중...</b>%0A모델 로딩 중입니다. 잠시 기다려주세요. (약 60초)"

curl -s "${OLLAMA_URL}/api/generate" \
  -d "{\"model\":\"${MODEL}\",\"prompt\":\"\",\"keep_alive\":-1,\"stream\":false}" \
  -o /dev/null

echo "[4/4] 완료! 텔레그램 알림 발송..."
SERVER_IP=$(hostname -I | awk '{print $1}')
tg_send "✅ <b>OpenClaw is ready!</b>%0A%0A🤖 모델: ${MODEL}%0A🌐 대시보드: https://oc.silverruler.xyz%0A🖥️ 서버: ${SERVER_IP}"

ollama ps
docker ps | grep openclaw
SCRIPT
chmod +x ~/openclaw/start.sh
```
