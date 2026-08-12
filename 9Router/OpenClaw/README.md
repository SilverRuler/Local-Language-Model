# OpenClaw & OmniRoute 서버 구축 및 설정 가이드 (GCP 환경)

이 문서는 GCP 서버 환경에서 **OmniRoute**를 AI API 프록시로 활용하여 **OpenClaw** 에이전트를 전역으로 구축하고, Cloudflare를 통한 외부 보안 접속(SSL/TLS) 및 텔레그램 봇 연동을 완료하기까지의 모든 과정을 상세하게 기록한 문서입니다.

---

## 1. OmniRoute 설치 및 기본 셋업
* **서버 구축**: OmniRoute 소스코드를 클론하여 로컬 포트(`http://127.0.0.1:20128/v1`)에 호스팅.
* **사용량 및 모델 조회**: `/root/OmniRoute/translate/` 하위에 스크립트를 작성하여 사용 가능한 무료 모델 리스트와 Quota 잔여량을 조회하도록 구성. (주요 모델: `auto/best-chat`)

## 2. OpenClaw 전역 설치 및 디렉토리 구성
과거 WSL2 환경에서 발생하던 설정 충돌과 환경 변수 꼬임 현상을 방지하기 위해 GCP 서버에 새롭게 전역(Global) 설치를 진행했습니다.

```bash
# OpenClaw 전역 설치
npm install -g openclaw

# 작업 및 설정 폴더 생성
mkdir -p /root/openclaw /root/.openclaw
```
> **참고**: CLI 특성상 현재 실행하는 폴더(`pwd`)의 설정을 전역 설정(`~/.openclaw`)보다 우선시하므로, 확실한 적용을 위해 양쪽 경로 모두에 동일한 `openclaw.json`을 세팅했습니다.

---

## 3. openclaw.json: OmniRoute 연동 설정
OpenClaw가 Ollama 대신 OmniRoute(OpenAI 호환 API)를 바라보도록 설정 파일을 조작했습니다.
`models` 객체 하위의 `providers`에 다음과 같이 `omniroute`를 추가했습니다.

```json
"providers": {
  "omniroute": {
    "baseUrl": "http://127.0.0.1:20129/v1",
    "api": "openai",
    "apiKey": "YOUR_KEY",
    "models": [
      {
        "id": "oc/hy3-free",
        "name": "oc/hy3-free",
        "reasoning": true,
        "input": ["text"],
        "contextWindow": 128000,
        "maxTokens": 8192,
        "compat": {
          "supportsTools": true,
          "supportsUsageInStreaming": true
        }
      }
    ]
  }
}
```
또한, 에이전트 구동 시 최우선으로 실행되는 모델(`agents.defaults.model.primary`)을 `"omniroute/auto/best-chat"`으로 교체했습니다.

---

## 4. 0.0.0.0 개방 및 Cloudflare 외부 접속 (CORS) 허용
OpenClaw 서버(18789 포트)에 Cloudflare 도메인(`https://oc2.silverruler.xyz`)으로 우회 접속할 때 발생하는 CORS(Origin 거부) 및 바인딩 오류를 해결하기 위한 설정입니다.

### 4.1. 0.0.0.0/0 포트 바인딩
OpenClaw 최신 버전은 `gateway.bind` 속성을 `"custom"`으로 명시하고 별도로 `customBindHost`를 지정해야만 전체 개방이 가능합니다.
```json
"gateway": {
  "bind": "custom",
  "customBindHost": "0.0.0.0",
  ...
}
```

### 4.2. 브라우저 Origin(CORS) 허용
클라우드플레어 우회 시 발생하는 `Gateway가 Control UI 연결을 수락하기 전에 이 페이지 origin을 거부했습니다` 에러를 막기 위해 다음 설정을 추가했습니다.
```json
"controlUi": {
  "allowedOrigins": [
    "https://oc2.silverruler.xyz",
    "http://oc2.silverruler.xyz",
    "http://localhost:18789",
    "http://127.0.0.1:18789"
  ],
  "allowInsecureAuth": true
}
```

---

## 5. Gateway 보안 접속 토큰(Token) 발급 및 적용
데스크톱이나 외부 브라우저에서 대시보드에 접근할 때 사용할 고정 토큰을 설정했습니다.
```json
"gateway": {
  "auth": {
    "mode": "token",
    "token": "omniroute_token_12345"
  }
}
```
* 외부에서 웹 대시보드(`https://oc2.silverruler.xyz`) 진입 시, **`omniroute_token_12345`** 를 입력하여 로그인 및 디바이스 페어링(Approve)을 통과할 수 있습니다.
* **토큰 변경 명령어**: `openclaw config set gateway.auth.token "새로운_토큰"`

---

## 6. PM2 백그라운드 구동 및 실시간 로그 확인
터미널을 종료해도 OpenClaw 서버가 24시간 가동되도록 PM2를 사용합니다.

```bash
# 백그라운드 실행
pm2 start openclaw -- gateway
```

**[중요] PM2 로그 확인 방법**
PM2 환경에서는 OpenClaw가 TTY(터미널 화면)가 없음을 감지하고 콘솔 출력을 차단하여 파일로만 로그를 씁니다. 따라서 `pm2 logs`에는 아무것도 나오지 않습니다. **실시간 통신/오류 로그**를 보려면 내장 로그 뷰어 명령어를 사용해야 합니다.
```bash
# 실시간 로그 확인
openclaw logs

# (대안) 리눅스 원본 파일 테일링
tail -f /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log
```

---

## 7. 트러블슈팅: 텔레그램 채팅 간헐적 무응답 문제
텔레그램 봇(Approve 등) 채팅 시 서버가 읽고 씹거나 응답을 안 하는 현상이 발생했습니다.
* **원인**: 로그 확인 결과 `Conflict: terminated by other getUpdates request` 에러 발견. 과거에 데스크톱(WSL2)에 켜둔 프로세스(또는 `start.sh`)가 완전히 죽지 않고 백그라운드에서 동일한 봇 토큰으로 폴링을 가로채고(스틸) 있었습니다.
* **해결**: 데스크톱(WSL2) 환경에 남아있는 모든 Node/OpenClaw 프로세스를 `pm2 kill`, `killall -9 node` 등으로 완전히 사살하여, 오직 GCP 서버 단 1대만 텔레그램 봇과 단독 통신하도록 정상화했습니다.

---

## 8. [부록] OpenClaw에서 사용하는 OmniRoute 모델 변경 방법
`auto/best-chat` 모델 대신 옴니라우트 내의 다른 모델(예: `aug/opus4.6`)로 변경하고 싶다면 다음 과정을 따릅니다.

1. **설정 파일 수정**: `/root/.openclaw/openclaw.json` (및 현재 폴더의 설정 파일)을 열어 `models.providers.omniroute.models` 배열 안에 새로운 모델 객체를 추가하거나, 기존 모델의 `"id"`와 `"name"` 속성을 원하는 모델명으로 변경합니다.
2. **기본(Primary) 에이전트 모델 교체**: 파일 상단의 `agents.defaults.model.primary` 값을 `"omniroute/원하는_모델_ID"`로 수정합니다.
3. **적용 및 재시작**: 
   ```bash
   # 설정 문법 검사
   openclaw config validate
   
   # 서버 재시작
   pm2 restart openclaw
   ```
