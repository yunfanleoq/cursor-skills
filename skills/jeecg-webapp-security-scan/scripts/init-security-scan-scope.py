#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在当前项目根目录生成 security-scan/scope.yaml（交互式）。跨项目通用。"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

DEFAULT = {
    "project_name": "",
    "scan_mode": "quick",
    "authorized": False,
    "targets": {
        "frontend_url": "",
        "api_base": "",
        "context_path": "",
    },
    "environment": {
        "type": "staging",
        "profile_expected": "prod",
        "destructive_tests_allowed": False,
    },
    "features": {
        "jimu_report": True,
        "druid": True,
        "file_upload": True,
        "public_registration": False,
    },
    "accounts": {
        "anonymous": True,
        "low_privilege": "",
        "admin": "",
    },
    "tokens": {
        "low_privilege_header": "X-Access-Token: ***",
        "admin_header": "X-Access-Token: ***",
    },
    "business_assets": {
        "sample_resource_ids": [],
        "sensitive_data_types": [],
    },
    "blockers": [],
    "notes": "",
}


def ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    val = input(f"{prompt}{hint}: ").strip()
    return val or default


def yn(prompt: str, default: bool = False) -> bool:
    d = "y" if default else "n"
    v = ask(prompt + " (y/n)", d).lower()
    return v in ("y", "yes", "1", "true")


def main() -> int:
    root = Path.cwd()
    out_dir = root / "security-scan"
    out_file = out_dir / "scope.yaml"

    print(f"项目根目录: {root}")
    print("生成扫描范围文件（勿将含真实 Token 的 scope.yaml 提交到 git）\n")

    data = {k: (v.copy() if isinstance(v, dict) else v) for k, v in DEFAULT.items()}
    data["project_name"] = ask("项目名称", root.name)
    mode = ask("扫描模式 quick|full|retest|code-audit", "quick")
    if mode in ("quick", "full", "retest", "code-audit", "config-only"):
        data["scan_mode"] = mode
    data["authorized"] = yn("已获书面/口头授权对该目标做安全测试", False)
    if not data["authorized"]:
        print("警告: authorized=false，Agent 应仅做静态 code-audit，不主动探测 URL。")

    data["targets"]["frontend_url"] = ask("前端 URL")
    data["targets"]["api_base"] = ask("API 根 URL（含 context-path）")
    data["targets"]["context_path"] = ask("context-path", "/jeecg-boot")

    env = ask("环境 staging|prod|local", "staging")
    if env in ("staging", "prod", "local"):
        data["environment"]["type"] = env
    data["environment"]["destructive_tests_allowed"] = yn("允许破坏性测试（RCE/批量导出等）", False)

    data["features"]["jimu_report"] = yn("含 JimuReport", True)
    data["features"]["druid"] = yn("含 Druid", True)
    data["features"]["file_upload"] = yn("含文件上传", True)
    data["features"]["public_registration"] = yn("可自助注册低权限账号", False)

    data["accounts"]["low_privilege"] = ask("低权限账号说明", "待提供")
    data["accounts"]["admin"] = ask("管理员账号说明", "待提供")

    out_dir.mkdir(parents=True, exist_ok=True)
    gitignore = root / "security-scan" / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("scope.local.yaml\n*.token.yaml\n", encoding="utf-8")

    if yaml:
        text = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    else:
        # minimal fallback without PyYAML
        import json

        text = "# install PyYAML for nicer output: pip install pyyaml\n"
        text += json.dumps(data, ensure_ascii=False, indent=2)

    out_file.write_text(text, encoding="utf-8")
    print(f"\n已写入: {out_file}")
    print("下一步: 在 Cursor 使用 @jeecg-webapp-security-scan 并引用该文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
