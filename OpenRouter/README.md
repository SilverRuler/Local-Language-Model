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
