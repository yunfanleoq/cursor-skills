# L3 安全回归 — Playwright E2E 自动化（JeecgBoot）

来源于 **xgsrms 生产复测（2026-06-01）** 的可复用模式。适用于已有 Vue3 前端 + 多角色测试账号的 Jeecg 类项目。

## 何时启用

| 模式 | 说明 |
|------|------|
| **L3 / e2e-security** | Authz、File、Rep、Auth-02、Api-03 等需 JWT + 验证码的项 |
| **retest** | 指定编号复测（如 Authz-03 exportXls） |

**前置**：`authorized: true`；生产环境仅非破坏性用例；Api-03 使用 **专用 probe 账号**，禁止批量压测真实用户。

---

## 目录与命令（xgsrms 参考布局）

```text
jeecgboot-vue3/
  tests/e2e/
    auth.setup.ts              # 六角色 OCR 登录 → .auth/*.json
    helpers/
      api-auth.ts              # JWT 读取、isAccessDenied、apiGet/Post
      captcha-api.ts           # API 拉验证码 + ddddocr
      login-api.ts             # RSA 登录、checkOnlyUser
      api-upload.ts            # multipart 上传
    security/
      authz-idor.spec.ts       # Authz-01～06
      file-upload.spec.ts      # File-01～04
      rep-admin.spec.ts        # Rep-02/03
      auth-enumeration.spec.ts # Auth-02
      api-rate-limit.spec.ts   # Api-03
  .auth/                       # gitignore，Playwright storageState
  .env.e2e                     # E2E_BASE_URL=https://host
```

```powershell
Set-Location jeecgboot-vue3
npm run test:e2e:security:full   # setup + 全部 security spec
npm run test:e2e:security        # 仅 security（需已有 .auth）
```

`playwright.config.ts`：`security` project 依赖 `setup`；`ignoreHTTPSErrors: true`（自签 HTTPS）。

---

## 测试账号矩阵（招聘类最小集）

| ID | 角色 | 用途 |
|----|------|------|
| test-qz | 求职者 A | 低权限、上传、IDOR 受害 |
| test-qz-b | 求职者 B | IDOR 攻击方 |
| test-bm | 部门 | File-04 富文本、审核 |
| test-bm-b | 部门 B | 部门隔离对照 |
| test-rl | 人事 | 业务流程 |
| admin | 管理员 | Rep-02/03、Authz-06b 对照 |

预置：`scripts/seed_test_users.py` → MySQL 执行；验证码 OCR：`scripts/e2e_captcha_ocr.py`（ddddocr）。

---

## JWT 从 storageState 读取（关键坑）

Jeecg Vue3 将 JWT 存在 localStorage **缓存桶**内，非裸 `TOKEN__` key：

```text
COMMON__LOCAL__KEY__ → JSON → value.TOKEN__.value  （eyJ...）
```

`readTokenFromAuthFile` 必须：

1. 读 `process.cwd() + '.auth/{accountId}.json'`（不是 `tests/.auth`）
2. 遍历 `origins[].localStorage[]`，解析 JSON 桶内 `TOKEN__.value` 与 `LOGIN__INFO__.value.token`
3. 请求头：`X-Access-Token: {jwt}`

---

## isAccessDenied 判定（Jeecg 统一）

HTTP 401/403 **或** 业务 JSON：

| 字段 | 拒绝值 |
|------|--------|
| `code` | 401、403、510 |
| `message` | 含 `无权限`、`没有权限`、`不允许`、`Unauthorized`、`denied` |

**注意**：Shiro 常返回 **HTTP 200 + code 510**，勿仅断言 HTTP 状态码。

Excel 导出（`exportXls`）失败时也可能返回 JSON 而非文件流，需 `parseJsonBody` + `isAccessDenied`。

---

## 分检查项自动化要点

### Authz-01～06（`authz-idor.spec.ts`）

