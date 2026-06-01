# 将本仓库发布到 GitHub

## 1. 在 GitHub 新建空仓库

例如：`soft-copyright-application-skill`（不要勾选 README，本地已有）。

## 2. 首次推送

```powershell
cd i:\cursorProjects\IPAgent\soft-copyright-application-skill
git init
git add .
git commit -m "Initial release: Cursor skill for China software copyright application materials"
git branch -M main
git remote add origin https://github.com/<your-org>/soft-copyright-application-skill.git
git push -u origin main
```

## 3. 其他机器使用

```powershell
git clone https://github.com/<your-org>/soft-copyright-application-skill.git
cd soft-copyright-application-skill
.\install.ps1
```

## 4. 与 IP Agent 项目的关系

- **本仓库**：可复用的 Cursor Skill（脚本 + 规范文档）
- **IP Agent 仓库** `soft-copyright/`：具体产品的 scope、手册、截图、项目内 `build_manual_pdf.ps1` 等

更新 Skill 脚本后：在本目录改完 → 推送 GitHub → 其他机器 `git pull` 后重新运行 `install.ps1`；本地 Cursor 技能目录也会同步更新。

## 5. 发布检查清单

- [ ] `requirements.txt` 可安装
- [ ] `install.ps1` / `install.sh` 在干净环境测试通过
- [ ] README 中 GitHub URL 已替换 `<your-org>`
- [ ] SKILL.md 中 clone URL 已替换
