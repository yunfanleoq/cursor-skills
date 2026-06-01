# soft-copyright-application

面向 [Cursor Agent Skills](https://cursor.com/docs) 的**中国软件著作权登记**申报材料整理技能。

从任意代码仓库生成版权中心所需的源程序 PDF、操作手册 PDF、申请表草稿与一致性校验；含 Playwright 实机截图自动化、中文排版禁则、截图/换行校验脚本。

## 功能概览

| 能力 | 说明 |
|------|------|
| 源程序鉴别材料 | 提取代码 → 前 30 + 后 30 页 PDF（≥50 行/页） |
| 文档鉴别材料 | Markdown + 实机截图 → 操作手册 PDF（禁则换行、图下说明） |
| 操作手册自动化 | Playwright 按场景 YAML 截图并生成说明书草稿 |
| 申请表辅助 | 生成/预览登记申请表字段 JSON 与 HTML 表单 |
| 校验 | 截图引用齐全性、MD 结构、换行风险 |

## 安装（Cursor Skill）

### 方式 A：克隆后安装到 Cursor 技能目录（推荐）

```powershell
git clone https://github.com/<your-org>/soft-copyright-application-skill.git
cd soft-copyright-application-skill
.\install-gh.ps1          # 可选：安装 gh 并加入 PATH
.\gh-login.ps1            # 登录 GitHub（首次发布需要）
.\install.ps1             # 安装 Cursor Skill
.\publish-github.ps1      # 可选：推送到你的 GitHub 仓库
```

```bash
git clone https://github.com/<your-org>/soft-copyright-application-skill.git
cd soft-copyright-application-skill
chmod +x install.sh
./install.sh
```

安装目标：`~/.cursor/skills/soft-copyright-application/`（Windows：`%USERPROFILE%\.cursor\skills\soft-copyright-application\`）

安装完成后**重启 Cursor**，或在对话中说「按 soft-copyright-application 技能整理软著材料」，Agent 会自动加载 `SKILL.md`。

### 方式 B：手动复制

将整个仓库复制到：

- **Windows**：`C:\Users\<你>\.cursor\skills\soft-copyright-application\`
- **macOS / Linux**：`~/.cursor/skills/soft-copyright-application/`

### Python 依赖

```powershell
py -3.12 -m pip install -r requirements.txt
# 若需 Playwright 自动截图
py -3.12 -m playwright install chromium
```

## 在目标项目中使用

本技能**不包含**具体产品的业务代码；在你的应用仓库中初始化软著工作目录：

```powershell
cd <你的项目根>
py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\init_soft_copyright_scope.py
```

会在项目内创建：

```
soft-copyright/
├── scope.yaml          # 软件名、版本、著作权人等
├── manual/             # 操作说明书.md、screenshots/
├── output/             # 生成的 PDF 等
└── automation/         # 可选：Playwright scenario.yaml
```

### 常用命令

```powershell
# 源程序 PDF
py -3.12 $env:USERPROFILE\.cursor\skills\soft-copyright-application\scripts\extract_source_pages.py --project-root . --scope soft-copyright/scope.yaml
py -3.12 $env:USERPROFILE\.cursor\skills\soft-copyright-application\scripts\generate_source_pdf.py --project-root . --scope soft-copyright/scope.yaml

# 操作手册：校验 + 生成 PDF
py -3.12 $env:USERPROFILE\.cursor\skills\soft-copyright-application\scripts\validate_manual_screenshots.py --project-root .
py -3.12 $env:USERPROFILE\.cursor\skills\soft-copyright-application\scripts\validate_manual_linebreaks.py --project-root .
py -3.12 $env:USERPROFILE\.cursor\skills\soft-copyright-application\scripts\generate_manual_pdf.py --project-root . --scope soft-copyright/scope.yaml
```

完整工作流见仓库内 [SKILL.md](SKILL.md)。

## 仓库结构

```
soft-copyright-application-skill/
├── SKILL.md                 # Cursor Agent 主技能（必读）
├── README.md                # 本文件
├── checklist.md             # 材料清单
├── pdf-format-spec.md       # PDF 版式规范
├── pdf-layout-guide.md      # 操作手册排版与禁则
├── manual-screenshot-workflow.md
├── scope-template.yaml
├── requirements.txt
├── install.ps1 / install.sh
└── scripts/
    ├── extract_source_pages.py
    ├── generate_source_pdf.py
    ├── generate_manual_pdf.py
    ├── validate_manual_screenshots.py
    ├── validate_manual_linebreaks.py
    ├── init_soft_copyright_scope.py
    ├── run_auto_manual.py
    └── auto_manual/         # Playwright 截图
```

## 参考示例

[IP Agent](https://github.com/) 仓库中的 `soft-copyright/` 目录为完整集成示例（含 `build_manual_pdf.ps1`、增量补拍脚本等），可作为 Web 应用类项目的参考。

## 许可证

MIT — 见 [LICENSE](LICENSE)。

## 贡献

欢迎 Issue / PR。推送前请在本地运行校验脚本，并更新 `SKILL.md` / `pdf-layout-guide.md` 中与行为变更相关的说明。
