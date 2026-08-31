```
260831 기준
oc 프로바이더들은 다 박살나서
openrouter 프로바이더가 필요. openrouter에 가입해서 개별적으로 키 받고
9라우터 프로바이더에서 오픈라우터 키 등록 및 가용한 모델들 전부다 클릭해주기 (네트워크 상황따라 fail 나는 모델도 있지만 일단 클릭)
그후에 콤보 들어가서 oc 계열은 헤더 검증 필요하니까 패쓰하고 openrouter 계열로 몇몇개 넣어주고 실행
```

```
  pm2 delete 9router
    pm2 start 9router --name '9router' -- --port 20129 --tray
    pm2 save
```
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
