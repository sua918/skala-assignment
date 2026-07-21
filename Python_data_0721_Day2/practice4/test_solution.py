from __future__ import annotations

import pandas as pd
import pytest

from .solution import clean_sales, winsorize


def sample_sales() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_id": ["A", "B", "C", "D"],
            "order_date": ["2026-07-01"] * 4,
            "region": ["Seoul", "Seoul", None, "Busan"],
            "category": ["Food", "Food", "Home", "Home"],
            "quantity": [1, 2, None, 100],
            "unit_price": [1000, None, 2000, 3000],
            "discount": [0, 0.1, None, 0.2],
        }
    )


def test_clean_sales_preserves_rows_and_fills_missing_values() -> None:
    clean, metrics = clean_sales(sample_sales())

    assert len(clean) == 4
    assert metrics["missing_after"] == 0
    assert str(clean["order_date"].dtype).startswith("datetime64")
    assert str(clean["category"].dtype) == "category"


def test_winsorize_clips_extreme_value() -> None:
    clipped, _, upper = winsorize(pd.Series([1, 2, 3, 100]))

    assert clipped.max() == upper
    assert clipped.max() < 100


def test_clean_sales_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="필수 컬럼"):
        clean_sales(pd.DataFrame({"order_id": [1]}))


def test_clean_sales_handles_invalid_date_and_unknown_category() -> None:
    frame = sample_sales()
    frame.loc[0, "order_date"] = "invalid"
    frame.loc[0, "category"] = None
    frame.loc[0, "unit_price"] = None

    clean, metrics = clean_sales(frame)

    assert metrics["missing_after"] == 0
    assert "Unknown" in clean["category"].cat.categories
    assert clean["order_date"].isna().sum() == 0
