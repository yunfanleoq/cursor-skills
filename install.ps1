# Install Cursor global skills from this monorepo to ~/.cursor/skills/
param(
    [string]$Skill = "all"
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$SkillsRoot = Join-Path $RepoRoot "skills"
$DestRoot = Join-Path $env:USERPROFILE ".cursor\skills"

$AllSkills = @(
    "baoyu-slide-deck",
    "frontend-code-review",
    "jeecg-e2e-doc-capture",
    "jeecg-webapp-security-scan",
    "ppt-master",
    "pptx-convert",
    "soft-copyright-application",
    "wechat-article-publish"
)

function Install-OneSkill {
    param([string]$Name)

    $src = Join-Path $SkillsRoot $Name
    $dest = Join-Path $DestRoot $Name

    if (-not (Test-Path $src)) {
        Write-Host "[SKIP] $Name — source not found" -ForegroundColor Yellow
        return
    }

    New-Item -ItemType Directory -Force -Path $DestRoot | Out-Null
    if (Test-Path $dest) {
        Remove-Item -Recurse -Force $dest
    }

    $exclude = @(".git", ".github", "__pycache__")
    Get-ChildItem -Path $src -Force | Where-Object { $exclude -notcontains $_.Name } |
        ForEach-Object { Copy-Item -Path $_.FullName -Destination $dest -Recurse -Force }

    Write-Host "[OK] $Name -> $dest" -ForegroundColor Green

    $req = Join-Path $dest "requirements.txt"
    if (Test-Path $req) {
        Write-Host "     Installing Python deps for $Name..." -ForegroundColor Cyan
        py -3.12 -m pip install -r $req 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "     [WARN] pip install failed — run manually if needed" -ForegroundColor Yellow
        }
    }
}

Write-Host "cursor-skills installer" -ForegroundColor Cyan
Write-Host "  Source: $SkillsRoot"
Write-Host "  Target: $DestRoot"
Write-Host ""

if ($Skill -eq "all") {
    foreach ($s in $AllSkills) { Install-OneSkill -Name $s }
} else {
    if ($AllSkills -notcontains $Skill) {
        Write-Host "[ERROR] Unknown skill: $Skill" -ForegroundColor Red
        Write-Host "Available: $($AllSkills -join ', ')" -ForegroundColor Gray
        exit 1
    }
    Install-OneSkill -Name $Skill
}

Write-Host ""
Write-Host "Done. Restart Cursor to reload skills." -ForegroundColor Green
