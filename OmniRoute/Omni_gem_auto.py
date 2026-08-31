import os
import sys
import json
import time
import shutil
import asyncio
import aiohttp
from tqdm import tqdm

# ==================== 설정 (여기만 수정하세요) ====================
API_URL = "http://gem.silverruler.xyz:20128/v1/chat/completions"

# 원본 자막의 언어를 설정하세요 ("English" 또는 "Japanese")
SOURCE_LANGUAGE = "Japanese"
#SOURCE_LANGUAGE = "English"

# 모델 우선순위 목록 - 앞에서부터 시도하며, 영구 오류(400/401/404) 발생 시 다음 모델로 자동 전환
# 2026-08-31 기준: OmniRoute 활성 provider = Agnes AI 하나뿐
# oc/hy3-free, oc/deepseek-v4-flash-free 등 구 무료 모델은 모두 지원 중단됨
MODEL_CANDIDATES = [
    "auto/best-coding",
    "auto/best-chaos",
    "agnes/agnes-2.0-flash",
]
MODEL_NAME = MODEL_CANDIDATES[0]  # 로그 출력용 (실제 사용은 폴백 로직이 결정)

# 동시 번역 스레드(동시 요청) 수 - 옴니라우트 성능/제한에 맞게 조절
MAX_CONCURRENT_REQUESTS = 4

CHUNK_SIZE = 30              # 청크당 번역할 자막 블록 수
TEMPERATURE = 0.3
REQUEST_TIMEOUT_SEC = 240    # 요청 응답 최대 대기 시간 (초)
RETRY_DELAY_SEC = 5          # 429 등 일시적 오류 시 재시도 대기 시간 (초)
# ===================================================================

# 전역 활성 모델 인덱스 (폴백 시 공유)
_active_model_index = 0

async def call_omni_api_stream(session, prompt, key, active_progress, model_name):
    """옴니라우트 API에 요청하고 스트리밍(SSE)으로 결과를 받아오는 함수"""
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": f"You are a professional translator. Translate the following {SOURCE_LANGUAGE} SRT subtitles into Korean. Preserve the exact subtitle numbering and timestamps. Only output the translated Korean SRT content without any additional markdown or explanations."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": TEMPERATURE,
        "stream": True # 옴니라우트 스트리밍 활성화
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer dummy_key"
    }

    full_text = ""
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SEC)

    async with session.post(API_URL, json=payload, headers=headers, timeout=timeout) as response:
        if response.status != 200:
            text = await response.text()
            raise Exception(f"HTTP Error: {response.status} - {text}")

        # 실시간 스트림 파싱
        async for raw_line in response.content:
            line = raw_line.decode('utf-8').strip()
            if not line or line.startswith(":"): # 빈 줄이나 코멘트 무시
                continue

            if line.startswith("data: "):
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    piece = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if piece:
                        full_text += piece
                        # 실시간으로 글자 수 업데이트 (tqdm 프로그레스 바 갱신용)
                        if key in active_progress:
                            active_progress[key]["chars"] = len(full_text)
                except json.JSONDecodeError:
                    continue

    out = full_text.strip()
    if not out:
        raise Exception("Empty response: 모델이 빈 응답을 반환했습니다 (200 OK지만 content 없음)")
    return out

async def progress_ticker(pbar: tqdm, active_progress: dict, stop_event: asyncio.Event):
    """활성화된 청크(스레드)들의 번역 진행(글자수, 시간)을 실시간으로 업데이트하는 백그라운드 태스크"""
    while not stop_event.is_set():
        if active_progress:
            now = time.monotonic()
            # ex: c1:10s/150자 | c2:8s/90자 ...
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

def split_blocks(content: str):
    """SRT 문서를 개별 자막 블록(번호, 타임코드, 텍스트 묶음)으로 쪼갬"""
    content = content.replace('\r\n', '\n')
    return [b.strip() for b in content.split('\n\n') if b.strip()]

def _is_permanent_error(status_code: int) -> bool:
    """영구 오류 여부: 해당 모델 자체가 지원 안 됨 → 다음 모델로 전환"""
    return status_code in (400, 401, 403, 404)

