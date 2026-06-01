---
name: soft-copyright-application
description: >-
  为中国软件著作权登记（中国版权保护中心）整理全套申报材料：申请表、源程序/文档鉴别材料 PDF（页眉页脚、
  页码、50行/页与30行/页）、实机截图用户操作手册、身份证明与一致性校验。从代码库生成合规 PDF 源程序，
  指导运行系统逐步截图编写操作手册。适用于软著、软件著作权、鉴别材料PDF、源代码PDF、操作说明书、用户手册、
  版权中心线上提交等场景。
---

# 软件著作权登记申报材料整理（全局 Skill）

适用于 **任意 Cursor 项目**。本仓库为**独立 GitHub 技能包**，安装后位于 `~/.cursor/skills/soft-copyright-application/`。

## 安装（从 GitHub / 本仓库）

```powershell
git clone https://github.com/yunfanleoq/soft-copyright-application-skill.git
cd soft-copyright-application-skill
.\install.ps1
```

```bash
git clone https://github.com/yunfanleoq/soft-copyright-application-skill.git
cd soft-copyright-application-skill
chmod +x install.sh && ./install.sh
```

### IP Agent 项目内固化（推荐）

[IPAgent](https://github.com/yunfanleoq/IPAgent) 已将本技能作为 **Git 子模块** 固化：

| 路径 | 说明 |
|------|------|
| `.cursor/skills/soft-copyright-application/` | 子模块（本仓库） |
| `.cursor/rules/soft-copyright-application.mdc` | Cursor 规则，软著相关对话自动关联 |
| `soft-copyright/` | scope、手册、截图、输出 |
| `soft-copyright/scripts/install_skill.ps1` | 初始化子模块并同步到全局 skills |

```powershell
git submodule update --init .cursor/skills/soft-copyright-application
powershell -ExecutionPolicy Bypass -File soft-copyright\scripts\install_skill.ps1
```

生成操作手册 PDF：`soft-copyright\scripts\build_manual_pdf.ps1`（含截图与换行校验）。

安装后重启 Cursor。也可手动将整个仓库（除 `.git`）复制到上述 skills 目录。详见 [README.md](README.md)。

---

执行时 **必须先读** [checklist.md](checklist.md)、[pdf-format-spec.md](pdf-format-spec.md)；输出 **必须套用** [output-template.md](output-template.md)。  
PDF 依赖见 [scripts/SETUP-WINDOWS.md](scripts/SETUP-WINDOWS.md) 或 `pip install -r requirements.txt`。

## 法律依据（摘要）

依据《计算机软件著作权登记办法》（国家版权局）第九条至第十二条、第十七条：

| 类别 | 要求 |
|------|------|
| 申请表 | 中国版权保护中心统一表格，中文填写，申请人签章 |
| 鉴别材料 | **程序** + **文档** 各一份；各由前、后连续 **30 页**组成；不足 60 页交全部 |
| 程序页行数 | 除特定情况外，**每页不少于 50 行** |
| 文档页行数 | 除特定情况外，**每页不少于 30 行** |
| 证明文件 | 身份证明；合作/委托/任务书/许可/继受等按情形附加 |
| 纸张 | A4、纵向、**单面**打印；鉴别材料**黑白** |
| **提交格式** | 鉴别材料须 **PDF** 上传；页眉=软件名+版本；**右上角**页码；页脚=著作权人全称 |

> 线上登记以 [中国版权保护中心](https://www.ccopyright.com.cn/) 当期系统提示为准。  
> **PDF 版式细则**（行数、页眉页脚、截图要求）见 [pdf-format-spec.md](pdf-format-spec.md)。

## 项目内可选配置（有则读，无则询问用户）

| 路径（相对项目根） | 用途 |
|-------------------|------|
| `soft-copyright/scope.yaml` | 软件名称、版本、权利人、开发方式、行数策略等 |
| `soft-copyright/manual/` | 操作说明书 Markdown、`screenshots/` 实机截图 |
| `soft-copyright/output/` | 生成物输出目录（含 **PDF**） |

无 `scope.yaml` 时，运行初始化脚本或按 [scope-template.yaml](scope-template.yaml) 向用户确认关键字段。

```powershell
# Windows
py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\init_soft_copyright_scope.py

# 或在项目根
py -3.12 .cursor/skills/soft-copyright-application/scripts/init_soft_copyright_scope.py
```

若 Skill 仅安装在用户目录，使用第一条命令。

## 工作流（必须按序执行）

### Step 0 — 确认申报场景

向用户确认（或从 `scope.yaml` 读取）：

1. **申请人身份**：企业法人 / 事业法人 / 自然人
2. **权利归属**：独立开发 / 合作 / 委托 / 下达任务 / 修改他人软件 / 继受
3. **提交方式**：线上（版权中心系统）/ 线下（地方代办窗口）
4. **软件全称与版本号**（全材料一致，版本号是否与 `V` 前缀以申请表为准）
5. **是否例外交存**（源程序机密遮盖，见 checklist §4）

### Step 1 — 扫描代码库（S1）

1. 读 `README.md`、`package.json` / `pyproject.toml` / `main.py` 等，归纳：
   - 软件功能定位、主要模块、技术栈、运行环境
   - 版本号（无则建议 `1.0` 或 `0.1.0` 与产品一致）
2. 统计源程序规模（用于判断交存「前30+后30」还是「全部」）：

```powershell
cd <项目根>
py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\extract_source_pages.py --scan-only
```

3. 记录：源文件数、有效代码行数、预估页数（50 行/页）

**默认纳入鉴别材料的扩展名**（可在 `scope.yaml` 覆盖）：

`py, js, ts, vue, jsx, tsx, java, kt, go, rs, cs, cpp, c, h, sql`

**默认排除目录**：

`node_modules, .venv, venv, dist, build, __pycache__, .git, coverage, .storage, alembic/versions, data/kb_seed, data/samples, eval/reports, *.min.js, lock 文件`

### Step 2 — 生成源程序鉴别材料（S2）

**2a 提取源码页（txt 草稿）**

```powershell
py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\extract_source_pages.py `
  --project-root "<项目根>" `
  --scope soft-copyright/scope.yaml `
  --output soft-copyright/output
```

产出：`source_concat.txt`、`02-源程序-前30页.txt`、`03-源程序-后30页.txt`、`source_stats.json`、`source_manifest.md`

**2b 生成源程序 PDF（版权中心上传格式）**

```powershell
py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\generate_source_pdf.py `
  --project-root "<项目根>" `
  --scope soft-copyright/scope.yaml `
  --output soft-copyright/output
```

产出：**`{软件全称}{版本}-源程序.pdf`**（默认 60 页：前 30+后 30 合并连续页码）

PDF 必须符合 [pdf-format-spec.md](pdf-format-spec.md) §二：

| 要素 | 要求 |
|------|------|
| 页眉左 | 软件全称 + 版本号 +「源程序」 |
| 页眉右 | `第 n 页 共 60 页`（右上角） |
| 页脚中 | 著作权人全称 |
| 正文 | 等宽字体，每页 **≥50 行**有效代码（末页 ≥15 行） |
| 文件 | 无加密、无水印，建议 <50MB |

**注意**：交存代码须体现核心业务逻辑；脱敏密钥与客户数据；开源组件须说明。

### Step 3 — 文档鉴别材料 · 用户操作手册（S3）

**性质**：文档鉴别材料须为 **PDF**；内容来自 **实机运行 + 界面截图**（见 [manual-screenshot-workflow.md](manual-screenshot-workflow.md)）。

**3a 自动化（推荐）— 启动 + Playwright 截图 + 生成说明书**

```powershell
# IP Agent 项目根目录
powershell -ExecutionPolicy Bypass -File .\soft-copyright\scripts\run_auto_manual.ps1 -StartServers -SeedDemo -Pdf
```

或已有服务运行时（省略启动）：

```powershell
powershell -ExecutionPolicy Bypass -File .\soft-copyright\scripts\run_auto_manual.ps1 -SeedDemo -Pdf
```

产出：`manual/screenshots/`、`manual/操作说明书.md`、可选 `output/*-操作手册.pdf`（草稿）。

**生成 PDF 前必须校验**（避免缺图或正文提前换行）：

```powershell
# 1. 截图文件齐全
py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\validate_manual_screenshots.py --project-root "<项目根>"

# 2. 换行风险 + Markdown 结构（同行多段 intro、表格缺列名等）
py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\validate_manual_linebreaks.py --project-root "<项目根>"
```

两项均返回码 `0` 后再生成 PDF。项目内可一键执行：

```powershell
powershell -ExecutionPolicy Bypass -File soft-copyright\scripts\build_manual_pdf.ps1
```

`validate_manual_screenshots.py`：`操作说明书.md` 引用的 PNG 均已存在。  
`validate_manual_linebreaks.py`：模拟 PDF 引擎 NBSP 保护后，扫描仍可能导致 fpdf 提前换行的中英文空格；并检查同一行多个 `**标签**` 段落未拆分等问题。

**WOA 流水线等增量截图**（不覆盖整份 MD 时）：

```powershell
# 字典管理 S18–S18d
py -3.12 soft-copyright/scripts/capture_dict_screenshots.py

# WOA 流水线 S04k–S04p + 陈述书编辑器
py -3.12 soft-copyright/scripts/capture_pipeline_screenshots.py
```

场景配置：`soft-copyright/automation/scenario.yaml`（可增删步骤与 `manual_steps` 章节）。

**操作手册 Markdown 排版注意**（详见 [pdf-layout-guide.md](pdf-layout-guide.md)）

| 问题 | 规范 |
|------|------|
| 正文提前换行 | intro 用 `**标签** 段落` **每段独立一行**；引擎对 OA/Agent/箭头等做 NBSP 保护 |
| 同行多个 intro | 禁止 `**A** …。**B** …` 写一行；须空行分段 |
| 行首孤标点 | 由 `wrap_text_kinsoku` 禁则 + 孤行合并处理 |
| 截图页缺表格 | 标签后补一句说明；引擎在截图前渲染表格 |
| 截图前大段空白 | 换页仅按截图高度判断，步骤可续页 |
| 表格续行只有序号 | 每行「界面阶段」列写完整名称 |
| 小标题缺冒号 | 单独标题行写 `**Agent 执行顺序一览：**` |
| 截图过小 | 图前 intro 过长时 PDF 自动换页再插图，保证与其他页同宽 |
| 截图标注 | **禁止**红框/箭头 overlay |

**3a' 手工截图（备选）**

1. 启动 `scripts/dev.ps1`  
2. 按 `screenshot-manifest.md` 逐项截图至 `manual/screenshots/`  

**3b 编写分步文稿**

- 目录结构：[manual-outline-template.md](manual-outline-template.md)  
- 每功能：`步骤 1…n` + 文字说明 + `![步骤](screenshots/...)`  
- 主稿路径：`soft-copyright/manual/操作说明书.md`  

**3c 排版并导出 PDF**

| 方式 | 说明 |
|------|------|
| **推荐** | Word/WPS：小四、行距 20 磅、插入截图；设置页眉页脚后 **导出 PDF** |
| 草稿 | `generate_manual_pdf.py` 合并 md+图片（**提交前须 Word 复核 ≥30 行/页**） |

文档 PDF 须符合 [pdf-format-spec.md](pdf-format-spec.md) §三：

- 前 **30** + 后 **30** 页（不足 60 页交全部）  
- 除附图页外每页 **≥30 行**  
- 页眉：`{软件全称} {版本} 操作手册`；页脚：著作权人全称  
- 截图内软件名、版本、单位名与申请表 **完全一致**

```powershell
py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\generate_manual_pdf.py `
  --project-root "<项目根>" --scope soft-copyright/scope.yaml
```

### Step 4 — 填写申请表字段草稿（S4）

根据扫描结果填写 [application-form-template.md](application-form-template.md) 各字段，输出到 `soft-copyright/output/申请表字段草稿.md`。

**第 4 步「软件功能与特点」— 生成字段 + 可视化界面**

```powershell
# 生成 JSON / Markdown / 独立 HTML 预览
py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\generate_application_form.py --project-root "<项目根>"

# 启动本地服务并在浏览器打开（推荐）
py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\serve_application_form.py --project-root "<项目根>"
```

字段规范与字数上限见 [application-form-spec.md](application-form-spec.md)。  
项目内可在 `scope.yaml` 的 `form_fields` 节覆盖各字段；源程序量自动取自代码扫描。

产出：
- `soft-copyright/output/application-form-fields.json`
- `soft-copyright/output/04-申请表字段草稿-第4步.md`
- `soft-copyright/output/application-form-viewer.html`（可双击打开，或经 serve 脚本访问）

重点字段：

| 字段 | 来源 |
|------|------|
| 软件全称 | `scope.yaml` → `software.full_name` |
| 简称 | 可选 |
| 版本号 | `scope.yaml` → `software.version` |
| 分类号 | 按功能选 [分类表](reference.md#附录-常用软件分类号) |
| 开发完成日期 | 用户确认，不晚于申请日 |
| 首次发表日期 | 未发表填「未发表」 |
| 开发方式 | 独立/合作/委托/下达任务 |
| 权利范围 | 通常「全部权利」 |
| 技术特点 | 从 README + 架构归纳 50～200 字 |

### Step 5 — 证明文件清单（S5）

按 `scope.yaml` 中 `applicant.type` 与 `ownership.type` 勾选 [checklist.md](checklist.md) §3，列出用户需准备的扫描件：

- 企业：营业执照副本复印件 **加盖公章**
- 自然人：身份证正反面
- 合作/委托/任务书：合同或任务书复印件

### Step 6 — 一致性校验（S6）

生成 [output-template.md](output-template.md) 格式的 **《软著申报材料包》**，并执行校验：

| 检查项 | 规则 |
|--------|------|
| 名称一致 | 申请表、页眉、说明书标题、文件名中的软件全称一致 |
| 版本一致 | 各材料版本号一致；`V` 有无与申请表一致 |
| 格式 | 源程序、文档均为 **PDF**，无加密无水印 |
| 页码 | 右上角连续；源程序 1～60（或全部）；文档自目录/正文起编 |
| 行数 | 程序 ≥50 行/页（末页≥15）；文档 ≥30 行/页 |
| 页数 | 各 ≥60 页则交前后 30；否则交全部 |
| 截图 | 手册为实机界面，含登录页；非设计稿 |
| 截图引用 | `validate_manual_screenshots.py` 校验 MD 引用与磁盘文件一致 |
| 签章 | 除鉴别材料外，证明文件加盖公章或签字 |

### Step 7 — 交付物目录

在 `soft-copyright/output/` 组织：

```text
soft-copyright/
├── manual/
│   ├── 操作说明书.md
│   ├── screenshot-manifest.md
│   ├── steps/                    # 分模块步骤稿
│   └── screenshots/              # 实机截图（用户拍摄）
└── output/
    ├── 00-材料清单与校验报告.md
    ├── 01-申请表字段草稿.md
    ├── {软件名}{版本}-源程序.pdf   ★ 上传用
    ├── {软件名}{版本}-操作手册.pdf  ★ 上传用
    ├── 02-源程序-前30页.txt        # 中间稿
    ├── source_stats.json
    └── source_pdf_meta.json
```

登录 [中国版权保护中心](https://www.ccopyright.com.cn/) 上传 **PDF** 鉴别材料；提交前对照 [pdf-format-spec.md](pdf-format-spec.md) §五自检。

## IP Agent 项目参考（示例 scope）

若当前仓库为 **IP Agent**，可优先使用已提供的 `soft-copyright/scope.yaml`（若存在）。典型表述：

- **软件全称**：知识产权智能体平台（或用户法定名称）
- **核心模块**：WOA 答复流水线、文档解析、知识库 RAG、期限监控、代理人工作台
- **技术栈**：FastAPI + Vue3 + PostgreSQL/SQLite + LLM

## 禁止事项

1. **不得**编造不存在的功能或模块  
2. **不得**将他人专有代码作为自有代码交存  
3. **不得**在材料中保留真实密钥、密码、生产数据库连接串  
4. **不得**擅自承诺登记一定能通过（仅整理材料合规性）

## 相关文件

| 文件 | 说明 |
|------|------|
| [checklist.md](checklist.md) | 分情形材料勾选清单 |
| [application-form-spec.md](application-form-spec.md) | **第 4 步表单字段规范与字数限制** |
| [manual-outline-template.md](manual-outline-template.md) | 操作说明书目录模板 |
| [output-template.md](output-template.md) | 最终交付文档结构 |
| [pdf-format-spec.md](pdf-format-spec.md) | **PDF 版式、页眉页脚、行数、截图要求** |
| [pdf-layout-guide.md](pdf-layout-guide.md) | **操作手册 MD 排版、防提前换行、表格与截图页** |
| [manual-screenshot-workflow.md](manual-screenshot-workflow.md) | 实机截图与手册编写流程 |
| [reference.md](reference.md) | 分类号、例外交存、常见问题 |
| [scope-template.yaml](scope-template.yaml) | 项目配置模板 |
| [scripts/SETUP-WINDOWS.md](scripts/SETUP-WINDOWS.md) | fpdf2 依赖与 PDF 生成命令 |
