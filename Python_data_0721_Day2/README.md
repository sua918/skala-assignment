# SKALA Python 데이터 분석 실습

Day 1 데이터 처리 기초·비동기 ETL 과제와 Day 2 데이터 정제·분석·자동화 과제, 데이터 드리프트 모니터링 추가과제를 한 저장소에서 실행할 수 있도록 구성했습니다.

결과보고서는 [Day 1 PDF](./Python_데이터분석_실습결과보고서_채수아.pdf)와 [Day 2 PDF](./Python_데이터분석_실습결과보고서2_채수아.pdf)에서 확인할 수 있습니다.

## 실행 환경

- Python 3.11 이상
- Windows PowerShell 기준
- 모든 명령은 `Python_data_0721_Day2` 폴더에서 실행

## 처음 실행

저장소를 내려받은 뒤 PowerShell에서 `Python_data_0721_Day2` 폴더로 이동합니다.

```powershell
cd .\Python_data_0721_Day2
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

`setup.ps1`은 가상환경 생성, 패키지 설치, 고정 시드 기반 실습 데이터 생성을 순서대로 수행합니다.

설치가 끝나면 전체 실습과 테스트를 한 번에 실행할 수 있습니다.

```powershell
.\run_all.ps1
```

## 구성

```text
Python_data_0721_Day2/
├─ Python_데이터분석_실습결과보고서_채수아.pdf
├─ Python_데이터분석_실습결과보고서2_채수아.pdf
├─ data/
│  └─ generate_data.py
├─ practice1/
├─ practice2/
├─ practice3/
├─ practice4/
├─ practice5/
├─ Total1/
├─ Total2/
├─ Total3/
├─ Advanced/
│  ├─ etl_blackbox/
│  └─ drift_monitor/
├─ project_paths.py
├─ requirements.txt
├─ setup.ps1
└─ run_all.ps1
```

`practice1`~`practice3`, `Total1`, `Advanced/etl_blackbox`는 Day 1 제출 과제이며, 나머지는 Day 2 제출 과제입니다. 실행 결과는 각 실습 폴더의 `output` 디렉터리에 생성됩니다.

## 주요 실행 명령

### Day 1 과제

```powershell
.\.venv\Scripts\python.exe practice1\solution.py
.\.venv\Scripts\python.exe practice2\solution.py
.\.venv\Scripts\python.exe practice3\solution.py
.\.venv\Scripts\python.exe Total1\pipeline.py
.\.venv\Scripts\python.exe Advanced\etl_blackbox\main.py
```

### Day 2 과제

```powershell
.\.venv\Scripts\python.exe practice4\solution.py
.\.venv\Scripts\python.exe practice5\solution.py
.\.venv\Scripts\python.exe Total2\analysis.py
.\.venv\Scripts\python.exe Total3\run_scheduler.py --mode once
.\.venv\Scripts\python.exe Advanced\drift_monitor\main.py --scenario mixed_shift
```

종합실습 3은 반복 주기 또는 매일 지정한 시각으로 실행할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe Total3\run_scheduler.py --mode interval --interval 60
.\.venv\Scripts\python.exe Total3\run_scheduler.py --mode daily --at 09:00
```

드리프트 모니터는 `stable`, `pricing`, `quality`, `mixed_shift` 시나리오를 지원합니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest practice4\test_solution.py -v
.\.venv\Scripts\python.exe -m pytest practice5\test_solution.py -v
.\.venv\Scripts\python.exe -m pytest Total1\test_pipeline.py -v
.\.venv\Scripts\python.exe -m pytest Total2\test_analysis.py -v
.\.venv\Scripts\python.exe -m pytest Total3\test_report.py Total3\test_scheduler.py -v
.\.venv\Scripts\python.exe -m pytest Advanced\etl_blackbox\test_blackbox.py -v
.\.venv\Scripts\python.exe -m pytest Advanced\drift_monitor\test_ingestion.py Advanced\drift_monitor\test_drift_monitor.py -v
```
