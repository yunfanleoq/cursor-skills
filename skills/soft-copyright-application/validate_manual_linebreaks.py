#!/usr/bin/env python3
"""Scan 操作说明书.md for PDF premature line-break risks (中英文混排空格等)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Import protector from sibling module
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from generate_manual_pdf import (  # noqa: E402
    FAQ_LABEL_RE,
    INTRO_LABEL_ONLY_RE,
    INTRO_LABEL_RE,
    STEP_RE,
    _protect_phrase_breaks,
    _split_inline_intro_line,
    _strip_md,
)

HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
IMG_RE = re.compile(r"^!\[(.*?)\]\((.+?)\)\s*$")
TABLE_SEP_RE = re.compile(r"^\|[-:\s|]+\|$")

# 仅匹配普通空格/制表符（不含 NBSP），避免把已保护文本误报
_SP = r"[ \t]"

RISK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("拉丁+空格+中文", re.compile(rf"[A-Za-z]{{2,}}{_SP}+[\u4e00-\u9fff]")),
    ("中文+空格+拉丁", re.compile(rf"[\u4e00-\u9fff]{_SP}+[A-Za-z]{{2,}}")),
    ("OA/WOA+空格+中文", re.compile(rf"\b(OA|WOA|AI|RAG|PDF){_SP}+[\u4e00-\u9fff]")),
    ("中文+空格+OA/WOA", re.compile(rf"[\u4e00-\u9fff]{_SP}+(OA|WOA|AI|D1|D2)\b")),
    ("空格斜杠空格", re.compile(rf"{_SP}/{_SP}")),
    ("箭头链空格", re.compile(rf"→{_SP}|{_SP}→")),
    ("图+空格+数字", re.compile(rf"图{_SP}+\d")),
    ("Enter+空格+键", re.compile(rf"Enter{_SP}+键", re.I)),
)


def _collect_text_blocks(md: str) -> list[tuple[int, str, str]]:
    """Return (line_no, kind, text) for prose likely rendered by write_body/write_step."""
    lines = md.splitlines()
    blocks: list[tuple[int, str, str]] = []
    i = 0
    while i < len(lines):
        ls = lines[i].strip()
        ln = i + 1
        if not ls or ls == "---" or ls.startswith("|") or TABLE_SEP_RE.match(ls):
            i += 1
            continue
        if HEADING_RE.match(ls) or IMG_RE.match(ls):
            i += 1
            continue
        if ls.startswith("**著作权人") or ls.startswith("**文档") or ls.startswith("**编写"):
            i += 1
            continue
        sm = STEP_RE.match(ls)
        if sm:
            blocks.append((ln, "step", _strip_md(sm.group(2))))
            i += 1
            continue
        if ls.startswith("**预期结果**"):
            blocks.append((ln, "expected", _strip_md(ls.replace("**预期结果**", "").strip())))
            i += 1
            continue
        faq_m = FAQ_LABEL_RE.match(ls)
        if faq_m:
            blocks.append((ln, "faq", _strip_md(faq_m.group(2))))
            i += 1
            continue
        if INTRO_LABEL_ONLY_RE.match(ls):
            i += 1
            continue
        ilm = INTRO_LABEL_RE.match(ls)
        if ilm and not STEP_RE.match(ls):
            rest = _strip_md(ilm.group(2))
            if rest:
                blocks.append((ln, "intro", rest))
            i += 1
            continue
        if ls.startswith("#"):
            i += 1
            continue
        if re.match(r"^\d+\.\s", ls) and "章" not in ls:
            i += 1
            continue
        # 普通段落（章首导语等）
        if not ls.startswith("**") and len(ls) > 20:
            blocks.append((ln, "para", _strip_md(ls)))
        i += 1
    return blocks


def _is_merged_intro_line(line: str) -> bool:
    """同行多个 **标签** 段落（排除句中强调 **不出现** 等）。"""
    if STEP_RE.match(line) or FAQ_LABEL_RE.match(line) or line.startswith("**预期结果"):
        return False
    parts = _split_inline_intro_line(line)
    if len(parts) < 2:
        return False
    matches = list(re.finditer(r"\*\*(.+?)\*\*", line))
    for idx in range(1, len(matches)):
        gap = line[matches[idx - 1].end() : matches[idx].start()].strip()
        if not gap or re.search(r"[。！？；]$", gap):
            continue
        return False
    return True


def scan_structural(md_path: Path) -> list[dict[str, str | int]]:
    """Markdown 结构问题：同一行多个 intro 标签、表格续行缺列名等。"""
    lines = md_path.read_text(encoding="utf-8").splitlines()
    findings: list[dict[str, str | int]] = []
    for i, raw in enumerate(lines, start=1):
        ls = raw.strip()
        if not ls or ls.startswith("#") or ls.startswith("![") or TABLE_SEP_RE.match(ls):
            continue
        if ls.startswith("|") and re.match(r"^\|\s*[①②③④⑤⑥⑦⑧⑨]\s*\|", ls):
            findings.append(
                {
                    "line": i,
                    "kind": "table",
                    "risk": "表格首列仅序号",
                    "match": ls.split("|")[1].strip(),
                    "snippet": ls[:72],
                }
            )
            continue
        if _is_merged_intro_line(ls):
            findings.append(
                {
                    "line": i,
                    "kind": "structure",
                    "risk": "同行多个intro标签",
                    "match": "多个 **标签**",
                    "snippet": ls[:72] + ("…" if len(ls) > 72 else ""),
                }
            )
            continue
        if INTRO_LABEL_ONLY_RE.match(ls):
            nxt = lines[i].strip() if i < len(lines) else ""
            if nxt.startswith("|"):
                findings.append(
                    {
                        "line": i,
                        "kind": "structure",
                        "risk": "标签后无正文直接接表格",
                        "match": ls,
                        "snippet": f"{ls} → 表格",
                    }
                )
    return findings


def scan_manual(md_path: Path) -> list[dict[str, str | int]]:
    md = md_path.read_text(encoding="utf-8")
    findings: list[dict[str, str | int]] = []
    for ln, kind, raw in _collect_text_blocks(md):
        protected = _protect_phrase_breaks(raw)
        for label, pat in RISK_PATTERNS:
            for m in pat.finditer(protected):
                snippet = protected[max(0, m.start() - 8) : m.end() + 12].replace("\n", " ")
                findings.append(
                    {
                        "line": ln,
                        "kind": kind,
                        "risk": label,
                        "match": m.group(0),
                        "snippet": snippet,
                    }
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate manual text for PDF line-break risks")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--manual",
        type=Path,
        default=None,
        help="Path to 操作说明书.md (default: soft-copyright/manual/操作说明书.md)",
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    manual = args.manual or (root / "soft-copyright/manual/操作说明书.md")
    if not manual.is_file():
        print(f"Manual not found: {manual}", file=sys.stderr)
        return 1

    findings = scan_structural(manual) + scan_manual(manual)
    blocks_n = len(_collect_text_blocks(manual.read_text(encoding="utf-8")))
    if not findings:
        print(f"OK: no line-break or structural risks in {manual.name} ({blocks_n} text blocks scanned)")
        return 0

    lb = [f for f in findings if f["kind"] != "structure" and f["kind"] != "table"]
    st = [f for f in findings if f["kind"] in ("structure", "table")]
    if st:
        print(f"STRUCT: {len(st)} markdown structure issue(s):")
        for f in st:
            print(f"  L{f['line']} [{f['risk']}]: {f['snippet']}")
    if lb:
        print(f"LINEBREAK: {len(lb)} potential premature line-break risk(s):")
        for f in lb[:80]:
            print(
                f"  L{f['line']} [{f['kind']}] {f['risk']}: "
                f"'{f['match']}' ...{f['snippet']}...",
            )
        if len(lb) > 80:
            print(f"  … and {len(lb) - 80} more")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
