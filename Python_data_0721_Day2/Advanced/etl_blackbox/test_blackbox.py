"""=============================================================================
파일명: test_blackbox.py
작성자: 채수아
작성일: 2026-07-20
작성 목적: ETL 블랙박스의 장애 재현, 적응형 제어와 산출물을 검증

입력:
    테스트용 소규모 시나리오와 pytest 임시 경로

검증 항목:
    정상 수집, 영구 장애 격리, 동시성 감소, 스키마 검증,
    재현 가능한 결과, JSONL·CSV·HTML 산출물

실행:
    pytest Advanced/etl_blackbox -v
=============================================================================
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

try:
    from Advanced.etl_blackbox.models import ScenarioConfig
    from Advanced.etl_blackbox.report import render_report
    from Advanced.etl_blackbox.simulator import run_once
except ModuleNotFoundError:
    from models import ScenarioConfig
    from report import render_report
    from simulator import run_once


def make_config(**updates) -> ScenarioConfig:
    """각 테스트가 필요한 값만 덮어쓸 수 있는 기본 설정을 만듭니다."""
    values = {
        "name": "test",
        "label": "테스트",
        "total_items": 12,
        "seed": 42,
        "base_delay_seconds": 0.001,
        "jitter_ratio": 0,
        "timeout_seconds": 0.05,
        "max_attempts": 2,
        "initial_concurrency": 6,
        "min_concurrency": 2,
        "max_concurrency": 10,
        "latency_threshold_ms": 40,
    }
    values.update(updates)
    return ScenarioConfig(**values)


def test_normal_scenario_collects_every_item(tmp_path: Path) -> None:
    """정상 시나리오에서 모든 요청이 수집되는지 확인합니다."""
    summary = asyncio.run(run_once(make_config(), "fixed-3", tmp_path))

    assert summary.requested == 12
    assert summary.extracted == 12
    assert summary.extract_failed == 0


def test_permanent_failures_move_to_dead_letter(tmp_path: Path) -> None:
    """영구 장애 ID가 최종 실패로 격리되는지 확인합니다."""
    summary = asyncio.run(
        run_once(
            make_config(permanent_failure_ids={2, 4}),
            "fixed-3",
            tmp_path,
        )
    )

    assert summary.extracted == 10
    assert summary.extract_failed == 2
    invalid = json.loads(
        (tmp_path / "runs" / summary.run_id / "invalid_records.json").read_text(
            encoding="utf-8"
        )
    )
    assert {item["id"] for item in invalid} == {2, 4}


def test_adaptive_mode_reduces_concurrency_during_outage(tmp_path: Path) -> None:
    """장애율이 높을 때 적응형 동시성이 감소하는지 확인합니다."""
    config = make_config(
        overload_capacity=3,
        overload_failure_ratio=0.9,
        initial_concurrency=6,
    )
    adaptive = asyncio.run(
        run_once(
            config,
            "adaptive",
            tmp_path / "adaptive",
        )
    )
    fixed = asyncio.run(
        run_once(
            config,
            "fixed-10",
            tmp_path / "fixed",
        )
    )

    assert adaptive.concurrency_history[0] == 6
    assert min(adaptive.concurrency_history) < 6
    assert adaptive.extract_failed <= fixed.extract_failed


def test_invalid_price_is_rejected_by_transform(tmp_path: Path) -> None:
    """음수 가격이 변환 단계에서 유효 데이터와 분리되는지 확인합니다."""
    summary = asyncio.run(
        run_once(
            make_config(invalid_price_ids={3}),
            "fixed-3",
            tmp_path,
        )
    )

    assert summary.extracted == 12
    assert summary.valid == 11
    assert summary.transform_invalid == 1


def test_same_seed_produces_same_outcome_counts(tmp_path: Path) -> None:
    """동일 시드와 장애 설정에서 핵심 건수가 재현되는지 확인합니다."""
    config = make_config(transient_failures={5: 1, 9: 1})
    first = asyncio.run(run_once(config, "fixed-3", tmp_path / "first"))
    second = asyncio.run(run_once(config, "fixed-3", tmp_path / "second"))

    assert (first.extracted, first.extract_failed, first.retries) == (
        second.extracted,
        second.extract_failed,
        second.retries,
    )


def test_jsonl_csv_and_html_outputs_are_created(tmp_path: Path) -> None:
    """블랙박스 이벤트와 데이터 및 HTML 리포트가 생성되는지 확인합니다."""
    summary = asyncio.run(run_once(make_config(), "fixed-3", tmp_path))
    report_path = tmp_path / "report.html"
    render_report([summary], report_path)

    events_path = Path(summary.events_file)
    records_path = Path(summary.records_file)
    assert events_path.is_file()
    assert records_path.is_file()
    assert json.loads(events_path.read_text(encoding="utf-8").splitlines()[0])
    html = report_path.read_text(encoding="utf-8")
    assert "ETL 블랙박스" in html
    assert "적응형 동시성 변화" in html
