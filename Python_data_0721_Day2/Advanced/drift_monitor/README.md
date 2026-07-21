# 스키마 호환·DLQ 재처리·드리프트 원인 추적 모니터

서로 다른 버전의 고객 이벤트를 표준 분석 스키마로 통합하고, 처리 실패 이벤트를 DLQ에서 복구한 뒤 데이터·모델 드리프트와 변화 원인까지 추적하는 추가과제입니다.

## 주요 기능

- v1 평면 이벤트와 v2 중첩 이벤트의 하위 호환 변환
- 필수 필드·지원 버전 검증과 실패 사유 코드화
- 검증 실패 이벤트 DLQ 격리, 안전한 별칭 보정, 상태 기반 재처리
- `event_id` 기준 중복 수용 차단으로 멱등성 보장
- 재처리 성공 데이터만 표준 DataFrame으로 연결
- 숫자형 컬럼: PSI와 KS 검정으로 분포 변화 감지
- 범주형 컬럼: Jensen–Shannon divergence와 신규 범주 감지
- 정제 전 결측률을 별도 보존하여 정제가 품질 문제를 가리지 않도록 처리
- 결측률이 2%p 이상 증가하면 주의, 4%p 이상 증가하면 위험으로 상태 상향
- 전체 평균 변화를 `고객 구성 효과`와 `그룹 내부 변화 효과`로 분해
- 변화 기여도가 높은 계약·결제·가입기간 그룹 자동 순위화
- 기준 데이터로 학습한 모델의 ROC-AUC·Recall·고위험 고객 비율 비교
- Pandas·Polars·DuckDB 동일 집계 결과 교차 검증
- 외부 인터넷 연결 없이 열리는 반응형 HTML 보고서 생성
- 고정 시드 기반 변화 시나리오 재현

## 실행

`Python_data_0721_Day2` 폴더에서 실행합니다.

```powershell
python Advanced/drift_monitor/main.py
```

다른 시나리오를 선택할 수도 있습니다.

```powershell
python Advanced/drift_monitor/main.py --scenario stable
python Advanced/drift_monitor/main.py --scenario pricing
python Advanced/drift_monitor/main.py --scenario quality
python Advanced/drift_monitor/main.py --scenario mixed_shift
```

## 시나리오

| 이름 | 내용 |
|---|---|
| `stable` | 의도적인 변화가 없는 정상 대조군 |
| `pricing` | 월 단위 계약 고객의 월 요금 변화 |
| `quality` | 결측률·신규 범주·이상치 증가 |
| `mixed_shift` | 고객 구성, 요금, 가입기간, 결측률의 복합 변화 |

기본값은 `mixed_shift`입니다. 원본 파일은 변경하지 않으며, `seed=42`로 기준·신규 샘플을 생성합니다.
기본 실행은 DLQ 재처리 경로를 확인할 수 있도록 복구 가능한 오류 3건, 복구 불가능한 오류 1건, 중복 이벤트 1건을 재현 가능하게 주입합니다. `run_ingestion()` 자체의 기본값은 오류를 주입하지 않으므로 실제 입력을 그대로 처리합니다.

## 산출물

실행 결과는 `Advanced/drift_monitor/output`에 생성됩니다.

- `drift_monitor_report.html`: 인터랙티브 통합 보고서
- `drift_metrics.csv`: 컬럼별 드리프트 점수
- `drift_overview.png`: 드리프트와 모델 지표 정적 요약
- `root_causes.json`: 그룹별 변화 기여도
- `schema_dlq_summary.json`: 버전 호환·수용·복구·중복 처리 요약
- `dlq_records.json`: 실패 사유, 재시도 횟수, 상태 이력이 포함된 DLQ
- `monitor_summary.json`: 전체 분석 결과
- `churn_drift_pipeline.joblib`: 기준 데이터로 학습한 모델
- `reference_sample.csv`, `current_sample.csv`: 재현 가능한 입력 샘플

## 처리 흐름

```text
v1/v2 이벤트 → 스키마 레지스트리 → 표준 컬럼 변환 → 분석 데이터
                         ↓ 실패
                       DLQ → 안전한 보정 → 재처리 ─┘
                                                ↓
                              드리프트 감지 → 원인 추적 → HTML 보고서
```

지원하지 않는 버전, 필수 필드 누락, 잘못된 라벨은 즉시 DLQ로 격리합니다. 재처리기는 버전이나 필드 별칭처럼 안전하게 판단할 수 있는 오류만 보정하며, 고객 식별자처럼 추론할 수 없는 값은 `failed` 상태로 남깁니다. 이미 수용한 `event_id`가 다시 들어오면 결과를 중복 반영하지 않습니다.

## 원인 추적 방식

숫자형 지표의 전체 평균 변화량을 각 고객 그룹에 대해 다음 두 부분으로 분해합니다.

1. `그룹 내부 변화`: 같은 그룹에서 평균값 자체가 달라진 효과
2. `고객 구성 변화`: 전체에서 해당 그룹이 차지하는 비중이 달라진 효과

표본이 작은 그룹은 제외합니다. 전체 평균과 비슷하게 움직인 효과는 제거하고, 평균에서 벗어난 그룹 내부 변화와 구성비 변화의 절댓값을 기준으로 상대 기여도를 계산합니다. 이 기여도는 관측된 변화의 원인 후보를 좁히는 지표이며 인과관계를 의미하지 않습니다.

## 테스트

```powershell
pytest Advanced/drift_monitor/test_drift_monitor.py -v
```

테스트는 두 스키마의 표준화, DLQ 복구·미해결 상태, 멱등성, 수집-분석 연결, 동일 분포, 의도적인 숫자 이동, 신규 범주, 결측치 정제·상태 상향, 시나리오 재현성, 원인 그룹 탐지, 전역 기여도 정규화, 소표본 제외를 검증합니다.
