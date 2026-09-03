import os
import sys
import json
import time
import shutil
import asyncio
import aiohttp
from tqdm import tqdm

# ==================== 설정 ====================

API_URL = "http://gem.silverruler.xyz:20129/v1/chat/completions"

# 원본 자막 언어
SOURCE_LANGUAGE = "Japanese"
# SOURCE_LANGUAGE = "English"

# 커스텀 콤보 모델
MODEL_NAME = "sr-combo"

# 동시 요청 수
MAX_CONCURRENT_REQUESTS = 4

# 청크당 자막 블록 수
CHUNK_SIZE = 30

TEMPERATURE = 0.3

# 요청 최대 대기 시간
REQUEST_TIMEOUT_SEC = 240

# 재시도 횟수
MAX_RETRIES = 3

# 재시도 대기 시간 (초)
RETRY_BACKOFF_SEC = 5

# 실제 9Router API Key
API_KEY = "YOUR_KEY"

# =================================================


def get_api_key():
    if not API_KEY:
        print()
        print("=" * 60)
        print("[ERROR] 9Router API Key가 없습니다.")
        print("=" * 60)
        sys.exit(1)
    return API_KEY


async def call_9router_api_stream(session, prompt, key, active_progress, api_key):
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
        "Authorization": f"Bearer {api_key}"
    }

    full_text = ""
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SEC)

    async with session.post(API_URL, json=payload, headers=headers, timeout=timeout) as response:
        if response.status != 200:
            text = await response.text()
            raise Exception(f"HTTP Error: {response.status} - {text}")

        async for raw_line in response.content:
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line or line.startswith(":"):
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

            # 에러 응답 처리 (스트림 도중 502 에러 등이 섞여 들어올 경우)
            if "error" in data:
                err_msg = data["error"].get("message", "Unknown error in stream")
                raise Exception(f"Stream Error: {err_msg}")

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


async def progress_ticker(pbar, active_progress, stop_event):
    while not stop_event.is_set():
        if active_progress:
            now = time.monotonic()
            parts = [
                f"{key}:{now - info['start']:.0f}s/{info['chars']}자"
                for key, info in sorted(active_progress.items())
            ]
            pbar.set_postfix_str(" | ".join(parts))
        else:
            pbar.set_postfix_str("")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass


def split_blocks(content):
    content = content.replace("\r\n", "\n")
    return [b.strip() for b in content.split("\n\n") if b.strip()]


async def translate_chunk(session, semaphore, key, chunk_blocks, pbar, active_progress, api_key):
    srt_chunk = "\n\n".join(chunk_blocks)

    async with semaphore:
        active_progress[key] = {"chars": 0, "start": time.monotonic()}

        try:
            for attempt in range(1 + MAX_RETRIES):
                if attempt > 0:
                    wait_sec = RETRY_BACKOFF_SEC * attempt
                    pbar.write(f"    [{key}] {wait_sec}초 후 재시도 {attempt}/{MAX_RETRIES}")
                    await asyncio.sleep(wait_sec)

                try:
                    translated_body = await call_9router_api_stream(session, srt_chunk, key, active_progress, api_key)
                    if attempt > 0:
                        pbar.write(f"    [{key}] 재시도 성공")
                    return translated_body, True
                except Exception as e:
                    pbar.write(f"    [{key}] 요청 실패 (시도 {attempt + 1}/{1 + MAX_RETRIES}): {e}")

            pbar.write(f"    [{key}] 재시도 {MAX_RETRIES}회 초과. 최종 실패 처리.")
            return srt_chunk, False

        finally:
            active_progress.pop(key, None)


def format_duration(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}시간 {m}분 {s}초"
    if m > 0:
        return f"{m}분 {s}초"
    return f"{s}초"


