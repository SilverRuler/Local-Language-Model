import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from peft import LoraConfig, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig
import os

# 1. 경로 설정
base_model_path = "/mnt/g/ollama/gemma-4-E4B-it"
dataset_id = "cognitivecomputations/dolphin-coder"
output_dir = "/mnt/g/ollama/gemma-4-E4B-dolphin-adapter"

# 2. 데이터셋 로드 및 전처리
print("데이터셋 로드 및 프롬프트 포맷팅 중...")
dataset = load_dataset(dataset_id, split="train[:5000]")

def format_dataset(example):
    example['text'] = f"<|im_start|>user\n{example['question']}<|im_end|>\n<|im_start|>assistant\n{example['response']}<|im_end|>"
    return example

dataset = dataset.map(format_dataset)

# 3. 토크나이저 및 양자화 설정
print("토크나이저 로드 중...")
tokenizer = AutoTokenizer.from_pretrained(base_model_path)
tokenizer.pad_token = tokenizer.eos_token

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16
)

# 4. 모델 로드
print("베이스 모델 로드 중 (4-bit)...")
model = AutoModelForCausalLM.from_pretrained(
    base_model_path,
    quantization_config=bnb_config,
    device_map={"": 0}
)

model = prepare_model_for_kbit_training(model)

# 5. LoRA 어댑터 설정
peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=[
        "q_proj.linear",
        "k_proj.linear",
        "v_proj.linear",
        "o_proj.linear",
        "gate_proj.linear",
        "up_proj.linear",
        "down_proj.linear"
    ],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)

# 6. SFTConfig 학습 인자 설정 (VRAM 극한 방어 세팅)
training_args = SFTConfig(
    output_dir=output_dir,
    per_device_train_batch_size=1,            # 수정됨: 배치 사이즈 1로 축소
    gradient_accumulation_steps=8,            # 수정됨: 누적 스텝 8로 증가
    gradient_checkpointing=True,              # 핵심 추가: VRAM 절약의 1등 공신
    gradient_checkpointing_kwargs={'use_reentrant': False}, # 최신 PyTorch 경고 방지용
    learning_rate=2e-4,
    logging_steps=10,
    max_steps=300,
    optim="paged_adamw_8bit",
    bf16=True,
    save_strategy="steps",
    save_steps=100,
    report_to="none",
    max_length=1024,
    dataset_text_field="text"
)

# 7. SFTTrainer 셋업 및 학습 시작
trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    peft_config=peft_config,
    processing_class=tokenizer,
    args=training_args,
)

print("학습을 시작합니다! VRAM을 방어하며 천천히 돌아갑니다...")
trainer.train()

# 8. 어댑터 저장
trainer.model.save_pretrained(output_dir)
tokenizer.save_pretrained(output_dir)
print(f"학습 완료 및 어댑터 저장됨: {output_dir}")
