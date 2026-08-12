# 로컬 한국어 TTS 설치 가이드 (OmniVoice / Chatterbox Multilingual V3)

## 1. OmniVoice

### 설치

```bash
conda create -n omnivoice python=3.11 -y
conda activate omnivoice

# PyTorch (CUDA 12.8 기준)
pip install torch==2.8.0+cu128 torchaudio==2.8.0+cu128 --extra-index-url https://download.pytorch.org/whl/cu128

# OmniVoice 설치
pip install omnivoice
```

### 실행 (웹 UI)

```bash
omnivoice-demo --ip 0.0.0.0 --port 8001
```

### CLI 추론 예시

```bash
omnivoice-infer \
    --model k2-fsa/OmniVoice \
    --text "테스트 문장" \
    --ref_audio ref.wav \
    --ref_text "레퍼런스 오디오 자막" \
    --output out.wav
```

> **주의:** 모델 가중치가 CC-BY-NC 라이선스라 상업적 이용 시 주의가 필요함. 코드는 Apache 2.0.

---

## 2. Chatterbox Multilingual V3

### 설치

```bash
conda create -yn chatterbox python=3.11
conda activate chatterbox

# 소스 클론 및 editable 설치 (multilingual_app.py 사용을 위해 필수)
git clone https://github.com/resemble-ai/chatterbox.git
cd chatterbox
pip install -e .

# setuptools 버전 고정 (pkg_resources 의존성 문제 방지, 필수)
pip install "setuptools<81"

# onnxruntime-gpu 설치 (워터마커 로딩에 필요)
pip install onnxruntime-gpu
```

### 실행 (웹 UI)

```bash
cd chatterbox
python multilingual_app.py --server_name 0.0.0.0
```

### Python 스크립트 예시

```python
import torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

model = ChatterboxMultilingualTTS.from_pretrained(device="cuda", t3_model="v3")

wav = model.generate(
    "테스트 문장입니다.",
    language_id="ko",
    audio_prompt_path="ref.wav",
    exaggeration=0.5,
    cfg_weight=0.5,
)
ta.save("out.wav", wav, model.sr)
```

### 파라미터 참고

| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `exaggeration` | 0.5 | 감정 과장 정도. 올릴수록 톤이 강해지고 말이 빨라지는 경향 |
| `cfg_weight` | 0.5 | 낮추면 발화 속도가 느려지고 또박또박해짐. `exaggeration`을 올릴 때 상쇄 목적으로 낮추는 조합 추천 |

> **라이선스:** 코드/모델 모두 MIT라 상업적 이용 문제없음. 단, 출력 오디오엔 PerTh 워터마크가 기본 삽입됨 (MP3 압축·재인코딩에도 유지, 사람 귀엔 안 들림).

---

## 3. 알아둘 점 (트러블슈팅 메모)

- **`setuptools<81` 핀은 환경별로 유지해야 함.** 이 conda 환경(`chatterbox`)을 재생성하거나 다른 머신에 옮길 때 `pip install setuptools`를 그냥 실행하면 최신 버전이 깔리면서 `pkg_resources` 관련 `ModuleNotFoundError`가 재발함. `requirements.txt`나 환경 구성 스크립트에 명시해둘 것.
- **pip 패키지와 git clone 소스를 혼용하지 말 것.** `multilingual_app.py` 같은 최신 앱 스크립트는 레포 소스 기준으로 작성되어 있어서, pip으로 설치한 `chatterbox-tts`(구버전)와 충돌하면 `TypeError: got an unexpected keyword argument` 같은 에러가 남. 반드시 클론한 레포 안에서 `pip install -e .`로 editable 설치할 것.
