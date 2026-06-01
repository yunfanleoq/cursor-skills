# Publish cursor-skills monorepo to GitHub
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
    Write-Host "[WARN] gh CLI not found. Install: winget install GitHub.cli" -ForegroundColor Yellow
    exit 1
}

if ((Invoke-GhQuiet auth status) -ne 0) {
    Write-Host "[WARN] Not logged in. Run: gh auth login" -ForegroundColor Yellow
    exit 1
}

Set-Location $RepoRoot
$Name = "cursor-skills"
$hasOrigin = @(git remote 2>$null) -contains "origin"

if ($hasOrigin) {
    Write-Host "[INFO] Pushing to origin..." -ForegroundColor Cyan
    git push -u origin main
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "[INFO] Creating GitHub repo and pushing..." -ForegroundColor Cyan
    & $Gh repo create $Name --public `
        --description "Cursor Agent Skills monorepo: Jeecg security scan, E2E doc capture, soft copyright, WeChat publish, frontend review" `
        --source=. `
        --remote=origin `
        --push
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host ""
Write-Host "[OK] Repo URL:" -ForegroundColor Green
$url = & $Gh repo view --json url -q .url 2>$null
if ($url) { Write-Host $url -ForegroundColor Green }
