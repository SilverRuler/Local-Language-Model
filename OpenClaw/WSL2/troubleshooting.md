# WSL2에서 실행 중인 서비스에 Windows 호스트가 접근 못하는 문제 트러블슈팅

> **환경:** Windows 데스크톱(호스트) + WSL2(Ubuntu) 위의 OpenClaw Gateway (포트 18789)  
> **증상:** 호스트 Chrome에서 `localhost:18789` 접속 불가, `oc.silverruler.xyz`(외부 rinetd 경유)로만 접속 가능

---

## 1. 문제 상황 요약

WSL2 내부에서 OpenClaw Gateway가 `0.0.0.0:18789`로 정상 리스닝 중임에도,  
Windows 호스트의 브라우저에서 `localhost:18789` 또는 `127.0.0.1:18789` 접속이 불가능한 상태.

같은 WSL2 위에서 실행 중인 Ollama(`11434`)는 호스트에서 정상 접속되는 상황이라  
더욱 혼란스러운 증상이었음.

---

## 2. 초기 오해 — bind 설정 문제라고 판단

### 2-1. openclaw.json 설정 확인

```json
"gateway": {
  "mode": "local",
  "port": 18789,
  "bind": "lan"
}
```

`bind: "lan"` 이면 `0.0.0.0`에 바인딩. WSL2 내부에서 확인:

```bash
ss -tlnp | grep 18789
# LISTEN 0.0.0.0:18789   → 모든 인터페이스 리스닝 확인
```

### 2-2. bind를 loopback으로 바꿔봤으나 의미 없음

`bind: "loopback"`으로 변경 → `127.0.0.1:18789`에만 바인딩됨  
→ 외부 접속(rinetd 경유 `oc.silverruler.xyz`) 차단됨  
→ 원래 문제(호스트 localhost 접속 불가)는 해결 안 됨  
→ **bind 설정은 원인이 아니었음, `lan`으로 원복**

> **결론:** OpenClaw의 `bind` 설정은 WSL2 내부 네트워크 인터페이스 선택 문제로,  
> Windows 호스트 접근 가능 여부와는 무관하다.

---

## 3. 두 번째 오해 — Windows Defender 방화벽 문제라고 판단

`localhostForwarding=true`가 `.wslconfig`에 설정되어 있어도 Windows Firewall이  
WSL2에서 포워딩된 트래픽을 차단할 수 있다고 판단.

```powershell
# 방화벽 인바운드 규칙 추가 시도
New-NetFirewallRule -DisplayName "OpenClaw Gateway 18789" `
  -Direction Inbound -Protocol TCP -LocalPort 18789 -Action Allow
```

→ `wf.msc` 확인 결과 18789 규칙이 이미 등록되어 있었음  
→ 규칙 추가해도 접속 불가  
→ **방화벽도 원인이 아니었음**

> **결론:** 방화벽 규칙이 이미 존재했다는 건, 과거에 이미 이 문제를 겪고 설정했었다는 흔적.

---

## 4. 실제 원인 발견 — iphlpsvc의 stale portproxy

### 4-1. WSL2 게이트웨이 IP에서 18789 테스트

WSL2 내부에서 Windows 호스트 IP(WSL2 게이트웨이)로 직접 요청:

```bash
# WSL2 내부에서
WINDOWS_HOST_IP=$(ip route | grep default | awk '{print $3}')
# → 172.17.96.1

curl -sv http://172.17.96.1:18789/
# → Connected! 하지만 Empty reply from server
```

**TCP 연결은 됨 → Windows 쪽에 18789 포트를 점유한 무언가가 있음.**

### 4-2. Windows 쪽 포트 점유 프로세스 확인

```powershell
netstat -ano | findstr :18789
# TCP    0.0.0.0:18789    0.0.0.0:0    LISTENING    5184

tasklist | findstr 5184
# svchost.exe    5184

tasklist /svc /fi "PID eq 5184"
# svchost.exe    5184    iphlpsvc
```

### 4-3. iphlpsvc의 정체

`iphlpsvc` = **IP Helper 서비스** = WSL2 `localhostForwarding`의 실제 구현체.

WSL2가 내부에서 특정 포트가 리스닝되는 것을 감지하면,  
iphlpsvc를 통해 Windows 쪽 `localhost:포트`를 WSL2 내부 IP로 포워딩하는  
portproxy 규칙을 자동 생성한다.

즉 iphlpsvc가 18789를 점유하고 있다는 건 **포워딩 자체는 설정되어 있다는 뜻**.

### 4-4. stale portproxy — 핵심 원인

```powershell
netsh interface portproxy show v4tov4
```

위 명령으로 확인하면, 포워딩 목적지 IP가 **현재 WSL2 IP가 아닌 과거 세션의 IP**를 가리키고 있었음.

```
현재 WSL2 IP:  172.17.98.249   ← 실제 서비스가 떠있는 곳
portproxy 목적지: 172.17.xx.xx  ← 이전 세션의 죽은 IP (stale)
```

#### 왜 이런 일이 생기나?

WSL2는 재시작할 때마다 내부 IP가 바뀐다.  
iphlpsvc의 portproxy 규칙은 WSL2 시작 시 자동으로 갱신되어야 하지만,  
**간혹 갱신에 실패하거나 이전 규칙이 잔존**하여 stale 상태가 된다.

```
[이전 WSL2 세션]
  WSL2 IP: 172.17.50.100
  portproxy: localhost:18789 → 172.17.50.100:18789  ← 등록됨

