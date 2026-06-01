# 扫描范围（scope.yaml）

保存到 **当前打开项目的** `security-scan/scope.yaml`（勿提交含真实 Token 的文件）。

```yaml
project_name: ""
scan_mode: quick
authorized: true

targets:
  frontend_url: ""
  api_base: ""
  context_path: ""

environment:
  type: staging
  profile_expected: prod
  destructive_tests_allowed: false

features:
  jimu_report: true
  druid: true
  file_upload: true
  public_registration: false

accounts:
  anonymous: true
  low_privilege: ""
  admin: ""

tokens:
  low_privilege_header: "X-Access-Token: ***"
  admin_header: "X-Access-Token: ***"

business_assets:
  sample_resource_ids: []
  sensitive_data_types: []

blockers: []
notes: ""
```
