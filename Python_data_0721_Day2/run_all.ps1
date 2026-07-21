$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"
$env:MPLCONFIGDIR = Join-Path $PSScriptRoot ".matplotlib"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$testRoot = Join-Path $PSScriptRoot "tmp"
$testTemp = Join-Path $testRoot "pytest"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found. Run .\setup.ps1 first."
}

function Invoke-Python {
    param([string[]]$CommandArgs)

    & $python @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

New-Item -ItemType Directory -Force -Path $testRoot | Out-Null

Write-Host "`n[1/12] Generate sample data"
Invoke-Python @("data\generate_data.py")

Write-Host "`n[2/12] Streaming web-log aggregation"
Invoke-Python @("practice1\solution.py")

Write-Host "`n[3/12] Pydantic schema validation"
Invoke-Python @("practice2\solution.py")

Write-Host "`n[4/12] Async data collection"
Invoke-Python @("practice3\solution.py")

Write-Host "`n[5/12] Pandas data cleaning"
Invoke-Python @("practice4\solution.py")

Write-Host "`n[6/12] Pandas/Polars/DuckDB benchmark"
Invoke-Python @("practice5\solution.py")

Write-Host "`n[7/12] Async ETL pipeline"
Invoke-Python @("Total1\pipeline.py")

Write-Host "`n[8/12] EDA/statistics/ML pipeline"
Invoke-Python @("Total2\analysis.py")

Write-Host "`n[9/12] Automated HTML report"
Invoke-Python @("Total3\run_scheduler.py", "--mode", "once")

Write-Host "`n[10/12] ETL black-box experiment"
Invoke-Python @("Advanced\etl_blackbox\main.py")

Write-Host "`n[11/12] Schema/DLQ/drift monitor"
Invoke-Python @("Advanced\drift_monitor\main.py", "--scenario", "mixed_shift")

Write-Host "`n[12/12] Automated tests"
Invoke-Python @(
    "-m",
    "pytest",
    "practice4\test_solution.py",
    "practice5\test_solution.py",
    "Total1\test_pipeline.py",
    "Total2\test_analysis.py",
    "Total3\test_report.py",
    "Total3\test_scheduler.py",
    "Advanced\etl_blackbox\test_blackbox.py",
    "Advanced\drift_monitor\test_ingestion.py",
    "Advanced\drift_monitor\test_drift_monitor.py",
    "-q",
    "-p",
    "no:cacheprovider",
    "--basetemp",
    $testTemp
)

Write-Host "`nAll tasks and tests completed."
