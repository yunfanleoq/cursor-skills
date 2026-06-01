# gh auth login wrapper (works even when gh is not on PATH)
$ErrorActionPreference = "Stop"
$GhExe = Join-Path $env:LOCALAPPDATA "gh-cli\bin\gh.exe"
if (-not (Test-Path $GhExe)) {
    if (Get-Command gh -ErrorAction SilentlyContinue) {
        & gh auth login @args
        exit $LASTEXITCODE
    }
    Write-Host "[WARN] gh not found. Run: .\install-gh.ps1" -ForegroundColor Yellow
    exit 1
}
& $GhExe auth login @args
