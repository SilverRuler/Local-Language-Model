import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# 1. 경로 설정##
base_model_path = "/mnt/g/ollama/gemma-4-E4B-it"
adapter_path = "/mnt/g/ollama/gemma-4-E4B-dolphin-adapter"
merged_output_dir = "/mnt/g/ollama/gemma-4-E4B-dolphin-merged"

print("1. 베이스 모델 로드 중 (VRAM 방어를 위해 CPU RAM 사용)...")
# 4-bit가 아닌 원본 bf16 상태로 로드합니다.
base_model = AutoModelForCausalLM.from_pretrained(
    base_model_path,
    device_map="cpu",
    torch_dtype=torch.bfloat16,
)

print("2. 파인튜닝된 LoRA 어댑터 필터 장착 중...")
model = PeftModel.from_pretrained(base_model, adapter_path)

print("3. 모델 병합(Merge) 및 찌꺼기 제거 중...")
model = model.merge_and_unload()

print("4. 토크나이저 로드 중...")
tokenizer = AutoTokenizer.from_pretrained(base_model_path)

print(f"5. 최종 병합된 소버린 AI 모델을 저장합니다: {merged_output_dir}")
model.save_pretrained(merged_output_dir, safe_serialization=True)
tokenizer.save_pretrained(merged_output_dir)

print("병합 용접 완벽하게 성공!")
