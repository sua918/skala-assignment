from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

try:
    from .config import CONFIG, Config
except ImportError:  # 스크립트 직접 실행 지원
    from config import CONFIG, Config


LOGGER = logging.getLogger(__name__)
REQUIRED_COLUMNS = {
    "order_id",
    "category",
    "region",
    "unit_price",
    "quantity",
    "discount",
}


def prepare(frame: pd.DataFrame) -> pd.DataFrame:
    """원본 판매 데이터를 검증하고 리포트 집계가 가능한 형태로 정제한다."""
    if frame.empty:
        raise ValueError("분석할 판매 데이터가 없습니다.")
    missing_columns = REQUIRED_COLUMNS - set(frame.columns)
    if missing_columns:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(sorted(missing_columns))}")

    clean = frame.copy()
    clean["unit_price"] = pd.to_numeric(clean["unit_price"], errors="coerce")
    clean["quantity"] = pd.to_numeric(clean["quantity"], errors="coerce")
    clean["discount"] = (
        pd.to_numeric(clean["discount"], errors="coerce").fillna(0).clip(0, 1)
    )
    clean["category"] = clean["category"].fillna("Unknown")
    clean["region"] = clean["region"].fillna("Unknown")
    clean["unit_price"] = clean["unit_price"].fillna(
        clean.groupby("category", observed=True)["unit_price"].transform("median")
    )
    clean["unit_price"] = clean["unit_price"].fillna(clean["unit_price"].median())
    clean["quantity"] = clean["quantity"].fillna(clean["quantity"].median())
    clean = clean.loc[(clean["unit_price"] > 0) & (clean["quantity"] > 0)].copy()
    if clean.empty:
        raise ValueError("정제 후 리포트에 사용할 데이터가 없습니다.")
    clean["amount"] = clean["unit_price"] * clean["quantity"] * (1 - clean["discount"])
    return clean


def aggregate(frame: pd.DataFrame, top_n: int = 5) -> dict:
    """정제된 데이터에서 KPI와 카테고리·지역별 매출을 계산한다."""
    if top_n <= 0:
        raise ValueError("top_n은 1 이상이어야 합니다.")
    order_totals = frame.groupby("order_id", observed=True)["amount"].sum()
    return {
        "kpi": {
            "주문 수": int(len(order_totals)),
            "총 순매출": round(float(frame["amount"].sum())),
            "평균 주문액": round(float(order_totals.mean())),
            "지역 수": int(frame["region"].nunique()),
        },
        "by_category": (
            frame.groupby("category", as_index=False)["amount"]
            .sum()
            .sort_values("amount", ascending=False)
            .head(top_n)
            .to_dict("records")
        ),
        "by_region": (
            frame.groupby("region", as_index=False)["amount"]
            .sum()
            .sort_values("amount", ascending=False)
            .to_dict("records")
        ),
    }


def render(
    data: dict, config: Config = CONFIG, generated_at: datetime | None = None
) -> Path:
    """집계 결과를 Jinja2 템플릿에 적용해 타임스탬프 HTML로 저장한다."""
    timestamp = generated_at or datetime.now()
    html = render_html(data, config, timestamp)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    destination = config.output_dir / f"sales_report_{timestamp:%Y%m%d_%H%M%S}.html"
    sequence = 1
    while destination.exists():
        destination = config.output_dir / (
            f"sales_report_{timestamp:%Y%m%d_%H%M%S}_{sequence:02d}.html"
        )
        sequence += 1
    destination.write_text(html, encoding="utf-8")
    return destination


def render_html(
    data: dict,
    config: Config = CONFIG,
    generated_at: datetime | None = None,
) -> str:
    """파일을 쓰지 않고 리포트 HTML 문자열을 생성한다."""
    timestamp = generated_at or datetime.now()
    environment = Environment(
        loader=FileSystemLoader(config.template_dir),
        autoescape=select_autoescape(["html"]),
    )
    template = environment.get_template("report.html")
    return template.render(
        title=config.title,
        generated_at=timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        **data,
    )


def run_once(config: Config = CONFIG) -> Path:
    """데이터 로딩부터 HTML 저장까지 한 번 실행한다."""
    if not config.data_path.is_file():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {config.data_path}")
    raw = pd.read_csv(config.data_path)
    clean = prepare(raw)
    destination = render(aggregate(clean, config.top_n), config)
    LOGGER.info("리포트 생성 완료: %s", destination)
    return destination


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    path = run_once()
    print("=" * 68)
    print("종합실습 3 | 분석 자동화 · 리포트 생성")
    print("=" * 68)
    print(f"HTML 리포트 생성 : {path.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
