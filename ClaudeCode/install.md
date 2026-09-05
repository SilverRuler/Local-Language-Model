# 9Router Claude Code AI Setup Guide

이 문서는 AI 에이전트가 다른 서버에서 9Router 기반의 Claude Code를 자동으로 세팅하기 위한 명세서입니다. AI 에이전트는 이 문서의 절차에 따라 사용자 개입 없이 환경을 구성하십시오.

## 목표
- `ubuntu` 계정을 사용하여 9Router API Billing 환경 구축
- Claude Code의 사용자 지정 모델 세팅 적용 (Opus, Sonnet, Haiku)
- 루트(`root`) 계정에서 `cl9` 명령어 입력 시 자동으로 `ubuntu` 계정으로 전환되어 Claude Code가 실행되도록 설정

## 사전 준비
이 문서와 함께 제공된 `260905U9Router.tar` 파일이 서버에 있어야 합니다. (기본 위치: `/root/260905U9Router.tar`)

## 실행 절차 (AI Agent용)

### 1. 계정 및 패키지 확인
1. `ubuntu` 계정이 존재하는지 확인하고, 없다면 생성합니다. (`useradd -m -s /bin/bash ubuntu`)
2. `npm` 명령어 사용이 가능한지 확인합니다. (Node.js 설치 필요)

### 2. Claude Code 전역 설치
다음 명령어로 `@anthropic-ai/claude-code`를 시스템 전역에 설치합니다.
```bash
npm install -g --prefix /usr/local @anthropic-ai/claude-code
```

### 3. 설정 파일 압축 해제 및 배치
제공된 `.tar` 파일의 압축을 해제하여 `.claude` 설정 폴더를 `ubuntu` 계정 홈 디렉터리에 배치합니다.
```bash
# 예시: /root/260905U9Router.tar 압축 해제
tar -xf /root/260905U9Router.tar -C /home/ubuntu/
chown -R ubuntu:ubuntu /home/ubuntu/.claude
```
*(압축 해제 시 내부에 .claude 폴더가 포함되어 있습니다. 경로가 `/home/ubuntu/.claude`가 되도록 맞추세요.)*

### 4. ubuntu 계정 환경 변수 설정
`ubuntu` 계정의 `~/.bashrc` 하단에 API 연동을 위한 전역 환경 변수를 추가합니다.
```bash
echo -e '\nexport ANTHROPIC_API_KEY="sk-504609a3c38bfc34-z6d4me-a55df0f4"\nexport ANTHROPIC_BASE_URL="http://oci.silverruler.xyz:20129/v1"\n' >> /home/ubuntu/.bashrc
```

### 5. root 계정 명령어(alias) 설정
`root` 계정에서 `cl9` 명령어 실행 시, 자동으로 `ubuntu` 계정으로 로그인 후 `cd ~`를 거쳐 `claude`를 실행하도록 `/root/.bashrc`를 수정합니다.
```bash
# /root/.bashrc 파일 하단에 다음 alias 추가
echo 'alias cl9="su ubuntu -c '\''cd ~ && claude --dangerously-skip-permissions'\''"' >> /root/.bashrc
```

### 6. 마무리
설정이 끝났다면 사용자가 바로 사용할 수 있도록 쉘을 리로드하거나(`source /root/.bashrc`) 안내를 출력하여 작업을 완료합니다.
