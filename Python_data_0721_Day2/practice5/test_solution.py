from __future__ import annotations

import pandas as pd
import pytest
from pathlib import Path

from .solution import (
    benchmark_engines,
    duckdb_query,
    normalized,
    pandas_query,
    polars_query,
)


def test_normalized_aligns_types_and_order() -> None:
    frame = pd.DataFrame(
        {
            "event_type": ["refund", "purchase"],
            "event_count": [2.0, 3.0],
            "avg_amount": [10, 20],
            "total_amount": [20, 60],
        }
    )

    result = normalized(frame)

    assert result["event_type"].tolist() == ["purchase", "refund"]
    assert str(result["event_count"].dtype) == "int64"


def test_benchmark_requires_positive_repeat_count() -> None:
    with pytest.raises(ValueError, match="1 이상"):
        benchmark_engines({}, Path("unused"), repeats=0)


def test_three_engines_return_same_result() -> None:
    path = Path(__file__).with_name("test_events_fixture.csv")

    expected = normalized(pandas_query(path))
    pd.testing.assert_frame_equal(
        expected, normalized(polars_query(path)), check_dtype=False
    )
    pd.testing.assert_frame_equal(
        expected, normalized(duckdb_query(path)), check_dtype=False
    )
