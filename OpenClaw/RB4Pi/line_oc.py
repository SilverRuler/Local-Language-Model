#!/usr/bin/env python3
"""
line_oc.py — OpenClaw + OmniRoute + LINE 자동 설정 스크립트
============================================================
새 라즈베리파이에서 OpenClaw를 OmniRoute + LINE으로 한 번에 설정한다.

사용법:
  python3 line_oc.py --omniroute-url http://127.0.0.1:20128/v1 --omniroute-key sk-xxx
  python3 line_oc.py --omniroute-url http://127.0.0.1:20128/v1 --omniroute-key sk-xxx \\
                     --line-token "토큰" --line-secret "시크릿"
  python3 line_oc.py --omniroute-url http://127.0.0.1:20128/v1 --omniroute-key sk-xxx \\
                     --line-token "토큰" --line-secret "시크릿" --restart-gateway
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ─── 색상 출력 ───────────────────────────────────────────────────────────────
def green(s):  return f"\033[92m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def red(s):    return f"\033[91m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"
def cyan(s):   return f"\033[96m{s}\033[0m"

def step(n, total, msg):
    print(f"\n{cyan(f'[{n}/{total}]')} {bold(msg)}")

def ok(msg):   print(f"  {green('✓')} {msg}")
def warn(msg): print(f"  {yellow('⚠')} {msg}")
def err(msg):  print(f"  {red('✗')} {msg}")

# ─── 설정 경로 ────────────────────────────────────────────────────────────────
CONFIG_PATH = Path(os.path.expanduser("~/.openclaw/openclaw.json"))
CONFIG_BAK  = Path(os.path.expanduser("~/.openclaw/openclaw.json.bak"))

# ─── 인자 파싱 ────────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="OpenClaw + OmniRoute + LINE 자동 설정 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # OmniRoute만 설정
  python3 line_oc.py --omniroute-url http://127.0.0.1:20128/v1 --omniroute-key sk-xxx

  # OmniRoute + LINE 한번에
  python3 line_oc.py \\
    --omniroute-url http://127.0.0.1:20128/v1 \\
    --omniroute-key sk-xxx \\
    --line-token "채널_액세스_토큰" \\
    --line-secret "채널_시크릿"

  # gateway 자동 재시작 포함
  python3 line_oc.py \\
    --omniroute-url http://127.0.0.1:20128/v1 \\
    --omniroute-key sk-xxx \\
    --line-token "채널_액세스_토큰" \\
    --line-secret "채널_시크릿" \\
    --restart-gateway

  # OmniRoute가 다른 서버에 있는 경우
  python3 line_oc.py \\
    --omniroute-url http://192.168.1.100:20128/v1 \\
    --omniroute-key sk-xxx \\
    --line-token "채널_액세스_토큰" \\
    --line-secret "채널_시크릿"
        """
    )
    parser.add_argument(
        "--omniroute-url",
        default="http://127.0.0.1:20128/v1",
        help="OmniRoute baseUrl (기본값: http://127.0.0.1:20128/v1)"
    )
    parser.add_argument(
        "--omniroute-key",
        default="YOUR_KEY",
        help="OmniRoute API 키"
    )
    parser.add_argument(
        "--model-id",
        default="auto/best-chat",
        help="사용할 모델 ID (기본값: auto/best-chat)"
    )
    parser.add_argument(
        "--line-token",
        default=None,
        help="LINE Channel Access Token (없으면 LINE 설정 건너뜀)"
    )
    parser.add_argument(
        "--line-secret",
        default=None,
        help="LINE Channel Secret"
    )
    parser.add_argument(
        "--tmux-session",
        default="openclaw",
        help="openclaw가 실행될 tmux 세션 이름 (기본값: openclaw)"
    )
    parser.add_argument(
        "--restart-gateway",
        action="store_true",
        help="설정 완료 후 tmux에서 gateway를 자동 재시작"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="기존 설정 백업 생성 안 함"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제로 파일을 수정하지 않고 변경사항만 출력"
    )
    return parser.parse_args()


