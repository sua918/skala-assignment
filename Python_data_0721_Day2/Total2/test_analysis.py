from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

from .analysis import REQUIRED_COLUMNS, validate_input


def valid_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": ["A", "B"],
            "gender": ["Female", "Male"],
            "senior": [0, 1],
            "tenure_months": [12, 24],
            "monthly_charges": [50.0, 80.0],
            "total_charges": [600.0, 1920.0],
            "contract": ["Month-to-month", "One year"],
            "payment_method": ["Card", "Transfer"],
            "num_services": [2, 4],
            "churn": [0, 1],
        }
    )


def test_validate_input_accepts_valid_schema() -> None:
    frame = valid_frame()
    assert set(frame.columns) == REQUIRED_COLUMNS
    validate_input(frame)


def test_validate_input_rejects_duplicate_customer() -> None:
    frame = valid_frame()
    frame.loc[1, "customer_id"] = "A"

    with pytest.raises(ValueError, match="중복"):
        validate_input(frame)


def test_validate_input_rejects_missing_column() -> None:
    with pytest.raises(ValueError, match="필수 컬럼"):
        validate_input(valid_frame().drop(columns="contract"))


def test_validate_input_rejects_missing_target() -> None:
    frame = pd.concat([valid_frame(), valid_frame().iloc[[0]]], ignore_index=True)
    frame.loc[2, "customer_id"] = "C"
    frame.loc[2, "churn"] = None

    with pytest.raises(ValueError, match="결측"):
        validate_input(frame)


@pytest.mark.filterwarnings(
    "ignore:Setting the shape on a NumPy array has been deprecated:DeprecationWarning"
)
def test_saved_pipeline_reproduces_recorded_auc() -> None:
    day_root = Path(__file__).resolve().parents[1]
    frame = pd.read_csv(day_root / "data" / "telco_churn.csv")
    features = frame.drop(columns=["churn", "customer_id"])
    target = frame["churn"]
    _, x_test, _, y_test = train_test_split(
        features,
        target,
        test_size=0.2,
        stratify=target,
        random_state=42,
    )
    output = Path(__file__).with_name("output")
    model = joblib.load(output / "churn_pipeline.joblib")
    recorded = json.loads((output / "metrics.json").read_text(encoding="utf-8"))

    auc = roc_auc_score(y_test, model.predict_proba(x_test)[:, 1])

    assert auc == pytest.approx(recorded["roc_auc"], abs=1e-12)
