```
1. ~/.claude/settings.json 설정

WSL2에서:

mkdir -p ~/.claude
nano ~/.claude/settings.json

다음처럼 설정합니다.

{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:20129/v1",
    "ANTHROPIC_AUTH_TOKEN": "9Router_API_KEY",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "oc/hy3-free",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "oc/hy3-free",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "oc/hy3-free"
  }
}

9Router 공식 문서에서도 Claude Code에 ANTHROPIC_BASE_URL과 인증 토큰을 지정하는 형태를 안내하고 있고, 실제 GitHub 이슈에서도 ANTHROPIC_DEFAULT_OPUS_MODEL, ANTHROPIC_DEFAULT_SONNET_MODEL, ANTHROPIC_DEFAULT_HAIKU_MODEL을 9Router 모델명으로 지정하는 설정이 확인됩니다.

여기서 9Router_API_KEY는 9Router Dashboard에서 발급된 키를 넣으면 됩니다.
```
