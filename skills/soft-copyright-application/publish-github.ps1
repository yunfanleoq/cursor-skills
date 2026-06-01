# Publish to GitHub (run: gh auth login)
$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

function Invoke-GhQuiet {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $script:Gh @Args 2>&1 | Out-Null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return $code
}

$Gh = $null
if (Get-Command gh -ErrorAction SilentlyContinue) {
    $Gh = (Get-Command gh).Source
}
if (-not $Gh) {
    $Gh = Get-ChildItem -Path "$env:LOCALAPPDATA\gh-cli", "C:\Program Files\GitHub CLI" -Recurse -Filter gh.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}

if (-not $Gh) {
    Write-Host "[WARN] gh CLI not found. Install: winget install GitHub.cli" -ForegroundColor Yellow
    Write-Host "       Or download from https://cli.github.com/" -ForegroundColor Yellow
    exit 1
}

if ((Invoke-GhQuiet auth status) -ne 0) {
    $GhCmd = if (Get-Command gh -ErrorAction SilentlyContinue) { "gh" } else { $Gh }
    Write-Host "[WARN] Not logged in to GitHub. Run:" -ForegroundColor Yellow
    Write-Host "       .\gh-login.ps1" -ForegroundColor Cyan
    Write-Host "   or: $GhCmd auth login" -ForegroundColor Cyan
    exit 1
}

Set-Location $RepoRoot
$Name = "soft-copyright-application-skill"
$hasOrigin = @(git remote 2>$null) -contains "origin"

if ($hasOrigin) {
    Write-Host "[INFO] Pushing to origin..." -ForegroundColor Cyan
    git push -u origin main
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "[INFO] Creating GitHub repo and pushing..." -ForegroundColor Cyan
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $Gh repo create $Name --public `
        --description "Cursor Agent Skill for China software copyright application materials" `
        --source=. `
        --remote=origin `
        --push 2>&1 | ForEach-Object { Write-Host $_ }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0) { exit $code }
}

Write-Host ""
Write-Host "[OK] Repo URL:" -ForegroundColor Green
$url = & $Gh repo view --json url -q .url 2>$null
if ($url) { Write-Host $url -ForegroundColor Green }
