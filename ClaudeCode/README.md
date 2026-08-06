```
#tmux에 무한루프 엔터 신호 보내기

while true
do
    tmux send-keys -t oc Enter
    sleep 2
done
```
