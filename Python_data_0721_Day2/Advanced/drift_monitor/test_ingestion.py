from __future__ import annotations

import pandas as pd

from drift_monitor.ingestion import (
    DeadLetterQueue,
    EventProcessor,
    SchemaRegistry,
    dataframe_to_events,
    run_ingestion,
)


def _frame(rows: int = 12) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": [f"C-{index}" for index in range(rows)],
            "gender": ["Female", "Male"] * (rows // 2),
            "senior": [0, 1] * (rows // 2),
            "tenure_months": list(range(1, rows + 1)),
            "monthly_charges": [50.0 + index for index in range(rows)],
            "total_charges": [500.0 + index * 10 for index in range(rows)],
            "contract": ["Month-to-month", "One year"] * (rows // 2),
            "payment_method": ["Card", "Transfer"] * (rows // 2),
            "num_services": [2, 3] * (rows // 2),
            "churn": [0, 1] * (rows // 2),
            "period": ["current"] * rows,
        }
    )


def test_v1_and_v2_are_normalized_to_same_schema() -> None:
    frame = _frame(12)
    same_row_twice = pd.concat([frame.iloc[[0]], frame.iloc[[0]]], ignore_index=True)
    v1, v2 = dataframe_to_events(same_row_twice, mixed_versions=True)

    registry = SchemaRegistry()
    first = registry.normalize(v1)
    second = registry.normalize(v2)
    for field in first.keys() - {"source_schema_version"}:
        assert first[field] == second[field]


def test_dlq_replay_recovers_aliases_and_keeps_irreparable_event() -> None:
    frame = _frame(12)
    events = dataframe_to_events(
        frame,
        mixed_versions=True,
        inject_failures=True,
    )
    queue = DeadLetterQueue()
    processor = EventProcessor(SchemaRegistry(), queue)
    processor.process(events)

    replay = queue.replay(processor)

    assert len(queue.records) == 4
    assert replay == {"recovered": 3, "unresolved": 1}
    assert {record["status"] for record in queue.records} == {"recovered", "failed"}


def test_duplicate_event_is_idempotently_ignored() -> None:
    events = dataframe_to_events(
        _frame(12),
        mixed_versions=True,
        include_duplicate=True,
    )
    queue = DeadLetterQueue()
    processor = EventProcessor(SchemaRegistry(), queue)
    processor.process(events)

    assert processor.duplicates == 1
    assert len(processor.accepted) == 12


def test_ingestion_summary_connects_replay_to_accepted_frame() -> None:
    reference = _frame(12).assign(period="reference")
    current = _frame(12)

    ref_result, cur_result, records, summary = run_ingestion(
        reference,
        current,
        inject_demo_failures=True,
        include_demo_duplicate=True,
    )

    assert len(ref_result) == 12
    assert len(cur_result) == summary["current"]["accepted_total"] == 11
    assert summary["current"]["recovered"] == 3
    assert summary["current"]["unresolved"] == 1
    assert len(records) == 4


def test_ingestion_does_not_inject_failures_by_default() -> None:
    reference = _frame(12).assign(period="reference")
    current = _frame(12)

    _, cur_result, records, summary = run_ingestion(reference, current)

    assert len(cur_result) == 12
    assert records == []
    assert summary["current"]["duplicates"] == 0