| ID | 方法 |
|----|------|
| Authz-01 | test-qz → `GET /sys/user/list` → 拒绝 |
| Authz-02 | A listMine 取 id → B `queryById`/`edit` → 拒绝 |
| Authz-03 | A listMine 取 applyId → B `GET .../exportXls?selections=` → 拒绝 |
| Authz-04 | test-qz → `GET .../xgsPositionApply/list` → 拒绝 |
| Authz-04b | A/B 各自 `xgsResumeBase/list`，createBy 不交叉 |
| Authz-05 | listMine JSON 无 `/www/wwwroot` 等绝对路径 |
| Authz-06 | test-qz → dataSource/quartz list → 拒绝 |
| Authz-06b | admin → dataSource list → 成功（对照） |

**Authz-03 典型漏洞**：`exportXls` 仅有 `@RequiresPermissions`，未校验 `selections` 归属。

**修复模式**（白盒 + 复测）：

```java
// exportXls 前对每条 selection 调用
XgsRecruitmentAuthUtil.assertCanExportApply(existing);

// assertCanExportApply：仅 canManageApplies() 或 ownsApply()，勿用 canExportApplies() 单独放行
```

### File-01～04（`file-upload.spec.ts`）

| ID | 端点 | 期望 |
|----|------|------|
| File-01 | `POST /sys/common/upload` + .html/.svg/.jsp | `SsrfFileTypeFilter` 拒绝 |
| File-02 | `POST /sys/oss/file/upload`（test-qz） | 403 / 无权限 |
| File-03 | 合法 1×1 PNG | success（对照） |
| File-04 | test-bm `edit` 岗位 duty 含 `<script>` | 入库后无 script/onerror |

### Rep-02/03（`rep-admin.spec.ts`）

| 路径 | 角色 | 期望 |
|------|------|------|
| `POST /jmreport/testConnection` | test-qz | 没有权限 / 510 |
| 同上，body 含 `jdbc:mysql://127.0.0.1:3306/...` | admin | success≠true，无「连接成功」 |
| `POST /jmreport/queryFieldBySql` + SQLi | admin | success≠true，无 SQL 堆栈泄露 |

Shiro：`/jmreport/**` → `jwt,roles[admin]`。生产另需 `jeecg.jmreport.firewall.lowCodeMode=prod`、`dataSourceSafe=true`。

### Auth-02（`auth-enumeration.spec.ts`）

1. `GET /sys/user/checkOnlyUser?username=&captcha=&checkKey=` — 须先 OCR 验证码；存在/不存在用户 **message 相同**（如「校验完成」），仅 `result` 布尔不同。
2. `POST /sys/login` — 存在/不存在用户名 + 错误密码，message 均为「用户名或密码错误」。

登录 API 须：`/sys/loginRsaPublicKey` → JSEncrypt 加密密码 → 带 captcha/checkKey。

### Api-03（`api-rate-limit.spec.ts`）

- 用户名：`e2e-ratelimit-{timestamp}`（专用 probe，避免锁真实账号）
- 错误密码 + 有效验证码，累计 **≥6 次**「用户名或密码错误」或出现「登录失败次数过多，请于10分钟后再次登录」
- 验证码 OCR 失败时会打断计数，循环最多 12 次

---

## 生产环境门禁

```bash
curl -sk https://{host}/{boot}/sys/randomImage/test | head -c 80
# 期望 success:true（非 502）
```

| 风险 | 约束 |
|------|------|
| Api-03 | probe 账号、≤12 次/轮 |
| 部署 | sudo 需人工；JAR 上传后 `restart-rms-backend.sh` |
| HTTPS | Playwright `ignoreHTTPSErrors: true` |

---

## 白盒 grep 补充（L3 相关）

```text
exportXls          # 是否调用 assertCanExportApply / create_by 过滤
assertCanExportApply
XgsPositionInputSanitizer
SsrfFileTypeFilter
CheckOnlyUserIpLimit
LOGIN_FAIL         # LoginController 失败锁定
/jmreport/**       # ShiroConfig roles[admin]
```

---

## 报告衔接

L3 全量通过后更新：

- 项目内 `docs/obsidian/12-*安全扫描报告*.md` §5 / §10.5
- checklist S10 闭环 + S11 E2E（若启用）

**xgsrms 2026-06-01 结果**：setup 6 + security 18 = **24/24** 通过。
