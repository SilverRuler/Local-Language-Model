```
#260801 업데이트해서인지 또 지랄났네
#일단 이걸로 임시로 게이트웨이 켜서 작동시키면 내 설정에 의해서 젬마4로 동작한다
openclaw gateway --allow-unconfigured

#텔레그램만 잘 안될때는 같은 토큰에 대해 이중 사용인지 확인
wsl --shutdown

```
```
#WSL2
~/.bashrc

# OpenClaw Completion
alias openclaw="docker compose -f /home/base/openclaw/docker-compose.yml exec openclaw-gateway node dist/index.js"
export OLLAMA_MODELS=/mnt/g/ollama/models
```

```
#WSL2 IP 보기
wsl hostname -I
```

```
#실제 마운트된 json을 찾아야하며
#토큰별 페어링 코드를 allow 해야함
docker exec openclaw-openclaw-gateway-1 node dist/index.js pairing list
docker exec openclaw-openclaw-gateway-1 node dist/index.js pairing approve --code <코드>
```

```
openclaw gateway status
openclaw devices list
openclaw devices approve <request-ID>
```

```
#터미널에서 agent 키는법
openclaw tui

#이 명령어들은 Gateway가 떠 있어야 정상 동작합니다
openclaw gateway status
openclaw gateway start

#설정 같은거 문제생기면 닥터로 수정
openclaw doctor
```

```
#하드코딩된 컨텍스트 값 수정
jq '.models.providers.ollama.models[0].contextWindow = 16384' \
    ~/.openclaw/openclaw.json > /tmp/openclaw.json.new
mv /tmp/openclaw.json.new ~/.openclaw/openclaw.json
```

```
#도커기반이라 홈 디렉터리를 인식하는데 있어서 컨테이너의 /home/node/.openclaw/workspace 를 인식하는데 그걸 수정해야함
#docker-compose.yml에 변수로 되어있다
#volumes:
#  - ${OPENCLAW_CONFIG_DIR}:/home/node/.openclaw
#  - ${OPENCLAW_WORKSPACE_DIR}:/home/node/.openclaw/workspace
#즉 .env를 봐야한다
OPENCLAW_CONFIG_DIR=/home/base/.openclaw
OPENCLAW_WORKSPACE_DIR=/home/base/.openclaw/workspace
OPENCLAW_GATEWAY_PORT=18789
OPENCLAW_BRIDGE_PORT=18790
OPENCLAW_GATEWAY_BIND=lan
OPENCLAW_GATEWAY_TOKEN=f436f7bcdb6da4b5e1fdb758229f879f8c9cf6a4ab4bc1c6e954a4edddb93d5a
```
```
#도커 접근
docker compose exec openclaw-gateway bash
#오픈 클로 들어가서 내부 명령어
openclaw message send   --channel telegram   --target 1777952457   --media ./hello2.py
```
```
#더 찾아야할게 생기면 내 오픈클로 대화 pdf 참조
```
