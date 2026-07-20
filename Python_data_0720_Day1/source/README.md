# SKALA Python 데이터 분석 실습

Python 데이터 처리 기초 실습, 비동기 ETL 종합실습, ETL 안정성 추가과제를 한 저장소에서 실행할 수 있도록 구성했습니다.

## 실행 환경

- Python 3.11 이상
- Windows PowerShell 기준
- 모든 명령은 `source` 폴더에서 실행

## 처음 실행

압축을 해제한 뒤 PowerShell에서 `source` 폴더로 이동합니다.

```powershell
cd .\source
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

설치가 끝나면 전체 실습과 테스트를 한 번에 실행할 수 있습니다.

```powershell
.\run_all.ps1
```

## 구성

```text
Python_data_0720_Day1/
├─ Python_데이터분석_실습결과보고서_채수아.pdf
└─ source/
   ├─ data/
   │  ├─ web_logs.csv
   │  ├─ api_response.json
   │  └─ generate_data.py
   ├─ ex01_streaming_agg/
   ├─ ex02_pydantic/
   ├─ ex03_async_collector/
   ├─ capstone01_async_etl/
   ├─ Advanced/
   │  └─ etl_blackbox/
   ├─ requirements.txt
   ├─ setup.ps1
   └─ run_all.ps1
```

실행 결과는 각 실습 폴더의 `output` 디렉터리에 생성됩니다.

## 주요 실행 명령

```powershell
.\.venv\Scripts\python.exe ex01_streaming_agg\solution.py
.\.venv\Scripts\python.exe ex02_pydantic\solution.py
.\.venv\Scripts\python.exe ex03_async_collector\solution.py
.\.venv\Scripts\python.exe capstone01_async_etl\pipeline.py
.\.venv\Scripts\python.exe Advanced\etl_blackbox\main.py
```

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest capstone01_async_etl\test_pipeline.py -v
.\.venv\Scripts\python.exe -m pytest Advanced\etl_blackbox\test_blackbox.py -v
```
