```
260831 기준 무료 라우팅 모델 다 뒤짐

  ### 💡 호출 예시 (Python / curl)

  엔드포인트: https://opencode.ai/zen/v1/chat/completions
  모델명: big-pickle

  curl 예시:

    curl -X POST https://opencode.ai/zen/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer YOUR_KEY" \
      -H "User-Agent: opencode/1.18.25" \
      -d '{"model":"big-pickle", "messages":[{"role":"user","content":"Hi"}]}'

```

```
https://opencode.ai/ko
```
```
npm install -g opencode-ai
opencode auth login
->opencode zen
```

```
전체 모델 수: 64

=== 무료로 사용 가능한 모델 ===
  - big-pickle
  - hy3-free
  - mimo-v2.5-free
  - muse-spark-1.2-contributor-free
  - nemotron-3-ultra-free
  - nemotron-3.5-lightning-free
  - x-preview-f-free

※ 참고: API 응답에 가격 필드가 없어 문서 기준으로 무료 여부를 확정할 수 없었던 모델도 있습니다.
   정확한 최신 가격은 https://opencode.ai/docs/zen/ 에서 확인하시는 게 안전합니다.
```
