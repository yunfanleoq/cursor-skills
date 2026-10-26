#!/usr/bin/env python3
"""End-to-end: source material -> article -> WeChat HTML -> optional publish."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.check_call(cmd)


def main():
    parser = argparse.ArgumentParser(description="WeChat article pipeline")
    parser.add_argument("--markdown", type=Path, required=True, help="Final markdown article")
    parser.add_argument("--title", required=True)
    parser.add_argument("--digest", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--open-comment", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--fans-only-comment", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--source-url", default=None)
    args = parser.parse_args()

    html_path = args.markdown.with_suffix(".wechat.html")
    run([sys.executable, str(SCRIPTS / "markdown_to_wechat_html.py"), str(args.markdown), "-o", str(html_path)])

    pub_cmd = [
        sys.executable,
        str(SCRIPTS / "wechat_publish.py"),
        "--html",
        str(html_path),
        "--title",
        args.title,
        "--digest",
        args.digest,
        "--author",
        args.author,
    ]
    if args.publish:
        pub_cmd.append("--publish")
    if args.open_comment is True:
        pub_cmd.append("--open-comment")
    elif args.open_comment is False:
        pub_cmd.append("--no-open-comment")
    if args.fans_only_comment is True:
        pub_cmd.append("--fans-only-comment")
    elif args.fans_only_comment is False:
        pub_cmd.append("--no-fans-only-comment")
    if args.source_url:
        pub_cmd.extend(["--source-url", args.source_url])
    if args.dry_run:
        pub_cmd.append("--dry-run")
    run(pub_cmd)


if __name__ == "__main__":
    main()
