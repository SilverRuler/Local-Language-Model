```
#tmux에 무한루프 엔터 신호 보내기

while true
do
    tmux send-keys -t oc Enter
    sleep 2
done
```

```
#셋업, WSL2일 경우 다시킬때 매번 다시해야함
omniroute setup-claude \
  --remote http://옴니라우트주소:20128
```

```
#클코 강제라우팅
omniroute launch --profile auto-best-coding
```

```
#api키 세팅은 주로 오픈클로에서
```
