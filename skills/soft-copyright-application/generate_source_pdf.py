#!/usr/bin/env python3
"""Generate CPCC-compliant source code identification PDF (60 pages typical)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("Install dependency: py -3.12 -m pip install fpdf2", file=sys.stderr)
    raise

# Reuse extraction logic
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from extract_source_pages import (  # noqa: E402
    build_concat,
    collect_files,
    effective_lines,
    extract_front_back,
    load_scope,
    paginate,
)


def find_cjk_font() -> Path | None:
  candidates = [
      Path(r"C:\Windows\Fonts\msyh.ttc"),
      Path(r"C:\Windows\Fonts\msyhbd.ttc"),
      Path(r"C:\Windows\Fonts\simsun.ttc"),
      Path(r"C:\Windows\Fonts\simhei.ttf"),
      "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
      "/System/Library/Fonts/PingFang.ttc",
  ]
  for p in candidates:
      if Path(p).exists():
          return Path(p)
  return None


class SourcePDF(FPDF):
    def __init__(
        self,
        header_left: str,
        footer_center: str,
        total_pages: int,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.header_left = header_left
        self.footer_center = footer_center
        self.total_pages = total_pages
        self.cjk_font = "CJK"

    def header(self) -> None:
        self.set_font(self.cjk_font, size=8)
        self.set_y(8)
        self.cell(0, 5, self.header_left, align="L")
        self.set_y(8)
        self.cell(0, 5, f"第 {self.page_no()} 页 共 {self.total_pages} 页", align="R")
        self.ln(10)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(self.cjk_font, size=8)
        self.cell(0, 8, self.footer_center, align="C")


def write_code_page(pdf: SourcePDF, page_lines: list[str], font_name: str) -> None:
    pdf.add_page()
    pdf.set_font(font_name, size=9)
    # 50 行铺满可打印区域（约 22mm 顶 ~ 282mm 底）
    body_top = pdf.get_y()
    body_bottom = 282.0
    n = max(1, len(page_lines))
    line_h = (body_bottom - body_top) / n
    line_h = max(4.8, min(line_h, 5.4))
    pdf.set_xy(pdf.l_margin, body_top)
    for line in page_lines:
        safe = line.replace("\t", "    ")[:120]
        pdf.cell(0, line_h, safe, new_x="LMARGIN", new_y="NEXT")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--scope", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--input-front", type=Path, help="Optional pre-built front txt")
    parser.add_argument("--input-back", type=Path, help="Optional pre-built back txt")
    args = parser.parse_args()

    root = args.project_root.resolve()
    scope_path = args.scope
    if scope_path and not scope_path.is_absolute():
        scope_path = root / scope_path
    scope = load_scope(scope_path)

    sw = scope.get("software", {})
    ap = scope.get("applicant", {})
    sc = scope.get("source_code", {})
    red = scope.get("redaction", {})
    out_cfg = scope.get("output", {})
    pdf_cfg = scope.get("pdf", {})

    full_name = sw.get("full_name", "软件全称")
    version = sw.get("version", "V1.0")
    applicant_name = ap.get("name", "著作权人全称")
    header_left = pdf_cfg.get("source_header", f"{full_name} {version}")
    label = pdf_cfg.get("source_label", "源程序")
    header_left = f"{header_left} {label}".strip()

    lines_per_page = int(sc.get("lines_per_page", 50))
    pages_front = int(sc.get("pages_front", 30))
    pages_back = int(sc.get("pages_back", 30))

    if args.input_front and args.input_back:
        # Parse txt pages marked by --- Page N ---
        def load_pages(path: Path) -> list[list[str]]:
            text = path.read_text(encoding="utf-8")
            pages: list[list[str]] = []
            current: list[str] = []
            for line in text.splitlines():
                if line.startswith("--- Page "):
                    if current:
                        pages.append(current)
                        current = []
                    continue
                if line.startswith("---") and "Page" in line:
                    continue
                current.append(line)
            if current:
                pages.append(current)
            return pages

        front_pages = load_pages(args.input_front)
        back_pages = load_pages(args.input_back)
    else:
        extensions = set(sc.get("extensions", ["py", "vue", "ts"]))
        exclude_dirs = set(sc.get("exclude_dirs", []))
        exclude_globs = tuple(sc.get("exclude_globs", ()))
        priority_paths = sc.get("priority_paths", [])
        files = collect_files(root, extensions, exclude_dirs, exclude_globs, priority_paths)
        all_lines, _ = build_concat(
            root,
            files,
            red.get("patterns", []),
            red.get("replace_with", "REDACTED"),
        )
        eff = effective_lines(all_lines)
        pages = paginate(eff, lines_per_page)
        front_pages, back_pages = extract_front_back(pages, pages_front, pages_back)
        if not back_pages and len(pages) <= pages_front + pages_back:
            back_pages = []

    submit_pages = front_pages + back_pages
    if not submit_pages:
        print("No pages to write", file=sys.stderr)
        return 1

    total = len(submit_pages)
    cjk_path = find_cjk_font()
    if not cjk_path:
        print("No CJK font found (Windows: msyh.ttc). Install or set pdf.cjk_font_path in scope.yaml", file=sys.stderr)
        return 1

    pdf = SourcePDF(
        header_left=header_left,
        footer_center=applicant_name,
        total_pages=total,
        orientation="P",
        unit="mm",
        format="A4",
    )
    pdf.set_auto_page_break(auto=False)
    pdf.add_font("CJK", "", str(cjk_path))
    code_font = "Courier"
    try:
        pdf.add_font("Courier", "", "cour.ttf")
    except Exception:
        code_font = "CJK"

    for page in submit_pages:
        write_code_page(pdf, page, code_font)

    out_dir = args.output or Path(out_cfg.get("dir", "soft-copyright/output"))
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    out_name = pdf_cfg.get("source_filename", f"{full_name}{version}-源程序.pdf")
    for ch in '<>:"/\\|?*':
        out_name = out_name.replace(ch, "_")
    out_path = out_dir / out_name
    pdf.output(str(out_path))

    meta = {
        "path": str(out_path),
        "pages": total,
        "header": header_left,
        "footer": applicant_name,
        "lines_per_page": lines_per_page,
    }
    (out_dir / "source_pdf_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
