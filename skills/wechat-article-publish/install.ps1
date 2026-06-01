# 安装 Cursor 技能（Windows）
$SkillDir = Join-Path $env:USERPROFILE ".cursor\skills\wechat-article-publish"
$RepoRoot = $PSScriptRoot

New-Item -ItemType Directory -Force -Path $SkillDir | Out-Null
Copy-Item (Join-Path $RepoRoot "SKILL.md") $SkillDir -Force

$CfgDir = Join-Path $env:USERPROFILE ".cursor"
$CfgExample = Join-Path $RepoRoot "config\wechat-publish.example.json"
$CfgTarget = Join-Path $CfgDir "wechat-publish.json"

Write-Host "技能已安装到: $SkillDir" -ForegroundColor Green

if (-not (Test-Path $CfgTarget)) {
    New-Item -ItemType Directory -Force -Path $CfgDir | Out-Null
    Copy-Item $CfgExample $CfgTarget
    Write-Host "已创建凭据模板: $CfgTarget" -ForegroundColor Yellow
    Write-Host "请编辑该文件，填入你的 AppID / AppSecret" -ForegroundColor Yellow
} else {
    Write-Host "凭据文件已存在，跳过: $CfgTarget" -ForegroundColor Gray
}

Write-Host ""
Write-Host "下一步:" -ForegroundColor Cyan
Write-Host "  1. 在 Cursor 中打开仓库目录: $RepoRoot"
Write-Host "  2. 编辑 $CfgTarget"
Write-Host "  3. pip install -r requirements.txt"
Write-Host "  4. 对 Agent 说: 把 xxx.mhtml 整理成公众号文章"
