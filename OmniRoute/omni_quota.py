import requests
import json
import os

def check_quota(api_base_url="http://localhost:20128"):
    headers = {
        "Authorization": "Bearer dummy_key",
        "Content-Type": "application/json"
    }

    # 옴니라우트(또는 호환 프록시)에서 자주 쓰이는 사용량 조회 API 경로 후보군
    endpoints = [
        "/v1/dashboard/billing/subscription",
        "/v1/dashboard/billing/usage",
        "/v1/usage",
        "/@@om-usage",       # 옴니라우트 특수 라우트
        "/api/quota",
        "/v1/user",
        "/v1/models"         # 모델 리스트에 quota 잔여량이 섞여 나오는지 확인용
    ]

    print("==================================================")
    print(" 옴니라우트 모델/전체 사용량(Quota) 조회 스크립트")
    print("==================================================\n")

    success_found = False

    for ep in endpoints:
        url = api_base_url + ep
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()

                # /v1/models 의 경우 너무 길어서 quota 관련 정보가 있는지 필터링
                if ep == "/v1/models":
                    has_quota = False
                    for m in data.get('data', []):
                        if 'quota' in m or 'usage' in m:
                            has_quota = True
                            break
                    if not has_quota:
                        continue # 단순 모델 목록이면 패스

                print(f"✅ 사용량 데이터 발견 (경로: {ep})")
                print("-" * 50)
                # 보기 좋게 JSON 포맷팅하여 출력
                print(json.dumps(data, indent=4, ensure_ascii=False))
                print("-" * 50 + "\n")
                success_found = True

        except requests.exceptions.RequestException:
            pass # 엔드포인트가 없거나 응답이 없으면 그냥 넘어감
        except json.JSONDecodeError:
            pass # JSON이 아니면 넘어감

    if not success_found:
        print("❌ 지원되는 표준 빌링/사용량(Quota) 조회 엔드포인트를 찾지 못했습니다.")
        print("현재 옴니라우트(또는 연결된 제공자) API에서 잔여량 조회를 직접 제공하지 않거나,")
        print("관리자 대시보드 UI를 통해서만 확인이 가능할 수 있습니다.\n")
        print("* 참고: 옴니라우트에서 제공되는 무료 모델(예: auto/best-chat 등)들은")
        print("  대부분 영구적인 할당량 제한 없이(혹은 분당 요청 속도 제한만 걸린 채)")
        print("  무제한으로 제공되는 경우가 많습니다.")

if __name__ == "__main__":
    check_quota()
