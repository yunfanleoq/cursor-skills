# Install to Cursor global skills: ~/.cursor/skills/soft-copyright-application/
$ErrorActionPreference = "Stop"
$Src = $PSScriptRoot
$Dest = Join-Path $env:USERPROFILE ".cursor\skills\soft-copyright-application"

Write-Host "Installing soft-copyright-application skill" -ForegroundColor Cyan
Write-Host "  Source: $Src"
Write-Host "  Target: $Dest"

New-Item -ItemType Directory -Force -Path (Split-Path $Dest -Parent) | Out-Null
if (Test-Path $Dest) {
    Remove-Item -Recurse -Force $Dest
}

$exclude = @(".git", ".github")
Get-ChildItem -Path $Src -Force | Where-Object { $exclude -notcontains $_.Name } | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $Dest -Recurse -Force
}

Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
py -3.12 -m pip install -r (Join-Path $Dest "requirements.txt")

Write-Host ""
Write-Host "Done. Restart Cursor or run:" -ForegroundColor Green
Write-Host "  py -3.12 $Dest\scripts\init_soft_copyright_scope.py" -ForegroundColor Gray
