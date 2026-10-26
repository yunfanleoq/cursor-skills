#!/usr/bin/env python3
"""Normalize Obsidian Web Clipper markdown for the WeChat article pipeline.

Reads a clipped .md from the Obsidian vault (YAML frontmatter + body),
writes articles/<slug>-from-obsidian.md with source metadata for Step 2.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_CONFIG = Path.home() / ".cursor" / "wechat-clipper.json"

# Obsidian Clipper / common frontmatter keys
URL_KEYS = ("url", "source", "link", "canonical")
TITLE_KEYS = ("title", "name")
AUTHOR_KEYS = ("author", "byline", "creator")


def load_config(path: Path | None = None) -> dict:
    cfg_path = path or DEFAULT_CONFIG
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {}


def slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    if path:
        tail = path.split("/")[-1]
        if tail and tail not in ("s", "index.html"):
            return re.sub(r"[^\w\-]", "-", tail)[:80]
    return re.sub(r"[^\w\-]", "-", urlparse(url).netloc or "clip")[:80]


def slug_from_name(name: str) -> str:
    base = Path(name).stem
    base = re.sub(r"[^\w\u4e00-\u9fff\-]", "-", base)
    base = re.sub(r"-+", "-", base).strip("-")
    return base[:80] or "clip"


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            meta[key] = val
    return meta, parts[2].lstrip("\n")


def pick(meta: dict[str, str], keys: tuple[str, ...]) -> str:
    for k in keys:
        for mk, mv in meta.items():
            if mk.lower() == k and mv.strip():
                return mv.strip()
    return ""


def strip_clipper_noise(body: str) -> str:
    lines = body.splitlines()
    out: list[str] = []
    skip_patterns = (
        re.compile(r"^>\s*\[!?\w+\]", re.I),
        re.compile(r"^#\s*Clipped from", re.I),
        re.compile(r"^via\s+Obsidian", re.I),
    )
    for line in lines:
        if any(p.search(line) for p in skip_patterns):
            continue
        out.append(line)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def copy_vault_assets(body: str, clip_path: Path, out_dir: Path) -> str:
    """Copy relative images next to articles/ and rewrite paths."""
    assets_dir = out_dir / "assets" / slug_from_name(clip_path.name)
    assets_dir.mkdir(parents=True, exist_ok=True)
    clip_dir = clip_path.parent

    def repl_md(m: re.Match[str]) -> str:
        alt, src = m.group(1), m.group(2)
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        src_path = (clip_dir / src).resolve()
        if not src_path.is_file():
            return m.group(0)
        dest = assets_dir / src_path.name
        if not dest.exists():
            shutil.copy2(src_path, dest)
        rel = dest.relative_to(out_dir).as_posix()
        return f"![{alt}]({rel})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl_md, body)


def build_output(
    clip_path: Path,
    out_dir: Path,
    slug: str | None = None,
    copy_assets: bool = True,
) -> Path:
    raw = clip_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(raw)
    body = strip_clipper_noise(body)

    url = pick(meta, URL_KEYS)
    title = pick(meta, TITLE_KEYS) or clip_path.stem
    author = pick(meta, AUTHOR_KEYS)

    if copy_assets:
        body = copy_vault_assets(body, clip_path, out_dir)

    final_slug = slug or (slug_from_url(url) if url else slug_from_name(clip_path.name))
    out_path = out_dir / f"{final_slug}-from-obsidian.md"

    header = [
        "<!-- obsidian-web-clipper -->",
        f"<!-- source_file: {clip_path} -->",
    ]
    if url:
        header.append(f"<!-- source_url: {url} -->")
    if author:
        header.append(f"<!-- author: {author} -->")
    header.append("")
    if title and not body.lstrip().startswith("# "):
        header.append(f"# {title}")
        header.append("")
    if url:
        header.append(f"> 原文链接：{url}")
        header.append("")

    out_path.write_text("\n".join(header) + body + "\n", encoding="utf-8")

    sidecar = out_dir / f"{final_slug}-from-obsidian.meta.json"
    sidecar.write_text(
        json.dumps(
            {
                "title": title,
                "url": url,
                "author": author,
                "source_file": str(clip_path),
                "prepared_at": datetime.now().isoformat(timespec="seconds"),
                "output_md": str(out_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Obsidian Web Clipper MD for WeChat pipeline")
    parser.add_argument("clip_md", type=Path, help="Path to clipped markdown in Obsidian vault")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "articles",
        help="Output directory (default: skill articles/)",
    )
    parser.add_argument("--slug", help="Override output slug")
    parser.add_argument("--no-copy-assets", action="store_true")
    parser.add_argument("--config", type=Path, help="wechat-clipper.json path")
    args = parser.parse_args()

    clip_path = args.clip_md.expanduser().resolve()
    if not clip_path.is_file():
        raise SystemExit(f"File not found: {clip_path}")

    cfg = load_config(args.config)
    out_dir = Path(cfg.get("articles_dir") or args.output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = build_output(
        clip_path,
        out_dir,
        slug=args.slug,
        copy_assets=not args.no_copy_assets,
    )
    print(out_path)


if __name__ == "__main__":
    main()
