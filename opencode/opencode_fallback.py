import os
import sys
import json
import time
import shutil
import asyncio
import aiohttp
from tqdm import tqdm

# ==================== 설정 ====================

# opencode Zen - OpenAI 호환(chat/completions) 엔드포인트
API_URL = "https://opencode.ai/zen/v1/chat/completions"

# 원본 자막 언어
SOURCE_LANGUAGE = "Japanese"
# SOURCE_LANGUAGE = "English"

# 무료 모델 폴백 순서 (2026-08-23 기준 opencode Zen 문서 기준)
# 앞쪽 모델이 429(한도초과)로 막히면 뒤쪽 모델로 자동 전환됩니다.
FREE_MODELS = [
    "big-pickle",
    "hy3-free",
    "mimo-v2.5-free",
    "nemotron-3-ultra-free",
    "nemotron-3.5-lightning-free",
    "x-preview-f-free",
    "muse-spark-1.2-contributor-free",
]

# 동시 요청 수 (무료 모델은 rate limit이 타이트하므로 낮게 유지 권장)
MAX_CONCURRENT_REQUESTS = 2

# 청크당 자막 블록 수
CHUNK_SIZE = 30

TEMPERATURE = 0.3

# 요청 최대 대기 시간
REQUEST_TIMEOUT_SEC = 240

# 실제 API 키 (opencode Zen)
API_KEY = "YOUR_KEY"

# =================================================


class RateLimitError(Exception):
    """429 FreeUsageLimitError 등 한도초과성 에러를 나타냄"""
    pass


class ModelRotator:
    """
    현재 사용 중인 무료 모델을 추적하고, 한도초과 시 다음 모델로 전환.
    전역으로 공유되어 모든 청크가 같은 전환 상태를 참조함.
    """

    def __init__(self, models):
        if not models:
            raise ValueError("FREE_MODELS 목록이 비어 있습니다.")
        self.models = models
        self.index = 0
        self.lock = asyncio.Lock()

    def current(self):
        return self.models[self.index]

    async def rotate(self):
        async with self.lock:
            self.index = (self.index + 1) % len(self.models)
            return self.models[self.index]


def get_api_key():
    """
    설정된 opencode Zen API Key를 반환합니다.
    """
    if not API_KEY:
        print()
        print("=" * 60)
        print("[ERROR] opencode Zen API Key가 설정되지 않았습니다.")
        print("=" * 60)
        sys.exit(1)

    return API_KEY

