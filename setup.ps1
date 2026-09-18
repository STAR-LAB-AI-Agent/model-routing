param([switch]$WithNanobot)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.11 -m venv .venv
    } else {
        & python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11, then run setup again.' }
}
& '.\.venv\Scripts\python.exe' -m ensurepip
if ($LASTEXITCODE -ne 0) { throw 'Unable to initialize pip.' }
& '.\.venv\Scripts\python.exe' -m pip install --require-hashes -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check your network and retry.' }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Test dependency installation failed.' }
if ($WithNanobot) {
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements-nanobot.txt
    if ($LASTEXITCODE -ne 0) { throw 'nanobot installation failed.' }
}
& '.\.venv\Scripts\python.exe' 'skills\ai-model-router\scripts\router.py' doctor
if ($LASTEXITCODE -ne 0) { throw 'Doctor failed.' }
Write-Host 'Ready. Double-click start-demo.bat.'
