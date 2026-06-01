# 常见修复 Playbook（Jeecg 招聘类 · 经 xgsrms 验证）

与 [e2e-automation.md](e2e-automation.md) 配套：发现项 → 修复 → E2E 复测。

## Authz-03 exportXls IDOR

**现象**：低权限用户带 `selections=他人ID` 调用 `exportXls` 返回 HTTP 200 + Excel。

**根因**：

1. Controller 直接 `super.exportXls`，未按条校验归属
2. `assertCanExportApply` 误用 `canExportApplies()` OR 逻辑，有菜单权限即可导出任意记录

**修复**：

```java
// XgsRecruitmentAuthUtil.assertCanExportApply
if (canManageApplies()) return;
if (ownsApply(user, apply)) return;
throw new UnauthorizedException("无权限导出该申请");

// XgsPositionApplyController.exportXls — selections 逐条 assertCanExportApply
// 无 selections 且非管理员：xgsPositionApply.setCreateBy(sysUser.getUsername())
```

**复测**：`Authz-03` in `authz-idor.spec.ts`；需 **重新部署后端 JAR**。

---

## PROJ-006 CSP / Auth-04 HTTPS / Cfg-06 Token

| 编号 | 措施 | 验证 |
|------|------|------|
| PROJ-006 | Nginx `Content-Security-Policy` | `curl -skI https://host/` |
| Auth-04 | 80→443 301；`.env.production` https | HTTP 跳转 |
| Cfg-06 | `rms.env` `JEECG_SECURITY_ALLOW_TOKEN_IN_QUERY=false` | 启动日志 |

---

## C-003 JimuReport Shiro

```java
filterChainDefinitionMap.put("/jmreport/**", "jwt,roles[admin]");
// excludeUrls 禁止含 jmreport 子路径（会优先 anon 绕过）
```

配合 `application-prod.yml`：

```yaml
jeecg:
  jmreport:
    firewall:
      dataSourceSafe: true
      lowCodeMode: prod
      api-ssrf-guard-enabled: true
```

---

## 部署脚本踩坑（xgs-server）

| 问题 | 处理 |
|------|------|
| CRLF | 上传后 `sed -i 's/\r$//'` |
| sudo 需密码 | 自动化 scp JAR，人工 sudo restart |
| `$HOME=/root` under sudo | restart 脚本用 `SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"` |
| 502 未拉起 | `stop-rms-backend.sh` + `restart-rms-backend.sh` |

---

## File / XSS

- 上传：`SsrfFileTypeFilter` 白名单（无 svg/html/jsp）
- 富文本：`XgsPositionInputSanitizer` + Jsoup `Whitelist.relaxed()` 于 Service 层 `save/update`

---

## Auth-02 枚举防护（代码已有则 E2E 验证即可）

- `checkOnlyUser`：验证码 gate + 统一 message + `CheckOnlyUserIpLimit`（30/min）
- `login`：用户不存在与密码错误统一「用户名或密码错误」+ `LOGIN_FAIL` Redis 计数（>5 锁定 10min）
