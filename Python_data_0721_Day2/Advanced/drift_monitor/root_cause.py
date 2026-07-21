from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CATEGORICAL_FEATURES, MonitorConfig, NUMERIC_FEATURES


def _segment_series(
    reference: pd.Series,
    current: pd.Series,
    column: str,
) -> tuple[pd.Series, pd.Series]:
    if column in CATEGORICAL_FEATURES:
        return (
            reference.astype("string").fillna("Unknown"),
            current.astype("string").fillna("Unknown"),
        )

    combined = pd.concat([reference, current], ignore_index=True).astype(float)
    try:
        _, edges = pd.qcut(combined, q=4, retbins=True, duplicates="drop")
    except ValueError:
        edges = np.array([-np.inf, np.inf])
    edges = np.unique(edges.astype(float))
    if len(edges) < 2:
        edges = np.array([-np.inf, np.inf])
    edges[0], edges[-1] = -np.inf, np.inf
    return (
        pd.cut(reference.astype(float), bins=edges, include_lowest=True).astype(
            "string"
        ),
        pd.cut(current.astype(float), bins=edges, include_lowest=True).astype("string"),
    )


def explain_numeric_shift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    target: str,
    config: MonitorConfig,
    segment_columns: list[str] | None = None,
) -> dict:
    """평균 변화량을 고객 구성 효과와 그룹 내부 변화 효과로 분해한다."""

    if segment_columns is None:
        segment_columns = [
            column
            for column in CATEGORICAL_FEATURES + NUMERIC_FEATURES
            if column != target
        ]

    ref_mean = float(reference[target].mean())
    cur_mean = float(current[target].mean())
    total_delta = cur_mean - ref_mean
    candidates: list[dict] = []

    for segment_column in segment_columns:
        ref_segments, cur_segments = _segment_series(
            reference[segment_column], current[segment_column], segment_column
        )
        ref_temp = pd.DataFrame(
            {"segment": ref_segments, "value": reference[target].to_numpy()}
        )
        cur_temp = pd.DataFrame(
            {"segment": cur_segments, "value": current[target].to_numpy()}
        )
        labels = sorted(
            set(ref_temp["segment"].dropna()) | set(cur_temp["segment"].dropna()),
            key=str,
        )

        rows: list[dict] = []
        for label in labels:
            ref_values = ref_temp.loc[ref_temp["segment"] == label, "value"]
            cur_values = cur_temp.loc[cur_temp["segment"] == label, "value"]
            if (
                len(ref_values) < config.min_group_size
                or len(cur_values) < config.min_group_size
            ):
                continue
            wr, wc = len(ref_values) / len(reference), len(cur_values) / len(current)
            mr, mc = float(ref_values.mean()), float(cur_values.mean())
            within_effect = 0.5 * (wr + wc) * (mc - mr)
            mix_effect = 0.5 * (mr + mc) * (wc - wr)
            centered_within_effect = 0.5 * (wr + wc) * ((mc - mr) - total_delta)
            explanation_score = abs(centered_within_effect) + abs(mix_effect)
            rows.append(
                {
                    "segment_feature": segment_column,
                    "segment": str(label),
                    "reference_count": len(ref_values),
                    "current_count": len(cur_values),
                    "reference_share": wr,
                    "current_share": wc,
                    "share_change_pp": (wc - wr) * 100,
                    "reference_mean": mr,
                    "current_mean": mc,
                    "mean_change": mc - mr,
                    "within_effect": within_effect,
                    "centered_within_effect": centered_within_effect,
                    "mix_effect": mix_effect,
                    "net_effect": within_effect + mix_effect,
                    "explanation_score": explanation_score,
                }
            )

        candidates.extend(rows)

    candidates.sort(key=lambda item: item["explanation_score"], reverse=True)
    denominator = sum(item["explanation_score"] for item in candidates) or 1.0
    for item in candidates:
        item["contribution"] = item["explanation_score"] / denominator
    top = candidates[: config.top_causes]
    return {
        "target": target,
        "reference_mean": ref_mean,
        "current_mean": cur_mean,
        "total_delta": total_delta,
        "direction": "increase"
        if total_delta > 0
        else "decrease"
        if total_delta < 0
        else "stable",
        "causes": top,
        "note": "기여도는 관측된 분포 변화의 분해 결과이며 인과관계를 의미하지 않습니다.",
    }


def build_root_cause_report(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    drift_results: list,
    config: MonitorConfig,
) -> list[dict]:
    targets = [
        item.feature
        for item in drift_results
        if item.kind == "numeric" and item.status in {"danger", "warning"}
    ]
    if "monthly_charges" not in targets:
        targets.insert(0, "monthly_charges")
    return [
        explain_numeric_shift(reference, current, target, config)
        for target in targets[:3]
    ]