def _is_transient_error(status_code: int) -> bool:
    """일시적 오류 여부: rate limit / 서버 문제 → 잠시 대기 후 재시도"""
    return status_code in (429, 500, 502, 503, 504)

async def translate_chunk(session, semaphore, key: str, chunk_blocks: list, pbar: tqdm, active_progress: dict):
    """청크 번역 - 모델 자동 폴백 포함"""
    global _active_model_index
    srt_chunk = '\n\n'.join(chunk_blocks)

    async with semaphore:
        active_progress[key] = {"chars": 0, "start": time.monotonic()}
        try:
            # 현재 전역 모델 인덱스부터 시작해 전체 후보 모델을 순서대로 시도
            start_idx = _active_model_index
            tried_count = 0

            while tried_count < len(MODEL_CANDIDATES):
                model_idx = (start_idx + tried_count) % len(MODEL_CANDIDATES)
                model = MODEL_CANDIDATES[model_idx]
                tried_count += 1

                try:
                    active_progress[key]["chars"] = 0
                    active_progress[key]["start"] = time.monotonic()
                    result = await call_omni_api_stream(session, srt_chunk, key, active_progress, model)
                    # 성공 시 전역 인덱스를 성공한 모델로 갱신
                    if _active_model_index != model_idx:
                        _active_model_index = model_idx
                        pbar.write(f"    [{key}] ✅ 모델 전환 성공: {model}")
                    return result, True

                except Exception as e:
                    err_str = str(e)
                    # HTTP 상태코드 추출
                    http_code = None
                    if "HTTP Error: " in err_str:
                        try:
                            http_code = int(err_str.split("HTTP Error: ")[1].split(" ")[0])
                        except (IndexError, ValueError):
                            pass

                    if http_code and _is_permanent_error(http_code):
                        # 영구 오류 → 즉시 다음 모델로 전환
                        pbar.write(f"    [{key}] ⚠ {model} 영구오류({http_code}), 다음 모델 시도...")
                        continue
                    elif http_code and _is_transient_error(http_code):
                        # 일시적 오류 → 잠시 대기 후 같은 모델 재시도 (1회)
                        pbar.write(f"    [{key}] ⏳ {model} 일시오류({http_code}), {RETRY_DELAY_SEC}초 후 재시도...")
                        await asyncio.sleep(RETRY_DELAY_SEC)
                        try:
                            active_progress[key]["chars"] = 0
                            active_progress[key]["start"] = time.monotonic()
                            result = await call_omni_api_stream(session, srt_chunk, key, active_progress, model)
                            if _active_model_index != model_idx:
                                _active_model_index = model_idx
                            return result, True
                        except Exception as e2:
                            pbar.write(f"    [{key}] ❌ {model} 재시도 실패: {str(e2)[:80]}, 다음 모델 시도...")
                            continue
                    else:
                        # 기타 오류 (타임아웃 등) → 다음 모델 시도
                        pbar.write(f"    [{key}] ❌ {model} 오류: {err_str[:80]}, 다음 모델 시도...")
                        continue

            # 모든 모델 실패
            pbar.write(f"    [{key}] 💀 모든 모델({len(MODEL_CANDIDATES)}개) 실패 - 원본 유지")
            return srt_chunk, False

        finally:
            active_progress.pop(key, None)

def format_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}시간 {m}분 {s}초"
    if m > 0:
        return f"{m}분 {s}초"
    return f"{s}초"

