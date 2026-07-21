from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pandas as pd
import pytest

from .config import Config
from .report import aggregate, prepare, render_html


def sample_sales() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_id": [1, 2, 3],
            "category": ["Food", "Food", "Home"],
            "region": ["Seoul", None, "Busan"],
            "unit_price": [1000, None, 2000],
            "quantity": [2, 1, 3],
            "discount": [0.1, None, 0.2],
        }
    )


def test_prepare_fills_missing_values_and_calculates_amount() -> None:
    clean = prepare(sample_sales())

    assert (
        clean[["unit_price", "quantity", "discount", "region"]].isna().sum().sum() == 0
    )
    assert clean["amount"].round(2).tolist() == [1800.0, 1000.0, 4800.0]


def test_aggregate_returns_expected_kpis() -> None:
    result = aggregate(prepare(sample_sales()), top_n=2)

    assert result["kpi"]["주문 수"] == 3
    assert result["kpi"]["총 순매출"] == 7600
    assert len(result["by_category"]) == 2


def test_average_order_value_uses_order_total() -> None:
    frame = pd.DataFrame(
        {
            "order_id": [1, 1, 2],
            "category": ["Food", "Food", "Home"],
            "region": ["Seoul", "Seoul", "Busan"],
            "amount": [100.0, 100.0, 100.0],
        }
    )

    result = aggregate(frame)

    assert result["kpi"]["주문 수"] == 2
    assert result["kpi"]["평균 주문액"] == 150


def test_render_creates_utf8_html() -> None:
    default_config = Config()
    config = Config(
        output_dir=default_config.output_dir,
        template_dir=default_config.template_dir,
    )
    generated_at = datetime(2026, 7, 21, 9, 30, 0)

    html = render_html(aggregate(prepare(sample_sales())), config, generated_at)

    assert "SKALA 일일 매출 운영 리포트" in html
    assert "총 순매출" in html


def test_config_is_immutable() -> None:
    config = Config()

    with pytest.raises(FrozenInstanceError):
        config.title = "변경 불가"  # type: ignore[misc]
