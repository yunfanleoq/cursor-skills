---
name: jeecg-e2e-doc-capture
description: >-
  JeecgBoot Vue3 E2E automation: Playwright multi-role login with ddddocr captcha OCR,
  step screenshot capture, HTML test report + soft-copyright operation manual (manifest.json),
  and test-user DB seeding for HR/recruitment apps. Use for E2E测试, Playwright, doc-capture,
  e2e-manual, 操作说明书采集, 测试账号预置, 图形验证码OCR, 多角色自动化, xgsrms 招聘系统测试,
  安全扫描登录复验, 软著截图流水线.
---

# JeecgBoot E2E 文档采集与多角色测试

适用于 **JeecgBoot + Vue3** 项目（图形验证码登录、多角色 HR/招聘业务）。本 Skill 描述通用工作流；**xgsrms 信工所招聘系统** 已实现全套脚本，路径见 [reference.md](reference.md)。

执行时 **必须先读** [checklist.md](checklist.md) 并按阶段勾选；故障排查见 [reference.md#故障排查](reference.md#故障排查)。

## 何时使用

| 用户意图 | 模式 |
|----------|------|
| 跑一遍 E2E + 生成报告/操作手册 | **full**（默认） |
| 仅刷新六角色登录态 | **setup** |
| 仅重新截图采集 | **doc-capture** |
| 预置/修复测试账号 | **seed-users** |
| 为安全扫描准备 JWT / 登录证据 | **auth-for-scan** |
| 扩展新业务流或 IDOR 用例 | **extend** |

## 架构（四段流水线）

```
seed_test_users.py → auth.setup.ts(OCR) → doc-capture.spec.ts(StepCapture) → generate_e2e_report_and_manual.py
         ↓                    ↓                         ↓                                    ↓
   sys_user SQL          .auth/*.json          manifest.json + screenshots          测试报告.html + e2e-manual/*.md
```

**验证码**：Jeecg 登录页 **4 位图形验证码**，用 `ddddocr`（**不是**易盾滑块）。OCR 失败时 `login.ts` 自动刷新验证码并重试（默认 4 次）。

**HTTPS 跳转**：生产 Nginx 常将 `http://` 301 到 `https://`；Playwright 须设 `ignoreHTTPSErrors: true`（已配置）。

## 前置条件

| 项 | 说明 |
|----|------|
| 授权环境 | 仅测用户明确授权的内网/预发；禁止未授权生产破坏性操作 |
| Node | 前端目录可 `npm install --legacy-peer-deps`（Jeecg  peer 冲突） |
| Python | `py -3 -m pip install -r scripts/e2e-requirements.txt`（ddddocr） |
| Playwright | `npx playwright install chromium` |
| JDK | 生成测试账号 SQL 时需 JDK（Jeecg PasswordUtil 哈希） |
| 命令分隔 | Windows PowerShell 用 `;`；npm script 内并行用 `&`；**禁止** `&&` |

## xgsrms 一键执行（已验证 2026-06-01：7/7 通过，16 步截图）

```powershell
Set-Location "I:\cursorProjects\xgsrms\jeecgboot-vue3"
Copy-Item .env.e2e.example .env.e2e   # 首次
py -3 -m pip install -r ..\scripts\e2e-requirements.txt
npm install --legacy-peer-deps
npx playwright install chromium
npm run test:e2e:full
```

### npm 脚本

| 命令 | 作用 |
|------|------|
| `test:e2e:full` | Playwright 全量 + 报告/手册生成 |
| `test:e2e:setup` | 仅六账号 OCR 登录 → `.auth/` |
| `test:e2e:doc` | 仅 doc-capture（依赖已有 `.auth/`） |
| `test:e2e:report` | 仅从最新 manifest 生成 HTML + MD |
| `test:e2e:headed` | 有界面调试 |

### 产出物

| 路径 | 说明 |
|------|------|
| `docs/e2e-runs/{runId}/测试报告.html` | 逐步截图 + 操作说明 + 页面说明 |
| `docs/e2e-runs/{runId}/manifest.json` | 结构化步骤（S01…） |
| `docs/e2e-manual/操作说明书-E2E采集-最新.md` | 软著结构操作手册 |
| `jeecgboot-vue3/.auth/*.json` | storageState（**gitignore**，含 Token） |

## 测试账号（xgsrms 标准六角色）

密码规则：业务账号 `{用户名}@2026`；admin 为 `zktw@2019`。

| id | 角色 | 用途 |
|----|------|------|
| test-qz | 求职者 A | 主流程 / 低权限 |
| test-qz-b | 求职者 B | IDOR 水平越权对照 |
| test-bm | 部门 A | 发布申请、部门审核 |
| test-bm-b | 部门 B | 部门隔离 IDOR |
| test-rl | 人事处 | 审核、发布、面试 |
| admin | 系统管理员 | 用户/角色管理 |

预置：`py -3 scripts/seed_test_users.py -o scripts/sql/mysql/xgs_seed_test_users.generated.sql`  
若 test-qz 密码已修复：`--skip-fix`。详见 `docs/测试账号预置指南.md`。

## 扩展新用例（extend 模式）

1. **新页面截图**：在 `tests/e2e/flows/doc-capture.spec.ts` 的 `ROLE_PAGES` 增加 `route/title/action/pageDesc`。
2. **新业务流**：新建 `tests/e2e/flows/*.spec.ts`，用 `test.use({ storageState: '.auth/xxx.json' })` 复用登录态。
3. **安全回归**：新建 `tests/e2e/security/*.spec.ts` 或 `tests/security/*.spec.ts`，对照 `jeecg-webapp-security-scan` checklist 的 Authz/File 项。
4. **每步元数据**：调用 `StepCapture.capture(page, { role, roleLabel, title, action, pageDesc, route })`；失败用 `markFail`。
5. 跑完后执行 `npm run test:e2e:report` 或 `test:e2e:full` 刷新报告。

## 与其他 Skill 衔接

| Skill | 衔接点 |
|-------|--------|
| `jeecg-webapp-security-scan` | E2E setup 提供多角色 JWT；Auth-01 可用 OCR 登录复验；Authz/File 待 L3 spec |
| `soft-copyright-application` | `docs/e2e-manual/` 为实机截图源，可转 Word/PDF 鉴别材料 |
| `xgsrms-prod-deploy` | 部署后复跑 `test:e2e:full` 验证生产可用 |

## 安装为全局 Skill（可选）

复制到用户目录后任意 Jeecg 项目可引用工作流（脚本仍在本仓库）：

```powershell
powershell -ExecutionPolicy Bypass -File .cursor\skills\jeecg-e2e-doc-capture\install-to-user-skills.ps1
```

## Agent 执行要求

1. **先读 checklist**，按 Phase 0→3 顺序；跳过已完成阶段须说明原因。
2. **真实执行**命令，汇报 pass/fail 与 runId；勿编造截图数量。
3. 失败时查 [reference.md#故障排查](reference.md#故障排查)，修复后重跑对应 phase。
4. 涉及安全扫描结论时，标注「E2E 已覆盖 / 待 L3 spec」，与 `jeecg-webapp-security-scan` 编号对齐。
5. **勿提交** `.auth/`、`.env.e2e`、`*.generated.sql`。

## 附加资源

- 逐步清单：[checklist.md](checklist.md)
- 文件地图、manifest 字段、故障表：[reference.md](reference.md)
- 项目内说明：`docs/e2e-runs/README.md`、`docs/自动化测试方案.md`
