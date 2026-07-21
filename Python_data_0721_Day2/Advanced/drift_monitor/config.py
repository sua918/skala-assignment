from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MonitorConfig:
    """드리프트 판정과 보고서 생성을 위한 불변 설정."""

    source_path: Path
    output_dir: Path
    random_seed: int = 42
    psi_warning: float = 0.10
    psi_danger: float = 0.25
    js_warning: float = 0.005
    js_danger: float = 0.020
    missing_warning_pp: float = 2.0
    min_group_size: int = 80
    top_causes: int = 6
    high_risk_threshold: float = 0.50


NUMERIC_FEATURES = [
    "tenure_months",
    "monthly_charges",
    "total_charges",
    "num_services",
]

CATEGORICAL_FEATURES = [
    "gender",
    "senior",
    "contract",
    "payment_method",
]

MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
