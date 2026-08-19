```
#원격 접속 제어 할떄는 뭐고 안할떄는 뭔지 도저히 모르겠음
omniroute launch --profile auto-best-coding --dangerously-skip-permissions --remote http://oci2.silverruler.xyz:20128
```
```
#환경변수

#claude with 9router
alias cl9="claude --dangerously-skip-permissions"
function clo() { omniroute launch --profile auto-best-coding --dangerously-skip-permissions --remote http://oci.silverruler.xyz:20128 -- "$@"; }
```
