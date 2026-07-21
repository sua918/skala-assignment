"""=============================================================================
파일명: main.py
작성자: 채수아
작성일: 2026-07-20
작성 목적: ETL 장애 시나리오와 동시성 전략을 비교하고 리포트를 생성

입력:
    코드에 정의된 정상·지연·장애 폭주 시나리오

처리 항목:
    고정 동시성 3·10·30과 적응형 제어 비교,
    JSONL 이벤트·CSV·요약 JSON·HTML 대시보드 생성

실행:
    python Advanced/etl_blackbox/main.py
=============================================================================
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

try:
    from Advanced.etl_blackbox.models import ScenarioConfig
    from Advanced.etl_blackbox.report import render_report
    from Advanced.etl_blackbox.simulator import run_experiment
except ModuleNotFoundError:
    from models import ScenarioConfig
    from report import render_report
    from simulator import run_experiment

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
logger = logging.getLogger(__name__)


def build_scenarios() -> list[ScenarioConfig]:
    """정상, 지연, 장애 폭주 시나리오를 재현 가능한 설정으로 반환합니다."""
    return [
        ScenarioConfig(
            name="normal",
            label="정상",
            total_items=60,
            seed=20260720,
            base_delay_seconds=0.012,
            jitter_ratio=0.15,
            transient_failures={17: 1, 41: 1},
            invalid_price_ids={13, 29},
            timeout_seconds=0.12,
            max_attempts=3,
            initial_concurrency=10,
            min_concurrency=2,
            max_concurrency=30,
            latency_threshold_ms=80,
        ),
        ScenarioConfig(
            name="latency",
            label="지연",
            total_items=60,
            seed=20260720,
            base_delay_seconds=0.014,
            jitter_ratio=0.2,
            slow_ids={7, 14, 21, 28, 35, 42, 49, 56},
            slow_multiplier=6,
            transient_failures={9: 1, 37: 2},
            invalid_price_ids={13, 29},
            timeout_seconds=0.11,
            max_attempts=3,
            initial_concurrency=10,
            min_concurrency=2,
            max_concurrency=30,
            latency_threshold_ms=75,
        ),
        ScenarioConfig(
            name="outage",
            label="장애 폭주",
            total_items=60,
            seed=20260720,
            base_delay_seconds=0.012,
            jitter_ratio=0.15,
            transient_failures={17: 2, 41: 1},
            permanent_failure_ids={54},
            overload_capacity=6,
            overload_failure_ratio=0.72,
            invalid_price_ids={13, 29},
            timeout_seconds=0.12,
            max_attempts=3,
            initial_concurrency=10,
            min_concurrency=2,
            max_concurrency=30,
            latency_threshold_ms=80,
        ),
    ]


def print_report(summaries: list) -> None:
    """시나리오와 실행 모드별 핵심 결과를 콘솔 표로 출력합니다."""
    print("=" * 88)
    print("Advanced: ETL 블랙박스 · 장애 재현 및 적응형 동시성 실험")
    print("=" * 88)
    print(
        f"{'시나리오':<10}{'모드':<12}{'성공':>8}{'재시도':>9}"
        f"{'격리':>7}{'p95(ms)':>11}{'시간(초)':>11}{'동시성 변화':>18}"
    )
    print("-" * 88)
    for item in summaries:
        values = item.concurrency_history
        if len(values) > 6:
            history = "→".join(
                [
                    *(str(value) for value in values[:3]),
                    "…",
                    *(str(value) for value in values[-2:]),
                ]
            )
        else:
            history = "→".join(str(value) for value in values)
        print(
            f"{item.scenario_label:<10}{item.mode:<12}"
            f"{item.extracted:>5}/{item.requested:<2}{item.retries:>9}"
            f"{item.extract_failed:>7}{item.p95_latency_ms:>11.1f}"
            f"{item.total_seconds:>11.3f}{history:>18}"
        )
    print(f"\nHTML 리포트: {OUTPUT_DIR / 'etl_blackbox_report.html'}")
    print(f"통합 요약 JSON: {OUTPUT_DIR / 'experiment_summary.json'}")


def main() -> int:
    """전체 실험을 실행하고 통합 결과와 HTML 리포트를 생성합니다."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    logger.info("ETL 블랙박스 실험을 시작합니다.")

    try:
        summaries = asyncio.run(run_experiment(build_scenarios(), OUTPUT_DIR))
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "experiment_summary.json").write_text(
            json.dumps(
                [summary.model_dump(mode="json") for summary in summaries],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        render_report(summaries, OUTPUT_DIR / "etl_blackbox_report.html")
    except (OSError, ValueError, RuntimeError) as error:
        logger.error("ETL 블랙박스 실험에 실패했습니다: %s", error)
        return 1

    print_report(summaries)
    logger.info("ETL 블랙박스 실험과 리포트 생성을 완료했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
