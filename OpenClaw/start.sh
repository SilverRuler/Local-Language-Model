#!/bin/bash

# ─────────────────────────────────────────────
# OpenClaw 시작 스크립트
# 실행: bash ~/openclaw/start.sh
# ─────────────────────────────────────────────

TELEGRAM_TOKEN="니토큰"
CHAT_ID="니챗아이디"
OLLAMA_URL="http://172.17.0.1:11434"
MODEL="gemma4-uncensored:latest"

tg_send() {
  curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}&text=$1&parse_mode=HTML" > /dev/null
}

echo "[1/4] OpenClaw 컨테이너 시작..."
cd ~/openclaw && docker compose up -d

# 게이트웨이 헬스체크 대기
echo "[2/4] 게이트웨이 준비 대기..."
for i in $(seq 1 30); do
  STATUS=$(curl -s --max-time 2 http://127.0.0.1:18789/healthz 2>/dev/null)
  if [ "$STATUS" = "ok" ] || echo "$STATUS" | grep -q "ok"; then
    echo "  → 게이트웨이 준비됨 (${i}초)"
    break
  fi
  sleep 1
done

# 모델 warm-up (백그라운드)
echo "[3/4] 모델 warm-up 시작 (백그라운드)..."
tg_send "⏳ <b>OpenClaw 시작 중...</b>%0A모델 로딩 중입니다. 잠시 기다려주세요. (약 60초)"

curl -s "${OLLAMA_URL}/api/generate" \
  -d "{\"model\":\"${MODEL}\",\"prompt\":\"\",\"keep_alive\":-1,\"stream\":false}" \
  -o /dev/null

# 완료 알림
echo "[4/4] 완료! 텔레그램 알림 발송..."
SERVER_IP=$(hostname -I | awk "{print \$1}")
tg_send "✅ <b>OpenClaw is ready!</b>%0A%0A🤖 모델: ${MODEL}%0A🌐 대시보드: https://oc.silverruler.xyz%0A🖥️ 서버: ${SERVER_IP}"

echo ""
echo "=== 완료 ==="
ollama ps
docker ps | grep openclaw