async def translate_srt_file(session, semaphore, file_path: str):
    print(f"\n번역 시작: {os.path.basename(file_path)}")
    print(f"  사용 모델 후보: {', '.join(MODEL_CANDIDATES)}")
    file_start_time = time.monotonic()

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    blocks = split_blocks(content)
    total_blocks = len(blocks)
    print(f"  총 자막 블록 수: {total_blocks}")

    chunks = [blocks[i:i + CHUNK_SIZE] for i in range(0, total_blocks, CHUNK_SIZE)]
    total_chunks = len(chunks)
    translated_chunks = [None] * total_chunks
    failed_flags = [False] * total_chunks

    pbar = tqdm(total=total_chunks, desc=f"{os.path.basename(file_path)}", unit="chunk")
    active_progress = {}
    stop_event = asyncio.Event()
    # 진행률 업데이트 백그라운드 코루틴 실행
    ticker_task = asyncio.create_task(progress_ticker(pbar, active_progress, stop_event))

    async def worker(i, chunk_blocks):
        key = f"c{i+1}"
        translated, ok = await translate_chunk(session, semaphore, key, chunk_blocks, pbar, active_progress)
        translated_chunks[i] = translated
        failed_flags[i] = not ok
        pbar.update(1)

    # 정의된 청크 수만큼 병렬로 작업 예약(가동) - semaphore(MAX_CONCURRENT_REQUESTS)가 알아서 제한
    await asyncio.gather(*[worker(i, c) for i, c in enumerate(chunks)])

    # 병렬 종료 후 ticker 종료
    stop_event.set()
    await ticker_task
    pbar.close()

    # 원본 파일에 덮어쓰기
    output_path = file_path

    final_content = '\n\n'.join(translated_chunks)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_content + '\n')

    failed_indices = [i + 1 for i, f in enumerate(failed_flags) if f]
    file_elapsed = time.monotonic() - file_start_time

    if failed_indices:
        print(f"⚠ {os.path.basename(file_path)}: 완료 - 일부 청크 실패 {failed_indices}")
    else:
        print(f"✅ {os.path.basename(file_path)}: 번역 성공 (원본 덮어쓰기 완료)")

    print(f"  -> 파일 소요 시간: {format_duration(file_elapsed)}")
    return file_elapsed, not failed_indices

async def main_async():
    global _active_model_index
    _active_model_index = 0  # 스크립트 시작 시 항상 첫 번째 모델부터 시작

    print("==================================================")
    print(f" 옴니라우트 API:          {API_URL}")
    print(f" 모델 후보 목록:")
    for i, m in enumerate(MODEL_CANDIDATES):
        print(f"   {i+1}. {m}")
    print(f" 원본 자막 언어:         {SOURCE_LANGUAGE}")
    print(f" 동시 요청(스레드) 수:   {MAX_CONCURRENT_REQUESTS}")
    print("==================================================\n")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 입력 인자가 없으면 "VideoDownloader" 폴더를 기본 타겟으로 잡음
    folder_name = sys.argv[1] if len(sys.argv) > 1 else "VideoDownloader"
    current_dir = os.path.join(script_dir, folder_name)

    if not os.path.isdir(current_dir):
        print(f"[{current_dir}] 폴더를 찾을 수 없습니다. 경로를 확인해주세요.")
        return

    # 타겟 폴더 내에서 이미 한국어로 번역된 것(_ko.srt)을 제외하고 원본(.srt)만 검색
    srt_files = [f for f in os.listdir(current_dir) if f.lower().endswith('.srt') and not f.endswith('_ko.srt')]

    if not srt_files:
        print(f"[{current_dir}] 폴더 내에 번역할 .srt 원본 파일이 없습니다.")
        return

    # 원본 백업
    backup_dir = os.path.join(current_dir, 'backup')
    os.makedirs(backup_dir, exist_ok=True)
    for srt_file in srt_files:
        shutil.copy2(os.path.join(current_dir, srt_file), os.path.join(backup_dir, srt_file))
    print(f"원본 자막 텍스트들을 backup/ 폴더에 안전하게 복사했습니다. (총 {len(srt_files)}개)\n")

    fail_dir = os.path.join(current_dir, 'fail')
    done_dir = os.path.join(current_dir, 'done')
    os.makedirs(fail_dir, exist_ok=True)
    os.makedirs(done_dir, exist_ok=True)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    success_count, fail_count = 0, 0
    file_timings = []
    folder_start_time = time.monotonic()

    # 클라이언트 세션 하나를 공유하여 빠른 통신 유도
    connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    async with aiohttp.ClientSession(connector=connector, trust_env=True) as session:
        for srt_file in srt_files:
            file_path = os.path.join(current_dir, srt_file)
            try:
                elapsed, is_success = await translate_srt_file(session, semaphore, file_path)
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

if __name__ == '__main__':
    # 윈도우 환경 asyncio 버그 예방
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main_async())
