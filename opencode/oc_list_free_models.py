"""
opencode Zen - 무료 모델 조회 스크립트

opencode Zen의 /v1/models 엔드포인트로 전체 모델 목록을 가져온 뒤,
응답에 가격 정보가 있으면 그것을 기준으로, 없으면 opencode 공식 문서
(https://opencode.ai/docs/zen/) 기준의 무료 모델 목록과 대조해서 판별합니다.

준비물:
  pip install requests

사용법:
  export OPENCODE_API_KEY="발급받은_API_키"
  python list_free_models.py
"""

import os
import requests

MODELS_ENDPOINT = "https://opencode.ai/zen/v1/models"

API_KEY = os.environ.get("OPENCODE_API_KEY")

# 2026-08-23 기준 opencode 공식 문서(opencode.ai/docs/zen)에 명시된 무료 모델.
# API 응답에 가격 필드가 없을 경우의 폴백(fallback) 기준으로 사용.
# 주의: 무료 모델은 opencode 측 정책에 따라 언제든 바뀔 수 있음.
KNOWN_FREE_MODEL_IDS = {
    "big-pickle",
    "x-preview-f-free",
    "mimo-v2.5-free",
    "hy3-free",
    "nemotron-3-ultra-free",
    "nemotron-3.5-lightning-free",
    "muse-spark-1.2-contributor-free",
}


def is_free_from_pricing_field(model: dict) -> bool | None:
    """
    응답 안에 가격 필드가 있는 경우 그것으로 무료 여부를 판별.
    스키마가 확실치 않아 여러 후보 키를 순서대로 탐색.
    찾을 수 없으면 None 반환.
    """
    candidates = [
        model.get("pricing"),
        model.get("cost"),
        model.get("price"),
    ]

    for c in candidates:
        if isinstance(c, dict):
            input_cost = c.get("input") or c.get("prompt") or c.get("input_cost")
            output_cost = c.get("output") or c.get("completion") or c.get("output_cost")

            if input_cost is not None and output_cost is not None:
                try:
                    return float(input_cost) == 0.0 and float(output_cost) == 0.0
                except (TypeError, ValueError):
                    pass

    return None


def main():
    if not API_KEY:
        raise SystemExit("환경변수 OPENCODE_API_KEY가 설정되어 있지 않습니다.")

    headers = {"Authorization": f"Bearer {API_KEY}"}

    response = requests.get(MODELS_ENDPOINT, headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"모델 목록 조회 실패 (상태 코드: {response.status_code})")
        print(response.text)
        return

    data = response.json()

    # OpenAI 호환 형식({"data": [...]})과 단순 리스트 형식 둘 다 대응
    models = data.get("data", data) if isinstance(data, dict) else data

    if not isinstance(models, list):
        print("예상치 못한 응답 형식입니다:")
        print(data)
        return

    free_models = []
    unknown_models = []

    for model in models:
        model_id = model.get("id") or model.get("model") or str(model)

        pricing_result = is_free_from_pricing_field(model)

        if pricing_result is True:
            free_models.append(model_id)
        elif pricing_result is None:
            # 가격 필드로 판단 불가 -> 문서 기준 폴백 목록으로 판별
            if model_id in KNOWN_FREE_MODEL_IDS:
                free_models.append(model_id)
            else:
                unknown_models.append(model_id)

    print(f"전체 모델 수: {len(models)}")
    print()
    print("=== 무료로 사용 가능한 모델 ===")
    if free_models:
        for m in sorted(set(free_models)):
            print(f"  - {m}")
    else:
        print("  (없음)")

    if unknown_models:
        print()
        print("※ 참고: API 응답에 가격 필드가 없어 문서 기준으로 무료 여부를 확정할 수 없었던 모델도 있습니다.")
        print("   정확한 최신 가격은 https://opencode.ai/docs/zen/ 에서 확인하시는 게 안전합니다.")


if __name__ == "__main__":
    main()
