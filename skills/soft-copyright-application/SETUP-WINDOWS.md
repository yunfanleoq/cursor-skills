# Windows 环境 — 软著 Skill 依赖

```powershell
py -3.12 -m pip install fpdf2 pyyaml
```

## 生成源程序 PDF

```powershell
cd <项目根>
py -3.12 $env:USERPROFILE\.cursor\skills\soft-copyright-application\scripts\extract_source_pages.py --scope soft-copyright/scope.yaml --output soft-copyright/output
py -3.12 $env:USERPROFILE\.cursor\skills\soft-copyright-application\scripts\generate_source_pdf.py --project-root . --scope soft-copyright/scope.yaml --output soft-copyright/output
```

产出：`soft-copyright/output/{软件名}{版本}-源程序.pdf`

## 一键自动生成操作手册（Playwright）

```powershell
cd <项目根>
py -3.12 -m pip install playwright pyyaml fpdf2
py -3.12 -m playwright install chromium

# IP Agent
powershell -ExecutionPolicy Bypass -File .\soft-copyright\scripts\run_auto_manual.ps1 -StartServers -SeedDemo -Pdf
```

## 生成操作手册 PDF（需先写 Markdown + 截图）

```powershell
py -3.12 $env:USERPROFILE\.cursor\skills\soft-copyright-application\scripts\generate_manual_pdf.py --project-root . --scope soft-copyright/scope.yaml
```

**正式提交**前建议用 Word/WPS 按 [pdf-format-spec.md](../pdf-format-spec.md) 调整页眉（右上页码）、页脚（著作权人）、每页 ≥30 行后重新导出 PDF。

## 中文字体

脚本自动使用 `C:\Windows\Fonts\msyh.ttc`（微软雅黑）。可在 `scope.yaml` 中设置：

```yaml
pdf:
  cjk_font_path: "C:\\Windows\\Fonts\\msyh.ttc"
```
