```
옴니는 호스트에서 돌고, 오픈웹UI가 도커라서 base url을 다음처럼 적고
KEY는 옴니라우트20128 에 들어가서 발급받는다
```
```
      # 옴니라우트는 호스트 머신에 있으므로 host.docker.internal을 통해 접근합니다.
      - OPENAI_API_BASE_URL=http://host.docker.internal:20128/v1
      - OPENAI_API_KEY=YOUR_API
```
