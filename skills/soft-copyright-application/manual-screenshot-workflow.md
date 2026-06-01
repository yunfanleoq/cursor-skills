# 用户操作手册 — 实机截图工作流

> 文档鉴别材料须为 **PDF**，内容来自 **真实运行** 的系统界面。

## 自动化（推荐）

使用 Playwright 驱动本机浏览器，配合项目 `scenario.yaml`：

```powershell
powershell -ExecutionPolicy Bypass -File .\soft-copyright\scripts\run_auto_manual.ps1 -StartServers -SeedDemo -Pdf
```

流程：启动前后端 → `seed_demo` → 按场景登录/导航/点击 → 截图 → 生成 `操作说明书.md` → 可选 PDF 草稿。

## 手工（备选）

Agent 负责列清单、写步骤文稿；**截图须用户**在浏览器中实际操作后保存。

---

## 阶段 A：环境准备

1. 启动项目（示例 IP Agent）：

```powershell
cd <项目根>
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

2. 浏览器访问 `http://localhost:5173`（或项目实际地址）  
3. 准备测试账号（演示数据脚本如 `seed_demo.ps1`）  
4. 截图工具：Windows `Win+Shift+S` / Snipping Tool；浏览器全页截图扩展（可选）  
5. 截图保存目录：`soft-copyright/manual/screenshots/`（按章节分子文件夹）

### 截图文件命名规范

```text
screenshots/
├── 00-cover/                    # 可选：关于页、登录前
├── 01-login/
│   ├── 01-login-page.png
│   └── 02-after-login-home.png
├── 02-case-list/
│   ├── 01-case-list.png
│   └── 02-case-create.png
├── 03-workbench/
│   ├── 01-workbench-overview.png
│   └── ...
└── ...
```

命名：`{序号}-{简短英文描述}.png`，便于 Agent 写入 Markdown。

---

## 阶段 B：必拍镜头清单（最低过审集）

Agent 根据项目路由/菜单生成 `soft-copyright/manual/screenshot-manifest.md`，至少包含：

| 编号 | 场景 | 操作要点 | 预期截图内容 |
|------|------|----------|--------------|
| S01 | 登录页 | 打开登录 URL | 登录表单、软件标识 |
| S02 | 登录后首页 | 成功登录 | 主导航、用户身份 |
| S03 | 核心业务 1 | 完整主流程 | 列表/详情/操作按钮 |
| S04 | 核心业务 2 | … | … |
| S05 | 智能体/批处理 | 触发一次任务 | 进度或结果页 |
| S06 | 知识库/检索 | 检索 + 结果 | 查询框与结果列表 |
| S07 | 文档/上传 | 上传或预览 | 文件树或 PDF 预览 |
| S08 | 设置/用户 | 打开设置页 | 角色或系统配置（脱敏） |

**IP Agent 扩展清单**（在 manifest 中展开）：

- 案件列表 → 进入工作台  
- WOA 流水线运行（S04k–S04p：`12-pipeline-*`～`17-response-preview`）  
- 知识库检索 / 问答  
- 字典管理四张（S18–S18d）  
- 全局 AI 助手  

### 截图完整性 + 换行风险校验

```powershell
py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\validate_manual_screenshots.py --project-root "<项目根>"

py -3.12 %USERPROFILE%\.cursor\skills\soft-copyright-application\scripts\validate_manual_linebreaks.py --project-root "<项目根>"
```

`validate_manual_linebreaks.py` 检查：PDF 引擎 NBSP 保护后仍可能提前换行的中英文空格；同一行多个 `**标签**` 段落未拆分；表格首列仅序号等。

### 增量补拍（保留已有 操作说明书.md 正文时）

| 脚本 | 范围 |
|------|------|
| `soft-copyright/scripts/capture_dict_screenshots.py` | 字典管理 4 张 |
| `soft-copyright/scripts/capture_pipeline_screenshots.py` | WOA 流水线 6 张 |

补拍后仅运行 `build_manual_pdf.ps1` 重新生成 PDF，**勿**用 `run_auto_manual.ps1` 覆盖手工扩充的 MD 章节。

排版与防提前换行规范见 [pdf-layout-guide.md](pdf-layout-guide.md)。

## 阶段 C：逐步操作记录模板

每个功能在 `soft-copyright/manual/steps/{模块}.md` 中按下列格式书写（Agent 可预填文字，用户补图）：

```markdown
## 5.3 审查意见答复工作台

### 功能说明
代理人在此查看 OA 文档、运行 WOA 智能体并编辑答复稿。

### 操作步骤

**步骤 1** 在左侧案件树中选择目标案件。  
![步骤1](screenshots/03-workbench/01-select-case.png)

**步骤 2** 在中间面板打开「审查意见」标签页，查看 PDF 内容。  
![步骤2](screenshots/03-workbench/02-oa-pdf.png)

**步骤 3** 点击右侧「运行流水线」，等待智能体完成分析。  
![步骤3](screenshots/03-workbench/03-pipeline-run.png)

**步骤 4** 在策略审查区确认特征对比矩阵，编辑答复正文后保存。  
![步骤4](screenshots/03-workbench/04-strategy-review.png)

### 预期结果
右侧显示可导出的答复草稿，状态为「已完成」。
```

---

## 阶段 D：排版为 PDF（满足 30 行/页与 60 页）

### 行数策略

- 正文：宋体/微软雅黑 **小四**，行距 **固定值 20 磅**  
- 每页 1～2 张截图时，配 **不少于 15 行** 说明文字（步骤 + 预期结果）  
- 纯文字页目标 **≥ 30 行**  
- 总页数 **≥ 60** 再截取前 30 + 后 30；不足 60 则全部交存

### 页眉页脚（Word / WPS）

| 位置 | 内容 |
|------|------|
| 页眉左 | `{软件全称} {版本号} 操作手册` |
| 页眉右 | `第 {n} 页 共 {total} 页` |
| 页脚中 | `{著作权人全称}` |

### 导出

1. Word 排版完成 → **另存为 PDF**  
2. 或使用 `scripts/generate_manual_pdf.py`（将 Markdown+图片合并为 PDF，见脚本说明）  
3. 用 `scripts/validate_pdf.py` 做页数/页眉抽查（可选）

---

## 阶段 E：Agent 职责边界

| Agent 可做 | 须用户完成 |
|------------|------------|
| 生成 screenshot-manifest、分步 Markdown 文稿 | 实机登录并截图 |
| 根据路由列出必拍菜单 | 确认截图中无敏感客户数据 |
| 合并文稿、检查名称一致性 | 最终 Word/PDF 页眉页脚目视确认 |
| 标注缺失截图位置 | 补拍后更新 `screenshots/` |

---

## 无运行环境时的处理

若暂时无法启动系统：

1. 在 manifest 中标记 `【待补截图】`  
2. **不得**用 Figma/原型图冒充  
3. 可先生成文字版步骤，待用户补图后再导出 PDF 提交
