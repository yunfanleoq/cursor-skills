# E2E 文档采集 — 参考手册

## xgsrms 文件地图

| 路径 | 职责 |
|------|------|
| `jeecgboot-vue3/playwright.config.ts` | baseURL、runId、projects(setup→doc-capture)、ignoreHTTPSErrors |
| `jeecgboot-vue3/.env.e2e.example` | 环境变量模板（复制为 `.env.e2e`） |
| `jeecgboot-vue3/tests/e2e/auth.setup.ts` | 六账号 UI 登录 → `.auth/{id}.json` |
| `jeecgboot-vue3/tests/e2e/helpers/login.ts` | 填表 + OCR + 重试；TOKEN 键 `TOKEN__` |
| `jeecgboot-vue3/tests/e2e/helpers/captcha.ts` | 调 `scripts/e2e_captcha_ocr.py` |
| `jeecgboot-vue3/tests/e2e/helpers/accounts.ts` | 六角色账号与 env 覆盖 |
| `jeecgboot-vue3/tests/e2e/helpers/step-capture.ts` | manifest + 全页截图 |
| `jeecgboot-vue3/tests/e2e/flows/doc-capture.spec.ts` | 各角色 `ROLE_PAGES` 路由采集 |
| `scripts/e2e_captcha_ocr.py` | ddddocr 4 位验证码 |
| `scripts/e2e-requirements.txt` | `ddddocr>=1.4.0` |
| `scripts/generate_e2e_report_and_manual.py` | HTML 报告 + e2e-manual MD |
| `scripts/seed_test_users.py` | 生成 MySQL 预置 SQL |
| `scripts/java/JeecgPasswordHash.java` | 与 Jeecg PasswordUtil 一致 |
| `scripts/sql/mysql/run_seed_on_server.sh` | 服务器执行辅助 |
| `docs/e2e-runs/` | 每次运行目录 `{runId}/` |
| `docs/e2e-manual/` | 最新操作说明书 symlink/副本 |
| `docs/测试账号预置指南.md` | SQL + admin 界面两种方式 |
| `docs/自动化测试方案.md` | 总体测试方案 |
| `docs/系统角色及测试计划.md` | 角色与用例规划 |

### gitignore（勿提交）

- `jeecgboot-vue3/.auth/`
- `jeecgboot-vue3/.env.e2e`
- `scripts/sql/mysql/*.generated.sql`

---

## manifest.json 字段

```json
{
  "runId": "2026-06-01T09-41-22",
  "baseURL": "http://10.28.12.15",
  "softwareName": "信工所招聘管理系统",
  "softwareVersion": "V1.0",
  "steps": [
    {
      "index": 1,
      "id": "S01",
      "role": "anonymous",
      "roleLabel": "匿名",
      "title": "登录页",
      "action": "打开系统登录地址…",
      "pageDesc": "登录页提供用户名、密码与图形验证码…",
      "route": "/login",
      "url": "https://10.28.12.15/login",
      "screenshot": "screenshots/01-anonymous-登录页.png",
      "status": "ok",
      "timestamp": "2026-06-01T09:41:30.000Z"
    }
  ]
}
```

报告生成脚本按 `roleLabel` 分组渲染 HTML；MD 手册按软著结构输出「步骤 + 截图 + 页面说明」。

---

## Playwright projects 依赖

```
setup (auth.setup.ts)
  └── doc-capture (doc-capture.spec.ts)  [dependencies: setup]
```

`doc-capture` 通过 `storageState: '.auth/{id}.json'` 免重复登录；S01 匿名登录页仍走 `loginViaUi` 或直访 `/login`。

---

## doc-capture 步骤一览（xgsrms 当前 16 步）

| ID | 角色 | 页面要点 |
|----|------|----------|
| S01 | 匿名 | 登录页 |
| S02 | test-qz | 登录后工作台 |
| S03–S06 | test-qz | 门户、岗位、我的申请/面试 |
| S07–S08 | test-bm | 发布申请、部门审核 |
| S09–S12 | test-rl | 岗位审核/发布、人力审核、面试邀请 |
| S13–S14 | admin | 用户/角色管理 |
| S15–S16 | test-qz-b / test-bm-b | 后台首页（IDOR 对照账号） |

