---
name: jeecg-webapp-security-scan
description: >-
  Cross-project security scanning for JeecgBoot-style apps (Spring Boot + Shiro/JWT + Vue,
  JimuReport, Druid, multi-role HR/recruitment with PII). Delivers checklists, curl steps,
  code-audit grep targets, attack-chain tests, and findings (PROJ-xxx or VULN-xxx). Includes
  L3 Playwright E2E regression (Authz/File/Rep/Auth-02/Api-03) per e2e-automation.md.
  Use for 漏洞扫描, 渗透测试, 安全测试, 安全复测, AWVS补测, IDOR, 越权, JeecgBoot安全, 低代码后台安全.
---

# Jeecg 类 Web 应用安全扫描（全局 Skill）

适用于 **任意 Cursor 项目**。技能文件位于用户目录 `~/.cursor/skills/jeecg-webapp-security-scan/`（与具体仓库无关）。

执行时 **必须先读** 同目录下 [checklist.md](checklist.md)；输出 **必须套用** [report-template.md](report-template.md)。

若项目含 Playwright 与测试账号，L3 自动化读 [e2e-automation.md](e2e-automation.md)；修复闭环读 [fixes-playbook.md](fixes-playbook.md)。

## 项目内可选资料（有则读，无则跳过）

打开工作区后，若存在下列路径则优先引用（更贴近该项目历史漏洞）：

| 路径（相对项目根） | 用途 |
|-------------------|------|
| `security-scan/scope.yaml` | 本次扫描范围（推荐） |
| `**/同类应用系统-安全扫描策略.md` | 详细策略 |
| `SECURITY-REMEDIATION.md` | 加固与 env 变量 |
| `scripts/security-remediation-verify.ps1` | 配置自检（有则跑） |
| `**/漏洞记录及修复情况记录表*.docx` | 记录表字段对齐 |

无上述文件时，仅用本 Skill 自带 [reference.md](reference.md) + checklist 即可完成扫描。

## 扫描前约束

1. **授权**：仅测用户明确授权的环境；禁止未授权生产的破坏性测试。
2. **先配置后接口**：未确认 `prod` profile 时，Swagger/报表/堆栈结论标注不确定性。
3. **多角色**：匿名 + 低权限业务用户 + 管理员（见 checklist）。
4. **DAST 不替代手工**：IDOR、业务越权、JDBC SSRF、验证码/枚举须手工或 code-audit。
5. **证据**：方法+路径+角色+状态码；禁止编造未验证结果。

## 工作流

### Step 0 — 扫描模式

| 模式 | 覆盖 |
|------|------|
| **quick**（默认） | S0 + S1 P0 + S3 IDOR + 攻击链 A/B/C |
| **full** | checklist S0～S12 |
| **L3 / e2e-security** | S3 + S4 + S5 + S2(Auth-02) + S6(Api-03) Playwright 自动化（见 [e2e-automation.md](e2e-automation.md)） |
| **retest** | 用户指定编号 + 对应链 |
| **code-audit** | 白盒 grep + B/C/D 风格编号 |
| **config-only** | Cfg-* + 项目内 verify 脚本（若有） |

### Step 1 — 范围（S0）

1. 若存在 `security-scan/scope.yaml`，读取并确认 `authorized: true`。
2. 否则用 [scope-template.md](scope-template.md) 向用户确认，或运行：

```bash
python ~/.cursor/skills/jeecg-webapp-security-scan/scripts/init-security-scan-scope.py
```

（Windows 路径：`%USERPROFILE%\.cursor\skills\jeecg-webapp-security-scan\scripts\init-security-scan-scope.py`）

生成文件建议放在当前项目 `security-scan/scope.yaml`，并加入 `.gitignore`（若含 Token）。

### Step 2 — 执行

按 [checklist.md](checklist.md) 勾选进度。有源码时 grep：

- `ShiroConfig`, `anon`, `excludeUrls`
- Controller `/list` vs `/listMine`, `create_by`, `@RequiresPermissions`
- `application-prod.yml`, `jeecg.security`
- `SsrfFileTypeFilter`, upload 白名单

### Step 3 — 攻击链（必报结论）

- **A**：低权限/匿名 → 他人 PII
- **B**：低权限 → 报表/数据源 → 外连 JDBC 或库凭据
- **C**：低权限 → Actuator/trace → 长 Token → 系统写接口

### Step 4 — 交付

扫描摘要 + 发现列表（report-template）+ 未测/阻塞 + P0/P1 建议。

### Step 5 — L3 E2E 回归（可选，有 Playwright 时）

1. 确认六角色 `.auth/*.json`（OCR 登录 setup）与 `E2E_BASE_URL`（HTTPS 自签则 `ignoreHTTPSErrors`）。
2. 按 [e2e-automation.md](e2e-automation.md) 跑 `security` project；**24 项**为 xgsrms 参考规模（Authz 14 + File 4 + Rep 3 + Auth-02 2 + Api-03 1）。
3. 失败项对照 [fixes-playbook.md](fixes-playbook.md)；需改 Java 时部署后再跑。
4. 更新项目扫描报告 §5 / §10，标记 checklist **S11**。

## 编号

- 新项目：`PROJ-001` 起，映射 checklist ID（如 `Authz-02`）。
- 延续历史表：`VULN-xxx` / `补充-xx` / `B-003` 等（见 [reference.md](reference.md)）。

## Jeecg 常见路径（`<boot>` = context-path）

```text
/<boot>/doc.html
/<boot>/druid/index.html
/<boot>/actuator
/<boot>/jmreport/
/<boot>/sys/login
/<boot>/sys/common/upload
/<boot>/sys/dataSource/list
/<boot>/sys/quartzJob/list
```

## 资源

- [checklist.md](checklist.md) · [report-template.md](report-template.md) · [reference.md](reference.md) · [examples.md](examples.md)
- [e2e-automation.md](e2e-automation.md) · [fixes-playbook.md](fixes-playbook.md)
