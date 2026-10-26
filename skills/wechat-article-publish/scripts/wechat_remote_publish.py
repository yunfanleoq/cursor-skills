#!/usr/bin/env python3
"""Publish WeChat articles via remote WeChat Agent (e.g. http://wechat.yclub.xin)."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

DEFAULT_CONFIG = Path.home() / ".cursor" / "wechat-agent-client.json"
DEFAULT_SSH_HOST = os.environ.get("WECHAT_AGENT_SSH", "dev@101.201.65.123")
DEFAULT_SSH_KEY = os.environ.get("WECHAT_AGENT_SSH_KEY", str(Path.home() / ".ssh" / "cpp_server_key"))
DEFAULT_REMOTE_ROOT = os.environ.get("WECHAT_AGENT_REMOTE_ROOT", "/www/wwwroot/wechat-agent-server")


def _scp(local: Path, remote_rel: str, ssh_host: str, ssh_key: str, remote_root: str) -> None:
    remote = f"{ssh_host}:{remote_root}/{remote_rel}"
    cmd = ["scp", "-i", ssh_key, "-o", "StrictHostKeyChecking=no", str(local), remote]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _sync_markdown_assets(md_path: Path, ssh_host: str, ssh_key: str, remote_root: str) -> None:
    base = md_path.parent
    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", md_path.read_text(encoding="utf-8"))
    for ref in refs:
        if ref.startswith(("http://", "https://", "data:")):
            continue
        local = (base / ref).resolve()
        if not local.exists():
            raise SystemExit(f"图片不存在: {local}")
        remote_rel = f"articles/{ref}".replace("\\", "/")
        remote_dir = "/".join(remote_rel.split("/")[:-1])
        subprocess.run(
            ["ssh", "-i", ssh_key, "-o", "StrictHostKeyChecking=no", ssh_host, f"mkdir -p {remote_root}/{remote_dir}"],
            check=True,
            capture_output=True,
            text=True,
        )
        _scp(local, remote_rel, ssh_host, ssh_key, remote_root)
        print(f"已上传素材: {ref}")


def load_client_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or DEFAULT_CONFIG
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))

    url = os.environ.get("WECHAT_AGENT_URL", "http://wechat.yclub.xin")
    api_key = os.environ.get("WECHAT_AGENT_API_KEY", "")
    if not api_key:
        raise SystemExit(
            f"Missing API key. Create {DEFAULT_CONFIG} or set WECHAT_AGENT_API_KEY.\n"
            "See config/wechat-agent-client.example.json"
        )
    return {
        "url": url.rstrip("/"),
        "api_key": api_key,
        "caller_name": os.environ.get("WECHAT_AGENT_CALLER_NAME", "cursor-local"),
        "verify_ssl": os.environ.get("WECHAT_AGENT_VERIFY_SSL", "false").lower() == "true",
    }


def _headers(cfg: dict[str, Any]) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": cfg["api_key"],
    }
    caller = cfg.get("caller_name")
    if caller:
        headers["X-Caller-Name"] = caller
    return headers


def health_check(cfg: dict[str, Any]) -> dict[str, Any]:
    resp = requests.get(
        f"{cfg['url']}/api/health",
        timeout=30,
        verify=cfg.get("verify_ssl", False),
    )
    resp.raise_for_status()
    return resp.json()


def submit_job(cfg: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    resp = requests.post(
        f"{cfg['url']}/api/v1/webhook",
        headers=_headers(cfg),
        json=body,
        timeout=60,
        verify=cfg.get("verify_ssl", False),
    )
    if resp.status_code >= 400:
        raise SystemExit(f"Submit failed ({resp.status_code}): {resp.text}")
    return resp.json()


def poll_job(cfg: dict[str, Any], job_id: str, interval: float = 2.0, timeout: float = 300.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{cfg['url']}/api/v1/jobs/{job_id}",
            headers=_headers(cfg),
            timeout=30,
            verify=cfg.get("verify_ssl", False),
        )
        if resp.status_code == 404:
            time.sleep(interval)
            continue
        resp.raise_for_status()
        job = resp.json()
        status = job.get("status")
        if status in {"succeeded", "failed"}:
            return job
        time.sleep(interval)
    raise SystemExit(f"Timeout waiting for job {job_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish markdown to WeChat via remote Agent")
    parser.add_argument("--config", type=Path, default=None, help="Path to wechat-agent-client.json")
    parser.add_argument("--markdown", type=Path, help="Local markdown file")
    parser.add_argument("--title", required=False, help="Article title")
    parser.add_argument("--digest", default="", help="Digest (<=120 chars)")
    parser.add_argument("--author", default="", help="Author name")
    parser.add_argument("--thumb", type=Path, help="Cover image (uploaded to server as articles/assets/thumb)")
    parser.add_argument("--sync-assets", action="store_true", default=True, help="SCP local images to agent server")
    parser.add_argument("--no-sync-assets", action="store_false", dest="sync_assets")
    parser.add_argument("--publish", action="store_true", help="Submit publish (default: draft only)")
    parser.add_argument("--no-wait", action="store_true", help="Submit only, do not poll job status")
    parser.add_argument("--health", action="store_true", help="Health check only")
    parser.add_argument(
        "--open-comment",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="开启评论（默认读 ~/.cursor/wechat-publish.json，未配置时为开启）",
    )
    parser.add_argument(
        "--fans-only-comment",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="仅粉丝可评论",
    )
    parser.add_argument("--source-url", default=None, help="阅读原文链接")
    args = parser.parse_args()

    if args.health:
        cfg = {}
        if args.config and args.config.exists():
            cfg = load_client_config(args.config)
        else:
            cfg_path = DEFAULT_CONFIG
            if cfg_path.exists():
                cfg = load_client_config(cfg_path)
            else:
                cfg = {
                    "url": os.environ.get("WECHAT_AGENT_URL", "http://wechat.yclub.xin").rstrip("/"),
                    "verify_ssl": False,
                }
        data = health_check(cfg)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    cfg = load_client_config(args.config)

    if not args.markdown or not args.title:
        raise SystemExit("--markdown and --title are required unless --health is used")

    # 微信标题长度校验（中文=1单位，英文/数字=0.5单位，上限64）
    title_units = 0.0
    for ch in args.title:
        title_units += 1.0 if (ord(ch) > 127 or ch in "——…") else 0.5
    if title_units > 64:
        raise SystemExit(
            f"标题超长（{title_units:.1f}/64 微信字符单位），请缩短标题后重试。\n"
            f"当前标题：{args.title}\n"
            f"提示：中文计1字，英文/数字计0.5字，可达约60个纯中文或100+英文。"
        )
    if title_units > 55:
        print(f"⚠️  标题接近上限（{title_units:.1f}/64 单位），建议控制在55以内确保完整显示。")

    md_path = args.markdown.resolve()
    if args.sync_assets:
        _sync_markdown_assets(md_path, DEFAULT_SSH_HOST, DEFAULT_SSH_KEY, DEFAULT_REMOTE_ROOT)
        if args.thumb:
            asset_dir = f"articles/assets/{md_path.stem}"
            thumb_rel = f"{asset_dir}/{args.thumb.name}"
            remote_dir = f"{DEFAULT_REMOTE_ROOT}/{asset_dir}"
            subprocess.run(
                ["ssh", "-i", DEFAULT_SSH_KEY, "-o", "StrictHostKeyChecking=no", DEFAULT_SSH_HOST, f"mkdir -p {remote_dir}"],
                check=True,
                capture_output=True,
                text=True,
            )
            _scp(args.thumb.resolve(), thumb_rel, DEFAULT_SSH_HOST, DEFAULT_SSH_KEY, DEFAULT_REMOTE_ROOT)
            print(f"已上传封面: {thumb_rel}")

    markdown_content = md_path.read_text(encoding="utf-8")
    body: dict[str, Any] = {
        "title": args.title,
        "digest": args.digest,
        "author": args.author,
        "publish": args.publish,
        "markdown_content": markdown_content,
        "async_mode": True,
    }
    if args.thumb:
        body["thumb_path"] = f"articles/assets/{md_path.stem}/{args.thumb.name}"
    if args.open_comment is not None:
        body["open_comment"] = args.open_comment
    if args.fans_only_comment is not None:
        body["fans_only_comment"] = args.fans_only_comment
    if args.source_url:
        body["content_source_url"] = args.source_url

    print(f"Submitting to {cfg['url']} ...")
    submitted = submit_job(cfg, body)
    print(json.dumps(submitted, ensure_ascii=False, indent=2))

    if args.no_wait:
        return

    job_id = submitted.get("job_id")
    if not job_id:
        return

    print(f"Polling job {job_id} ...")
    result = poll_job(cfg, job_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("status") != "succeeded":
        raise SystemExit(result.get("error") or "Job failed")


if __name__ == "__main__":
    main()
