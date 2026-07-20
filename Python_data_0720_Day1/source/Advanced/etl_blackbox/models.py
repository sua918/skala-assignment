"""=============================================================================
파일명: models.py
작성자: 채수아
작성일: 2026-07-20
작성 목적: ETL 블랙박스의 시나리오, 이벤트와 실행 결과 스키마를 정의

입력:
    시뮬레이터가 생성하는 설정, 원시 상품, 실행 이벤트와 측정값

검증 항목:
    시나리오 범위, 상품 가격, 이벤트 구조, 실행 결과 필수 필드

실행:
    main.py와 simulator.py에서 모델을 가져와 사용
=============================================================================
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

RunMode = Literal["fixed-3", "fixed-10", "fixed-30", "adaptive"]


class ScenarioConfig(BaseModel):
    """장애 주입 방식과 동시성 제어 범위를 검증합니다."""

    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    total_items: int = Field(ge=1, le=500)
    seed: int = Field(ge=0)
    base_delay_seconds: float = Field(gt=0, le=2)
    jitter_ratio: float = Field(ge=0, le=1)
    slow_ids: set[int] = Field(default_factory=set)
    slow_multiplier: float = Field(default=1.0, ge=1, le=20)
    transient_failures: dict[int, int] = Field(default_factory=dict)
    permanent_failure_ids: set[int] = Field(default_factory=set)
    overload_capacity: int | None = Field(default=None, ge=1, le=100)
    overload_failure_ratio: float = Field(default=0.0, ge=0, le=1)
    invalid_price_ids: set[int] = Field(default_factory=set)
    timeout_seconds: float = Field(gt=0, le=5)
    max_attempts: int = Field(ge=1, le=6)
    initial_concurrency: int = Field(ge=1, le=100)
    min_concurrency: int = Field(ge=1, le=50)
    max_concurrency: int = Field(ge=1, le=100)
    latency_threshold_ms: float = Field(gt=0)

    @field_validator("transient_failures")
    @classmethod
    def validate_failure_counts(cls, value: dict[int, int]) -> dict[int, int]:
        """일시 실패 횟수가 음수가 아닌지 확인합니다."""
        if any(count < 0 for count in value.values()):
            raise ValueError("일시 실패 횟수는 0 이상이어야 합니다")
        return value


class Product(BaseModel):
    """수집된 상품 한 건의 타입과 가격 규칙을 검증합니다."""

    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    category: str = Field(min_length=2)
    price: float = Field(gt=0)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """상품명의 공백을 제거하고 비어 있지 않은 값만 허용합니다."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("공백만 있는 문자열은 허용되지 않습니다")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        """카테고리의 공백을 제거하고 소문자로 통일합니다."""
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("공백만 있는 문자열은 허용되지 않습니다")
        return normalized


class BlackBoxEvent(BaseModel):
    """요청과 ETL 단계에서 발생한 이벤트 한 건을 표현합니다."""

    sequence: int = Field(ge=1)
    run_id: str
    scenario: str
    mode: RunMode
    phase: Literal["extract", "transform", "load", "control"]
    event_type: str
    elapsed_ms: float = Field(ge=0)
    item_id: int | None = None
    attempt: int | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class RunSummary(BaseModel):
    """한 시나리오와 실행 모드의 최종 측정 결과를 보관합니다."""

    run_id: str
    scenario: str
    scenario_label: str
    mode: RunMode
    requested: int
    extracted: int
    extract_failed: int
    valid: int
    transform_invalid: int
    retries: int
    p50_latency_ms: float
    p95_latency_ms: float
    extract_seconds: float
    transform_seconds: float
    load_seconds: float
    total_seconds: float
    concurrency_history: list[int]
    event_count: int
    events_file: str
    records_file: str
