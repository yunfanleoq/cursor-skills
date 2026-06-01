#!/usr/bin/env python3
"""Extract article text from WeChat / web MHTML saved pages."""

from __future__ import annotations

import argparse
import html
import quopri
import re
from pathlib import Path


def decode_qp(s: str) -> str:
    s = s.replace("=\n", "").replace("=\r\n", "")
    try:
        return quopri.decodestring(s.encode("latin-1")).decode("utf-8")
    except Exception:
        return s


def extract_mhtml_text(mhtml_path: Path) -> str:
    raw = mhtml_path.read_bytes().decode("utf-8", errors="replace")

    m = re.search(r'id=3D"js_content".*?</div>\s*<div id=3D"js_tags"', raw, re.DOTALL)
    if not m:
        m = re.search(r'id="js_content".*?</div>\s*<div id="js_tags"', raw, re.DOTALL)
    content = m.group(0) if m else raw

    parts = re.findall(r'<span leaf(?:=3D""|="")>(.*?)</span>', content, re.DOTALL)
    decoded: list[str] = []
    for part in parts:
        d = decode_qp(part)
        d = re.sub(r"<[^>]+>", "", d)
        d = html.unescape(d.strip())
        if d and d not in ("&nbsp;", " "):
            decoded.append(d)

    h2s = re.findall(r'<h2[^>]*>.*?<span leaf(?:=3D""|="")>(.*?)</span>', content, re.DOTALL)
    for h in h2s:
        t = decode_qp(re.sub(r"<[^>]+>", "", h))
        t = html.unescape(t.strip())
        if t and t not in decoded:
            decoded.insert(0, f"## {t}")

    return "\n".join(decoded)


def main():
    parser = argparse.ArgumentParser(description="Extract text from MHTML")
    parser.add_argument("input", type=Path, help="Input .mhtml file")
    parser.add_argument("-o", "--output", type=Path, help="Output .txt file")
    args = parser.parse_args()

    text = extract_mhtml_text(args.input)
    out = args.output or args.input.with_suffix(".txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Extracted {len(text.splitlines())} lines -> {out}")


if __name__ == "__main__":
    main()
