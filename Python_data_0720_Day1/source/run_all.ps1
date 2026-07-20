$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$testRoot = Join-Path $PSScriptRoot "tmp"
$testTemp = Join-Path $testRoot "pytest"

if (-not (Test-Path -LiteralPath $python)) {
    throw "가상환경이 없습니다. 먼저 .\setup.ps1을 실행해 주세요."
}

New-Item -ItemType Directory -Force -Path $testRoot | Out-Null

Write-Host "`n[1/8] 대용량 웹 로그 스트리밍 집계"
& $python ex01_streaming_agg\solution.py

Write-Host "`n[2/8] 로그 처리 방식별 메모리 비교"
& $python ex01_streaming_agg\memory_comparison.py

Write-Host "`n[3/8] Pydantic 중첩 스키마 검증"
& $python ex02_pydantic\solution.py

Write-Host "`n[4/8] asyncio 비동기 데이터 수집"
& $python ex03_async_collector\solution.py

Write-Host "`n[5/8] 비동기 ETL 파이프라인"
& $python capstone01_async_etl\pipeline.py

Write-Host "`n[6/8] 비동기 ETL 테스트"
& $python -m pytest capstone01_async_etl\test_pipeline.py -q -p no:cacheprovider --basetemp $testTemp

Write-Host "`n[7/8] ETL 블랙박스 실험"
& $python Advanced\etl_blackbox\main.py

Write-Host "`n[8/8] ETL 블랙박스 테스트"
& $python -m pytest Advanced\etl_blackbox\test_blackbox.py -q -p no:cacheprovider --basetemp $testTemp

Write-Host "`n전체 실행과 테스트가 완료되었습니다."
