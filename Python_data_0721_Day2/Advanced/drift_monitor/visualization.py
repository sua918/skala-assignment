from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import rcParams

from .report import FEATURE_LABELS


STATUS_COLORS = {
    "danger": "#d84a4a",
    "warning": "#e79b24",
    "stable": "#0f9f8f",
}


def create_overview_chart(payload: dict, destination: Path) -> Path:
    """Word 보고서와 정적 미리보기에 사용할 핵심 결과 그림을 만든다."""

    plt.style.use("seaborn-v0_8-whitegrid")
    rcParams["font.family"] = "Malgun Gothic"
    rcParams["axes.unicode_minus"] = False
    figure, axes = plt.subplots(
        1, 2, figsize=(12.5, 5.1), gridspec_kw={"width_ratios": [1.3, 0.9]}
    )
    figure.patch.set_facecolor("#f5f7fa")

    drift = list(reversed(payload["drift"]))
    labels = [FEATURE_LABELS.get(item["feature"], item["feature"]) for item in drift]
    scores = [item["score"] for item in drift]
    colors = [STATUS_COLORS[item["status"]] for item in drift]
    bars = axes[0].barh(labels, scores, color=colors, height=0.62)
    axes[0].bar_label(bars, fmt="%.3f", padding=4, fontsize=8)
    axes[0].set_title(
        "컬럼별 드리프트 점수", loc="left", fontsize=13, fontweight="bold"
    )
    axes[0].set_xlabel("PSI 또는 Jensen-Shannon divergence")
    axes[0].spines[["top", "right", "left"]].set_visible(False)

    model = payload["model"]
    metric_labels = ["평균 위험도", "고위험 비율", "ROC-AUC", "Recall"]
    reference = [
        model["reference"]["average_risk"],
        model["reference"]["high_risk_rate"],
        model["reference"]["roc_auc"],
        model["reference"]["recall"],
    ]
    current = [
        model["current"]["average_risk"],
        model["current"]["high_risk_rate"],
        model["current"]["roc_auc"],
        model["current"]["recall"],
    ]
    positions = list(range(len(metric_labels)))
    width = 0.34
    axes[1].bar(
        [value - width / 2 for value in positions],
        reference,
        width,
        label="기준",
        color="#b6c2d2",
    )
    axes[1].bar(
        [value + width / 2 for value in positions],
        current,
        width,
        label="신규",
        color="#246bfd",
    )
    axes[1].set_xticks(positions, metric_labels, rotation=18)
    axes[1].set_ylim(0, 1)
    axes[1].set_title("모델 예측·성능 변화", loc="left", fontsize=13, fontweight="bold")
    axes[1].legend(frameon=False, ncols=2, loc="upper right")
    axes[1].spines[["top", "right", "left"]].set_visible(False)

    figure.suptitle(
        payload["scenario"]["title"],
        x=0.065,
        y=1.01,
        ha="left",
        fontsize=16,
        fontweight="bold",
        color="#172033",
    )
    figure.tight_layout()
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        destination, dpi=190, bbox_inches="tight", facecolor=figure.get_facecolor()
    )
    plt.close(figure)
    return destination