# ─── 메인 로직 ───────────────────────────────────────────────────────────────
def main():
    args = parse_args()

    print(bold("\n══════════════════════════════════════════════════"))
    print(bold("  OpenClaw + OmniRoute + LINE 자동 설정 스크립트"))
    print(bold("══════════════════════════════════════════════════\n"))

    total_steps = 5
    if args.line_token:
        total_steps = 6
    if args.restart_gateway:
        total_steps += 1

    # ── Step 1: 설정 파일 확인 ──────────────────────────────────────────────
    step(1, total_steps, "설정 파일 확인")

    if not CONFIG_PATH.exists():
        err(f"설정 파일이 없습니다: {CONFIG_PATH}")
        err("openclaw가 설치되어 있는지 확인하고, 한 번 실행해서 초기화해주세요.")
        err("  openclaw configure")
        sys.exit(1)

    ok(f"설정 파일 발견: {CONFIG_PATH}")

    # ── Step 2: 백업 ────────────────────────────────────────────────────────
    step(2, total_steps, "기존 설정 백업")

    if args.no_backup:
        warn("--no-backup 옵션: 백업 생성 건너뜀")
    elif args.dry_run:
        warn("--dry-run 옵션: 백업 시뮬레이션만")
    else:
        shutil.copy2(CONFIG_PATH, CONFIG_BAK)
        ok(f"백업 생성: {CONFIG_BAK}")

    # ── Step 3: 설정 로드 ──────────────────────────────────────────────────
    step(3, total_steps, "현재 설정 로드")

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        ok("JSON 파싱 성공")
    except json.JSONDecodeError as e:
        err(f"JSON 파싱 실패: {e}")
        err("설정 파일이 손상되었습니다. 백업에서 복구하거나 openclaw configure를 재실행하세요.")
        sys.exit(1)

    # ── Step 4: OmniRoute 설정 추가 ────────────────────────────────────────
    step(4, total_steps, "OmniRoute 설정 추가")

    model_id = args.model_id
    omniroute_url = args.omniroute_url
    omniroute_key = args.omniroute_key

    # models 섹션
    config["models"] = {
        "mode": "merge",
        "providers": {
            "omniroute": {
                "baseUrl": omniroute_url,
                "api": "openai-completions",
                "apiKey": omniroute_key,
                "models": [
                    {
                        "id": model_id,
                        "name": model_id,
                        "reasoning": True,
                        "input": ["text"],
                        "cost": {
                            "input": 0,
                            "output": 0,
                            "cacheRead": 0,
                            "cacheWrite": 0
                        },
                        "contextWindow": 128000,
                        "maxTokens": 8192,
                        "compat": {
                            "supportsTools": True,
                            "supportsUsageInStreaming": True
                        }
                    }
                ]
            }
        }
    }
    ok(f"models.providers.omniroute → {omniroute_url}")

    # agents 섹션
    if "agents" not in config:
        config["agents"] = {}
    if "defaults" not in config["agents"]:
        config["agents"]["defaults"] = {}

    full_model_id = f"omniroute/{model_id}"
    config["agents"]["defaults"]["model"] = {"primary": full_model_id}
    config["agents"]["defaults"]["models"] = {full_model_id: {}}
    ok(f"agents.defaults.model.primary → {full_model_id}")

    # auth 섹션
    if "auth" not in config:
        config["auth"] = {}
    if "profiles" not in config["auth"]:
        config["auth"]["profiles"] = {}

    config["auth"]["profiles"]["omniroute:default"] = {
        "provider": "omniroute",
        "mode": "api_key"
    }
    ok("auth.profiles.omniroute:default → api_key 모드")

    # ── Step 5: LINE 설정 추가 (옵션) ──────────────────────────────────────
    current_step = 5
    if args.line_token:
        step(current_step, total_steps, "LINE 채널 설정 추가")
        current_step += 1

        if not args.line_secret:
            err("--line-token 사용 시 --line-secret도 필요합니다.")
            sys.exit(1)

        # channels 섹션
        if "channels" not in config:
            config["channels"] = {}
        config["channels"]["line"] = {
            "enabled": True,
            "channelAccessToken": args.line_token,
            "channelSecret": args.line_secret
        }
        ok("channels.line 설정 완료")

        # plugins 섹션
        if "plugins" not in config:
            config["plugins"] = {}
        if "entries" not in config["plugins"]:
            config["plugins"]["entries"] = {}
        config["plugins"]["entries"]["line"] = {"enabled": True}
        ok("plugins.entries.line → enabled")

        # LINE 웹훅 URL 안내
        print(f"\n  {yellow('★')} LINE Developer Console 웹훅 URL 등록 필요:")
        print(f"     {bold('https://YOUR_DOMAIN/line/webhook')}")
        print(f"  {yellow('★')} /channels/line/webhook 가 아닌 /line/webhook 임에 주의!")
    else:
        warn("--line-token 미제공: LINE 설정 건너뜀")

    # ── Step 5 or 6: 설정 저장 ─────────────────────────────────────────────
    step(current_step, total_steps, "설정 파일 저장")
    current_step += 1

    new_config_str = json.dumps(config, indent=2, ensure_ascii=False)

    if args.dry_run:
        warn("--dry-run 모드: 실제 저장 안 함. 변경될 내용 미리보기:")
        print("\n" + "─" * 60)
        # models/agents/auth 요약만 출력
        summary = {
            "models": config.get("models", {}),
            "agents": config.get("agents", {}),
            "auth": config.get("auth", {}),
        }
        if args.line_token:
            summary["channels"] = config.get("channels", {})
            summary["plugins"] = config.get("plugins", {})
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        print("─" * 60 + "\n")
    else:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(new_config_str)
        ok(f"설정 저장 완료: {CONFIG_PATH}")

    # JSON 유효성 최종 확인
    try:
        json.loads(new_config_str)
        ok("JSON 유효성 검증 통과")
    except json.JSONDecodeError as e:
        err(f"JSON 유효성 오류: {e}")
        if not args.dry_run:
            warn("백업에서 복구 중...")
            shutil.copy2(CONFIG_BAK, CONFIG_PATH)
            warn(f"복구 완료: {CONFIG_BAK} → {CONFIG_PATH}")
        sys.exit(1)

    # ── 마지막 Step: gateway 재시작 (옵션) ─────────────────────────────────
    if args.restart_gateway:
        step(current_step, total_steps, f"openclaw gateway 재시작 (tmux: {args.tmux_session})")

        session = args.tmux_session

        # tmux 세션 존재 여부 확인
        result = subprocess.run(
            ["tmux", "has-session", "-t", session],
            capture_output=True
        )

        if result.returncode != 0:
            warn(f"tmux 세션 '{session}' 없음. 새로 생성 중...")
            subprocess.run(["tmux", "new-session", "-d", "-s", session])
            ok(f"tmux 세션 '{session}' 생성됨")
            time.sleep(0.5)
            subprocess.run(["tmux", "send-keys", "-t", session, "openclaw gateway", "Enter"])
        else:
            ok(f"tmux 세션 '{session}' 발견. 재시작 중...")
            # 기존 프로세스 종료
            subprocess.run(["tmux", "send-keys", "-t", session, "C-c", ""])
            time.sleep(1.5)
            # 재시작
            subprocess.run(["tmux", "send-keys", "-t", session, "openclaw gateway", "Enter"])

        ok("openclaw gateway 시작 명령 전송")
        print(f"  {yellow('→')} 잠시 후 상태 확인:")
        print(f"     {bold(f'tmux capture-pane -t {session} -p | tail -15')}")

        # 5초 후 상태 캡처
        time.sleep(5)
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", session, "-p"],
            capture_output=True, text=True
        )
        output = result.stdout

        if "ready" in output:
            ok("gateway ready 확인!")
        elif "error" in output.lower():
            warn("에러 감지. 로그 확인 필요:")
            for line in output.split("\n")[-15:]:
                if line.strip():
                    print(f"     {line}")
        else:
            warn("아직 시작 중... 직접 확인:")
            print(f"     tmux attach -t {session}")

        if args.line_token and "line" in output.lower():
            ok("LINE provider 시작 확인!")

    # ── 완료 메시지 ──────────────────────────────────────────────────────────
    print(f"\n{bold('══════════════════════════════════════════════════')}")
    print(f"{green('  ✓ 설정 완료!')}")
    print(f"{bold('══════════════════════════════════════════════════')}\n")

    sess = args.tmux_session
    cmd_start = bold('tmux send-keys -t ' + sess + ' "openclaw gateway" Enter')
    cmd_check = bold('tmux capture-pane -t ' + sess + ' -p | tail -10')
    print("다음 단계:")
    print(f"  1. gateway가 실행 중이 아니라면:")
    print(f"     {cmd_start}")
    print(f"  2. 상태 확인:")
    print(f"     {cmd_check}")

    if args.line_token:
        print(f"  3. LINE Developer Console에서 웹훅 URL 등록:")
        print(f"     {bold('https://YOUR_DOMAIN/line/webhook')}")
        print(f"     (Messaging API 탭 → Webhook URL → Verify)")
        print(f"  4. Pairing:")
        print(f"     {bold('openclaw pair')}")
        print(f"  5. Auto-reply 끄기:")
        print(f"     {bold('https://manager.line.biz → 응답 설정 → 자동응답 끄기')}")
    else:
        print(f"  3. Pairing:")
        print(f"     {bold('openclaw pair')}")

    if not args.dry_run and not args.no_backup:
        print(f"\n  백업 위치: {CONFIG_BAK}")
        print(f"  복구: cp {CONFIG_BAK} {CONFIG_PATH}")

    print()


if __name__ == "__main__":
    main()
