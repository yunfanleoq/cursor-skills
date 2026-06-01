# 使用示例（任意 Cursor 项目）

## 启用方式

1. 确认技能在 **`%USERPROFILE%\.cursor\skills\jeecg-webapp-security-scan\`**（个人技能，全项目可用）。
2. 对话输入：`@jeecg-webapp-security-scan` + 任务描述。

## 示例 1：任意项目 quick 扫描

```
@jeecg-webapp-security-scan
目标 https://app.example.com/api-boot，预发环境，低权限 user1 / 管理员 admin，做 quick 扫描。
```

## 示例 2：先生成 scope 再扫描

```powershell
cd D:\projects\other-hr-system
python $env:USERPROFILE\.cursor\skills\jeecg-webapp-security-scan\scripts\init-security-scan-scope.py
```

然后在 Cursor：

```
@jeecg-webapp-security-scan 读取 security-scan/scope.yaml，执行 full 扫描。
```

## 示例 3：仅 code-audit（无环境）

```
@jeecg-webapp-security-scan 对当前仓库做 code-audit，框架是 JeecgBoot 3.7。
```

## 示例 4：xgsrms 仓库（有本地策略文档时）

Agent 应额外读取：

- `Fw_ 招聘系统漏洞报告及测试记录/同类应用系统-安全扫描策略.md`
- `scripts/security-remediation-verify.ps1`
- `docs/obsidian/09-安全与扫描.md`（项目记忆）
- Skill 内 [e2e-automation.md](e2e-automation.md) · [fixes-playbook.md](fixes-playbook.md)

编号可继续用 `VULN-xxx`。

## 示例 5：xgsrms L3 E2E 全量回归（2026-06-01 固化）

```
@jeecg-webapp-security-scan
生产 https://10.28.12.15/xgszp-boot 已授权；测试账号已预置；执行 L3 e2e-security 并更新扫描报告。
```

Agent 应：

1. 读 Skill [e2e-automation.md](e2e-automation.md)
2. 确认后端在线：`curl -sk .../sys/randomImage/test`
3. 运行：

```powershell
Set-Location I:\cursorProjects\xgsrms\jeecgboot-vue3
npm run test:e2e:security:full
```

4. 失败则查 [fixes-playbook.md](fixes-playbook.md)（如 Authz-03 exportXls → 部署 JAR）
5. 更新 `docs/obsidian/12-生产环境安全扫描报告-2026-06-01.md`

**预期**：setup 6 + security 18 = 24/24。

## 示例 6：单项复测 Authz-03

```
@jeecg-webapp-security-scan 复测 Authz-03 exportXls IDOR，后端已部署修复。
```

```powershell
Set-Location jeecgboot-vue3
npx playwright test tests/e2e/security/authz-idor.spec.ts --grep Authz-03
```
