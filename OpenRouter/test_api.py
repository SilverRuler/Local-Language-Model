from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="YOUR_KEY"
)

response = client.chat.completions.create(
    model="openrouter/free",
    messages=[
        {
            "role": "user",
            "content": "OpenRouter가 무엇인지 설명해주세요."
        }
    ]
)

print(response.choices[0].message.content)
