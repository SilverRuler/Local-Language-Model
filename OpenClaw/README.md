```
WSL2
~/.bashrc

# OpenClaw Completion
alias openclaw="docker compose -f /home/base/openclaw/docker-compose.yml exec openclaw-gateway node dist/index.js"
export OLLAMA_MODELS=/mnt/g/ollama/models
```

```
WSL2 IP 보기
wsl hostname -I
```

```
실제 마운트된 json을 찾아야하며
토큰별 페어링 코드를 allow 해야함
docker exec openclaw-openclaw-gateway-1 node dist/index.js pairing list
docker exec openclaw-openclaw-gateway-1 node dist/index.js pairing approve --code <코드>
```

```
openclaw gateway status
openclaw devices list
openclaw devices approve <request-ID>
```

```
터미널에서 agent 키는법
openclaw tui

이 명령어들은 Gateway가 떠 있어야 정상 동작합니다
openclaw gateway status
openclaw gateway start
```

```
더 찾아야할게 생기면 내 오픈클로 대화 pdf 참조
```
