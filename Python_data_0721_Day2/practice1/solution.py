"""=============================================================================
파일명: solution.py
작성자: 채수아
작성일: 2026-07-20
작성 목적: 대용량 웹 로그를 메모리 효율적으로 집계하고 주요 지표를 출력

입력:
    data/web_logs.csv

집계 항목:
    전체 요청 수, 상태코드별 요청 수, 5xx 오류율,
    경로별 요청 수, 시간대별 요청 수, 접속 상위 IP

실행:
    python ex01_streaming_agg/solution.py
=============================================================================
"""

import csv
import logging
from collections import Counter
from collections.abc import Iterator
from functools import reduce
from pathlib import Path
from typing import Any

# 실행 위치와 관계없이 프로젝트의 data 폴더를 찾습니다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "web_logs.csv"
REQUIRED_COLUMNS = {"ip", "timestamp", "path", "status"}

logger = logging.getLogger(__name__)


def read_logs(path: Path) -> Iterator[dict[str, str]]:
    """CSV 로그를 메모리에 쌓지 않고 한 행씩 반환합니다."""
    if not path.is_file():
        raise FileNotFoundError(f"입력 로그 파일을 찾을 수 없습니다: {path}")

    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"입력 로그에 필수 컬럼이 없습니다: {missing}")

        yield from reader


def fold(
    acc: dict[str, Any],
    row: dict[str, str],
) -> dict[str, Any]:
    """로그 한 건을 누적 결과에 반영합니다."""
    acc["total"] += 1
    acc["status"][row["status"]] += 1
    acc["path"][row["path"]] += 1
    acc["ip"][row["ip"]] += 1

    # ISO 형식 타임스탬프(YYYY-MM-DDTHH:MM:SS)에서 시간만 추출합니다.
    hour = row["timestamp"][11:13]
    acc["hour"][hour] += 1

    return acc


def print_report(result: dict[str, Any]) -> None:
    """집계 결과를 읽기 쉬운 콘솔 리포트로 출력합니다."""
    total = result["total"]
    status_counter = result["status"]
    path_counter = result["path"]
    hour_counter = result["hour"]
    ip_counter = result["ip"]

    error_5xx = sum(
        count for status, count in status_counter.items() if status.startswith("5")
    )
    error_ratio = error_5xx / total * 100

    print("=" * 50)
    print("실습 1: 대용량 로그 스트리밍 집계")
    print("=" * 50)
    print(f"총 요청 수 : {total:,}건")
    print(f"5xx 오류   : {error_5xx:,}건")
    print(f"5xx 오류율 : {error_ratio:.2f}%")

    print("\n[상태코드별 요청]")
    for status, count in sorted(status_counter.items()):
        print(f"{status}: {count:,}건")

    print("\n[인기 경로 TOP 5]")
    for path, count in path_counter.most_common(5):
        print(f"{path:<25} {count:>7,}건")

    print("\n[시간대별 요청]")
    for hour, count in sorted(hour_counter.items()):
        print(f"{hour}시: {count:,}건")

    print("\n[접속 상위 IP TOP 5]")
    for ip, count in ip_counter.most_common(5):
        print(f"{ip:<18} {count:>4,}건")


def main() -> int:
    """로그를 집계하고 리포트를 출력합니다."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    initial = {
        "total": 0,
        "status": Counter(),
        "path": Counter(),
        "hour": Counter(),
        "ip": Counter(),
    }

    logger.info("로그 집계를 시작합니다: %s", DATA_PATH)

    try:
        result = reduce(fold, read_logs(DATA_PATH), initial)
    except (FileNotFoundError, ValueError) as error:
        logger.error("로그 집계에 실패했습니다: %s", error)
        return 1

    print_report(result)
    logger.info("로그 집계를 완료했습니다: 총 %s건", f"{result['total']:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
