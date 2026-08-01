import requests
import sys

def get_usable_models(api_base_url="http://localhost:20128/v1"):
    print("옴니라우트 모델 리스트를 불러오는 중...\n")
    try:
        response = requests.get(f"{api_base_url}/models", timeout=10)
        response.raise_for_status()
        data = response.json()

        models = data.get('data', [])
        if not models:
            print("사용 가능한 모델이 없습니다.")
            return

        print("==================================================================")
        print(" [사용 가능한 옴니라우트 모델 리스트]")
        print(" (무료 모델 위주로 정렬 및 표시됩니다)")
        print("==================================================================")

        # 이름이나 ID에 free, 🆓 등이 들어간 모델을 위로 정렬하거나 눈에 띄게 표시
        free_keywords = ["free", "🆓", "무료"]

        # 모델 분류
        free_models = []
        other_models = []

        for m in models:
            m_id = m.get('id', '')
            m_name = m.get('name', '')

            is_free = False
            for k in free_keywords:
                if k.lower() in m_id.lower() or k in m_name:
                    is_free = True
                    break

            if is_free:
                free_models.append(m)
            else:
                other_models.append(m)

        # 출력 (무료 모델 먼저)
        idx = 1
        if free_models:
            print(" [확인된 무료 모델]")
            for m in free_models:
                print(f" {idx:2d}. ID: {m.get('id'):<30} | NAME: {m.get('name')}")
                idx += 1
            print("-" * 66)

        if other_models:
            print(" [기타 모델 (무료일 확률 높음)]")
            for m in other_models:
                print(f" {idx:2d}. ID: {m.get('id'):<30} | NAME: {m.get('name')}")
                idx += 1

        print("==================================================================")
        print("원하시는 모델의 'ID' 값을 복사해서 translate.py의 MODEL_NAME 에 붙여넣으세요.")
        print("예시: MODEL_NAME = \"auto/best-chat\"")

    except requests.exceptions.RequestException as e:
        print(f"모델 목록을 불러오는 데 실패했습니다: {e}")
        print("옴니라우트 서버가 켜져 있는지 확인하세요.")

if __name__ == "__main__":
    get_usable_models()
