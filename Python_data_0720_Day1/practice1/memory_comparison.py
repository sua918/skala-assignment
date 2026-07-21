"""=============================================================================
파일명: memory_comparison.py
작성자: 채수아
작성일: 2026-07-20
작성 목적: 전체 로딩 방식과 스트리밍 방식의 최대 메모리 사용량 비교

입력:
    data/web_logs.csv

비교 항목:
    readlines 전체 로딩 방식과 파일 스트리밍 방식의 최대 메모리

실행:
    python ex01_streaming_agg/memory_comparison.py
=============================================================================
"""

import gc
import logging
import tracemalloc
from collections.abc import Callable
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "web_logs.csv"

logger = logging.getLogger(__name__)


def count_with_readlines(path: Path) -> int:
    """파일의 모든 줄을 리스트로 올린 뒤 데이터 행을 계산합니다."""
    with path.open(encoding="utf-8") as file:
        lines = file.readlines()

    return len(lines) - 1  # 헤더 제외


def count_with_streaming(path: Path) -> int:
    """파일을 한 줄씩 읽으며 데이터 행을 계산합니다."""
    with path.open(encoding="utf-8") as file:
        next(file)  # 헤더 제외
        return sum(1 for _ in file)


def measure_peak_memory(
    counter: Callable[[Path], int],
    path: Path,
) -> tuple[int, float]:
    """행 계산 함수의 결과와 최대 메모리 사용량을 반환합니다."""
    gc.collect()
    tracemalloc.start()

    row_count = counter(path)
    _, peak = tracemalloc.get_traced_memory()

    tracemalloc.stop()
    return row_count, peak / 1024 / 1024


def main() -> int:
    """두 파일 읽기 방식의 최대 메모리 사용량을 비교합니다."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    if not DATA_PATH.is_file():
        logger.error("입력 로그 파일을 찾을 수 없습니다: %s", DATA_PATH)
        return 1

    list_count, list_peak = measure_peak_memory(
        count_with_readlines,
        DATA_PATH,
    )
    stream_count, stream_peak = measure_peak_memory(
        count_with_streaming,
        DATA_PATH,
    )

    print("=" * 52)
    print("실습 1 확장: 로그 읽기 방식별 최대 메모리 비교")
    print("=" * 52)
    print(f"전체 로딩 : {list_count:,}건 / {list_peak:.2f} MB")
    print(f"스트리밍  : {stream_count:,}건 / {stream_peak:.2f} MB")
    print(f"메모리 차이: {list_peak / stream_peak:.1f}배")

    if list_count != stream_count:
        logger.error("두 방식의 행 개수가 일치하지 않습니다.")
        return 1

    logger.info("두 방식 모두 %s건을 처리했습니다.", list_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
