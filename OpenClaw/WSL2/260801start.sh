#!/bin/bash
# ─────────────────────────────────────────────
# OpenClaw 네이티브(pm2) 시작 스크립트
# ─────────────────────────────────────────────
TELEGRAM_TOKEN="8653818281:AAG-jsjWnKcLyDG7Olbr4iqsvSXrboSSyh0"
CHAT_ID="1777952457"
OLLAMA_URL="http://127.0.0.1:11434"
MODEL="gemma4-uncensored:latest"
GATEWAY_PORT=18789

tg_send() {
  curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}&text=$1&parse_mode=HTML" > /dev/null
}

tg_send "⏳ <b>OpenClaw 시작 중...</b>%0A모델 로딩 중입니다. 잠시 기다려주세요. (약 60초)"

# 헬스체크 + 워밍업 + 완료알림은 백그라운드에서 진행
(
  echo "[대기] 게이트웨이 준비 대기..."
  for i in $(seq 1 30); do
    STATUS=$(curl -s --max-time 2 "http://127.0.0.1:${GATEWAY_PORT}/healthz" 2>/dev/null)
    if echo "$STATUS" | grep -q "ok"; then
      echo "  → 게이트웨이 준비됨 (${i}초)"
      break
    fi
    sleep 1
  done

  echo "[워밍업] 모델 로딩 시작..."
  curl -s "${OLLAMA_URL}/api/generate" \
    -d "{\"model\":\"${MODEL}\",\"prompt\":\"\",\"keep_alive\":-1,\"stream\":false}" \
    -o /dev/null

  SERVER_IP=$(hostname -I | awk '{print $1}')
  tg_send "✅ <b>OpenClaw is ready!</b>%0A%0A🤖 모델: ${MODEL}%0A🌐 대시보드: https://oc.silverruler.xyz%0A🖥️ 서버: ${SERVER_IP}"
) &

# pm2가 이 프로세스를 감시하도록 exec로 넘김 (여기서 셸이 게이트웨이 프로세스로 대체됨)
exec openclaw gateway
