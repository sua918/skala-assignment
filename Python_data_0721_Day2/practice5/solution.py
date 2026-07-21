from __future__ import annotations

import json
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path

import duckdb
import pandas as pd
import polars as pl
from pandas.testing import assert_frame_equal

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_paths import data_dir, output_dir  # noqa: E402


QUERY_DESCRIPTION = (
    "제공 데이터에는 status/value 컬럼이 없으므로 amount > 0인 이벤트만 골라 "
    "event_type별 건수·평균 금액·총금액을 집계한다."
)


def pandas_query(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    filtered = frame.loc[frame["amount"] > 0]
    return (
        filtered.groupby("event_type", as_index=False)
        .agg(
            event_count=("event_id", "count"),
            avg_amount=("amount", "mean"),
            total_amount=("amount", "sum"),
        )
        .sort_values("event_type")
        .reset_index(drop=True)
    )


def polars_query(path: Path) -> pd.DataFrame:
    result = (
        pl.scan_csv(path)
        .filter(pl.col("amount") > 0)
        .group_by("event_type")
        .agg(
            pl.len().alias("event_count"),
            pl.col("amount").mean().alias("avg_amount"),
            pl.col("amount").sum().alias("total_amount"),
        )
        .sort("event_type")
        .collect()
    )
    return result.to_pandas()


def duckdb_query(path: Path) -> pd.DataFrame:
    normalized = path.as_posix().replace("'", "''")
    return duckdb.sql(
        f"""
        SELECT event_type,
               COUNT(*) AS event_count,
               AVG(amount) AS avg_amount,
               SUM(amount) AS total_amount
        FROM read_csv_auto('{normalized}')
        WHERE amount > 0
        GROUP BY event_type
        ORDER BY event_type
        """
    ).df()


def benchmark_engines(
    engines: dict[str, Callable[[Path], pd.DataFrame]],
    path: Path,
    repeats: int = 3,
) -> tuple[dict[str, pd.DataFrame], dict[str, list[float]]]:
    """모든 엔진을 워밍업한 뒤 라운드마다 실행 순서를 회전해 측정한다."""
    if repeats <= 0:
        raise ValueError("반복 횟수는 1 이상이어야 합니다.")
    names = list(engines)
    results: dict[str, pd.DataFrame] = {}
    timings = {name: [] for name in names}

    for name in names:
        results[name] = engines[name](path)

    for round_index in range(repeats):
        order = names[round_index:] + names[:round_index]
        for name in order:
            started = time.perf_counter()
            results[name] = engines[name](path)
            timings[name].append(time.perf_counter() - started)
    return results, timings


def normalized(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy().sort_values("event_type").reset_index(drop=True)
    result["event_count"] = result["event_count"].astype("int64")
    result["avg_amount"] = result["avg_amount"].astype("float64")
    result["total_amount"] = result["total_amount"].astype("float64")
    return result


def main() -> None:
    path = data_dir() / "events_large.csv"
    engines = {
        "Pandas": pandas_query,
        "Polars Lazy": polars_query,
        "DuckDB": duckdb_query,
    }
    results, timings = benchmark_engines(engines, path)

    baseline = normalized(results["Pandas"])
    for name in ("Polars Lazy", "DuckDB"):
        assert_frame_equal(
            baseline,
            normalized(results[name]),
            check_dtype=False,
            rtol=1e-9,
            atol=1e-9,
        )

    medians = {name: statistics.median(values) for name, values in timings.items()}
    fastest = min(medians, key=medians.get)
    benchmark_table = pd.DataFrame(
        [
            {
                "engine": name,
                "median_seconds": round(medians[name], 4),
                "relative_to_fastest": round(medians[name] / medians[fastest], 2),
            }
            for name in sorted(medians, key=medians.get)
        ]
    )

    print("=" * 72)
    print("실습 5 | Pandas · Polars · DuckDB 성능 비교")
    print("=" * 72)
    print(f"비교 질의              : {QUERY_DESCRIPTION}")
    print("세 엔진 결과 일치 검증 : PASS")
    print("\n집계 결과")
    print(baseline.round(2).to_string(index=False))
    print("\n벤치마크 중앙값 (3회)")
    print(benchmark_table.to_string(index=False))

    out = output_dir(__file__)
    baseline.to_csv(out / "aggregation_result.csv", index=False, encoding="utf-8-sig")
    benchmark_table.to_csv(out / "benchmark.csv", index=False, encoding="utf-8-sig")
    lazy_plan = (
        pl.scan_csv(path)
        .filter(pl.col("amount") > 0)
        .group_by("event_type")
        .agg(
            pl.len().alias("event_count"),
            pl.col("amount").mean().alias("avg_amount"),
            pl.col("amount").sum().alias("total_amount"),
        )
        .explain()
    )
    (out / "polars_lazy_plan.txt").write_text(lazy_plan, encoding="utf-8")
    metrics = {
        "result_match": True,
        "query": QUERY_DESCRIPTION,
        "fastest_engine": fastest,
        "median_seconds": {key: round(value, 6) for key, value in medians.items()},
    }
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n비교 결과 저장           : {out.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