async def call_opencode_api_stream(
    session,
    prompt,
    key,
    active_progress,
    api_key,
    model_name
):
    """
    opencode Zen API에 요청하고 SSE 스트리밍으로 결과를 받습니다.
    429(한도초과) 발생 시 RateLimitError를 던져서 상위에서 모델 전환을 처리하게 함.
    """

    payload = {
        "model": model_name,

        "messages": [
            {
                "role": "system",
                "content": (
                    f"You are a professional translator. "
                    f"Translate the following {SOURCE_LANGUAGE} SRT subtitles "
                    f"into Korean. "
                    f"Preserve the exact subtitle numbering and timestamps. "
                    f"Only output the translated Korean SRT content "
                    f"without any additional markdown or explanations."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        "temperature": TEMPERATURE,

        "stream": True
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    full_text = ""

    timeout = aiohttp.ClientTimeout(
        total=REQUEST_TIMEOUT_SEC
    )

    async with session.post(
        API_URL,
        json=payload,
        headers=headers,
        timeout=timeout
    ) as response:

        if response.status == 429:
            text = await response.text()
            raise RateLimitError(text)

        if response.status != 200:
            text = await response.text()
            raise Exception(
                f"HTTP Error: {response.status} - {text}"
            )

        # SSE 스트림 처리
        async for raw_line in response.content:

            line = raw_line.decode(
                "utf-8",
                errors="ignore"
            ).strip()

            if not line:
                continue

            if line.startswith(":"):
                continue

            if not line.startswith("data:"):
                continue

            data_str = line[5:].strip()

            if data_str == "[DONE]":
                break

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            choices = data.get("choices", [])

            if not choices:
                continue

            delta = choices[0].get("delta", {})
            piece = delta.get("content", "")

            if piece:
                full_text += piece

                if key in active_progress:
                    active_progress[key]["chars"] = len(full_text)

    return full_text.strip()


async def progress_ticker(
    pbar,
    active_progress,
    stop_event
):
    """
    현재 실행 중인 청크의 진행상황을 표시합니다.
    """

    while not stop_event.is_set():

        if active_progress:

            now = time.monotonic()

            parts = [
                f"{key}:{now - info['start']:.0f}s/"
                f"{info['chars']}자"

                for key, info
                in sorted(
                    active_progress.items()
                )
            ]

            pbar.set_postfix_str(
                " | ".join(parts)
            )

        else:

            pbar.set_postfix_str("")

        try:

            await asyncio.wait_for(
                stop_event.wait(),
                timeout=1.0
            )

        except asyncio.TimeoutError:
            pass


def split_blocks(content):
    """
    SRT를 개별 자막 블록으로 분리합니다.
    """

    content = content.replace(
        "\r\n",
        "\n"
    )

    return [
        b.strip()
        for b in content.split("\n\n")
        if b.strip()
    ]


async def translate_chunk(
    session,
    semaphore,
    key,
    chunk_blocks,
    pbar,
    active_progress,
    api_key,
    rotator
):
    """
    한 청크를 번역. 429 발생 시 다음 무료 모델로 전환하며,
    등록된 모델을 전부 소진할 때까지 재시도.
    """

    srt_chunk = "\n\n".join(
        chunk_blocks
    )

    async with semaphore:

        active_progress[key] = {
            "chars": 0,
            "start": time.monotonic()
        }

        try:

            last_err = None

            # 등록된 무료 모델 수만큼 재시도 기회를 줌
            for _ in range(len(rotator.models)):

                model_name = rotator.current()

                try:

                    translated_body = (
                        await call_opencode_api_stream(
                            session,
                            srt_chunk,
                            key,
                            active_progress,
                            api_key,
                            model_name
                        )
                    )

                    return translated_body, True

                except RateLimitError:

                    pbar.write(
                        f"    [{key}] '{model_name}' 한도초과 "
                        f"-> 다음 무료 모델로 전환"
                    )

                    await rotator.rotate()

                    # 진행률 표시에 남은 잔상 제거
                    active_progress[key]["chars"] = 0
                    active_progress[key]["start"] = time.monotonic()

                    continue

                except Exception as e:

                    # 한도초과가 아닌 다른 에러는 모델을 바꿔도
                    # 같은 이유로 실패할 가능성이 높으므로 즉시 중단
                    last_err = e
                    break

            if last_err is not None:
                pbar.write(
                    f"    [{key}] 요청 실패: {last_err}"
                )
            else:
                pbar.write(
                    f"    [{key}] 등록된 무료 모델을 모두 소진했습니다. "
                    f"(전부 한도초과)"
                )

            return srt_chunk, False

        finally:

            active_progress.pop(
                key,
                None
            )


def format_duration(seconds):

    m, s = divmod(
        int(seconds),
        60
    )

    h, m = divmod(
        m,
        60
    )

    if h > 0:
        return f"{h}시간 {m}분 {s}초"

    if m > 0:
        return f"{m}분 {s}초"

    return f"{s}초"


async def translate_srt_file(
    session,
    semaphore,
    file_path,
    api_key,
    rotator
):

    print(
        f"\n번역 시작: "
        f"{os.path.basename(file_path)}"
    )

    print(
        f"  시작 모델: {rotator.current()}"
    )

    file_start_time = time.monotonic()

    with open(
        file_path,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as f:

        content = f.read()

    blocks = split_blocks(
        content
    )

    total_blocks = len(
        blocks
    )

    print(
        f"  총 자막 블록 수: "
        f"{total_blocks}"
    )

    chunks = [
        blocks[i:i + CHUNK_SIZE]

        for i
        in range(
            0,
            total_blocks,
            CHUNK_SIZE
        )
    ]

    total_chunks = len(
        chunks
    )

    translated_chunks = [
        None
    ] * total_chunks

    failed_flags = [
        False
    ] * total_chunks

    pbar = tqdm(
        total=total_chunks,
        desc=os.path.basename(
            file_path
        ),
        unit="chunk"
    )

    active_progress = {}

    stop_event = asyncio.Event()

    ticker_task = asyncio.create_task(
        progress_ticker(
            pbar,
            active_progress,
            stop_event
        )
    )

    async def worker(
        i,
        chunk_blocks
    ):

        key = f"c{i + 1}"

        translated, ok = (
            await translate_chunk(
                session,
                semaphore,
                key,
                chunk_blocks,
                pbar,
                active_progress,
                api_key,
                rotator
            )
        )

        translated_chunks[i] = translated

        failed_flags[i] = not ok

        pbar.update(1)

    await asyncio.gather(
        *[
            worker(i, c)
            for i, c
            in enumerate(chunks)
        ]
    )

    stop_event.set()

    await ticker_task

    pbar.close()

    # 결과 저장
    output_path = file_path

    final_content = "\n\n".join(
        translated_chunks
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            final_content + "\n"
        )

    failed_indices = [
        i + 1

        for i, failed
        in enumerate(
            failed_flags
        )

        if failed
    ]

    file_elapsed = (
        time.monotonic()
        - file_start_time
    )

    if failed_indices:

        print(
            f"⚠ "
            f"{os.path.basename(file_path)}: "
            f"완료 - 일부 청크 실패 "
            f"{failed_indices}"
        )

    else:

        print(
            f"✅ "
            f"{os.path.basename(file_path)}: "
            f"번역 성공 "
            f"(원본 덮어쓰기 완료)"
        )

    print(
        f"  -> 파일 소요 시간: "
        f"{format_duration(file_elapsed)}"
    )

    print(
        f"  -> 종료 시점 모델: {rotator.current()}"
    )

    return (
        file_elapsed,
        not failed_indices
    )


async def main_async():

    api_key = get_api_key()

    rotator = ModelRotator(FREE_MODELS)

    print(
        "=================================================="
    )

    print(
        f" 무료 모델 폴백 순서: "
        f"{' -> '.join(FREE_MODELS)}"
    )

    print(
        f" 원본 자막 언어:         "
        f"{SOURCE_LANGUAGE}"
    )

    print(
        f" 동시 요청 수:           "
        f"{MAX_CONCURRENT_REQUESTS}"
    )

    print(
        "==================================================\n"
    )

    script_dir = os.path.dirname(
        os.path.abspath(__file__)
    )

    folder_name = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "VideoDownloader"
    )

    current_dir = os.path.join(
        script_dir,
        folder_name
    )

    if not os.path.isdir(
        current_dir
    ):

        print(
            f"[{current_dir}] "
            f"폴더를 찾을 수 없습니다."
        )

        return

    srt_files = [
        f

        for f
        in os.listdir(
            current_dir
        )

        if (
            f.lower().endswith(".srt")
            and not f.endswith("_ko.srt")
        )
    ]

    if not srt_files:

        print(
            f"[{current_dir}] "
            f"번역할 .srt 파일이 없습니다."
        )

        return

    # 백업
    backup_dir = os.path.join(
        current_dir,
        "backup"
    )

    os.makedirs(
        backup_dir,
        exist_ok=True
    )

    for srt_file in srt_files:

        shutil.copy2(
            os.path.join(
                current_dir,
                srt_file
            ),

            os.path.join(
                backup_dir,
                srt_file
            )
        )

    print(
        f"원본 자막 텍스트들을 "
        f"backup/ 폴더에 안전하게 복사했습니다. "
        f"(총 {len(srt_files)}개)\n"
    )

    fail_dir = os.path.join(
        current_dir,
        "fail"
    )

    done_dir = os.path.join(
        current_dir,
        "done"
    )

    os.makedirs(
        fail_dir,
        exist_ok=True
    )

    os.makedirs(
        done_dir,
        exist_ok=True
    )

    semaphore = asyncio.Semaphore(
        MAX_CONCURRENT_REQUESTS
    )

    success_count = 0
    fail_count = 0

    file_timings = []

    folder_start_time = (
        time.monotonic()
    )

    connector = aiohttp.TCPConnector(
        resolver=aiohttp.ThreadedResolver()
    )

    async with aiohttp.ClientSession(
        connector=connector,
        trust_env=True
    ) as session:

        for srt_file in srt_files:

            file_path = os.path.join(
                current_dir,
                srt_file
            )

            try:

                elapsed, is_success = (
                    await translate_srt_file(
                        session,
                        semaphore,
                        file_path,
                        api_key,
                        rotator
                    )
                )

                file_timings.append(
                    (
                        srt_file,
                        elapsed,
                        is_success
                    )
                )

                if is_success:

                    success_count += 1

                    shutil.copy2(
                        file_path,
                        os.path.join(
                            done_dir,
                            srt_file
                        )
                    )

                else:

                    fail_count += 1

                    shutil.copy2(
                        file_path,
                        os.path.join(
                            fail_dir,
                            srt_file
                        )
                    )

            except Exception as e:

                print(
                    f"Failed to process "
                    f"{srt_file}: {e}\n"
                )

                fail_count += 1

                file_timings.append(
                    (
                        srt_file,
                        0.0,
                        False
                    )
                )

                if os.path.exists(
                    file_path
                ):

                    shutil.copy2(
                        file_path,
                        os.path.join(
                            fail_dir,
                            srt_file
                        )
                    )

    folder_elapsed = (
        time.monotonic()
        - folder_start_time
    )

    print(
        "\n"
        + "=" * 60
    )

    print(
        "작업 파일별 상세 소요 시간"
    )

    print(
        "=" * 60
    )

    for (
        name,
        elapsed,
        is_success
    ) in file_timings:

        status = (
            ""
            if is_success
            else " (실패)"
        )

        print(
            f"  {name}: "
            f"{format_duration(elapsed)}"
            f"{status}"
        )

    print("-" * 60)

    print(
        f"전체 작업 소요 시간: "
        f"{format_duration(folder_elapsed)}"
    )

    print(
        "=" * 60
    )

    print(
        f"요약: "
        f"성공={success_count}, "
        f"부분실패/에러={fail_count}"
    )

    print(
        f"최종 사용 모델: {rotator.current()}"
    )


if __name__ == "__main__":

    if sys.platform == "win32":

        asyncio.set_event_loop_policy(
            asyncio.WindowsSelectorEventLoopPolicy()
        )

    asyncio.run(
        main_async()
    )
