from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import (
    CATEGORICAL_FEATURES,
    MODEL_FEATURES,
    NUMERIC_FEATURES,
    MonitorConfig,
)
from .root_cause import explain_numeric_shift


def train_model(reference: pd.DataFrame, path: Path, random_seed: int = 42) -> Pipeline:
    numeric = Pipeline(
        [("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]
    )
    preprocessor = ColumnTransformer(
        [
            ("numeric", numeric, NUMERIC_FEATURES),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                CATEGORICAL_FEATURES,
            ),
        ]
    )
    pipeline = Pipeline(
        [
            ("preprocessor", preprocessor),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=120,
                    min_samples_leaf=4,
                    class_weight="balanced",
                    random_state=random_seed,
                    n_jobs=1,
                ),
            ),
        ]
    )
    pipeline.fit(reference[MODEL_FEATURES], reference["churn"])
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, path)
    return pipeline


def _period_metrics(frame: pd.DataFrame, probabilities, threshold: float) -> dict:
    predictions = (probabilities >= threshold).astype(int)
    labels = frame["churn"].astype(int)
    return {
        "rows": len(frame),
        "churn_rate": float(labels.mean()),
        "average_risk": float(probabilities.mean()),
        "high_risk_rate": float(predictions.mean()),
        "roc_auc": float(roc_auc_score(labels, probabilities)),
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
    }


def monitor_model(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    config: MonitorConfig,
) -> tuple[dict, dict]:
    model_path = config.output_dir / "churn_drift_pipeline.joblib"
    training, reference_evaluation = train_test_split(
        reference,
        test_size=0.30,
        random_state=config.random_seed,
        stratify=reference["churn"],
    )
    model = train_model(training, model_path, config.random_seed)
    ref_probability = model.predict_proba(reference_evaluation[MODEL_FEATURES])[:, 1]
    cur_probability = model.predict_proba(current[MODEL_FEATURES])[:, 1]

    ref_scored = reference_evaluation.copy()
    cur_scored = current.copy()
    ref_scored["risk_score"] = ref_probability
    cur_scored["risk_score"] = cur_probability

    metrics = {
        "threshold": config.high_risk_threshold,
        "reference": _period_metrics(
            reference_evaluation, ref_probability, config.high_risk_threshold
        ),
        "current": _period_metrics(
            current, cur_probability, config.high_risk_threshold
        ),
    }
    metrics["change"] = {
        key: metrics["current"][key] - metrics["reference"][key]
        for key in ["churn_rate", "average_risk", "high_risk_rate", "roc_auc", "recall"]
    }
    causes = explain_numeric_shift(
        ref_scored,
        cur_scored,
        "risk_score",
        config,
        segment_columns=CATEGORICAL_FEATURES + NUMERIC_FEATURES,
    )
    return metrics, causes
