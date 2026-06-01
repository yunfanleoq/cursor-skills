#!/usr/bin/env python3
"""Extract source code pages for software copyright registration (China)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_EXTENSIONS = {
    "py", "js", "ts", "vue", "jsx", "tsx", "java", "kt", "go", "rs", "cs", "cpp", "c", "h", "sql"
}
DEFAULT_EXCLUDE_DIRS = {
    "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".git",
    "coverage", ".storage", ".cursor", ".idea", ".vscode",
}
DEFAULT_EXCLUDE_GLOBS = ("*.min.js", "*.lock", "package-lock.json", "pnpm-lock.yaml")


def load_scope(scope_path: Path | None) -> dict[str, Any]:
    if scope_path is None or not scope_path.is_file():
        return {}
    try:
        import yaml  # type: ignore
    except ImportError:
        print("Warning: PyYAML not installed; using defaults. pip install pyyaml", file=sys.stderr)
        return {}
    with scope_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def should_exclude(path: Path, exclude_dirs: set[str], exclude_globs: tuple[str, ...]) -> bool:
    parts = set(path.parts)
    if parts & exclude_dirs:
        return True
    name = path.name
    for pat in exclude_globs:
        if pat.startswith("*."):
            if name.endswith(pat[1:]):
                return True
        elif name == pat:
            return True
    return False


def collect_files(
    root: Path,
    extensions: set[str],
    exclude_dirs: set[str],
    exclude_globs: tuple[str, ...],
    priority_paths: list[str],
) -> list[Path]:
    found: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lstrip(".").lower() not in extensions:
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        if should_exclude(rel, exclude_dirs, exclude_globs):
            continue
        found.append(rel)

    def sort_key(rel: Path) -> tuple[int, str]:
        s = rel.as_posix()
        for i, pref in enumerate(priority_paths):
            if s.startswith(pref.replace("\\", "/")):
                return (i, s)
        return (len(priority_paths), s)

    found.sort(key=sort_key)
    return found


def read_lines(path: Path, redact_patterns: list[str], replace_with: str) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="gbk", errors="replace")
    lines = text.splitlines()
    if redact_patterns:
        compiled = [re.compile(p, re.IGNORECASE) for p in redact_patterns]
        out: list[str] = []
        for line in lines:
            for pat in compiled:
                line = pat.sub(replace_with, line)
            out.append(line)
        lines = out
    return lines


def build_concat(
    root: Path,
    files: list[Path],
    redact_patterns: list[str],
    replace_with: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    all_lines: list[str] = []
    manifest: list[dict[str, Any]] = []
    for rel in files:
        header = f"/* ===== File: {rel.as_posix()} ===== */"
        body = read_lines(root / rel, redact_patterns, replace_with)
        block = [header, *body, ""]
        manifest.append({
            "path": rel.as_posix(),
            "lines": len(body),
            "start_line_in_concat": len(all_lines) + 1,
        })
        all_lines.extend(block)
    return all_lines, manifest


def effective_lines(lines: list[str]) -> list[str]:
    return [ln for ln in lines if ln.strip()]


def paginate(lines: list[str], lines_per_page: int) -> list[list[str]]:
    pages: list[list[str]] = []
    buf: list[str] = []
    for ln in lines:
        buf.append(ln)
        if len(buf) >= lines_per_page:
            pages.append(buf)
            buf = []
    if buf:
        while len(buf) < lines_per_page:
            buf.append("")
        pages.append(buf)
    return pages


def pages_to_text(pages: list[list[str]], header: str) -> str:
    chunks: list[str] = []
    for i, page in enumerate(pages, 1):
        chunks.append(f"--- Page {i} --- [{header}]")
        chunks.extend(page)
        chunks.append("")
    return "\n".join(chunks)


def extract_front_back(
    pages: list[list[str]], front_n: int, back_n: int
) -> tuple[list[list[str]], list[list[str]]]:
    total = len(pages)
    need = front_n + back_n
    if total <= need:
        return pages, []
    return pages[:front_n], pages[-back_n:]


def scan_project(root: Path, scope: dict[str, Any]) -> dict[str, Any]:
    """Return source code statistics without writing output files."""
    sw = scope.get("software", {})
    sc = scope.get("source_code", {})
    red = scope.get("redaction", {})

    extensions = set(sc.get("extensions", list(DEFAULT_EXTENSIONS)))
    exclude_dirs = set(sc.get("exclude_dirs", list(DEFAULT_EXCLUDE_DIRS)))
    exclude_globs = tuple(sc.get("exclude_globs", list(DEFAULT_EXCLUDE_GLOBS)))
    priority_paths = sc.get("priority_paths", [])
    lines_per_page = int(sc.get("lines_per_page", 50))
    pages_front = int(sc.get("pages_front", 30))
    pages_back = int(sc.get("pages_back", 30))
    redact_patterns = red.get("patterns", [])
    replace_with = red.get("replace_with", "REDACTED")

    files = collect_files(root, extensions, exclude_dirs, exclude_globs, priority_paths)
    if not files:
        return {
            "project_root": str(root),
            "software": {"full_name": sw.get("full_name", ""), "version": sw.get("version", "")},
            "file_count": 0,
            "total_lines": 0,
            "effective_lines": 0,
            "lines_per_page": lines_per_page,
            "total_pages": 0,
            "deposit_strategy": "full",
            "pages_front": pages_front,
            "pages_back": pages_back,
        }

    all_lines, _manifest = build_concat(root, files, redact_patterns, replace_with)
    eff = effective_lines(all_lines)
    pages = paginate(eff, lines_per_page)
    total_pages = len(pages)

    return {
        "project_root": str(root),
        "software": {"full_name": sw.get("full_name", ""), "version": sw.get("version", "")},
        "file_count": len(files),
        "total_lines": len(all_lines),
        "effective_lines": len(eff),
        "lines_per_page": lines_per_page,
        "total_pages": total_pages,
        "deposit_strategy": "full" if total_pages <= pages_front + pages_back else "front_back",
        "pages_front": pages_front,
        "pages_back": pages_back,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract source pages for soft copyright filing")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--scope", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--scan-only", action="store_true")
    args = parser.parse_args()

    root = args.project_root.resolve()
    scope_path = args.scope
    if scope_path and not scope_path.is_absolute():
        scope_path = root / scope_path
    scope = load_scope(scope_path)

    sw = scope.get("software", {})
    sc = scope.get("source_code", {})
    red = scope.get("redaction", {})
    out_cfg = scope.get("output", {})

    extensions = set(sc.get("extensions", list(DEFAULT_EXTENSIONS)))
    exclude_dirs = set(sc.get("exclude_dirs", list(DEFAULT_EXCLUDE_DIRS)))
    exclude_globs = tuple(sc.get("exclude_globs", list(DEFAULT_EXCLUDE_GLOBS)))
    priority_paths = sc.get("priority_paths", [])
    lines_per_page = int(sc.get("lines_per_page", 50))
    pages_front = int(sc.get("pages_front", 30))
    pages_back = int(sc.get("pages_back", 30))
    redact_patterns = red.get("patterns", [])
    replace_with = red.get("replace_with", "REDACTED")

    full_name = sw.get("full_name", "软件全称")
    version = sw.get("version", "V1.0")
    header = f"{full_name} {version} 源程序"

    files = collect_files(root, extensions, exclude_dirs, exclude_globs, priority_paths)
    if not files:
        print(f"No source files found under {root}", file=sys.stderr)
        return 1

    all_lines, manifest = build_concat(root, files, redact_patterns, replace_with)
    eff = effective_lines(all_lines)
    pages = paginate(eff, lines_per_page)
    total_pages = len(pages)

    stats = {
        "project_root": str(root),
        "software": {"full_name": full_name, "version": version},
        "file_count": len(files),
        "total_lines": len(all_lines),
        "effective_lines": len(eff),
        "lines_per_page": lines_per_page,
        "total_pages": total_pages,
        "deposit_strategy": "full" if total_pages <= pages_front + pages_back else "front_back",
        "pages_front": pages_front,
        "pages_back": pages_back,
    }

    print(json.dumps(stats, ensure_ascii=False, indent=2))

    if args.scan_only:
        return 0

    out_dir = args.output or Path(out_cfg.get("dir", "soft-copyright/output"))
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    front_pages, back_pages = extract_front_back(pages, pages_front, pages_back)

    (out_dir / "source_concat.txt").write_text("\n".join(all_lines), encoding="utf-8")
    (out_dir / "source_stats.json").write_text(
        json.dumps({**stats, "manifest": manifest}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest_md = ["# 源程序文件清单\n", f"- 有效代码行：{len(eff)}\n", f"- 折算页数：{total_pages}\n\n", "| 路径 | 行数 |\n|------|------|\n"]
    for m in manifest:
        manifest_md.append(f"| {m['path']} | {m['lines']} |\n")
    (out_dir / "source_manifest.md").write_text("".join(manifest_md), encoding="utf-8")

    (out_dir / "02-源程序-前30页.txt").write_text(
        pages_to_text(front_pages, header), encoding="utf-8"
    )
    if back_pages:
        (out_dir / "03-源程序-后30页.txt").write_text(
            pages_to_text(back_pages, header), encoding="utf-8"
        )
    elif total_pages <= pages_front + pages_back:
        (out_dir / "03-源程序-后30页.txt").write_text(
            "(与全部交存相同，仅一份即可)\n", encoding="utf-8"
        )

    print(f"Written to {out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
