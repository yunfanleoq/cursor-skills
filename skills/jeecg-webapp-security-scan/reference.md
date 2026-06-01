# 参考：Jeecg 类系统常见漏洞域（跨项目）

来源于 JeecgBoot 多角色业务系统实践；编号可在新项目中改用 `PROJ-xxx`。

## 攻击链

| 链 | 路径 |
|----|------|
| A | 匿名/低权限 → 用户/简历/申请列表 → 附件/导出 |
| B | 低权限 → `/jmreport/testConnection` 或 `/sys/dataSource/add` → JDBC/外连库 |
| C | 低权限 → `/actuator` httptrace → 管理员 Token → Quartz/配置写 |

## 检查项 → 典型编号

| 域 | 编号示例 |
|----|----------|
| Profile/Swagger/报表 dev 模式 | C-001, VULN-005, 017–018, 024 |
| 凭据硬编码 | C-002, VULN-027, 032 |
| Shiro anon 报表 | C-003 |
| IDOR 列表 | VULN-001, 002, 020, B-003, B-004 |
| 上传/XSS | VULN-006, 039, 补充-02 |
| 枚举/验证码 | 补充-03～06 |
| 系统 API 缺权限 | VULN-019, 040, 041, 023 |
| 登录密钥 | VULN-004, 038, 022 |

## 白盒 grep 关键词

`ShiroConfig`, `filterChainDefinitionMap`, `anon`, `excludeUrls`, `listMine`, `create_by`, `RequiresPermissions`, `SsrfFileTypeFilter`, `spring.profiles.active`, `knife4j.production`, `lowCodeMode`, `assertCanExportApply`, `exportXls`, `XgsRecruitmentAuthUtil`, `CheckOnlyUserIpLimit`, `LOGIN_FAIL`

## L3 E2E 关键路径（`<boot>` = context-path）

| 用途 | 路径 |
|------|------|
| 通用上传 | `POST /<boot>/sys/common/upload` |
| OSS 管理上传 | `POST /<boot>/sys/oss/file/upload` |
| JimuReport SSRF | `POST /<boot>/jmreport/testConnection` |
| JimuReport SQLi | `POST /<boot>/jmreport/queryFieldBySql` |
| 用户枚举 | `GET /<boot>/sys/user/checkOnlyUser` |
| RSA 登录 | `GET /<boot>/sys/loginRsaPublicKey` + `POST /<boot>/sys/login` |
| 验证码 | `GET /<boot>/sys/randomImage/{checkKey}` |

## Jeecg 响应判定备忘

- 无权限常见：**HTTP 200 + code 510 + message「没有权限，请联系管理员分配权限！」**
- `isAccessDenied` 须匹配 `无权限` **与** `没有权限`
- exportXls 拒绝时返回 JSON，非 Excel 流

## xgsrms 参考实现

| 资产 | 路径 |
|------|------|
| E2E helpers | `jeecgboot-vue3/tests/e2e/helpers/api-auth.ts` 等 |
| 测试账号 SQL | `scripts/seed_test_users.py` |
| 生产报告 | `docs/obsidian/12-生产环境安全扫描报告-2026-06-01.md` |
| 项目记忆 | `docs/obsidian/09-安全与扫描.md` |

## 严重级别（简要）

- **严重**：全量 PII、凭据泄露、任意文件读、库直连
- **高危**：批量 IDOR、报表 RCE 链、弱口令监控、低权限写系统配置
- **中危**：枚举、XSS、Actuator、密钥下发、任务列表泄露

## 可选：项目内扩展文档

若工作区有 `同类应用系统-安全扫描策略.md` 或漏洞汇总 docx，读取后与本 reference 合并，避免重复劳动。
