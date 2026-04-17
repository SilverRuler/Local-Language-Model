from unsloth import FastLanguageModel
import torch

# 1. 설정
# 방금 학습이 끝난 어댑터 경로
adapter_path = "/mnt/g/ollama/gemma-4-E4B-dolphin-adapter-fast-test"
# GGUF 파일이 저장될 폴더 경로
output_path = "/mnt/g/ollama/gemma-4-E4B-dolphin-GGUF-result"

print("모델 및 어댑터 로드 중...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = adapter_path,
    max_seq_length = 1024,
    dtype = None,
    load_in_4bit = True,
)

print("GGUF 변환 및 내보내기 시작 (q4_k_m 양자화)...")
# 이 함수가 자동으로 병합(Merge) 후 GGUF로 변환하여 저장합니다.
model.save_pretrained_gguf(
    output_path, 
    tokenizer, 
    quantization_method = "q4_k_m"
)

print(f"변환 완료! 결과물 위치: {output_path}")
