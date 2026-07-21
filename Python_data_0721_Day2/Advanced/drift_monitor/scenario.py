from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


@dataclass(frozen=True)
class ScenarioInfo:
    name: str
    title: str
    description: str
    injected_changes: list[str]


SCENARIOS = {
    "mixed_shift": ScenarioInfo(
        name="mixed_shift",
        title="요금·고객 구성 복합 변화",
        description="계약 구성과 특정 고객군의 요금·가입기간이 동시에 달라진 상황",
        injected_changes=[
            "월 단위·전자수표 고객 비중 증가",
            "해당 고객군 월 요금 35% 상승",
            "해당 고객군 가입기간 단축",
            "TotalCharges 결측 4% 추가",
        ],
    ),
    "pricing": ScenarioInfo(
        name="pricing",
        title="특정 고객군 요금 변화",
        description="고객 구성은 유지하면서 월 단위 계약 고객의 요금만 달라진 상황",
        injected_changes=["월 단위 계약 고객 월 요금 45% 상승"],
    ),
    "quality": ScenarioInfo(
        name="quality",
        title="데이터 품질 저하",
        description="실제 고객 특성보다 수집 데이터의 품질이 달라진 상황",
        injected_changes=[
            "TotalCharges 결측 12% 추가",
            "PaymentMethod 신규 범주 Mobile wallet 유입",
            "일부 고객의 서비스 개수 이상치 추가",
        ],
    ),
    "stable": ScenarioInfo(
        name="stable",
        title="안정 상태",
        description="기준 기간과 신규 기간의 분포가 거의 같은 정상 대조군",
        injected_changes=["의도적인 변화 없음"],
    ),
}


def _split_source(frame: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    reference, current = train_test_split(
        frame,
        test_size=0.5,
        random_state=seed,
        stratify=frame[["contract", "churn"]],
    )
    return reference.reset_index(drop=True), current.reset_index(drop=True)


def _weighted_resample(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    target = (frame["contract"] == "Month-to-month") & (
        frame["payment_method"] == "Electronic check"
    )
    weights = np.where(target, 6.0, 1.0)
    sampled = frame.sample(
        n=len(frame),
        replace=True,
        weights=weights,
        random_state=seed,
    ).copy()
    sampled["customer_id"] = [f"CUR-{index:05d}" for index in range(len(sampled))]
    return sampled.reset_index(drop=True)


def build_scenario(
    source: pd.DataFrame,
    scenario: str = "mixed_shift",
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, ScenarioInfo]:
    """원본 데이터에서 재현 가능한 기준·신규 기간 데이터를 만든다."""

    if scenario not in SCENARIOS:
        choices = ", ".join(sorted(SCENARIOS))
        raise ValueError(f"지원하지 않는 시나리오입니다: {scenario} (선택: {choices})")

    rng = np.random.default_rng(seed)
    reference, current = _split_source(source, seed)

    if scenario == "mixed_shift":
        current = _weighted_resample(current, seed + 1)
        focus = (current["contract"] == "Month-to-month") & (
            current["payment_method"] == "Electronic check"
        )
        current.loc[focus, "monthly_charges"] = (
            current.loc[focus, "monthly_charges"] * 1.35
        ).clip(upper=155)
        current.loc[focus, "tenure_months"] = (
            current.loc[focus, "tenure_months"] * 0.45
        ).round()
        missing_index = rng.choice(
            current.index, size=int(len(current) * 0.04), replace=False
        )
        current.loc[missing_index, "total_charges"] = np.nan

    elif scenario == "pricing":
        focus = current["contract"] == "Month-to-month"
        current.loc[focus, "monthly_charges"] = (
            current.loc[focus, "monthly_charges"] * 1.45
        ).clip(upper=165)

    elif scenario == "quality":
        missing_index = rng.choice(
            current.index, size=int(len(current) * 0.12), replace=False
        )
        current.loc[missing_index, "total_charges"] = np.nan
        wallet_index = rng.choice(
            current.index, size=int(len(current) * 0.08), replace=False
        )
        current.loc[wallet_index, "payment_method"] = "Mobile wallet"
        outlier_index = rng.choice(
            current.index, size=max(10, int(len(current) * 0.015)), replace=False
        )
        current.loc[outlier_index, "num_services"] = 18

    reference["period"] = "reference"
    current["period"] = "current"
    return reference, current, SCENARIOS[scenario]
