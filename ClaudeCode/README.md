```
#GCP ubuntu 로컬계정
alias clo="omniroute launch --profile auto-best-coding --dangerously-skip-permissions"
alias cloo="omniroute launch --profile auto-best-coding --dangerously-skip-permissions --remote http://oci2.silverruler.xyz:20128"
alias cl9="claude --dangerously-skip-permissions"
```
```
#WSL2, GCP 에서 로컬 계정으로 clo
alias cloo="omniroute launch --profile auto-best-coding --dangerously-skip-permissions --remote http://oci2.silverruler.xyz:20128"
```
```
방법 B. 설정 파일 직접 수정하기
  Claude Code가 현재 프로필의 설정을 저장하는 JSON 파일을 열어 모델을 수동으로 변경합니다.

  • 파일 경로: /home/ubuntu/.claude/profiles/auto-best-coding/settings.json
  • 해당 파일의 "model" 값을 "auto/best-coding"으로 수정하고 저장합니다.

```
```
#tmux에 무한루프 엔터 신호 보내기

while true
do
    tmux send-keys -t oc Enter
    sleep 2
done
```

```
#초기세팅, WSL2일 경우 다시킬때 매번 다시해야함
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
