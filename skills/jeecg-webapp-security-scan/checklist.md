# 扫描检查清单（全局 Skill · 任意项目）

执行时逐项勾选：通过 / 失败 / 跳过 / 阻塞。历史编号见 [reference.md](reference.md)。

## 账号矩阵

| 角色 | 必填 | 用途 |
|------|------|------|
| 匿名 | 是 | 暴露面、匿名 API |
| 低权限业务用户 | 是 | IDOR、上传、报表 |
| 系统管理员 | 是 | 对照 |
| 中权限（审核等） | 视业务 | 审批流越权 |

## S0 范围

- [ ] 目标 base URL、`<boot>` context-path
- [ ] 环境授权与禁止项
- [ ] 是否含 JimuReport / Druid / 外置 DB
- [ ] 已读 `security-scan/scope.yaml`（若有）

## S1 配置与暴露面（P0）

| ID | 检查项 | 参考 |
|----|--------|------|
| Cfg-01 | `spring.profiles.active` 为 prod | C-001 |
| Cfg-02 | 无硬编码 DB/邮件/AI/签名密钥 | C-002 |
| Cfg-03 | 5xx 无完整堆栈/SQL | C-001 |
| Cfg-04 | CORS 白名单、安全响应头 | — |
| Cfg-05 | JWT/签名密钥非默认值 | VULN-022, 028 |
| Cfg-06 | Token 不出现在 URL（生产） | — |
| Cfg-07 | 进程非 root | VULN-026 |
| Cfg-08 | 静态目录无 PHP 等误执行 | VULN-033 |
| Cfg-09 | 面板/旁路端口不对外 | VULN-030, 031 |
| Exp-01 | Swagger/Knife4j 不可匿名访问 | VULN-005 |
| Exp-02 | Druid 禁用或强保护 | VULN-003 |
| Exp-03 | Actuator/httptrace 不泄露 Token | VULN-010 |
| Exp-04 | 无生产 `test`/`debug` 接口 | B-005 |
| Exp-05 | `/jmreport/**` 非 Shiro anon | C-003 |

## S2 认证与会话

| ID | 检查项 | 参考 |
|----|--------|------|
| Auth-01 | 验证码不可绕过 | 补充-06 |
| Auth-02 | 用户名枚举统一文案+限流 | 补充-03, 04 |
| Auth-03 | 手机/邮箱枚举无差异提示 | 补充-05 |
| Auth-04 | 登录无匿名长期 AES；优先 RSA/TLS | VULN-004, 038 |
| Auth-05 | 密码重置仅 POST+鉴权 | — |
| Auth-06 | JWT 有效期与登出合理 | C-004 |

## S3 授权与 IDOR（重点）

**方法**：用户 A 建资源 → 用户 B/匿名访问 → `/list` vs `/listMine`。

| ID | 检查项 | 参考 |
|----|--------|------|
| Authz-01 | 低权限不可全量用户列表 | VULN-001 |
| Authz-02 | 不可读改他人核心业务实体 | VULN-002, 020 |
| Authz-03 | 不可导出他人文件 | B-003 |
| Authz-04 | 不可全量业务申请/订单类数据 | B-004 |
| Authz-05 | 附件路径不可预测泄露 | VULN-007 |
| Authz-06 | dataSource/Quartz 等需权限 | VULN-019, 040, 041 |
| Authz-07 | 匿名接口无 PII | VULN-009 |

## S4 JimuReport（有则必测）

| ID | 检查项 | 参考 |
|----|--------|------|
| Rep-01 | 匿名不可访问 `/jmreport/**` | C-003 |
| Rep-02 | testConnection 无 SSRF/任意外连 JDBC | VULN-017 |
| Rep-03 | queryFieldBySql 无 SQLi | VULN-018 |
| Rep-04 | 低权限不可任意建报表 | VULN-024 |
| Rep-05 | `lowCodeMode=prod`, `dataSourceSafe=true` | C-001 |

## S5 文件与 XSS

| ID | 检查项 | 参考 |
|----|--------|------|
| File-01 | 禁止 svg/jsp/html 等危险上传 | VULN-006, 039 |
| File-02 | 低权限不可上传管理类型 | VULN-006 |
| File-03 | 存储型 XSS 不可执行 | 补充-02 |
| File-04 | 富文本已消毒 | 补充-02 |
| File-05 | 无任意文件读 | VULN-026 |
| File-06 | URL 拉取无内网 SSRF | — |

## S6 API 滥用

| ID | 检查项 | 参考 |
|----|--------|------|
| Api-01 | 无硬编码签名密钥 | VULN-022 |
| Api-03 | 登录/短信/导出有限流 | 补充-05, 06 |

## S7 依赖

- [ ] Shiro ≥1.13 — D-001
- [ ] SnakeYAML ≥2.0 — D-002
- [ ] JimuReport 已知 CNVD — VULN-017/018

## S8 攻击链（必跑）

- [ ] **链 A**：无法获取他人 PII
- [ ] **链 B**：无法外连恶意 JDBC / 直连库
- [ ] **链 C**：无法经 Actuator 提权到系统写接口

## S9 白盒

- [ ] Controller 数据权限、`edit` 所有权
- [ ] Shiro anon / excludeUrls
- [ ] 上传白名单
- [ ] 系统管理 Controller 权限注解

## S10 闭环

- [ ] 项目 verify 脚本（若有）
- [ ] 发现写入记录表 / 报告
- [ ] 复测 PoC 失败

## S11 L3 Playwright E2E（有前端测试基建时）

详见 [e2e-automation.md](e2e-automation.md)。xgsrms 2026-06-01：**24/24** 通过。

| 套件 | 检查项 | spec 文件（参考） |
|------|--------|-------------------|
| authz-idor | Authz-01～06 + 06b | `tests/e2e/security/authz-idor.spec.ts` |
| file-upload | File-01～04 | `tests/e2e/security/file-upload.spec.ts` |
| rep-admin | Rep-02/03 | `tests/e2e/security/rep-admin.spec.ts` |
| auth-enumeration | Auth-02 | `tests/e2e/security/auth-enumeration.spec.ts` |
| api-rate-limit | Api-03 | `tests/e2e/security/api-rate-limit.spec.ts` |

- [ ] setup 六角色 OCR → `.auth/*.json`
- [ ] `isAccessDenied` 含「没有权限」（Jeecg 510）
- [ ] exportXls IDOR 白盒 + Authz-03 复测
- [ ] 报告 §5 待测项清零
