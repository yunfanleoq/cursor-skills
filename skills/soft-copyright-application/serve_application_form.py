#!/usr/bin/env python3
"""Serve application form viewer and optionally open browser."""

from __future__ import annotations

import argparse
import http.server
import json
import subprocess
import sys
import webbrowser
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PORT = 8765


def configure_stdio_utf8() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


def ensure_generated(root: Path, scope: str) -> Path:
    out_dir = root / "soft-copyright" / "output"
    html_path = out_dir / "application-form-viewer.html"
    json_path = out_dir / "application-form-fields.json"

    if not json_path.is_file() or not html_path.is_file():
        gen = SCRIPT_DIR / "generate_application_form.py"
        cmd = [sys.executable, str(gen), "--project-root", str(root), "--scope", scope, "--quiet"]
        print("正在生成表单字段...", file=sys.stderr)
        rc = subprocess.call(cmd)
        if rc != 0:
            raise SystemExit(rc)

    return html_path


def main() -> int:
    configure_stdio_utf8()
    parser = argparse.ArgumentParser(description="Open soft copyright application form viewer")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--scope", type=str, default="soft-copyright/scope.yaml")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    root = args.project_root.resolve()
    html_path = ensure_generated(root, args.scope)
    out_dir = html_path.parent

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(out_dir), **kw)

        def log_message(self, fmt: str, *a) -> None:
            print(f"[{self.log_date_time_string()}] {fmt % a}")

    url = f"http://127.0.0.1:{args.port}/application-form-viewer.html"
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"填写助手目录: {out_dir}")
    print(f"打开地址: {url}")
    print("按 Ctrl+C 停止服务")
    print("提示: localhost:3025 是 browser-tools，不是本填写助手（本服务默认 8765 端口）")

    if not args.no_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止服务。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
