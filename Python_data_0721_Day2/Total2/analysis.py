from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import polars as pl
from matplotlib import rcParams
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from project_paths import data_dir, output_dir  # noqa: E402


REQUIRED_COLUMNS = {
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
}


def validate_input(frame: pd.DataFrame) -> None:
    if frame.empty:
        raise ValueError("분석할 고객 데이터가 없습니다.")
    missing_columns = REQUIRED_COLUMNS - set(frame.columns)
    if missing_columns:
        raise ValueError(f"필수 컬럼이 없습니다: {', '.join(sorted(missing_columns))}")
    if frame["customer_id"].duplicated().any():
        raise ValueError("customer_id 중복값이 있습니다.")
    if frame["churn"].isna().any():
        raise ValueError("churn 컬럼에는 결측값이 없어야 합니다.")
    if set(frame["churn"].dropna().unique()) != {0, 1}:
        raise ValueError("churn 컬럼에는 0과 1 두 클래스가 필요합니다.")


def run_analysis() -> dict:
    source = data_dir() / "telco_churn.csv"
    out = output_dir(__file__)

    lazy = pl.scan_csv(source)
    eda = (
        lazy.group_by("churn")
        .agg(
            pl.len().alias("customers"),
            pl.col("monthly_charges").mean().alias("avg_monthly_charges"),
            pl.col("tenure_months").mean().alias("avg_tenure_months"),
            pl.col("total_charges").mean().alias("avg_total_charges"),
        )
        .sort("churn")
        .collect()
    )
    eda.write_csv(out / "eda_summary.csv")

    frame = pd.read_csv(source)
    validate_input(frame)
    fig = px.box(
        frame,
        x="churn",
        y="monthly_charges",
        color="contract",
        title="이탈 여부별 월 요금 분포",
        labels={
            "churn": "이탈 여부",
            "monthly_charges": "월 요금",
            "contract": "계약 유형",
        },
    )
    fig.update_layout(template="plotly_white")
    fig.write_html(out / "churn_eda_report.html", include_plotlyjs=True)

    churned = frame.loc[frame["churn"] == 1, "monthly_charges"]
    stayed = frame.loc[frame["churn"] == 0, "monthly_charges"]
    t_stat, t_pvalue = stats.ttest_ind(
        churned,
        stayed,
        equal_var=False,
        nan_policy="omit",
    )
    contingency = pd.crosstab(frame["contract"], frame["churn"])
    chi2, chi_pvalue, dof, _ = stats.chi2_contingency(contingency)

    target = frame["churn"]
    features = frame.drop(columns=["churn", "customer_id"])
    numeric_columns = [
        "senior",
        "tenure_months",
        "monthly_charges",
        "total_charges",
        "num_services",
    ]
    categorical_columns = ["gender", "contract", "payment_method"]

    numeric_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    preprocessor = ColumnTransformer(
        [
            ("numeric", numeric_pipeline, numeric_columns),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                categorical_columns,
            ),
        ]
    )
    model = Pipeline(
        [
            ("preprocessor", preprocessor),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=300,
                    min_samples_leaf=3,
                    class_weight="balanced",
                    random_state=42,
                    n_jobs=1,
                ),
            ),
        ]
    )

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.2,
        stratify=target,
        random_state=42,
    )
    model.fit(x_train, y_train)
    probabilities = model.predict_proba(x_test)[:, 1]
    predictions = model.predict(x_test)
    auc = roc_auc_score(y_test, probabilities)
    report = classification_report(
        y_test, predictions, output_dict=True, zero_division=0
    )
    matrix = confusion_matrix(y_test, predictions)
    model_path = out / "churn_pipeline.joblib"
    joblib.dump(model, model_path)
    loaded_model = joblib.load(model_path)
    reloaded_predictions = loaded_model.predict(x_test)
    reload_verified = bool((reloaded_predictions == predictions).all())
    if not reload_verified:
        raise RuntimeError("저장 전후 Pipeline 예측 결과가 다릅니다.")

    plt.style.use("seaborn-v0_8-whitegrid")
    rcParams["font.family"] = "Malgun Gothic"
    rcParams["axes.unicode_minus"] = False
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    means = frame.groupby("churn")["monthly_charges"].mean()
    axes[0].bar(["잔류", "이탈"], means.values, color=["#1f77b4", "#ef553b"])
    axes[0].set_title("이탈 여부별 평균 월 요금")
    axes[0].set_ylabel("월 요금")
    contract_rates = frame.groupby("contract")["churn"].mean().sort_values()
    axes[1].barh(contract_rates.index, contract_rates.values * 100, color="#636efa")
    axes[1].set_title("계약 유형별 이탈률")
    axes[1].set_xlabel("이탈률(%)")
    figure.tight_layout()
    figure.savefig(out / "churn_overview.png", dpi=180, bbox_inches="tight")
    plt.close(figure)

    metrics = {
        "rows": len(frame),
        "churn_rate": float(target.mean()),
        "t_test": {"statistic": float(t_stat), "pvalue": float(t_pvalue)},
        "chi_square": {
            "statistic": float(chi2),
            "pvalue": float(chi_pvalue),
            "degrees_of_freedom": int(dof),
        },
        "roc_auc": float(auc),
        "reload_verified": reload_verified,
        "classification_report": report,
        "confusion_matrix": matrix.tolist(),
        "interpretation": "월 요금과 계약 유형은 이탈 여부와 유의한 연관을 보이지만 인과를 의미하지 않는다.",
    }
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metrics


def main() -> None:
    metrics = run_analysis()
    print("=" * 72)
    print("종합실습 2 | EDA + 통계 + ML 파이프라인")
    print("=" * 72)
    print(f"분석 고객 수       : {metrics['rows']:,}명")
    print(f"이탈률             : {metrics['churn_rate']:.2%}")
    print(f"t-검정 p-value     : {metrics['t_test']['pvalue']:.3e}")
    print(f"카이제곱 p-value   : {metrics['chi_square']['pvalue']:.3e}")
    print(f"ROC-AUC            : {metrics['roc_auc']:.4f}")
    churn_report = metrics["classification_report"]["1"]
    print(f"이탈 Precision     : {churn_report['precision']:.4f}")
    print(f"이탈 Recall        : {churn_report['recall']:.4f}")
    print(f"이탈 F1            : {churn_report['f1-score']:.4f}")
    print(f"모델 재로딩 검증   : {'PASS' if metrics['reload_verified'] else 'FAIL'}")
    print(f"해석               : {metrics['interpretation']}")
    print(f"산출물             : {(output_dir(__file__)).relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
