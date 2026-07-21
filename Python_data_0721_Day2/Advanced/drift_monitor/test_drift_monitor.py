from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from drift_monitor.cleaning import clean_frame
from drift_monitor.config import MonitorConfig
from drift_monitor.drift import categorical_js, detect_drift, population_stability_index
from drift_monitor.root_cause import explain_numeric_shift
from drift_monitor.scenario import build_scenario


def _config() -> MonitorConfig:
    return MonitorConfig(
        source_path=Path("input.csv"),
        output_dir=Path("output"),
        min_group_size=20,
    )


def _sample(rows: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    contract = np.where(np.arange(rows) % 2 == 0, "Month-to-month", "Two year")
    return pd.DataFrame(
        {
            "customer_id": [f"C-{index}" for index in range(rows)],
            "gender": np.where(np.arange(rows) % 2 == 0, "Female", "Male"),
            "senior": rng.integers(0, 2, rows),
            "tenure_months": rng.integers(1, 73, rows),
            "monthly_charges": rng.normal(70, 12, rows),
            "total_charges": rng.normal(2500, 600, rows),
            "contract": contract,
            "payment_method": np.where(
                np.arange(rows) % 3 == 0, "Electronic check", "Credit card"
            ),
            "num_services": rng.integers(1, 9, rows),
            "churn": rng.integers(0, 2, rows),
        }
    )


def test_same_numeric_distribution_has_near_zero_psi() -> None:
    values = pd.Series(np.arange(1, 501))
    score, _ = population_stability_index(values, values.copy())
    assert score < 1e-8


def test_shifted_numeric_distribution_is_detected() -> None:
    reference = pd.Series(np.linspace(10, 100, 1000))
    current = reference * 1.7
    score, _ = population_stability_index(reference, current)
    assert score >= 0.25


def test_new_category_is_recorded() -> None:
    reference = pd.Series(["card", "bank"] * 100)
    current = pd.Series(["card", "wallet"] * 100)
    score, detail = categorical_js(reference, current)
    assert score > 0
    assert "wallet" in detail["new_categories"]


def test_cleaning_preserves_raw_missing_count() -> None:
    frame = _sample()
    frame.loc[:39, "total_charges"] = np.nan
    cleaned, snapshot = clean_frame(frame)
    assert cleaned["total_charges"].isna().sum() == 0
    assert snapshot.missing_cells == 40


def test_missing_rate_spike_escalates_status() -> None:
    reference, _ = clean_frame(_sample())
    current = reference.copy()
    results = detect_drift(
        reference,
        current,
        _config(),
        raw_missing_reference={"total_charges": 0.0},
        raw_missing_current={"total_charges": 0.08},
    )
    target = next(item for item in results if item.feature == "total_charges")
    assert target.status == "danger"
    assert target.detail["missing_change_pp"] == 8.0


def test_mixed_scenario_is_reproducible() -> None:
    source = _sample(800)
    first_ref, first_cur, _ = build_scenario(source, "mixed_shift", seed=42)
    second_ref, second_cur, _ = build_scenario(source, "mixed_shift", seed=42)
    pd.testing.assert_frame_equal(first_ref, second_ref)
    pd.testing.assert_frame_equal(first_cur, second_cur)


def test_root_cause_finds_changed_contract_group() -> None:
    reference = _sample(800)
    current = reference.copy()
    focus = current["contract"] == "Month-to-month"
    current.loc[focus, "monthly_charges"] += 45
    explanation = explain_numeric_shift(
        reference,
        current,
        "monthly_charges",
        _config(),
        segment_columns=["contract"],
    )
    assert explanation["causes"][0]["segment_feature"] == "contract"
    assert explanation["causes"][0]["segment"] == "Month-to-month"
    assert explanation["causes"][0]["within_effect"] > 0


def test_tiny_segments_are_excluded() -> None:
    reference = _sample(200)
    current = reference.copy()
    reference.loc[:4, "payment_method"] = "Rare"
    current.loc[:4, "payment_method"] = "Rare"
    explanation = explain_numeric_shift(
        reference,
        current,
        "monthly_charges",
        _config(),
        segment_columns=["payment_method"],
    )
    assert all(item["segment"] != "Rare" for item in explanation["causes"])


def test_root_cause_contributions_use_one_global_denominator() -> None:
    reference = _sample(800)
    current = reference.copy()
    current.loc[current["contract"] == "Month-to-month", "monthly_charges"] += 45

    explanation = explain_numeric_shift(
        reference,
        current,
        "monthly_charges",
        _config(),
    )

    assert 0 < sum(item["contribution"] for item in explanation["causes"]) <= 1
