```
260831 기준 가용 모델
  [NVIDIA Nemotron 계열 - 가장 강력함]

  • nvidia/nemotron-3-ultra-550b-a55b:free (무려 550B 파라미터의 거대 모델, 마지막에 정상 응답 확인!)
  • nvidia/nemotron-3-super-120b-a12b:free
  • nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free (추론 특화)
  • nvidia/nemotron-3.5-lightning:free
  • nvidia/nemotron-3.5-content-safety:free

  [그 외 유망한 성능의 모델들]

  • cohere/north-mini-code:free (코딩 및 논리 특화)
  • minimax/minimax-m3:free / minimax/minimax-m2.7:free (중화권 텍스트 강자)
  • poolside/laguna-s-2.1:free / poolside/laguna-xs-2.1:free
  • liquid/lfm-2.5-2.6b:free
  • inclusionai/ling-3.0-flash-fin:free
  • dots-studio/dots-3-note-preview:free
  • openrouter/free (오픈라우터 자체 자동 라우팅 무료 모델)

```
```
• 기본 엔드포인트 URL: https://openrouter.ai/api/v1
  • 채팅(completions) URL: https://openrouter.ai/api/v1/chat/completions
  • 모델 조회 URL: https://openrouter.ai/api/v1/models

```
```
#개념
OpenRouter는 별도의 로컬 프로그램을 설치해서 돌리는 서비스가 아닙니다.
쉽게 말하면 여러 LLM API를 하나의 OpenAI-compatible API로 묶어주는 LLM 라우터/집계 서비스입니다. OpenRouter 자체가 모델을 실행하는 게 아니라, 요청을 받아 OpenAI·Anthropic·Google·DeepSeek 등 여러 모델 제공업체로 전달합니다.
```
```
#베이스URL
base_url="https://openrouter.ai/api/v1"
```
```
#모델 목록 확인 API
curl https://openrouter.ai/api/v1/models
```

```
#할 필요 있나 싶음
openrouter.ai의 
srt 스크립트 번역 테스트
openwebui 연동
openclaw 연동
claude code 연동
```
