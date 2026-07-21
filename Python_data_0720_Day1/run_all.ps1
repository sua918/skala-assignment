$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"

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

Write-Host "`n[1/8] Streaming web-log aggregation"
Invoke-Python @("practice1\solution.py")

Write-Host "`n[2/8] Memory usage comparison"
Invoke-Python @("practice1\memory_comparison.py")

Write-Host "`n[3/8] Pydantic schema validation"
Invoke-Python @("practice2\solution.py")

Write-Host "`n[4/8] Async data collection"
Invoke-Python @("practice3\solution.py")

Write-Host "`n[5/8] Async ETL pipeline"
Invoke-Python @("Total1\pipeline.py")

Write-Host "`n[6/8] Async ETL tests"
Invoke-Python @("-m", "pytest", "Total1\test_pipeline.py", "-q", "-p", "no:cacheprovider", "--basetemp", $testTemp)

Write-Host "`n[7/8] ETL black-box experiment"
Invoke-Python @("Advanced\etl_blackbox\main.py")

Write-Host "`n[8/8] ETL black-box tests"
Invoke-Python @("-m", "pytest", "Advanced\etl_blackbox\test_blackbox.py", "-q", "-p", "no:cacheprovider", "--basetemp", $testTemp)

Write-Host "`nAll tasks and tests completed."
