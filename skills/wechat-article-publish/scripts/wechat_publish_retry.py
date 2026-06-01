#!/usr/bin/env python3
"""Retry WeChat publish until IP whitelist allows access."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def get_token(appid: str, secret: str) -> dict:
    return requests.get(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={"grant_type": "client_credential", "appid": appid, "secret": secret},
        timeout=30,
    ).json()


def main():
    parser = argparse.ArgumentParser(description="Retry WeChat publish on IP whitelist errors")
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--digest", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--thumb", type=Path)
    parser.add_argument("--config", type=Path, default=Path.home() / ".cursor" / "wechat-publish.json")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--max-retries", type=int, default=36)
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    appid, secret = cfg.get("appid"), cfg.get("secret")
    if not appid or not secret:
        print("错误: 未配置 appid/secret", file=sys.stderr)
        sys.exit(1)

    pub_script = Path(__file__).with_name("wechat_publish.py")
    for i in range(args.max_retries):
        data = get_token(appid, secret)
        if "access_token" not in data:
            ip_match = re.search(r"invalid ip ([0-9.]+)", data.get("errmsg", ""))
            ip_s = ip_match.group(1) if ip_match else "?"
            print(f"[{i + 1}/{args.max_retries}] IP 未在白名单: {ip_s}，{args.interval} 秒后重试...")
            time.sleep(args.interval)
            continue

        cmd = [
            sys.executable,
            str(pub_script),
            "--html",
            str(args.html),
            "--title",
            args.title,
            "--digest",
            args.digest,
            "--author",
            args.author or cfg.get("author", ""),
            "--config",
            str(args.config),
        ]
        if args.thumb:
            cmd.extend(["--thumb", str(args.thumb)])
        if args.publish:
            cmd.append("--publish")

        print("access_token 获取成功，开始发布...")
        result = subprocess.run(cmd)
        sys.exit(result.returncode)

    print("超时：请关闭 IP 白名单或添加当前 IP 后重试", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
