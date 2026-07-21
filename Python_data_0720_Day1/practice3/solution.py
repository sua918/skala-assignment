"""=============================================================================
파일명: solution.py
작성자: 채수아
작성일: 2026-07-20
작성 목적: 동시성 제한과 재시도 기능을 갖춘 비동기 데이터 수집기를 구현

입력:
    모의 API 응답 60건 (USE_REAL_HTTP=True이면 JSONPlaceholder API)

수집 항목:
    asyncio 동시 수집, Semaphore 백프레셔, 요청 타임아웃,
    지수 백오프 재시도, 실패 데이터 dead-letter 격리,
    동기 기준선과 비동기 실행 시간 비교

실행:
    python ex03_async_collector/solution.py
=============================================================================
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import Counter
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

USE_REAL_HTTP = False
REQUEST_COUNT = 60
MAX_CONCURRENT = 10
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 1.0
MOCK_DELAY_SECONDS = 0.24
MOCK_BACKOFF_SECONDS = 0.05
REAL_BACKOFF_SECONDS = 1.0

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

logger = logging.getLogger(__name__)


class RetriableCollectionError(Exception):
    """재시도로 회복될 가능성이 있는 수집 오류를 나타냅니다."""


def measure_sequential_baseline(count: int = REQUEST_COUNT) -> float:
    """모의 요청을 순서대로 기다리며 동기 방식의 실제 실행 시간을 측정합니다."""
    started = time.perf_counter()
    for _ in range(count):
        time.sleep(MOCK_DELAY_SECONDS)
    return time.perf_counter() - started


async def fetch_mock(item_id: int, attempt: int) -> dict[str, Any]:
    """네트워크 대기를 모의하고 일시 오류를 포함한 응답 한 건을 반환합니다."""
    await asyncio.sleep(MOCK_DELAY_SECONDS)

    # 두 요청은 첫 시도에만 실패하여 재시도와 복구 과정을 확인할 수 있습니다.
    if item_id in {17, 41} and attempt == 1:
        raise RetriableCollectionError("일시적인 모의 서버 오류")

    return {
        "id": item_id,
        "status": "ok",
        "value": item_id * 7 % 101,
        "source": "mock",
    }


async def fetch_real(client: Any, item_id: int) -> dict[str, Any]:
    """httpx 비동기 클라이언트로 실제 API 응답 한 건을 가져옵니다."""
    import httpx

    try:
        response = await client.get(
            f"https://jsonplaceholder.typicode.com/todos/{item_id}"
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise RetriableCollectionError(str(error)) from error

    try:
        payload = response.json()
    except json.JSONDecodeError as error:
        raise RetriableCollectionError("API 응답이 올바른 JSON이 아닙니다.") from error

    if not isinstance(payload, dict):
        raise RetriableCollectionError("API 응답이 JSON 객체 형식이 아닙니다.")
    return payload


async def collect_one(
    item_id: int,
    semaphore: asyncio.Semaphore,
    client: Any | None,
    retry_counts: Counter[int],
    max_attempts: int,
) -> dict[str, Any]:
    """한 ID를 제한된 동시성으로 수집하고 실패 시 지수 백오프로 재시도합니다."""
    backoff_base = REAL_BACKOFF_SECONDS if USE_REAL_HTTP else MOCK_BACKOFF_SECONDS
    last_error: BaseException | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            # 요청 구간만 Semaphore로 감싸 백오프 중에는 입장권을 반납합니다.
            async with semaphore:
                request = (
                    fetch_real(client, item_id)
                    if USE_REAL_HTTP
                    else fetch_mock(item_id, attempt)
                )
                return await asyncio.wait_for(
                    request,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
        except (TimeoutError, RetriableCollectionError) as error:
            last_error = error
            if attempt == max_attempts:
                break

            retry_counts[item_id] += 1
            wait_seconds = backoff_base * (2 ** (attempt - 1))
            logger.warning(
                "ID %d 수집 실패(%s/%s): %s - %.2f초 후 재시도",
                item_id,
                attempt,
                max_attempts,
                error,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)

    raise RuntimeError(
        f"ID {item_id} 수집 실패: {max_attempts}회 시도 후 중단 ({last_error})"
    )


async def collect_all(
    count: int = REQUEST_COUNT,
    max_concurrent: int = MAX_CONCURRENT,
    max_attempts: int = MAX_ATTEMPTS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter[int]]:
    """전체 요청을 동시에 실행하고 성공 데이터와 최종 실패를 분리합니다."""
    if count < 1:
        raise ValueError("요청 수는 1 이상이어야 합니다.")
    if max_concurrent < 1:
        raise ValueError("동시 요청 제한은 1 이상이어야 합니다.")
    if max_attempts < 1:
        raise ValueError("최대 시도 횟수는 1 이상이어야 합니다.")

    semaphore = asyncio.Semaphore(max_concurrent)
    retry_counts: Counter[int] = Counter()

    async with AsyncExitStack() as stack:
        client: Any | None = None
        if USE_REAL_HTTP:
            try:
                import httpx
            except ImportError as error:
                raise RuntimeError(
                    "실제 HTTP 모드에는 httpx가 필요합니다. "
                    "'python -m pip install httpx'로 설치하세요."
                ) from error

            client = await stack.enter_async_context(
                httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
            )

        tasks = [
            collect_one(
                item_id,
                semaphore,
                client,
                retry_counts,
                max_attempts,
            )
            for item_id in range(1, count + 1)
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    collected: list[dict[str, Any]] = []
    dead_letters: list[dict[str, Any]] = []

    # 한 요청의 최종 실패가 다른 요청의 성공 결과를 없애지 않도록 분리합니다.
    for item_id, result in enumerate(raw_results, start=1):
        if isinstance(result, BaseException):
            dead_letters.append(
                {
                    "id": item_id,
                    "error_type": type(result).__name__,
                    "error": str(result),
                    "attempts": max_attempts,
                }
            )
        else:
            collected.append(result)

    return collected, dead_letters, retry_counts


def save_results(
    collected: list[dict[str, Any]],
    dead_letters: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> None:
    """수집 데이터, 최종 실패, 실행 지표를 UTF-8 JSON 파일로 저장합니다."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "collected.json": collected,
        "dead_letter.json": dead_letters,
        "metrics.json": metrics,
    }

    for filename, data in outputs.items():
        (OUTPUT_DIR / filename).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def print_report(
    collected: list[dict[str, Any]],
    dead_letters: list[dict[str, Any]],
    retry_counts: Counter[int],
    sequential_seconds: float,
    elapsed_seconds: float,
) -> None:
    """수집 성능과 재시도 및 실패 격리 결과를 콘솔에 출력합니다."""
    speedup = sequential_seconds / elapsed_seconds

    print("=" * 68)
    print("실습 3: asyncio 기반 비동기 수집기")
    print("=" * 68)
    print(f"요청 수          : {REQUEST_COUNT}건")
    print(f"동시 요청 제한   : {MAX_CONCURRENT}건")
    print(f"성공 / 최종 실패 : {len(collected)}건 / {len(dead_letters)}건")
    print(f"재시도           : {sum(retry_counts.values())}회 {dict(retry_counts)}")
    print(f"비동기 실행 시간 : {elapsed_seconds:.2f}초")
    if not USE_REAL_HTTP:
        print(f"동기 실행 시간   : {sequential_seconds:.2f}초")
        print(f"실측 속도 향상   : 약 {speedup:.1f}배")
    print(
        f"실행 모드        : {'실제 HTTP' if USE_REAL_HTTP else '오프라인 모의 실행'}"
    )
    print(f"결과 저장 위치   : {OUTPUT_DIR}")


