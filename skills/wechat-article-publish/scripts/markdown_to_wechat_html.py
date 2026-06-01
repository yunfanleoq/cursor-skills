#!/usr/bin/env python3
"""Convert markdown article to WeChat-compatible HTML.

WeChat 编辑器对 ul/li、blockquote 支持较差，易出空 bullet、引用截断。
本转换器采用 section + p 段落式排版（参考主流公众号排版习惯）。
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

P = "margin:12px 8px;line-height:1.75;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;font-size:16px;color:#3f3f3f;"
H1 = "font-size:22px;font-weight:bold;color:#0F4C81;margin:24px 8px 12px;line-height:1.4;"
H2 = "font-size:20px;font-weight:bold;color:#fff;background:#0F4C81;padding:10px 16px;margin:32px 8px 16px;border-radius:8px;text-align:center;line-height:1.4;"
H3 = "font-size:18px;font-weight:bold;color:#0F4C81;margin:24px 8px 10px;line-height:1.4;"
QUOTE = "margin:16px 8px;padding:12px 16px;background:#f7f9fc;border-left:4px solid #0F4C81;line-height:1.75;font-size:16px;color:#555;"
LI = "margin:6px 8px;line-height:1.75;font-size:16px;color:#3f3f3f;padding-left:4px;"


def md_to_wechat_html(md: str, base_dir: Path) -> str:
    lines = md.splitlines()
    out: list[str] = []
    in_code = False
    in_table = False
    list_buf: list[str] = []

    def flush_list():
        nonlocal list_buf
        if not list_buf:
            return
        for item in list_buf:
            if not item.strip():
                continue
            out.append(
                f'<p style="{LI}"><span style="color:#0F4C81;font-weight:bold;margin-right:6px;">•</span>{inline(item)}</p>'
            )
        list_buf = []

    def inline(text: str) -> str:
        text = html.escape(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(
            r"`(.+?)`",
            r'<code style="background:#f6f8fa;padding:2px 4px;border-radius:3px;font-size:90%;">\1</code>',
            text,
        )
        return text

    def block(text: str) -> str:
        return f'<p style="{P}">{inline(text)}</p>'

    for raw in lines:
        line = raw.rstrip()

        if line.strip().startswith("```"):
            flush_list()
            in_code = not in_code
            if in_code:
                out.append(
                    '<section style="margin:12px 8px;padding:12px;background:#0d1117;border-radius:8px;overflow-x:auto;">'
                    '<pre style="color:#c9d1d9;font-size:13px;line-height:1.5;margin:0;white-space:pre-wrap;word-break:break-all;">'
                )
            else:
                out.append("</pre></section>")
            continue
        if in_code:
            out.append(html.escape(line) + "\n")
            continue

        if not line.strip():
            flush_list()
            continue

        if line.startswith("# "):
            flush_list()
            out.append(f'<p style="{H1}">{inline(line[2:].strip())}</p>')
            continue
        if line.startswith("## "):
            flush_list()
            out.append(f'<section style="{H2}">{inline(line[3:].strip())}</section>')
            continue
        if line.startswith("### "):
            flush_list()
            out.append(f'<p style="{H3}">{inline(line[4:].strip())}</p>')
            continue

        img = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
        if img:
            flush_list()
            alt, src = img.group(1), img.group(2)
            img_path = (base_dir / src).resolve()
            if img_path.exists():
                out.append(
                    f'<p style="text-align:center;margin:16px 8px;">'
                    f'<img data-local-path="{html.escape(str(img_path))}" alt="{html.escape(alt)}" '
                    f'style="max-width:100%;border-radius:8px;display:block;margin:0 auto;" />'
                    f"</p>"
                )
            continue

        if line.strip().startswith(">"):
            flush_list()
            quote = line.strip().lstrip(">").strip()
            out.append(f'<section style="{QUOTE}">{inline(quote)}</section>')
            continue

        if line.strip().startswith("|") and "|" in line:
            flush_list()
            if not in_table:
                in_table = True
                out.append(
                    '<section style="margin:12px 8px;overflow-x:auto;">'
                    '<table style="width:100%;border-collapse:collapse;font-size:14px;word-break:break-word;">'
                )
            if set(line.replace("|", "").strip()) <= {"-", " "}:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            row = "".join(
                f'<td style="border:1px solid #e5e5e5;padding:8px;vertical-align:top;">{inline(c)}</td>'
                for c in cells
            )
            out.append(f"<tr>{row}</tr>")
            continue
        if in_table:
            out.append("</table></section>")
            in_table = False

        m = re.match(r"^[-*]\s+(.*)", line.strip())
        if m:
            list_buf.append(m.group(1))
            continue

        m = re.match(r"^\d+\.\s+(.*)", line.strip())
        if m:
            list_buf.append(m.group(1))
            continue

        if line.strip() == "---":
            flush_list()
            out.append('<p style="margin:24px 8px;border-top:1px solid #eee;height:0;font-size:0;">&nbsp;</p>')
            continue

        flush_list()
        out.append(block(line.strip()))

    flush_list()
    if in_table:
        out.append("</table></section>")

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Markdown -> WeChat HTML")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()

    md = args.input.read_text(encoding="utf-8")
    html_content = md_to_wechat_html(md, args.input.parent)
    out = args.output or args.input.with_suffix(".wechat.html")
    out.write_text(html_content, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
