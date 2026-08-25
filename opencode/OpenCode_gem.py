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

# opencode Zen 무료 모델 (Ox Alpha Free)
# 표시명이 아닌 모델 ID 사용: Ox Alpha Free -> x-preview-f-free
MODEL_NAME = "x-preview-f-free"

# 동시 요청 수
MAX_CONCURRENT_REQUESTS = 1

# 청크당 자막 블록 수
CHUNK_SIZE = 30

TEMPERATURE = 0.3

# 요청 최대 대기 시간
REQUEST_TIMEOUT_SEC = 240

# 청크당 최대 재시도 횟수 (실패 시 추가로 3번 더 시도)
MAX_RETRIES = 3

# 재시도 대기 시간 (초) - 재시도 횟수에 비례해 증가 (5초, 10초, 15초)
RETRY_BACKOFF_SEC = 5

# 실제 API 키 (opencode Zen)
API_KEY = "YOUR_KEY"

# =================================================


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
    api_key
):
    """
    opencode Zen API에 요청하고 SSE 스트리밍으로 결과를 받습니다.
    """

    payload = {
        "model": MODEL_NAME,

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

        # 핵심:
        # dummy_key가 아니라 실제 opencode Zen API Key 사용
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

            # SSE comment
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

            # OpenAI-compatible streaming response
            choices = data.get(
                "choices",
                []
            )

            if not choices:
                continue

            delta = choices[0].get(
                "delta",
                {}
            )

            piece = delta.get(
                "content",
                ""
            )

            if piece:

                full_text += piece

                if key in active_progress:

                    active_progress[key]["chars"] = len(
                        full_text
                    )

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
    api_key
):

    srt_chunk = "\n\n".join(
        chunk_blocks
    )

    async with semaphore:

        active_progress[key] = {
            "chars": 0,
            "start": time.monotonic()
        }

        last_error = None

        try:

            # 최초 1회 + 실패 시 MAX_RETRIES번 재시도
            for attempt in range(1 + MAX_RETRIES):

                if attempt > 0:

                    wait_sec = RETRY_BACKOFF_SEC * attempt

                    pbar.write(
                        f"    [{key}] {wait_sec}초 후 "
                        f"재시도 {attempt}/{MAX_RETRIES}"
                    )

                    await asyncio.sleep(wait_sec)

                try:

                    translated_body = (
                        await call_opencode_api_stream(
                            session,
                            srt_chunk,
                            key,
                            active_progress,
                            api_key
                        )
                    )

                    if attempt > 0:
                        pbar.write(
                            f"    [{key}] 재시도 성공"
                        )

                    return translated_body, True

                except Exception as e:

                    last_error = e

                    pbar.write(
                        f"    [{key}] 요청 실패 "
                        f"(시도 {attempt + 1}/"
                        f"{1 + MAX_RETRIES}): "
                        f"{e}"
                    )

            # 모든 재시도 소진 -> 최종 실패 처리
            pbar.write(
                f"    [{key}] 재시도 "
                f"{MAX_RETRIES}회 초과, "
                f"최종 실패 처리: {last_error}"
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
    api_key
):

    print(
        f"\n번역 시작: "
        f"{os.path.basename(file_path)}"
    )

    print(
        f"  사용 모델: {MODEL_NAME}"
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
                api_key
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

    return (
        file_elapsed,
        not failed_indices
    )


async def main_async():

    # API Key 확인
    api_key = get_api_key()

    print(
        "=================================================="
    )

    print(
        f" 선택된 opencode Zen 모델: "
        f"{MODEL_NAME}"
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
                        api_key
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


if __name__ == "__main__":

    if sys.platform == "win32":

        asyncio.set_event_loop_policy(
            asyncio.WindowsSelectorEventLoopPolicy()
        )

    asyncio.run(
        main_async()
    )