---

## 测试账号 SQL 已知问题

| 错误 | 原因 | 处理 |
|------|------|------|
| `Unknown column 'post'` | 旧版 INSERT 含不存在列 | 使用当前 `seed_test_users.py`（已移除 post） |
| `Duplicate entry '0' for uniq_sys_user_work_no` | work_no 重复 | 新账号 `work_no=用户名`；email/phone 置 NULL |
| 克隆角色失败 | 模板 `test-qz`/`test-bm` 不存在 | 先手工或 SQL 创建模板账号 |
| test-bm-b 无部门 | 仅 1 个部门 | 界面新建「测试部门B」后再 seed |

---

## 故障排查

### OCR / 登录

| 现象 | 排查 |
|------|------|
| `缺少 ddddocr` | `py -3 -m pip install -r scripts/e2e-requirements.txt` |
| `OCR 结果无效` / 过短 | 手动保存验证码图跑 `e2e_captcha_ocr.py`；检查是否 4 位字母数字 |
| 4 次重试仍失败 | `npm run test:e2e:headed` 目视；验证码是否过难/接口异常 |
| 仍在登录页 | 密码错 → seed 或 admin 重置；账号 status≠正常 |
| `TOKEN__` 为空 | 后端 `/sys/login` 失败；查 Nginx `/xgszp-boot` 反代 |

### Playwright / npm

| 现象 | 排查 |
|------|------|
| peer dependency 冲突 | `npm install --legacy-peer-deps` |
| 浏览器未安装 | `npx playwright install chromium` |
| 超时 networkidle | 页面长轮询；step-capture 已 catch，可加大 route `waitMs` |
| HTTPS 证书错误 | `ignoreHTTPSErrors: true`（已配置） |

### 报告

| 现象 | 排查 |
|------|------|
| 找不到 manifest | 先跑 doc-capture；或 `--run-dir docs/e2e-runs/{runId}` |
| 手册未更新 | 单独 `npm run test:e2e:report` |

### 环境

| 现象 | 排查 |
|------|------|
| 301 到 HTTPS | 正常；manifest 中 url 可能为 `https://` |
| API 404 | 确认 `E2E_BASE_URL` 为前端根，非 `/xgszp-boot` |

---

## 验证码方案对比（勿混用）

| 场景 | 方案 |
|------|------|
| Jeecg 登录页 4 位图形码 | **ddddocr** + `e2e_captcha_ocr.py` |
| 网易易盾滑块 | 其他项目 `yidun_slider.py` 等，**本仓库未使用** |

---

## 安全扫描映射（与 jeecg-webapp-security-scan）

| 扫描项 | E2E 现状 | 下一步 spec |
|--------|----------|-------------|
| Auth-01 | setup OCR 六账号成功 | — |
| Auth-02 | OCR 具备 | 用户名枚举对比脚本 |
| Authz-01～06 | 账号 + JWT 就绪 | `authz-idor.spec.ts` |
| File-01～04 | 登录 fixture 就绪 | 上传/下载 fixture |
| Rep-02/03 | admin 可登录 | API 专项（授权窗口） |

---

## 迁移到其他 Jeecg 项目

1. 复制 `tests/e2e/`、`playwright.config.ts`、`.env.e2e.example` 到目标 Vue3 前端根。
2. 复制 `scripts/e2e_captcha_ocr.py`、`e2e-requirements.txt`、`generate_e2e_report_and_manual.py`。
3. 修改 `accounts.ts` 账号、`doc-capture.spec.ts` 的 `ROLE_PAGES` 路由。
4. 调整 `login.ts` 选择器（placeholder/按钮文案因主题而异）。
5. 确认 `TOKEN__` localStorage 键名与项目一致（Jeecg Vue3 默认 `TOKEN__`）。