[WSL2 재시작]
  WSL2 IP: 172.17.98.249  ← 바뀜
  portproxy: localhost:18789 → 172.17.50.100:18789  ← 갱신 실패, 여전히 죽은 IP

[결과]
  Chrome → localhost:18789 → iphlpsvc → 172.17.50.100:18789 → dead → 접속 실패
```

#### Ollama(11434)는 왜 됐나?

Ollama는 이 WSL2 세션에서 처음부터 떠있었고, WSL2 시작 시 portproxy가 정상적으로 생성되어 현재 IP를 올바르게 가리키고 있었음.  
OpenClaw(18789)는 이전 세션에서 등록된 stale 규칙이 남아 충돌한 것.

---

## 5. 해결 방법

### 방법 1: portproxy 수동 갱신 (즉시 적용)

```powershell
# 기존 stale 룰 삭제
netsh interface portproxy delete v4tov4 listenport=18789 listenaddress=0.0.0.0

# 현재 WSL2 IP로 새로 추가
# (WSL2 IP는 WSL2 내부에서 `ip addr show eth0`로 확인)
netsh interface portproxy add v4tov4 `
  listenport=18789 listenaddress=0.0.0.0 `
  connectport=18789 connectaddress=172.17.98.249
```

→ **이 방법으로 해결됨.**

### 방법 2: WSL2 완전 재시작 (자동 갱신 시도)

```powershell
wsl --shutdown
# 이후 WSL2 재시작
```

재시작 시 iphlpsvc가 portproxy를 새 IP로 자동 갱신함.  
단, 간혹 자동 갱신이 실패하는 경우 방법 1을 사용해야 함.

### 방법 3: WSL2 Mirrored 네트워킹 모드 (근본 해결)

`.wslconfig`에서 mirrored 모드로 변경하면 IP가 고정되어 이 문제가 근본적으로 발생하지 않음:

```ini
[wsl2]
networkingMode=mirrored
```

단, mirrored 모드는 Windows 11 22H2 이상 + WSL 2.0.0 이상에서만 지원.

---

## 6. 전체 흐름 정리

```
증상: 호스트 Chrome에서 localhost:18789 접속 불가
  │
  ├─ [오해 1] OpenClaw bind 설정 문제?
  │     bind: "lan" → 0.0.0.0 바인딩 확인
  │     loopback으로 바꿔봤으나 오히려 외부 접속까지 차단
  │     → bind는 관계없음 ✗
  │
  ├─ [오해 2] Windows Defender 방화벽 문제?
  │     방화벽 규칙 이미 존재 + 추가해도 안 됨
  │     → 방화벽은 관계없음 ✗
  │
  ├─ [단서] WSL2 내부에서 Windows 호스트 IP:18789 → Empty reply
  │     → Windows 쪽에 18789를 점유한 프로세스 존재
  │
  ├─ [확인] netstat → PID 5184, tasklist → svchost.exe(iphlpsvc)
  │     → WSL2 localhostForwarding 포트프록시 메커니즘 자체가 18789 점유 중
  │
  ├─ [원인] portproxy의 목적지 IP가 이전 WSL2 세션의 죽은 IP (stale)
  │     현재 WSL2 IP: 172.17.98.249
  │     portproxy 목적지: 구버전 IP → 연결 실패
  │
  └─ [해결] netsh portproxy 삭제 후 현재 IP로 재등록 → 접속 성공 ✅
```

---

## 7. 향후 예방

WSL2 재시작 후 portproxy가 자동 갱신되지 않는 경우를 대비해,  
아래 PowerShell 스크립트를 WSL2 시작 시 실행되도록 등록해두면 편리함:

```powershell
# refresh-wsl2-portproxy.ps1
$wslIp = (wsl hostname -I).Trim().Split()[0]
$port = 18789

netsh interface portproxy delete v4tov4 listenport=$port listenaddress=0.0.0.0 2>$null
netsh interface portproxy add v4tov4 listenport=$port listenaddress=0.0.0.0 connectport=$port connectaddress=$wslIp

Write-Host "portproxy updated: localhost:$port → $wslIp`:$port"
```
