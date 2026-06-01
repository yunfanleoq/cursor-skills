# Download GitHub CLI (if needed) and add to user PATH
$ErrorActionPreference = "Stop"
$GhDir = Join-Path $env:LOCALAPPDATA "gh-cli"
$GhExe = Join-Path $GhDir "bin\gh.exe"
$Version = "2.67.0"
$ZipUrl = "https://github.com/cli/cli/releases/download/v$Version/gh_${Version}_windows_amd64.zip"

if (-not (Test-Path $GhExe)) {
    Write-Host "[INFO] Downloading GitHub CLI $Version ..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $GhDir | Out-Null
    $zip = Join-Path $env:TEMP "gh_$Version.zip"
    Invoke-WebRequest -Uri $ZipUrl -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $GhDir -Force
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
}

$BinDir = Split-Path $GhExe -Parent
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$BinDir", "User")
    $env:Path = "$env:Path;$BinDir"
    Write-Host "[OK] Added to user PATH: $BinDir" -ForegroundColor Green
    Write-Host "     Restart terminal (or Cursor) then run: gh auth login" -ForegroundColor Yellow
} else {
    $env:Path = "$env:Path;$BinDir"
    Write-Host "[OK] gh already on PATH: $BinDir" -ForegroundColor Green
}

& $GhExe --version