async def translate_srt_file(session, semaphore, file_path, api_key):
    print(f"\n번역 시작: {os.path.basename(file_path)}")
    print(f"  사용 모델: {MODEL_NAME}")
    file_start_time = time.monotonic()

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    blocks = split_blocks(content)
    total_blocks = len(blocks)
    print(f"  총 자막 블록 수: {total_blocks}")

    chunks = [blocks[i:i + CHUNK_SIZE] for i in range(0, total_blocks, CHUNK_SIZE)]
    total_chunks = len(chunks)

    translated_chunks = [None] * total_chunks
    failed_flags = [False] * total_chunks

    pbar = tqdm(total=total_chunks, desc=os.path.basename(file_path), unit="chunk")
    active_progress = {}
    stop_event = asyncio.Event()

    ticker_task = asyncio.create_task(progress_ticker(pbar, active_progress, stop_event))

    async def worker(i, chunk_blocks):
        key = f"c{i + 1}"
        translated, ok = await translate_chunk(session, semaphore, key, chunk_blocks, pbar, active_progress, api_key)
        translated_chunks[i] = translated
        failed_flags[i] = not ok
        pbar.update(1)

    await asyncio.gather(*[worker(i, c) for i, c in enumerate(chunks)])
    stop_event.set()
    await ticker_task
    pbar.close()

    final_content = "\n\n".join(translated_chunks)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(final_content + "\n")

    failed_indices = [i + 1 for i, failed in enumerate(failed_flags) if failed]
    file_elapsed = time.monotonic() - file_start_time

    if failed_indices:
        print(f"⚠ {os.path.basename(file_path)}: 완료 - 일부 청크 실패 {failed_indices}")
    else:
        print(f"✅ {os.path.basename(file_path)}: 번역 성공 (원본 덮어쓰기 완료)")
    print(f"  -> 파일 소요 시간: {format_duration(file_elapsed)}")

    return file_elapsed, not failed_indices


async def main_async():
    api_key = get_api_key()
    print("==================================================")
    print(f" 선택된 9Router 모델: {MODEL_NAME}")
    print(f" 원본 자막 언어:         {SOURCE_LANGUAGE}")
    print(f" 동시 요청 수:           {MAX_CONCURRENT_REQUESTS}")
    print("==================================================\n")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    folder_name = sys.argv[1] if len(sys.argv) > 1 else "VideoDownloader"
    current_dir = os.path.join(script_dir, folder_name)

    if not os.path.isdir(current_dir):
        print(f"[{current_dir}] 폴더를 찾을 수 없습니다.")
        return

    srt_files = [f for f in os.listdir(current_dir) if f.lower().endswith(".srt") and not f.endswith("_ko.srt")]
    if not srt_files:
        print(f"[{current_dir}] 번역할 .srt 파일이 없습니다.")
        return

    backup_dir = os.path.join(current_dir, "backup")
    os.makedirs(backup_dir, exist_ok=True)
    for srt_file in srt_files:
        shutil.copy2(os.path.join(current_dir, srt_file), os.path.join(backup_dir, srt_file))
    print(f"원본 자막 텍스트들을 backup/ 폴더에 안전하게 복사했습니다. (총 {len(srt_files)}개)\n")

    fail_dir = os.path.join(current_dir, "fail")
    done_dir = os.path.join(current_dir, "done")
    os.makedirs(fail_dir, exist_ok=True)
    os.makedirs(done_dir, exist_ok=True)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    success_count = fail_count = 0
    file_timings = []
    folder_start_time = time.monotonic()

    connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    async with aiohttp.ClientSession(connector=connector, trust_env=True) as session:
        for srt_file in srt_files:
            file_path = os.path.join(current_dir, srt_file)
            try:
                elapsed, is_success = await translate_srt_file(session, semaphore, file_path, api_key)
                file_timings.append((srt_file, elapsed, is_success))
                if is_success:
                    success_count += 1
                    shutil.copy2(file_path, os.path.join(done_dir, srt_file))
                else:
                    fail_count += 1
                    shutil.copy2(file_path, os.path.join(fail_dir, srt_file))
            except Exception as e:
                print(f"Failed to process {srt_file}: {e}\n")
                fail_count += 1
                file_timings.append((srt_file, 0.0, False))
                if os.path.exists(file_path):
                    shutil.copy2(file_path, os.path.join(fail_dir, srt_file))

    folder_elapsed = time.monotonic() - folder_start_time
    print("\n" + "=" * 60)
    print("작업 파일별 상세 소요 시간")
    print("=" * 60)
    for name, elapsed, is_success in file_timings:
        status = "" if is_success else " (실패)"
        print(f"  {name}: {format_duration(elapsed)}{status}")
    print("-" * 60)
    print(f"전체 작업 소요 시간: {format_duration(folder_elapsed)}")
    print("=" * 60)
    print(f"요약: 성공={success_count}, 부분실패/에러={fail_count}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main_async())
