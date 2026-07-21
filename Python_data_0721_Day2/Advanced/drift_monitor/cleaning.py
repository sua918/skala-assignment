from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import NUMERIC_FEATURES


REQUIRED_COLUMNS = {
    "customer_id",
    "gender",
    "senior",
    "tenure_months",
    "monthly_charges",
    "total_charges",
    "contract",
    "payment_method",
    "num_services",
    "churn",
}


@dataclass(frozen=True)
class QualitySnapshot:
    rows: int
    duplicate_ids: int
    missing_cells: int
    missing_rate: float
    numeric_coercions: int

    def as_dict(self) -> dict:
        return {
            "rows": self.rows,
            "duplicate_ids": self.duplicate_ids,
            "missing_cells": self.missing_cells,
            "missing_rate": self.missing_rate,
            "numeric_coercions": self.numeric_coercions,
        }


def validate_columns(frame: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(sorted(missing))}")
    if frame.empty:
        raise ValueError("분석할 데이터가 없습니다.")


def clean_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, QualitySnapshot]:
    """드리프트를 숨기지 않는 최소 정제와 품질 스냅샷을 반환한다."""

    validate_columns(frame)
    cleaned = frame.copy()
    before_missing = int(cleaned.isna().sum().sum())
    coercions = 0

    for column in NUMERIC_FEATURES + ["churn"]:
        before = cleaned[column].isna().sum()
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
        coercions += int(cleaned[column].isna().sum() - before)

    for column in ["gender", "contract", "payment_method"]:
        cleaned[column] = cleaned[column].astype("string").str.strip()
        cleaned[column] = cleaned[column].fillna("Unknown")

    for column in NUMERIC_FEATURES:
        if cleaned[column].isna().any():
            if column == "total_charges":
                medians = cleaned.groupby("contract")[column].transform("median")
                cleaned[column] = cleaned[column].fillna(medians)
            cleaned[column] = cleaned[column].fillna(cleaned[column].median())

    snapshot = QualitySnapshot(
        rows=len(cleaned),
        duplicate_ids=int(cleaned["customer_id"].duplicated().sum()),
        missing_cells=before_missing,
        missing_rate=before_missing / max(cleaned.shape[0] * cleaned.shape[1], 1),
        numeric_coercions=coercions,
    )
    return cleaned, snapshot


def raw_missing_rates(frame: pd.DataFrame) -> dict[str, float]:
    return {column: float(frame[column].isna().mean()) for column in frame.columns}
