"""=============================================================================
파일명: test_pipeline.py
작성자: 채수아
작성일: 2026-07-20
작성 목적: 비동기 ETL 파이프라인의 각 단계를 독립적으로 검증

입력:
    테스트 함수에서 생성하는 소규모 상품 데이터와 임시 저장 경로

검증 항목:
    스키마 정규화, 가격 규칙, 분리 건수, Parquet 라운드트립,
    비동기 재시도, 전체 파이프라인 산출물

실행:
    cd capstone01_async_etl && pytest -v
=============================================================================
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from capstone01_async_etl.pipeline import extract, load, run, transform
except ModuleNotFoundError:
    from pipeline import extract, load, run, transform


def make_valid_row() -> dict[str, Any]:
    """각 테스트가 독립적으로 수정할 수 있는 정상 상품 한 건을 반환합니다."""
    return {
        "id": 1,
        "name": " Product A ",
        "category": " FOOD ",
        "price": 10.5,
        "seller": {
            "seller_id": 2,
            "region": " Gwangju ",
        },
    }


def test_category_is_normalized_to_lowercase() -> None:
    """카테고리 공백 제거와 소문자 정규화를 검증합니다."""
    valid, invalid = transform([make_valid_row()])

    assert invalid == []
    assert valid[0].category == "food"
    assert valid[0].name == "Product A"
    assert valid[0].seller.region == "Gwangju"


def test_negative_price_is_rejected() -> None:
    """0 이하 가격이 유효 데이터에 포함되지 않는지 검증합니다."""
    row = make_valid_row()
    row["price"] = -1

    valid, invalid = transform([row])

    assert valid == []
    assert len(invalid) == 1
    assert invalid[0]["id"] == 1
    assert invalid[0]["errors"][0]["loc"] == ("price",)


def test_valid_and_invalid_counts_match_input() -> None:
    """변환 전후의 유효·무효 합계가 입력 건수와 일치하는지 검증합니다."""
    bad_price = make_valid_row()
    bad_price["id"] = 2
    bad_price["price"] = 0
    bad_seller = make_valid_row()
    bad_seller["id"] = 3
    bad_seller["seller"] = {"seller_id": 0, "region": "Seoul"}
    rows = [make_valid_row(), bad_price, bad_seller]

    valid, invalid = transform(rows)

    assert len(valid) == 1
    assert len(invalid) == 2
    assert len(valid) + len(invalid) == len(rows)


def test_parquet_round_trip(tmp_path: Path) -> None:
    """Parquet 저장 후 다시 읽은 DataFrame이 원본과 같은지 검증합니다."""
    valid, invalid = transform([make_valid_row()])
    assert invalid == []

    original = load(valid, tmp_path)
    restored = pd.read_parquet(tmp_path / "products.parquet")

    pd.testing.assert_frame_equal(original, restored)
    assert (tmp_path / "products.csv").read_text(encoding="utf-8").startswith("id,")


def test_extract_collects_all_ids_after_retry() -> None:
    """일시 오류가 발생한 ID도 재시도 후 모두 수집되는지 검증합니다."""
    rows, failed = asyncio.run(extract([1, 9, 37], max_concurrent=2))

    assert failed == []
    assert [row["id"] for row in rows] == [1, 9, 37]


def test_run_summary_and_outputs(tmp_path: Path) -> None:
    """전체 파이프라인 요약과 UTF-8 부가 산출물 생성을 검증합니다."""
    summary = asyncio.run(run(list(range(1, 31)), tmp_path))
    invalid = json.loads(
        (tmp_path / "invalid_records.json").read_text(encoding="utf-8")
    )

    assert summary["requested"] == 30
    assert summary["extracted"] == 30
    assert summary["valid"] == 28
    assert summary["transform_invalid"] == 2
    assert summary["rows_saved"] == 28
    assert {item["id"] for item in invalid} == {13, 29}
    assert (tmp_path / "products.csv").is_file()
    assert (tmp_path / "products.parquet").is_file()
    assert (tmp_path / "summary.json").is_file()
