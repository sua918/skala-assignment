from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

# Pandas 2.x에서는 명시적으로 활성화하고, 3.x에서는 기본 활성화 상태를 사용한다.
if pd.__version__.startswith("2."):
    pd.options.mode.copy_on_write = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_paths import data_dir, output_dir  # noqa: E402


def winsorize(
    series: pd.Series,
    factor: float = 1.5,
    minimum: float | None = None,
) -> tuple[pd.Series, float, float]:
    q1, q3 = series.quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - factor * iqr, q3 + factor * iqr
    if minimum is not None:
        lower = max(lower, minimum)
    return series.clip(lower=lower, upper=upper), float(lower), float(upper)


def clean_sales(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    required = {
        "order_id",
        "order_date",
        "region",
        "category",
        "quantity",
        "unit_price",
        "discount",
    }
    missing_columns = required - set(raw.columns)
    if raw.empty:
        raise ValueError("정제할 판매 데이터가 없습니다.")
    if missing_columns:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(sorted(missing_columns))}")

    df = raw.copy()
    before_missing = int(df.isna().sum().sum())

    df["order_date"] = pd.to_datetime(
        df["order_date"],
        errors="coerce",
        format="mixed",
    )
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["discount"] = pd.to_numeric(df["discount"], errors="coerce")
    before_max_price = float(df["unit_price"].max())
    before_max_quantity = float(df["quantity"].max())

    if df["order_date"].notna().sum() == 0:
        raise ValueError("유효한 주문일이 없습니다.")
    df["order_date"] = df["order_date"].fillna(df["order_date"].median())
    df["category"] = df["category"].fillna("Unknown").astype("category")
    df["region"] = df["region"].fillna("Unknown").astype("category")
    df.loc[df["unit_price"] <= 0, "unit_price"] = pd.NA

    df["unit_price"] = df["unit_price"].fillna(
        df.groupby("category", observed=True)["unit_price"].transform("median")
    )
    df["unit_price"] = df["unit_price"].fillna(df["unit_price"].median())
    df["quantity"] = df["quantity"].fillna(df["quantity"].median())
    if df[["unit_price", "quantity"]].isna().any().any():
        raise ValueError("단가 또는 수량을 대치할 유효값이 없습니다.")
    df["discount"] = df["discount"].fillna(0).clip(0, 1)

    df["unit_price"], price_lower, price_upper = winsorize(df["unit_price"], minimum=0)
    df["quantity"], quantity_lower, quantity_upper = winsorize(
        df["quantity"], minimum=0
    )
    df["amount"] = df["quantity"] * df["unit_price"] * (1 - df["discount"])

    metrics = {
        "rows": len(df),
        "missing_before": before_missing,
        "missing_after": int(df.isna().sum().sum()),
        "max_price_before": before_max_price,
        "max_price_after": float(df["unit_price"].max()),
        "max_quantity_before": before_max_quantity,
        "max_quantity_after": float(df["quantity"].max()),
        "price_bounds": [price_lower, price_upper],
        "quantity_bounds": [quantity_lower, quantity_upper],
        "total_sales": float(df["amount"].sum()),
    }
    return df, metrics


def main() -> None:
    raw = pd.read_csv(data_dir() / "sales_raw.csv")
    clean, metrics = clean_sales(raw)
    summary = (
        clean.groupby("category", observed=True)
        .agg(
            orders=("order_id", "count"),
            avg_price=("unit_price", "mean"),
            total_quantity=("quantity", "sum"),
            total_sales=("amount", "sum"),
        )
        .sort_values("total_sales", ascending=False)
        .round(2)
    )
    pivot = clean.pivot_table(
        index="region",
        columns="category",
        values="amount",
        aggfunc="sum",
        fill_value=0,
        observed=True,
    ).round(0)
    category_master = pd.DataFrame(
        {
            "category": ["Electronics", "Home", "Beauty", "Food", "Fashion"],
            "manager": ["김하늘", "박서준", "이수빈", "정다현", "최윤호"],
        }
    )
    merged = clean.merge(category_master, on="category", how="left")
    if len(merged) != len(clean):
        raise ValueError("병합 전후 행 수가 달라졌습니다.")
    unmatched_managers = int(merged["manager"].isna().sum())
    if unmatched_managers:
        raise ValueError(
            f"담당자가 연결되지 않은 거래가 {unmatched_managers}건 있습니다."
        )
    metrics["merge_rows_before"] = len(clean)
    metrics["merge_rows_after"] = len(merged)
    metrics["unmatched_managers"] = unmatched_managers

    print("=" * 72)
    print("실습 4 | Pandas 2.x 데이터 정제")
    print("=" * 72)
    print(f"행 수                   : {metrics['rows']:,}")
    print(
        f"결측값                  : {metrics['missing_before']:,} → {metrics['missing_after']:,}"
    )
    print(
        f"단가 최댓값             : {metrics['max_price_before']:,.0f} → {metrics['max_price_after']:,.0f}"
    )
    print(
        f"수량 최댓값             : {metrics['max_quantity_before']:,.0f} → {metrics['max_quantity_after']:,.1f}"
    )
    print(f"총 순매출                : {metrics['total_sales']:,.0f}원")
    print(f"병합 행 수               : {len(clean):,} → {len(merged):,}")
    print(f"담당자 미지정            : {unmatched_managers:,}건")
    print("\n정제 후 데이터 타입")
    print(clean.dtypes.to_string())
    print("\n카테고리별 집계")
    print(summary.to_string())
    print("\n지역 × 카테고리 피벗")
    print(pivot.to_string())

    out = output_dir(__file__)
    clean.to_csv(out / "sales_clean.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(out / "category_summary.csv", encoding="utf-8-sig")
    pivot.to_csv(out / "region_category_pivot.csv", encoding="utf-8-sig")
    merged[["order_id", "category", "manager"]].head(50).to_csv(
        out / "merge_sample.csv",
        index=False,
        encoding="utf-8-sig",
    )
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n정제 결과 저장           : {out.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
