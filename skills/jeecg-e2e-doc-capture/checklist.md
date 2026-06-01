# E2E 文档采集 — 执行清单

复制到对话或本地跟踪，按 Phase 勾选。

```
任务: jeecg-e2e-doc-capture
目标环境: _______________  (例 http://10.28.12.15)
模式: [ ] full  [ ] setup  [ ] doc-capture  [ ] seed-users  [ ] auth-for-scan  [ ] extend
runId: _______________
```

---

## Phase 0 — 环境与测试账号（seed-users / 首次 full 必做）

- [ ] **0.1** 确认目标环境已授权（内网/VPN）
- [ ] **0.2** 复制 `jeecgboot-vue3/.env.e2e.example` → `.env.e2e`，核对 `E2E_BASE_URL` 与账号密码
- [ ] **0.3** Python：`py -3 -m pip install -r scripts/e2e-requirements.txt`
- [ ] **0.4** Node：`npm install --legacy-peer-deps`（在 `jeecgboot-vue3/`）
- [ ] **0.5** Playwright：`npx playwright install chromium`
- [ ] **0.6** 模板账号 `test-qz`、`test-bm` 在库中存在且角色正确
- [ ] **0.7** 生成 SQL：`py -3 scripts/seed_test_users.py -o scripts/sql/mysql/xgs_seed_test_users.generated.sql`
  - test-qz 密码已 OK → 加 `--skip-fix`
- [ ] **0.8** 服务器执行 SQL（或 admin 界面手工建账号）
- [ ] **0.9** 验证 SQL：`test-qz-b`、`test-bm-b` 存在，六账号角色正确
- [ ] **0.10** 浏览器或 `test:e2e:setup` 试登至少 1 个账号

---

## Phase 1 — 多角色登录态（setup）

- [ ] **1.1** `npm run test:e2e:setup`
- [ ] **1.2** 确认 `jeecgboot-vue3/.auth/` 下 6 个 JSON：`test-qz.json` … `admin.json`
- [ ] **1.3** 若 OCR 失败：单独跑 `py -3 scripts/e2e_captcha_ocr.py <图片路径>` 调试；检查 ddddocr 安装
- [ ] **1.4** 若密码错误：回到 Phase 0.7–0.8

**预期**：6 passed（authenticate × 6），约 30–60s。

---

## Phase 2 — 文档截图采集（doc-capture / full）

- [ ] **2.1** `npm run test:e2e:doc` 或 `npm run test:e2e:full`
- [ ] **2.2** 确认 `docs/e2e-runs/{runId}/screenshots/` 有全页 PNG
- [ ] **2.3** 确认 `manifest.json` 中 `steps[].status` 均为 `ok`
- [ ] **2.4** 核对步骤数（xgsrms doc-capture 当前 **16** 步 S01–S16）
- [ ] **2.5** 打开 `测试报告.html` 目视检查关键页面未空白/未登录页

**预期**：1 passed（doc-capture），总时长约 1–2 min（含 setup）。

---

## Phase 3 — 报告与操作手册（report / full 自动）

- [ ] **3.1** `npm run test:e2e:report`（full 已自动执行则跳过）
- [ ] **3.2** 确认 `docs/e2e-runs/{runId}/测试报告.html`
- [ ] **3.3** 确认 `docs/e2e-manual/操作说明书-E2E采集-最新.md` 已更新
- [ ] **3.4** （可选）将 e2e-manual 纳入软著 PDF 流水线

---

## Phase 4 — 安全扫描衔接（auth-for-scan，可选）

- [ ] **4.1** 读取 `jeecg-webapp-security-scan` checklist，确认扫描模式（quick/full/retest）
- [ ] **4.2** Auth-01：引用 E2E setup 六账号 OCR 登录成功作为证据
- [ ] **4.3** Authz-01～06：规划 `tests/e2e/security/authz-idor.spec.ts`（使用 `.auth/test-qz-b.json` 等）
- [ ] **4.4** File-01～04：规划上传 fixture + 多角色下载对比
- [ ] **4.5** 更新项目安全报告「E2E / 测试账号」章节（如有 `docs/obsidian/*安全*`）

---

## Phase 5 — 扩展用例（extend，按需）

- [ ] **5.1** 在 `ROLE_PAGES` 或新 spec 增加步骤
- [ ] **5.2** 每步填写 `action`（用户操作）与 `pageDesc`（页面功能说明）— 软著手册必填
- [ ] **5.3** 重跑 full，manifest 步骤 ID 连续（S01…）
- [ ] **5.4** 完整业务链（岗位创建→投递→三级审核→面试）— **尚未默认实现**，单独 spec

---

## 完成汇报模板

向用户汇报时使用：

```markdown
## E2E 执行结果

- **环境**: {baseURL}
- **runId**: {runId}
- **Playwright**: {setup N/N, doc-capture M/M}
- **截图步骤**: {count}（{S01–Sxx}）
- **产出**: 测试报告.html、操作说明书-E2E采集-最新.md
- **阻塞/待办**: {无 | 列表}
```
