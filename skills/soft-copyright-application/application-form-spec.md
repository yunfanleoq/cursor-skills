# 版权中心在线表单 — 第 4 步「软件功能与特点」字段规范

> 对应中国版权保护中心登记系统 **软件功能与特点** 步骤。各字段字数上限以系统当期提示为准；下表按常见 **50 字短字段** 与 **长文本** 区分。

## 短文本字段（通常 ≤50 字）

| 字段 ID | 系统标签 | 建议填写 | 上限 |
|---------|----------|----------|------|
| `hardware_dev` | 开发的硬件环境 | x86_64 PC，双核及以上，内存 8GB，硬盘 50GB | 50 |
| `hardware_run` | 运行的硬件环境 | 服务器 x86_64 4 核 8GB 以上；客户端 PC | 50 |
| `os_dev` | 开发该软件的操作系统 | Windows 11 / Linux | 50 |
| `dev_tools` | 软件开发环境 / 开发工具 | Python 3.12、Node.js 20、Cursor IDE | 50 |
| `os_run` | 该软件的运行平台 / 操作系统 | Windows Server / Linux；Chrome/Edge 120+ | 50 |
| `support_env` | 软件运行支撑环境 / 支持软件 | SQLite 或 PostgreSQL；Chrome/Edge 浏览器 | 50 |
| `purpose` | 开发目的 | 为专利代理机构提供审查意见答复智能辅助 | 50 |
| `field` | 面向领域 / 行业 | 知识产权服务、生物医药专利代理 | 50 |

## 其他字段

| 字段 ID | 系统标签 | 说明 | 上限 |
|---------|----------|------|------|
| `languages` | 编程语言 | 勾选按钮 + 补充文本；存为数组与逗号串 | 120（补充） |
| `source_lines` | 源程序量 | 有效代码行数（非空行），单位「行」 | 数字 |
| `main_functions` | 软件的主要功能 | 分条 5～10 条，每条一行 | 500 |
| `technical_features` | 软件的技术特点 | 100～300 字，突出架构与核心能力 | 300 |

## 填写原则

1. **与代码库一致**：硬件/语言/支撑环境须能在 `README`、`pyproject.toml`、`package.json` 中找到依据。
2. **与鉴别材料一致**：软件全称、版本、功能描述须与源程序 PDF、操作手册一致。
3. **短字段先压缩**：超 50 字时删冗余标点、用「/」代替「或」、去掉空格。
4. **源程序量**：运行 `extract_source_pages.py --scan-only`，取 `effective_lines`。
5. **编程语言**：系统有快捷按钮时优先点选 Python、TypeScript、Vue、HTML；其余写入补充框。

## 生成与查看

```powershell
py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\generate_application_form.py --project-root "<项目根>"

# 打开可视化界面（自动启动本地服务并打开浏览器）
py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\serve_application_form.py --project-root "<项目根>"
```

产出：`soft-copyright/output/application-form-fields.json`、独立 HTML 预览、Markdown 草稿。
