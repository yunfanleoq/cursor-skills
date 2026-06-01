# 将 jeecg-e2e-doc-capture 安装到用户全局 Cursor Skills 目录
$ErrorActionPreference = "Stop"
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = Join-Path $env:USERPROFILE ".cursor\skills\jeecg-e2e-doc-capture"

if (-not (Test-Path (Join-Path $env:USERPROFILE ".cursor\skills"))) {
    New-Item -ItemType Directory -Path (Join-Path $env:USERPROFILE ".cursor\skills") -Force | Out-Null
}

if (Test-Path $dest) {
    Remove-Item -Recurse -Force $dest
}

Copy-Item -Recurse -Force $src $dest
Write-Host "Installed: $dest"
Write-Host "Files: SKILL.md, checklist.md, reference.md, install-to-user-skills.ps1"
Write-Host "Note: xgsrms scripts remain in the repo; this skill documents the workflow."
