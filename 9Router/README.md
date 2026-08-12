```
#옴니라우트처럼 자동라우트 기능은 없음 oc 계열의 free 사용해야함
#인스톨 정리, 노드 설치 필수
npm install -g 9router

#포트 변경 실행
9router --port 20129

#환경변수(키) 등록
echo "export NINEROUTER_KEY='YOUR_API_KEY'" >> ~/.bashrc
source ~/.bashrc

#default API ENDPOINT
http://localhost:20128/v1

#API 호출 확인용
curl http://gem.silverruler.xyz:20129/v1/chat/completions \
-H "Authorization: Bearer $NINEROUTER_KEY" \
-H "Content-Type: application/json" \
-d '{
"model": "oc/hy3-free",
"messages": [
{
"role": "user",
"content": "Reply with exactly: 9Router test successful."
}
],
"max_tokens": 50
}'

```

```
========================================
  Choose Interface (v0.5.50)
  🚀 Server: http://localhost:20129
========================================

 ★ Web UI (Open in Browser)
  ☆ Terminal UI (Interactive CLI)
  ☆ Hide to Tray (Background)
  ☆ Exit

Press Enter to go back to menu...Open browser man

Press Enter to go back to menu...
```
