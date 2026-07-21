"""=============================================================================
파일명: simulator.py
작성자: 채수아
작성일: 2026-07-20
작성 목적: 장애를 재현하며 ETL 실행 과정과 적응형 동시성 변화를 기록

입력:
    ScenarioConfig와 fixed-3, fixed-10, fixed-30, adaptive 실행 모드

처리 항목:
    지연·일시 오류·영구 장애 주입, 재시도, 동시성 제어,
    Pydantic 검증, CSV 적재, JSONL 이벤트 기록

실행:
    python Advanced/etl_blackbox/main.py
=============================================================================
"""

from __future__ import annotations

import asyncio
import csv
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

try:
    from Advanced.etl_blackbox.models import (
        BlackBoxEvent,
        Product,
        RunMode,
        RunSummary,
        ScenarioConfig,
    )
except ModuleNotFoundError:
    from models import BlackBoxEvent, Product, RunMode, RunSummary, ScenarioConfig


class InjectedServiceError(RuntimeError):
    """시나리오가 의도적으로 발생시킨 수집 오류입니다."""


@dataclass(slots=True)
class FetchOutcome:
    """요청 한 건의 최종 결과와 관측 지표를 전달합니다."""

    item_id: int
    payload: dict[str, Any] | None
    error: str | None
    retries: int
    latency_ms: float


