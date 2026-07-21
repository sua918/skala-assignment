from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


CURRENT_SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = (1, 2)
CANONICAL_FIELDS = (
    "customer_id",
    "gender",
    "senior",
    "tenure_months",
    "monthly_charges",
    "total_charges",
    "contract",
    "payment_method",
    "num_services",
    "churn",
)


class SchemaValidationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _native(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def _mapping(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise SchemaValidationError("invalid_structure", f"{name} 객체가 필요합니다.")
    return value


@dataclass(frozen=True)
class SchemaRegistry:
    """지원 버전을 표준 분석 스키마로 변환하는 호환성 레지스트리."""

    current_version: int = CURRENT_SCHEMA_VERSION
    supported_versions: tuple[int, ...] = SUPPORTED_SCHEMA_VERSIONS

    def normalize(self, event: dict) -> dict:
        if not isinstance(event, dict):
            raise SchemaValidationError("invalid_event", "이벤트는 객체여야 합니다.")
        event_id = str(event.get("event_id", "")).strip()
        if not event_id:
            raise SchemaValidationError("missing_event_id", "event_id가 없습니다.")
        version = event.get("schema_version")
        if version not in self.supported_versions:
            raise SchemaValidationError(
                "unsupported_schema",
                f"지원하지 않는 스키마 버전입니다: {version}",
            )
        payload = _mapping(event.get("payload"), "payload")
        if version == 1:
            canonical = {field: payload.get(field) for field in CANONICAL_FIELDS}
            canonical["period"] = payload.get("period")
        else:
            demographics = _mapping(payload.get("demographics"), "demographics")
            subscription = _mapping(payload.get("subscription"), "subscription")
            billing = _mapping(payload.get("billing"), "billing")
            label = _mapping(payload.get("label"), "label")
            canonical = {
                "customer_id": payload.get("customerId"),
                "gender": demographics.get("gender"),
                "senior": demographics.get("isSenior"),
                "tenure_months": subscription.get("tenureMonths"),
                "monthly_charges": billing.get("monthlyCharges"),
                "total_charges": billing.get("totalCharges"),
                "contract": subscription.get("contract"),
                "payment_method": billing.get("paymentMethod"),
                "num_services": subscription.get("serviceCount"),
                "churn": label.get("churn"),
                "period": payload.get("period"),
            }

        missing = [
            field
            for field in CANONICAL_FIELDS
            if field != "total_charges" and canonical.get(field) is None
        ]
        if missing:
            raise SchemaValidationError(
                "missing_required_field",
                f"필수 필드가 없습니다: {', '.join(missing)}",
            )
        if canonical["churn"] not in (0, 1):
            raise SchemaValidationError(
                "invalid_churn", "churn은 0 또는 1이어야 합니다."
            )
        canonical["event_id"] = event_id
        canonical["source_schema_version"] = version
        return canonical


def _v1_payload(row: dict) -> dict:
    return {field: _native(row.get(field)) for field in CANONICAL_FIELDS} | {
        "period": _native(row.get("period"))
    }


def _v2_payload(row: dict) -> dict:
    return {
        "customerId": _native(row.get("customer_id")),
        "period": _native(row.get("period")),
        "demographics": {
            "gender": _native(row.get("gender")),
            "isSenior": _native(row.get("senior")),
        },
        "subscription": {
            "tenureMonths": _native(row.get("tenure_months")),
            "contract": _native(row.get("contract")),
            "serviceCount": _native(row.get("num_services")),
        },
        "billing": {
            "monthlyCharges": _native(row.get("monthly_charges")),
            "totalCharges": _native(row.get("total_charges")),
            "paymentMethod": _native(row.get("payment_method")),
        },
        "label": {"churn": _native(row.get("churn"))},
    }


def dataframe_to_events(
    frame: pd.DataFrame,
    *,
    mixed_versions: bool,
    inject_failures: bool = False,
    include_duplicate: bool = False,
) -> list[dict]:
    events: list[dict] = []
    for index, row in enumerate(frame.to_dict("records")):
        version = 2 if mixed_versions and index % 2 else 1
        customer_id = str(row.get("customer_id", index))
        period = str(row.get("period", "unknown"))
        events.append(
            {
                "event_id": f"{period}:{customer_id}",
                "schema_version": version,
                "payload": _v2_payload(row) if version == 2 else _v1_payload(row),
            }
        )

    if inject_failures and len(events) >= 4:
        events[0]["schema_version"] = 99
        billing = events[1]["payload"]["billing"]
        events[1]["payload"]["monthly_charges"] = billing.pop("monthlyCharges")
        events[2]["payload"]["customerId"] = events[2]["payload"].pop("customer_id")
        events[3]["payload"].pop("customerId", None)
    if include_duplicate and len(events) >= 5:
        events.append(deepcopy(events[4]))
    return events


class DeadLetterQueue:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def add(self, event: dict, error: SchemaValidationError) -> None:
        self.records.append(
            {
                "dlq_id": f"DLQ-{len(self.records) + 1:05d}",
                "event_id": event.get("event_id"),
                "schema_version": event.get("schema_version"),
                "reason_code": error.code,
                "error_message": str(error),
                "status": "pending",
                "retry_count": 0,
                "event": deepcopy(event),
                "history": [{"status": "pending", "reason_code": error.code}],
            }
        )

    def replay(self, processor: EventProcessor) -> dict:
        recovered = 0
        unresolved = 0
        for record in self.records:
            if record["status"] != "pending":
                continue
            record["retry_count"] += 1
            candidate = repair_event(record["event"])
            try:
                accepted = processor.accept(candidate)
            except SchemaValidationError as error:
                record["status"] = "failed"
                record["reason_code"] = error.code
                record["error_message"] = str(error)
                record["history"].append(
                    {"status": "failed", "reason_code": error.code}
                )
                unresolved += 1
            else:
                record["status"] = "recovered" if accepted else "duplicate"
                record["history"].append({"status": record["status"]})
                recovered += int(accepted)
        return {"recovered": recovered, "unresolved": unresolved}


class EventProcessor:
    def __init__(self, registry: SchemaRegistry, dlq: DeadLetterQueue):
        self.registry = registry
        self.dlq = dlq
        self.accepted: list[dict] = []
        self.accepted_ids: set[str] = set()
        self.received = 0
        self.duplicates = 0

    def accept(self, event: dict) -> bool:
        event_id = str(event.get("event_id", ""))
        if event_id and event_id in self.accepted_ids:
            self.duplicates += 1
            return False
        normalized = self.registry.normalize(event)
        self.accepted.append(normalized)
        self.accepted_ids.add(normalized["event_id"])
        return True

    def process(self, events: list[dict]) -> None:
        for event in events:
            self.received += 1
            try:
                self.accept(event)
            except SchemaValidationError as error:
                self.dlq.add(event, error)


def repair_event(event: dict) -> dict:
    """안전하게 추론 가능한 구버전 별칭만 보정한다."""

    repaired = deepcopy(event)
    payload = repaired.get("payload")
    if not isinstance(payload, dict):
        return repaired
    if repaired.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS:
        if any(field in payload for field in CANONICAL_FIELDS):
            repaired["schema_version"] = 1
    if repaired.get("schema_version") == 1 and "customer_id" not in payload:
        if "customerId" in payload:
            payload["customer_id"] = payload.pop("customerId")
    if repaired.get("schema_version") == 2:
        billing = payload.get("billing")
        if isinstance(billing, dict) and "monthlyCharges" not in billing:
            if "monthly_charges" in payload:
                billing["monthlyCharges"] = payload.pop("monthly_charges")
        if "customerId" not in payload and "customer_id" in payload:
            payload["customerId"] = payload.pop("customer_id")
    return repaired


def _version_counts(records: list[dict]) -> dict[str, int]:
    counts = Counter(str(record["source_schema_version"]) for record in records)
    return dict(sorted(counts.items()))


def run_ingestion(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    *,
    inject_demo_failures: bool = False,
    include_demo_duplicate: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict], dict]:
    registry = SchemaRegistry()

    reference_dlq = DeadLetterQueue()
    reference_processor = EventProcessor(registry, reference_dlq)
    reference_processor.process(dataframe_to_events(reference, mixed_versions=False))

    current_dlq = DeadLetterQueue()
    current_processor = EventProcessor(registry, current_dlq)
    current_events = dataframe_to_events(
        current,
        mixed_versions=True,
        inject_failures=inject_demo_failures,
        include_duplicate=include_demo_duplicate,
    )
    current_processor.process(current_events)
    accepted_initial = len(current_processor.accepted)
    replay = current_dlq.replay(current_processor)

    summary = {
        "compatibility": {
            "current_schema_version": registry.current_version,
            "supported_versions": list(registry.supported_versions),
            "mode": "backward-compatible",
        },
        "demonstration": {
            "failures_injected": inject_demo_failures,
            "duplicate_injected": include_demo_duplicate,
        },
        "reference": {
            "received": reference_processor.received,
            "accepted": len(reference_processor.accepted),
            "dlq": len(reference_dlq.records),
            "duplicates": reference_processor.duplicates,
            "accepted_schema_versions": _version_counts(reference_processor.accepted),
        },
        "current": {
            "received": current_processor.received,
            "accepted_initial": accepted_initial,
            "dlq_initial": len(current_dlq.records),
            "recovered": replay["recovered"],
            "unresolved": replay["unresolved"],
            "duplicates": current_processor.duplicates,
            "accepted_total": len(current_processor.accepted),
            "accepted_schema_versions": _version_counts(current_processor.accepted),
        },
    }
    return (
        pd.DataFrame(reference_processor.accepted),
        pd.DataFrame(current_processor.accepted),
        current_dlq.records,
        summary,
    )
