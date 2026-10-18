param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path .venv/Scripts/python.exe)) {
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed" }
    }
    & ./.venv/Scripts/python.exe -m pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
    npm ci --prefix tools/javascript --ignore-scripts
    if ($LASTEXITCODE -ne 0) { throw "Parser installation failed" }
    npm ci --prefix frontend --ignore-scripts
    if ($LASTEXITCODE -ne 0) { throw "Frontend installation failed" }
    npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
    & ./.venv/Scripts/python.exe -m graphscope doctor
    if ($LASTEXITCODE -ne 0) { throw "Configuration checks failed" }
} finally { Pop-Location }
