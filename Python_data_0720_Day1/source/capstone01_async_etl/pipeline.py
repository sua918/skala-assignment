"""=============================================================================
파일명: pipeline.py
작성자: 채수아
작성일: 2026-07-20
작성 목적: 비동기 수집부터 검증과 파일 저장까지 ETL 파이프라인을 실행

입력:
    상품 ID 목록과 해당 ID로 생성되는 모의 API 응답

처리 항목:
    Extract: 비동기 수집, 동시성 제한, 재시도, 실패 격리
    Transform: Pydantic 검증과 유효/무효 데이터 분리
    Load: DataFrame 변환 후 CSV와 Parquet 저장

실행:
    python capstone01_async_etl/pipeline.py
=============================================================================
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import ValidationError

try:
    from capstone01_async_etl.models import Product
except ModuleNotFoundError:
    from models import Product

REQUEST_COUNT = 60
MAX_CONCURRENT = 10
MAX_ATTEMPTS = 3
MOCK_DELAY_SECONDS = 0.03
BACKOFF_SECONDS = 0.01
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DATAFRAME_COLUMNS = [
    "id",
    "name",
    "category",
    "price",
    "seller_id",
    "seller_region",
]

logger = logging.getLogger(__name__)


async def fetch_mock_product(item_id: int, attempt: int) -> dict[str, Any]:
    """상품 API 대기를 모의하고 ID에 대응하는 원시 상품 한 건을 반환합니다."""
    await asyncio.sleep(MOCK_DELAY_SECONDS)

    if item_id in {9, 37} and attempt == 1:
        raise TimeoutError("일시적인 모의 수집 지연")

    category = [" DATA ", " Cloud ", " AI "][item_id % 3]
    region = ["Gwangju", "Seoul", "Busan"][item_id % 3]
    return {
        "id": item_id,
        "name": f" Product {item_id:03d} ",
        "category": category,
        "price": -100.0 if item_id in {13, 29} else round(8.5 + item_id * 1.37, 2),
        "seller": {
            "seller_id": item_id % 7 + 1,
            "region": region,
        },
    }


async def extract(
    ids: list[int],
    max_concurrent: int = MAX_CONCURRENT,
    max_attempts: int = MAX_ATTEMPTS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """ID 목록을 제한된 동시성으로 수집하고 최종 실패를 별도로 반환합니다."""
    if max_concurrent < 1:
        raise ValueError("동시 요청 제한은 1 이상이어야 합니다.")
    if max_attempts < 1:
        raise ValueError("최대 시도 횟수는 1 이상이어야 합니다.")

    semaphore = asyncio.Semaphore(max_concurrent)

    async def collect_one(item_id: int) -> dict[str, Any]:
        last_error: TimeoutError | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                # 백오프 중에는 입장권을 반납하도록 실제 요청 구간만 제한합니다.
                async with semaphore:
                    return await fetch_mock_product(item_id, attempt)
            except TimeoutError as error:
                last_error = error
                if attempt == max_attempts:
                    break

                wait_seconds = BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "상품 ID %d 수집 실패(%d/%d): %s - %.2f초 후 재시도",
                    item_id,
                    attempt,
                    max_attempts,
                    error,
                    wait_seconds,
                )
                await asyncio.sleep(wait_seconds)

        raise RuntimeError(
            f"상품 ID {item_id} 수집 실패: {max_attempts}회 시도 후 중단 ({last_error})"
        )

    results = await asyncio.gather(
        *(collect_one(item_id) for item_id in ids),
        return_exceptions=True,
    )

    collected: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for item_id, result in zip(ids, results, strict=True):
        if isinstance(result, BaseException):
            failed.append(
                {
                    "id": item_id,
                    "stage": "extract",
                    "error_type": type(result).__name__,
                    "error": str(result),
                }
            )
        else:
            collected.append(result)

    return collected, failed


def transform(
    raw: list[dict[str, Any]],
) -> tuple[list[Product], list[dict[str, Any]]]:
    """원시 상품을 검증하여 유효 모델과 검증 실패 정보를 분리합니다."""
    valid: list[Product] = []
    invalid: list[dict[str, Any]] = []

    # 한 건의 검증 실패가 이후 데이터 처리를 막지 않도록 개별 처리합니다.
    for row_number, row in enumerate(raw, start=1):
        try:
            valid.append(Product.model_validate(row))
        except ValidationError as error:
            invalid.append(
                {
                    "row": row_number,
                    "id": row.get("id"),
                    "stage": "transform",
                    "data": row,
                    "errors": error.errors(),
                }
            )

    return valid, invalid


def products_to_frame(valid: list[Product]) -> pd.DataFrame:
    """검증된 중첩 상품 모델을 저장하기 쉬운 평면 DataFrame으로 변환합니다."""
    rows = [
        {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "price": product.price,
            "seller_id": product.seller.seller_id,
            "seller_region": product.seller.region,
        }
        for product in valid
    ]
    return pd.DataFrame(rows, columns=DATAFRAME_COLUMNS)


def load(valid: list[Product], out_dir: str | Path = OUTPUT_DIR) -> pd.DataFrame:
    """검증된 상품을 UTF-8 CSV와 타입을 보존하는 Parquet 파일로 저장합니다."""
    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    frame = products_to_frame(valid)
    frame.to_csv(destination / "products.csv", index=False, encoding="utf-8")
    frame.to_parquet(destination / "products.parquet", index=False)
    return frame


def save_json(data: Any, path: Path) -> None:
    """파이프라인 부가 정보를 UTF-8 JSON 파일로 저장합니다."""
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


async def run(
    ids: list[int],
    out_dir: str | Path = OUTPUT_DIR,
) -> dict[str, Any]:
    """Extract, Transform, Load 단계를 순서대로 조율하고 요약을 반환합니다."""
    destination = Path(out_dir)
    started = time.perf_counter()

    raw, extract_failed = await extract(ids)
    valid, transform_invalid = transform(raw)
    frame = load(valid, destination)

    invalid_records = [*extract_failed, *transform_invalid]
    elapsed_seconds = time.perf_counter() - started
    summary = {
        "requested": len(ids),
        "extracted": len(raw),
        "extract_failed": len(extract_failed),
        "valid": len(valid),
        "transform_invalid": len(transform_invalid),
        "invalid_total": len(invalid_records),
        "rows_saved": len(frame),
        "elapsed_seconds": round(elapsed_seconds, 4),
        "csv": str(destination / "products.csv"),
        "parquet": str(destination / "products.parquet"),
    }

    save_json(invalid_records, destination / "invalid_records.json")
    save_json(summary, destination / "summary.json")
    return summary


def print_report(summary: dict[str, Any]) -> None:
    """ETL 단계별 처리 건수와 생성 결과를 콘솔 리포트로 출력합니다."""
    print("=" * 68)
    print("종합실습 1: 비동기 ETL 파이프라인")
    print("=" * 68)
    print(f"요청 / 수집 성공 : {summary['requested']}건 / {summary['extracted']}건")
    print(f"수집 최종 실패   : {summary['extract_failed']}건")
    print(f"검증 유효 / 무효 : {summary['valid']}건 / {summary['transform_invalid']}건")
    print(f"최종 저장        : {summary['rows_saved']}건")
    print(f"실행 시간        : {summary['elapsed_seconds']:.2f}초")
    print(f"CSV              : {summary['csv']}")
    print(f"Parquet          : {summary['parquet']}")


def main() -> int:
    """기본 60개 상품 ID로 전체 ETL 파이프라인을 실행합니다."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )
    logger.info("비동기 ETL 파이프라인을 시작합니다.")

    try:
        summary = asyncio.run(run(list(range(1, REQUEST_COUNT + 1))))
    except (OSError, RuntimeError, ValueError) as error:
        logger.error("비동기 ETL 파이프라인 실행에 실패했습니다: %s", error)
        return 1

    print_report(summary)
    print(f"\n요약 딕셔너리: {summary}")
    logger.info("비동기 ETL 파이프라인을 완료했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