class EventRecorder:
    """실행 중 발생한 이벤트에 순번과 상대 시간을 붙여 보관합니다."""

    def __init__(self, run_id: str, scenario: str, mode: RunMode) -> None:
        self.run_id = run_id
        self.scenario = scenario
        self.mode = mode
        self.started = time.perf_counter()
        self.events: list[BlackBoxEvent] = []

    def emit(
        self,
        phase: str,
        event_type: str,
        *,
        item_id: int | None = None,
        attempt: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """현재 시점의 블랙박스 이벤트를 추가합니다."""
        self.events.append(
            BlackBoxEvent(
                sequence=len(self.events) + 1,
                run_id=self.run_id,
                scenario=self.scenario,
                mode=self.mode,
                phase=phase,
                event_type=event_type,
                elapsed_ms=round((time.perf_counter() - self.started) * 1000, 3),
                item_id=item_id,
                attempt=attempt,
                detail=detail or {},
            )
        )

    def save_jsonl(self, path: Path) -> None:
        """모든 이벤트를 시간 순서대로 UTF-8 JSONL 파일에 저장합니다."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as file:
            for event in self.events:
                file.write(event.model_dump_json())
                file.write("\n")


def percentile(values: list[float], ratio: float) -> float:
    """정렬된 관측값에서 nearest-rank 방식 백분위수를 계산합니다."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * ratio) - 1)
    return ordered[index]


def fixed_concurrency(mode: RunMode, config: ScenarioConfig) -> int:
    """실행 모드에 대응하는 최초 동시 요청 수를 반환합니다."""
    if mode == "adaptive":
        return config.initial_concurrency
    return int(mode.split("-")[1])


def deterministic_delay(
    config: ScenarioConfig,
    item_id: int,
    attempt: int,
) -> float:
    """시드와 ID로 매 실행에서 같은 모의 지연 시간을 생성합니다."""
    generator = random.Random(config.seed + item_id * 1009 + attempt * 9173)
    jitter = generator.uniform(-config.jitter_ratio, config.jitter_ratio)
    multiplier = config.slow_multiplier if item_id in config.slow_ids else 1.0
    return config.base_delay_seconds * multiplier * (1 + jitter)


async def collect_one(
    item_id: int,
    current_concurrency: int,
    config: ScenarioConfig,
    recorder: EventRecorder,
) -> FetchOutcome:
    """한 ID를 제한 횟수만큼 재시도하고 성공 또는 최종 실패를 반환합니다."""
    request_started = time.perf_counter()
    last_error = ""

    for attempt in range(1, config.max_attempts + 1):
        recorder.emit(
            "extract",
            "request_started",
            item_id=item_id,
            attempt=attempt,
        )
        delay = deterministic_delay(config, item_id, attempt)

        try:
            await asyncio.wait_for(
                asyncio.sleep(delay),
                timeout=config.timeout_seconds,
            )
            if item_id in config.permanent_failure_ids:
                raise InjectedServiceError("주입된 영구 서버 오류")
            if (
                config.overload_capacity is not None
                and current_concurrency > config.overload_capacity
            ):
                overload_ratio = (
                    config.overload_failure_ratio
                    * (current_concurrency - config.overload_capacity)
                    / current_concurrency
                )
                overload_random = random.Random(
                    config.seed
                    + item_id * 3571
                    + attempt * 101
                    + current_concurrency * 17
                )
                if overload_random.random() < overload_ratio:
                    raise InjectedServiceError("서비스 처리 용량 초과")
            if attempt <= config.transient_failures.get(item_id, 0):
                raise InjectedServiceError("주입된 일시 서버 오류")

            price = -100.0 if item_id in config.invalid_price_ids else 10 + item_id
            payload = {
                "id": item_id,
                "name": f" Product {item_id:03d} ",
                "category": ["Data", "Cloud", "AI"][item_id % 3],
                "price": price,
            }
            latency_ms = (time.perf_counter() - request_started) * 1000
            recorder.emit(
                "extract",
                "request_succeeded",
                item_id=item_id,
                attempt=attempt,
                detail={"latency_ms": round(latency_ms, 3)},
            )
            return FetchOutcome(
                item_id=item_id,
                payload=payload,
                error=None,
                retries=attempt - 1,
                latency_ms=latency_ms,
            )
        except (TimeoutError, InjectedServiceError) as error:
            last_error = str(error) or "요청 타임아웃"
            recorder.emit(
                "extract",
                "request_failed",
                item_id=item_id,
                attempt=attempt,
                detail={"error": last_error},
            )
            if attempt < config.max_attempts:
                wait_seconds = 0.005 * (2 ** (attempt - 1))
                recorder.emit(
                    "extract",
                    "retry_scheduled",
                    item_id=item_id,
                    attempt=attempt,
                    detail={"wait_ms": round(wait_seconds * 1000, 3)},
                )
                await asyncio.sleep(wait_seconds)

    latency_ms = (time.perf_counter() - request_started) * 1000
    recorder.emit(
        "extract",
        "dead_letter",
        item_id=item_id,
        attempt=config.max_attempts,
        detail={"error": last_error, "latency_ms": round(latency_ms, 3)},
    )
    return FetchOutcome(
        item_id=item_id,
        payload=None,
        error=last_error,
        retries=max(config.max_attempts - 1, 0),
        latency_ms=latency_ms,
    )


def next_adaptive_concurrency(
    current: int,
    outcomes: list[FetchOutcome],
    config: ScenarioConfig,
) -> tuple[int, str]:
    """최근 배치의 실패율과 p95 지연을 기준으로 다음 동시성을 결정합니다."""
    failure_rate = sum(outcome.error is not None for outcome in outcomes) / len(
        outcomes
    )
    retry_rate = sum(outcome.retries > 0 for outcome in outcomes) / len(outcomes)
    p95_ms = percentile([outcome.latency_ms for outcome in outcomes], 0.95)

    if failure_rate >= 0.2 or retry_rate >= 0.2 or p95_ms > config.latency_threshold_ms:
        return max(config.min_concurrency, current // 2), "혼잡 감지"
    if failure_rate == 0 and p95_ms < config.latency_threshold_ms * 0.75:
        return min(config.max_concurrency, current + 2), "안정 구간"
    return current, "유지"


async def extract(
    config: ScenarioConfig,
    mode: RunMode,
    recorder: EventRecorder,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[float], int, list[int]]:
    """모든 ID를 배치 단위로 수집하고 동시성 변화를 기록합니다."""
    current = fixed_concurrency(mode, config)
    history = [current]
    collected: list[dict[str, Any]] = []
    dead_letters: list[dict[str, Any]] = []
    latencies: list[float] = []
    retries = 0
    next_id = 1

    while next_id <= config.total_items:
        batch_ids = list(range(next_id, min(config.total_items + 1, next_id + current)))
        recorder.emit(
            "control",
            "batch_started",
            detail={"concurrency": current, "ids": batch_ids},
        )
        outcomes = await asyncio.gather(
            *(collect_one(item_id, current, config, recorder) for item_id in batch_ids)
        )

        for outcome in outcomes:
            latencies.append(outcome.latency_ms)
            retries += outcome.retries
            if outcome.payload is not None:
                collected.append(outcome.payload)
            else:
                dead_letters.append(
                    {"id": outcome.item_id, "stage": "extract", "error": outcome.error}
                )

        if mode == "adaptive":
            changed, reason = next_adaptive_concurrency(current, outcomes, config)
            if changed != current:
                recorder.emit(
                    "control",
                    "concurrency_changed",
                    detail={
                        "before": current,
                        "after": changed,
                        "reason": reason,
                    },
                )
                current = changed
                history.append(current)

        next_id += len(batch_ids)

    return collected, dead_letters, latencies, retries, history


def transform(
    raw: list[dict[str, Any]],
    recorder: EventRecorder,
) -> tuple[list[Product], list[dict[str, Any]]]:
    """원시 상품을 검증하여 유효 데이터와 오류 정보를 분리합니다."""
    valid: list[Product] = []
    invalid: list[dict[str, Any]] = []

    for row in raw:
        try:
            valid.append(Product.model_validate(row))
        except ValidationError as error:
            invalid.append(
                {
                    "id": row.get("id"),
                    "stage": "transform",
                    "errors": error.errors(),
                }
            )
            recorder.emit(
                "transform",
                "validation_failed",
                item_id=row.get("id"),
                detail={"error_count": error.error_count()},
            )

    recorder.emit(
        "transform",
        "transform_completed",
        detail={"valid": len(valid), "invalid": len(invalid)},
    )
    return valid, invalid


def load_csv(products: list[Product], path: Path, recorder: EventRecorder) -> None:
    """검증된 상품을 UTF-8 CSV 파일로 저장합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["id", "name", "category", "price"],
        )
        writer.writeheader()
        writer.writerows(product.model_dump() for product in products)
    recorder.emit("load", "load_completed", detail={"rows": len(products)})


async def run_once(
    config: ScenarioConfig,
    mode: RunMode,
    output_dir: Path,
) -> RunSummary:
    """한 시나리오와 동시성 모드의 E·T·L을 실행하고 요약을 저장합니다."""
    run_id = f"{config.name}_{mode}"
    run_dir = output_dir / "runs" / run_id
    events_path = run_dir / "events.jsonl"
    records_path = run_dir / "valid_records.csv"
    recorder = EventRecorder(run_id, config.name, mode)
    total_started = time.perf_counter()

    extract_started = time.perf_counter()
    raw, dead_letters, latencies, retries, history = await extract(
        config,
        mode,
        recorder,
    )
    extract_seconds = time.perf_counter() - extract_started

    transform_started = time.perf_counter()
    valid, invalid = transform(raw, recorder)
    transform_seconds = time.perf_counter() - transform_started

    load_started = time.perf_counter()
    load_csv(valid, records_path, recorder)
    load_seconds = time.perf_counter() - load_started
    total_seconds = time.perf_counter() - total_started
    recorder.save_jsonl(events_path)

    summary = RunSummary(
        run_id=run_id,
        scenario=config.name,
        scenario_label=config.label,
        mode=mode,
        requested=config.total_items,
        extracted=len(raw),
        extract_failed=len(dead_letters),
        valid=len(valid),
        transform_invalid=len(invalid),
        retries=retries,
        p50_latency_ms=round(percentile(latencies, 0.5), 3),
        p95_latency_ms=round(percentile(latencies, 0.95), 3),
        extract_seconds=round(extract_seconds, 4),
        transform_seconds=round(transform_seconds, 4),
        load_seconds=round(load_seconds, 4),
        total_seconds=round(total_seconds, 4),
        concurrency_history=history,
        event_count=len(recorder.events),
        events_file=str(events_path),
        records_file=str(records_path),
    )
    (run_dir / "summary.json").write_text(
        json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "invalid_records.json").write_text(
        json.dumps(
            [*dead_letters, *invalid], ensure_ascii=False, indent=2, default=str
        ),
        encoding="utf-8",
    )
    return summary


async def run_experiment(
    scenarios: list[ScenarioConfig],
    output_dir: Path,
    modes: tuple[RunMode, ...] = (
        "fixed-3",
        "fixed-10",
        "fixed-30",
        "adaptive",
    ),
) -> list[RunSummary]:
    """모든 시나리오와 동시성 모드를 순서대로 실행합니다."""
    summaries: list[RunSummary] = []
    for scenario in scenarios:
        for mode in modes:
            summaries.append(await run_once(scenario, mode, output_dir))
    return summaries