async def main_async(sequential_seconds: float) -> int:
    """비동기 수집을 실행하고 결과 파일과 요약 리포트를 생성합니다."""
    logger.info(
        "비동기 수집을 시작합니다: 요청 %d건, 동시 제한 %d건",
        REQUEST_COUNT,
        MAX_CONCURRENT,
    )
    started = time.perf_counter()

    try:
        collected, dead_letters, retry_counts = await collect_all()
    except (RuntimeError, ValueError, OSError) as error:
        logger.error("비동기 수집을 시작하지 못했습니다: %s", error)
        return 1

    elapsed_seconds = time.perf_counter() - started
    metrics = {
        "requested": REQUEST_COUNT,
        "collected": len(collected),
        "failed": len(dead_letters),
        "retries": sum(retry_counts.values()),
        "retry_ids": dict(retry_counts),
        "sequential_seconds": round(sequential_seconds, 4),
        "elapsed_seconds": round(elapsed_seconds, 4),
        "max_concurrent": MAX_CONCURRENT,
        "max_attempts": MAX_ATTEMPTS,
        "mode": "real_http" if USE_REAL_HTTP else "mock",
    }

    try:
        save_results(collected, dead_letters, metrics)
    except OSError as error:
        logger.error("수집 결과 저장에 실패했습니다: %s", error)
        return 1

    print_report(
        collected,
        dead_letters,
        retry_counts,
        sequential_seconds,
        elapsed_seconds,
    )
    logger.info("비동기 수집과 결과 저장을 완료했습니다.")
    return 0


def main() -> int:
    """로깅을 설정하고 비동기 실행 진입점을 호출합니다."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )
    sequential_seconds = (
        measure_sequential_baseline() if not USE_REAL_HTTP else float("nan")
    )
    return asyncio.run(main_async(sequential_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
