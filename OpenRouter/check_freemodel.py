import time
import requests
from openai import OpenAI

API_KEY = "YOUR_KEY"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY
)

models = requests.get(
    "https://openrouter.ai/api/v1/models"
).json()["data"]

free_models = []

for model in models:
    pricing = model.get("pricing", {})

    if (
        pricing.get("prompt") == "0"
        and pricing.get("completion") == "0"
        and "text" in model.get("architecture", {}).get("output_modalities", ["text"])
    ):
        free_models.append(model)

print(f"무료 모델 {len(free_models)}개 발견\n")

for model in free_models:

    model_id = model["id"]
    name = model.get("name", model_id)

    print("=" * 100)
    print(f"MODEL : {name}")
    print(f"ID    : {model_id}")

    start = time.time()

    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": "OpenRouter가 무엇인지 짧게 설명해주세요."
                }
            ],
            max_tokens=100
        )

        elapsed = time.time() - start

        text = response.choices[0].message.content

        print(f"TIME  : {elapsed:.2f}s")
        print(f"TEXT  : {text}")

    except Exception as e:

        elapsed = time.time() - start

        print(f"TIME  : {elapsed:.2f}s")
        print(f"ERROR : {e}")
