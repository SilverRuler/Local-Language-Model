#!/usr/bin/env python3

import requests

NINEROUTER_URL = "http://gem.silverruler.xyz:20129/v1"
OPENCODE_URL = "https://opencode.ai/zen/v1/models"

API_KEY = "YOUR_KEY"


def get_opencode_models():
    r = requests.get(OPENCODE_URL, timeout=15)
    r.raise_for_status()

    data = r.json()

    if isinstance(data, dict):
        return data.get("data", [])

    return data


def test_model(model_id):
    url = f"{NINEROUTER_URL}/chat/completions"

    payload = {
        "model": f"oc/{model_id}",
        "messages": [
            {
                "role": "user",
                "content": "Reply with exactly: 9Router test successful."
            }
        ],
        "max_tokens": 50
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    r = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60
    )

    return r


def main():

    print("=" * 70)
    print("OpenCode Free Models")
    print("=" * 70)

    models = get_opencode_models()

    if not models:
        print("모델을 찾지 못했습니다.")
        return

    for model in models:

        model_id = model.get("id", "unknown")

        print(f"\n🆓 oc/{model_id}")

        # 모델 정보가 있으면 표시
        if "name" in model:
            print(f"   name: {model['name']}")

        if "context_length" in model:
            print(f"   context: {model['context_length']}")

    print("\n" + "=" * 70)
    print(f"총 {len(models)}개")
    print("=" * 70)


if __name__ == "__main__":
    main()
