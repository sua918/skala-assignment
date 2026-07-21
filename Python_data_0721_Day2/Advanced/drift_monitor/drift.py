from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from .config import CATEGORICAL_FEATURES, MonitorConfig, NUMERIC_FEATURES


EPSILON = 1e-6


@dataclass(frozen=True)
class DriftResult:
    feature: str
    kind: str
    score: float
    metric: str
    status: str
    reference_value: float | str
    current_value: float | str
    change: float
    pvalue: float | None
    detail: dict

    def as_dict(self) -> dict:
        return {
            "feature": self.feature,
            "kind": self.kind,
            "score": self.score,
            "metric": self.metric,
            "status": self.status,
            "reference_value": self.reference_value,
            "current_value": self.current_value,
            "change": self.change,
            "pvalue": self.pvalue,
            "detail": self.detail,
        }


def _status(score: float, warning: float, danger: float) -> str:
    if score >= danger:
        return "danger"
    if score >= warning:
        return "warning"
    return "stable"


def _worse_status(first: str, second: str) -> str:
    priority = {"stable": 0, "warning": 1, "danger": 2}
    return first if priority[first] >= priority[second] else second


def _missing_status(delta_pp: float, config: MonitorConfig) -> str:
    if delta_pp >= config.missing_warning_pp * 2:
        return "danger"
    if delta_pp >= config.missing_warning_pp:
        return "warning"
    return "stable"


def _numeric_bins(reference: pd.Series, bins: int = 10) -> np.ndarray:
    values = reference.dropna().astype(float)
    if values.nunique() <= 1:
        value = float(values.iloc[0]) if len(values) else 0.0
        return np.array([-np.inf, value, np.inf])
    quantiles = np.linspace(0, 1, bins + 1)
    edges = np.unique(values.quantile(quantiles).to_numpy(dtype=float))
    if len(edges) < 3:
        edges = np.array([values.min(), values.median(), values.max()], dtype=float)
    edges[0], edges[-1] = -np.inf, np.inf
    return edges


def population_stability_index(
    reference: pd.Series, current: pd.Series
) -> tuple[float, dict]:
    edges = _numeric_bins(reference)
    ref_bins = pd.cut(reference.astype(float), bins=edges, include_lowest=True)
    cur_bins = pd.cut(current.astype(float), bins=edges, include_lowest=True)
    categories = ref_bins.cat.categories
    ref_share = ref_bins.value_counts(normalize=True, sort=False).reindex(
        categories, fill_value=0
    )
    cur_share = cur_bins.value_counts(normalize=True, sort=False).reindex(
        categories, fill_value=0
    )
    ref_safe = ref_share.to_numpy() + EPSILON
    cur_safe = cur_share.to_numpy() + EPSILON
    values = (cur_safe - ref_safe) * np.log(cur_safe / ref_safe)
    detail = {
        "bins": [str(value) for value in categories],
        "reference_share": ref_share.round(6).tolist(),
        "current_share": cur_share.round(6).tolist(),
        "bin_contribution": values.round(6).tolist(),
    }
    return float(values.sum()), detail


def categorical_js(reference: pd.Series, current: pd.Series) -> tuple[float, dict]:
    ref = reference.astype("string").fillna("Unknown")
    cur = current.astype("string").fillna("Unknown")
    categories = sorted(set(ref.unique()) | set(cur.unique()), key=str)
    ref_share = (
        ref.value_counts(normalize=True).reindex(categories, fill_value=0).astype(float)
    )
    cur_share = (
        cur.value_counts(normalize=True).reindex(categories, fill_value=0).astype(float)
    )
    midpoint = (ref_share + cur_share) / 2
    kl_ref = np.where(
        ref_share > 0,
        ref_share * np.log((ref_share + EPSILON) / (midpoint + EPSILON)),
        0,
    )
    kl_cur = np.where(
        cur_share > 0,
        cur_share * np.log((cur_share + EPSILON) / (midpoint + EPSILON)),
        0,
    )
    js = float(0.5 * (kl_ref.sum() + kl_cur.sum()))
    detail = {
        "categories": [str(value) for value in categories],
        "reference_share": ref_share.round(6).tolist(),
        "current_share": cur_share.round(6).tolist(),
        "new_categories": [
            str(value) for value in categories if value not in set(ref.unique())
        ],
    }
    return js, detail


def detect_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    config: MonitorConfig,
    raw_missing_reference: dict[str, float] | None = None,
    raw_missing_current: dict[str, float] | None = None,
) -> list[DriftResult]:
    results: list[DriftResult] = []

    for feature in NUMERIC_FEATURES:
        score, detail = population_stability_index(reference[feature], current[feature])
        statistic, pvalue = stats.ks_2samp(reference[feature], current[feature])
        ref_mean, cur_mean = (
            float(reference[feature].mean()),
            float(current[feature].mean()),
        )
        detail.update(
            {
                "reference_median": float(reference[feature].median()),
                "current_median": float(current[feature].median()),
                "ks_statistic": float(statistic),
            }
        )
        ref_missing = (raw_missing_reference or {}).get(feature, 0.0)
        cur_missing = (raw_missing_current or {}).get(feature, 0.0)
        missing_delta_pp = (cur_missing - ref_missing) * 100
        detail.update(
            {
                "reference_missing_rate": ref_missing,
                "current_missing_rate": cur_missing,
                "missing_change_pp": missing_delta_pp,
            }
        )
        base_status = _status(score, config.psi_warning, config.psi_danger)
        results.append(
            DriftResult(
                feature=feature,
                kind="numeric",
                score=score,
                metric="PSI",
                status=_worse_status(
                    base_status, _missing_status(missing_delta_pp, config)
                ),
                reference_value=ref_mean,
                current_value=cur_mean,
                change=cur_mean - ref_mean,
                pvalue=float(pvalue),
                detail=detail,
            )
        )

    for feature in CATEGORICAL_FEATURES:
        score, detail = categorical_js(reference[feature], current[feature])
        ref_top = str(reference[feature].astype(str).value_counts().index[0])
        cur_top = str(current[feature].astype(str).value_counts().index[0])
        max_change = max(
            abs(a - b)
            for a, b in zip(
                detail["reference_share"], detail["current_share"], strict=True
            )
        )
        ref_missing = (raw_missing_reference or {}).get(feature, 0.0)
        cur_missing = (raw_missing_current or {}).get(feature, 0.0)
        missing_delta_pp = (cur_missing - ref_missing) * 100
        detail.update(
            {
                "reference_missing_rate": ref_missing,
                "current_missing_rate": cur_missing,
                "missing_change_pp": missing_delta_pp,
            }
        )
        base_status = _status(score, config.js_warning, config.js_danger)
        results.append(
            DriftResult(
                feature=feature,
                kind="categorical",
                score=score,
                metric="JS",
                status=_worse_status(
                    base_status, _missing_status(missing_delta_pp, config)
                ),
                reference_value=ref_top,
                current_value=cur_top,
                change=float(max_change),
                pvalue=None,
                detail=detail,
            )
        )

    priority = {"danger": 0, "warning": 1, "stable": 2}
    return sorted(results, key=lambda item: (priority[item.status], -item.score))
