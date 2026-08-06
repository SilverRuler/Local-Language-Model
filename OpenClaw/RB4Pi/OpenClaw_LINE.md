# OpenClaw + OmniRoute + LINE 웹훅 설정 가이드

> 라즈베리파이에서 OpenClaw를 OmniRoute 모델로 연결하고 LINE 채널을 연동하는 전체 과정

---

## 목차

1. [사전 조건](#1-사전-조건)
2. [OmniRoute 연결 설정](#2-omniroute-연결-설정)
3. [openclaw gateway 실행](#3-openclaw-gateway-실행)
4. [gateway가 안 켜질 때 해결법](#4-gateway가-안-켜질-때-해결법)
5. [LINE 웹훅 연동](#5-line-웹훅-연동)
6. [OpenClaw Pairing 설정](#6-openclaw-pairing-설정)
7. [Auto-Reply 메시지 끄기](#7-auto-reply-메시지-끄기)
8. [자동화 스크립트 사용](#8-자동화-스크립트-사용)

---

## 1. 사전 조건

- OpenClaw가 이미 설치되어 있어야 함 (`openclaw` 명령어 사용 가능)
- OmniRoute가 **같은 서버** 또는 **접근 가능한 서버**의 포트 `20128`에서 tmux 세션으로 실행 중
- LINE Messaging API 채널이 준비되어 있어야 함 (Channel Access Token, Channel Secret)
- 외부에서 접근 가능한 HTTPS 도메인이 준비되어 있어야 함 (예: `https://oc3.silverruler.xyz`)

---

## 2. OmniRoute 연결 설정

OpenClaw가 OmniRoute를 모델 제공자로 인식하게 하려면 `~/.openclaw/openclaw.json`을 직접 편집해야 한다.
`openclaw configure` 의 wizard UI로는 커스텀 provider 설정이 잘 안 되므로 **JSON 직접 편집**을 권장.

### 2-1. 현재 설정 확인

```bash
cat ~/.openclaw/openclaw.json
```

### 2-2. 필요한 섹션 3개 추가

`~/.openclaw/openclaw.json`에 아래 3개 섹션을 추가한다.

#### ① models 섹션 — OmniRoute를 provider로 등록

```json
"models": {
  "mode": "merge",
  "providers": {
    "omniroute": {
      "baseUrl": "http://127.0.0.1:20128/v1",
      "api": "openai-completions",
      "apiKey": "sk-여기에_api_키",
      "models": [
        {
          "id": "auto/best-chat",
          "name": "auto/best-chat",
          "reasoning": true,
          "input": ["text"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 128000,
          "maxTokens": 8192,
          "compat": { "supportsTools": true, "supportsUsageInStreaming": true }
        }
      ]
    }
  }
}
```

> baseUrl의 IP/포트는 OmniRoute가 실행 중인 위치에 맞게 수정.
> 같은 서버면 127.0.0.1:20128, 다른 서버면 해당 서버의 IP:20128.

#### ② agents 섹션 — 기본 모델을 omniroute로 지정

```json
"agents": {
  "defaults": {
    "model": {
      "primary": "omniroute/auto/best-chat"
    },
    "models": {
      "omniroute/auto/best-chat": {}
    }
  }
}
```

#### ③ auth 섹션 — provider 인증 방식 등록

```json
"auth": {
  "profiles": {
    "omniroute:default": {
      "provider": "omniroute",
      "mode": "api_key"
    }
  }
}
```

### 2-3. Python으로 한 번에 패치하기 (권장)

수동으로 JSON 편집하다가 문법 오류 나는 것을 방지하기 위해 Python 스크립트로 패치:

```bash
python3 /root/line_oc.py --omniroute-url http://127.0.0.1:20128/v1 --omniroute-key "sk-키값"
```

또는 라인 토큰까지 한번에:

```bash
python3 /root/line_oc.py \
  --omniroute-url http://127.0.0.1:20128/v1 \
  --omniroute-key "sk-키값" \
  --line-token "LINE_채널_액세스_토큰" \
  --line-secret "LINE_채널_시크릿"
```

### 2-4. 설정 확인

```bash
cat ~/.openclaw/openclaw.json | python3 -m json.tool | grep -A3 "omniroute"
```

---

## 3. openclaw gateway 실행

### tmux 세션에서 실행하기 (권장)

```bash
# openclaw 세션이 없으면 새로 생성
tmux new-session -d -s openclaw

# 세션 안에서 gateway 실행
tmux send-keys -t openclaw "openclaw gateway" Enter
```

### 실행 확인

```bash
sleep 5
tmux capture-pane -t openclaw -p | tail -10
```

아래와 같은 메시지가 나오면 정상:

```
[gateway] agent model: omniroute/auto/best-chat (thinking=medium, fast=off)
[gateway] ready
[line] [default] starting LINE provider (...)
```

---

## 4. gateway가 안 켜질 때 해결법

### 문제 증상

`openclaw gateway start` 실행했더니 아래 메시지 출력 후 바로 종료됨:

```
Gateway service disabled.
Start with: openclaw gateway install
Start with: openclaw gateway
Start with: systemctl --user start openclaw-gateway.service
```

### 원인

`openclaw gateway start`는 systemd 서비스로 등록된 경우에만 작동한다.
라즈베리파이처럼 서비스 등록이 안 된 환경에서는 `start` 없이 바로 `openclaw gateway`를 써야 한다.

### 해결

```bash
# 틀린 명령어 (서비스 미등록 환경에서)
# openclaw gateway start   <-- 이렇게 하면 안됨

# 올바른 명령어
openclaw gateway
```

### tmux에서 잘못된 명령어가 실행 중인 경우

```bash
# 기존 프로세스 종료
tmux send-keys -t openclaw C-c ""
sleep 1

# 올바른 명령어로 재시작
tmux send-keys -t openclaw "openclaw gateway" Enter
sleep 5

# 상태 확인
tmux capture-pane -t openclaw -p | tail -10
```

### systemd 서비스로 영구 등록하고 싶은 경우 (선택사항)

```bash
openclaw gateway install
systemctl --user enable openclaw-gateway
systemctl --user start openclaw-gateway
# 이후부터는 openclaw gateway start / stop 사용 가능
```

---

## 5. LINE 웹훅 연동

### 5-1. openclaw.json에 LINE 채널 정보 추가

`~/.openclaw/openclaw.json`에 아래 섹션을 추가:

```json
"channels": {
  "line": {
    "enabled": true,
    "channelAccessToken": "여기에_LINE_채널_액세스_토큰",
    "channelSecret": "여기에_LINE_채널_시크릿"
  }
},
"plugins": {
  "entries": {
    "line": {
      "enabled": true
    }
  }
}
```

### 5-2. gateway 재시작

설정 변경 후 gateway를 재시작해야 적용된다:

```bash
tmux send-keys -t openclaw C-c ""
sleep 1
tmux send-keys -t openclaw "openclaw gateway" Enter
sleep 5
tmux capture-pane -t openclaw -p | grep -E "line|ready|error"
```

### 5-3. LINE Developer Console에서 웹훅 URL 등록

#### 웹훅 URL 형식 (핵심!)

```
https://{외부도메인}/line/webhook
```

예시:
```
https://oc3.silverruler.xyz/line/webhook
```

> 주의: 경로가 정확해야 한다.
> /channels/line/webhook  <-- 이건 404
> /line/webhook           <-- 이게 정확한 경로

openclaw의 LINE 플러그인 소스에서 실제로 등록하는 경로는 `/line/webhook` 이다.
(플러그인 코드: `path: options.path ?? "/line/webhook"`)

#### LINE Developers Console 등록 순서

1. https://developers.line.biz 접속
2. 해당 채널 클릭 → Messaging API 탭
3. Webhook URL 항목 → 위 URL 입력
4. Verify 버튼 클릭 → "Success" 확인
5. Use webhook 토글 → ON
6. Auto-reply messages → Disabled (아래 섹션 참고)

### 5-4. 웹훅 엔드포인트 동작 테스트

```bash
# 로컬에서 경로 존재 확인
# 401 = 경로 OK (서명 없어서 거절됨, 정상)
# 404 = 경로 잘못됨
curl -s -o /dev/null -w "%{http_code}" \
  http://127.0.0.1:18789/line/webhook \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"destination":"test","events":[]}'

# 외부 도메인으로 확인
# 400 = 외부에서 접근 가능 (서명 없어서 거절됨, 정상)
curl -s -o /dev/null -w "%{http_code}" \
  https://YOUR_DOMAIN/line/webhook \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"destination":"test","events":[]}'
```

---

## 6. OpenClaw Pairing 설정

다른 기기(폰, PC 등)에서 OpenClaw 대시보드에 접속하려면 pairing이 필요하다.

### 방법 1: CLI pairing 코드 발급 (가장 간단)

```bash
openclaw pair
```

출력된 URL 또는 코드를 다른 기기의 브라우저에서 열거나 입력.

### 방법 2: 대시보드에서 pairing

1. 브라우저에서 `https://YOUR_DOMAIN` 접속
2. 대시보드 → Settings → Pairing 또는 Devices
3. Add Device → QR코드 또는 pairing 코드 확인
4. 연결할 기기에서 해당 코드 입력

### 방법 3: 토큰 직접 사용

`openclaw.json`의 `gateway.auth.token` 값을 복사해서 다른 기기 접속 시 입력:

```bash
python3 -c "
import json
with open('/root/.openclaw/openclaw.json') as f:
    d = json.load(f)
print('Token:', d['gateway']['auth']['token'])
print('URL:  ', 'https://YOUR_DOMAIN')
"
```

---

## 7. Auto-Reply 메시지 끄기

LINE Official Account에서 자동 응답이 켜져 있으면 OpenClaw의 응답과 겹쳐서 이중 응답이 발생한다.
반드시 꺼야 한다.

### LINE Developers Console에서 끄기

1. https://developers.line.biz → 해당 채널
2. Messaging API 탭
3. Auto-reply messages → Edit 클릭 (LINE Official Account Manager로 이동됨)
4. 자동 응답 메시지 → "사용 안 함" 으로 변경
5. 인사 메시지 → 필요시 "사용 안 함" 으로 변경

### LINE Official Account Manager에서 직접 끄기

1. https://manager.line.biz 접속
2. 해당 계정 선택
3. 응답 설정 메뉴
4. 자동 응답 → 끄기
5. 챗봇 → 켜기 (webhook으로 응답하게 설정)

---

## 8. 자동화 스크립트 사용

`/root/line_oc.py` 를 사용하면 새 라즈베리파이에서도 한 번에 설정 가능.

### 기본 사용법

```bash
# OmniRoute만 설정
python3 /root/line_oc.py \
  --omniroute-url http://127.0.0.1:20128/v1 \
  --omniroute-key "sk-키값"

# OmniRoute + LINE 한번에 설정
python3 /root/line_oc.py \
  --omniroute-url http://127.0.0.1:20128/v1 \
  --omniroute-key "sk-키값" \
  --line-token "CHANNEL_ACCESS_TOKEN" \
  --line-secret "CHANNEL_SECRET"

# OmniRoute가 다른 서버에 있는 경우
python3 /root/line_oc.py \
  --omniroute-url http://192.168.1.100:20128/v1 \
  --omniroute-key "sk-키값" \
  --line-token "CHANNEL_ACCESS_TOKEN" \
  --line-secret "CHANNEL_SECRET"

# gateway 자동 재시작 포함
python3 /root/line_oc.py \
  --omniroute-url http://127.0.0.1:20128/v1 \
  --omniroute-key "sk-키값" \
  --line-token "CHANNEL_ACCESS_TOKEN" \
  --line-secret "CHANNEL_SECRET" \
  --restart-gateway
```

### 스크립트가 하는 일

1. ~/.openclaw/openclaw.json 백업 (openclaw.json.bak)
2. models 섹션 추가 (OmniRoute provider 등록)
3. agents 섹션 추가 (기본 모델 설정)
4. auth 섹션 추가 (인증 방식 등록)
5. LINE channels/plugins 섹션 추가 (--line-token 옵션 사용 시)
6. 설정 검증 (JSON 문법 확인)
7. gateway tmux 세션 재시작 (--restart-gateway 옵션 사용 시)

---

## 전체 빠른 요약

| 단계 | 명령어/작업 |
|------|------------|
| 1. OmniRoute 설정 | `python3 /root/line_oc.py --omniroute-url ... --omniroute-key ...` |
| 2. LINE 설정 | `--line-token ... --line-secret ...` 옵션 추가 |
| 3. gateway 실행 | `tmux send-keys -t openclaw "openclaw gateway" Enter` |
| 4. gateway 안 켜질 때 | `start` 빼고 `openclaw gateway`만 실행 |
| 5. LINE 웹훅 URL | `https://도메인/line/webhook` (슬래시 경로 주의) |
| 6. Pairing | `openclaw pair` 실행 후 코드 입력 |
| 7. Auto-reply 끄기 | LINE Official Account Manager → 응답 설정 → 자동응답 끄기 |
