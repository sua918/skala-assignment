from __future__ import annotations

import time

import duckdb
import pandas as pd
import polars as pl


def _timed(function):
    start = time.perf_counter()
    result = function()
    return result, time.perf_counter() - start


def compare_engines(frame: pd.DataFrame) -> dict:
    """동일한 계약별 집계를 세 엔진으로 실행하고 결과 일치를 검증한다."""

    def pandas_query():
        return (
            frame.groupby("contract", as_index=False)
            .agg(
                customers=("customer_id", "count"),
                avg_monthly_charges=("monthly_charges", "mean"),
                churn_rate=("churn", "mean"),
            )
            .sort_values("contract")
            .reset_index(drop=True)
        )

    def polars_query():
        return (
            pl.from_pandas(frame)
            .lazy()
            .group_by("contract")
            .agg(
                pl.len().alias("customers"),
                pl.col("monthly_charges").mean().alias("avg_monthly_charges"),
                pl.col("churn").mean().alias("churn_rate"),
            )
            .sort("contract")
            .collect()
            .to_pandas()
        )

    def duckdb_query():
        connection = duckdb.connect()
        try:
            connection.register("customer_frame", frame)
            return connection.execute(
                """
                SELECT contract,
                       COUNT(*) AS customers,
                       AVG(monthly_charges) AS avg_monthly_charges,
                       AVG(churn) AS churn_rate
                FROM customer_frame
                GROUP BY contract
                ORDER BY contract
                """
            ).df()
        finally:
            connection.close()

    pandas_result, pandas_time = _timed(pandas_query)
    polars_result, polars_time = _timed(polars_query)
    duckdb_result, duckdb_time = _timed(duckdb_query)

    for candidate in [polars_result, duckdb_result]:
        pd.testing.assert_frame_equal(
            pandas_result,
            candidate,
            check_dtype=False,
            atol=1e-8,
            rtol=1e-8,
        )

    timings = {
        "Pandas": pandas_time,
        "Polars": polars_time,
        "DuckDB": duckdb_time,
    }
    fastest = min(timings, key=timings.get)
    return {
        "timings": timings,
        "fastest": fastest,
        "results_match": True,
        "query": "계약 유형별 고객 수·평균 월 요금·이탈률",
    }
