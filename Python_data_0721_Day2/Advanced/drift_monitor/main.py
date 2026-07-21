from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PACKAGE_DIR = Path(__file__).resolve().parent
DAY2_ROOT = PACKAGE_DIR.parents[1]
ADVANCED_ROOT = PACKAGE_DIR.parent
if str(ADVANCED_ROOT) not in sys.path:
    sys.path.insert(0, str(ADVANCED_ROOT))

from drift_monitor.benchmark import compare_engines  # noqa: E402
from drift_monitor.cleaning import clean_frame, raw_missing_rates  # noqa: E402
from drift_monitor.config import MonitorConfig  # noqa: E402
from drift_monitor.drift import detect_drift  # noqa: E402
from drift_monitor.ingestion import run_ingestion  # noqa: E402
from drift_monitor.model_monitor import monitor_model  # noqa: E402
from drift_monitor.report import render_report  # noqa: E402
from drift_monitor.root_cause import build_root_cause_report  # noqa: E402
from drift_monitor.scenario import SCENARIOS, build_scenario  # noqa: E402
from drift_monitor.visualization import create_overview_chart  # noqa: E402


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_monitor(scenario_name: str = "mixed_shift") -> dict:
    source = DAY2_ROOT / "data" / "telco_churn.csv"
    output = PACKAGE_DIR / "output"
    output.mkdir(parents=True, exist_ok=True)
    config = MonitorConfig(source_path=source, output_dir=output)

    source_frame = pd.read_csv(source)
    scenario_reference, scenario_current, scenario = build_scenario(
        source_frame,
        scenario=scenario_name,
        seed=config.random_seed,
    )
    raw_reference, raw_current, dlq_records, ingestion = run_ingestion(
        scenario_reference,
        scenario_current,
        inject_demo_failures=True,
        include_demo_duplicate=True,
    )
    reference_missing = raw_missing_rates(raw_reference)
    current_missing = raw_missing_rates(raw_current)
    reference, reference_quality = clean_frame(raw_reference)
    current, current_quality = clean_frame(raw_current)

    drift_results = detect_drift(
        reference,
        current,
        config,
        reference_missing,
        current_missing,
    )
    root_causes = build_root_cause_report(reference, current, drift_results, config)
    model_metrics, model_causes = monitor_model(reference, current, config)
    benchmark = compare_engines(current)

    payload = {
        "scenario": {
            "name": scenario.name,
            "title": scenario.title,
            "description": scenario.description,
            "injected_changes": scenario.injected_changes,
        },
        "seed": config.random_seed,
        "ingestion": ingestion,
        "dlq_records": dlq_records,
        "quality": {
            "reference": reference_quality.as_dict(),
            "current": current_quality.as_dict(),
        },
        "drift": [item.as_dict() for item in drift_results],
        "root_causes": root_causes,
        "model": model_metrics,
        "model_causes": model_causes,
        "benchmark": benchmark,
    }

    pd.DataFrame(
        [
            {
                "feature": item.feature,
                "kind": item.kind,
                "metric": item.metric,
                "score": item.score,
                "status": item.status,
                "reference_value": item.reference_value,
                "current_value": item.current_value,
                "change": item.change,
            }
            for item in drift_results
        ]
    ).to_csv(output / "drift_metrics.csv", index=False, encoding="utf-8-sig")
    _write_json(output / "monitor_summary.json", payload)
    _write_json(output / "root_causes.json", root_causes)
    _write_json(output / "dlq_records.json", dlq_records)
    _write_json(output / "schema_dlq_summary.json", ingestion)
    raw_reference.to_csv(
        output / "reference_sample.csv", index=False, encoding="utf-8-sig"
    )
    raw_current.to_csv(output / "current_sample.csv", index=False, encoding="utf-8-sig")
    report_path = render_report(payload, output / "drift_monitor_report.html")
    create_overview_chart(payload, output / "drift_overview.png")

    danger = sum(item.status == "danger" for item in drift_results)
    warning = sum(item.status == "warning" for item in drift_results)
    print("=" * 72)
    print("Advanced | 스키마·DLQ·드리프트 통합 모니터")
    print("=" * 72)
    print(f"시나리오           : {scenario.title}")
    print(f"기준 / 신규 고객   : {len(reference):,} / {len(current):,}명")
    print(
        "DLQ 최초 / 복구 / 미해결: "
        f"{ingestion['current']['dlq_initial']} / "
        f"{ingestion['current']['recovered']} / "
        f"{ingestion['current']['unresolved']}건"
    )
    print(f"위험 / 주의 컬럼   : {danger} / {warning}개")
    print(
        f"평균 이탈 위험도   : {model_metrics['reference']['average_risk']:.2%} → {model_metrics['current']['average_risk']:.2%}"
    )
    print(
        f"ROC-AUC            : {model_metrics['reference']['roc_auc']:.4f} → {model_metrics['current']['roc_auc']:.4f}"
    )
    print(f"엔진 결과 검증     : {'PASS' if benchmark['results_match'] else 'FAIL'}")
    print(f"HTML 리포트        : {report_path.relative_to(DAY2_ROOT)}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="스키마·DLQ·드리프트 통합 모니터")
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        default="mixed_shift",
        help="재현할 신규 데이터 변화 시나리오",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_monitor(args.scenario)


if __name__ == "__main__":
    main()
