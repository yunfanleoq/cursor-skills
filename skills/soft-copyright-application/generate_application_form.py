#!/usr/bin/env python3
"""Generate copyright center application form fields (step 4) from scope.yaml."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

# reuse scan logic from sibling script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_source_pages import load_scope, scan_project  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
VIEWER_TEMPLATE = SKILL_DIR / "scripts" / "application_form_viewer" / "index.html"


def configure_stdio_utf8() -> None:
    """Avoid mojibake when printing Chinese on Windows consoles."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass

FIELD_SPECS: list[dict[str, Any]] = [
    {"id": "hardware_dev", "label": "开发的硬件环境", "max": 50, "group": "环境"},
    {"id": "hardware_run", "label": "运行的硬件环境", "max": 50, "group": "环境"},
    {"id": "os_dev", "label": "开发该软件的操作系统", "max": 50, "group": "环境"},
    {"id": "dev_tools", "label": "软件开发环境 / 开发工具", "max": 50, "group": "环境"},
    {"id": "os_run", "label": "该软件的运行平台 / 操作系统", "max": 50, "group": "环境"},
    {"id": "support_env", "label": "软件运行支撑环境 / 支持软件", "max": 50, "group": "环境"},
    {"id": "languages", "label": "编程语言", "max": 120, "group": "语言", "type": "languages"},
    {"id": "source_lines", "label": "源程序量（行）", "max": None, "group": "规模", "type": "number"},
    {"id": "purpose", "label": "开发目的", "max": 50, "group": "说明"},
    {"id": "field", "label": "面向领域 / 行业", "max": 50, "group": "说明"},
    {"id": "main_functions", "label": "软件的主要功能", "min": 500, "max": 1000, "group": "说明", "type": "textarea"},
    {"id": "tech_tags", "label": "软件的技术特点（标签勾选）", "max": None, "group": "说明", "type": "tags"},
    {"id": "technical_features", "label": "软件的技术特点（补充说明）", "max": 100, "group": "说明", "type": "textarea"},
]


def _char_len(text: str) -> int:
    return len(text.replace("\r", "").replace("\n", ""))


def _default_main_functions(scope: dict[str, Any]) -> str:
    custom = scope.get("form_fields", {}).get("main_functions")
    if custom:
        return str(custom).strip()
    name = scope.get("software", {}).get("full_name", "本软件")
    return (
        f"1. 案件管理与审查意见（OA）文档上传解析\n"
        f"2. 多智能体协同的答复策略分析与陈述书辅助撰写\n"
        f"3. 权利要求分解、特征对比与创造性论证\n"
        f"4. 知识库检索增强（RAG）与法规案例引用\n"
        f"5. 答复期限监控与待办提醒\n"
        f"6. 代理人工作台与流程管理\n"
        f"7. 用户权限、字典与系统配置管理"
    )


def _default_technical_features(scope: dict[str, Any]) -> str:
    custom = scope.get("form_fields", {}).get("technical_features")
    if custom:
        return str(custom).strip()
    return (
        "采用B/S架构，FastAPI+Vue3+LLM多智能体协同，"
        "支持OA解析、权利要求分解、RAG检索及陈述书答复辅助"
    )


def _default_tech_tags(scope: dict[str, Any]) -> list[str]:
    tags = scope.get("form_fields", {}).get("tech_tags")
    if tags:
        return [str(t) for t in tags]
    return ["人工智能软件"]


def _build_steps(scope: dict[str, Any]) -> list[dict[str, Any]]:
    sw = scope.get("software", {})
    dev = scope.get("development", {})
    own = scope.get("ownership", {})
    app = scope.get("applicant", {})
    pdf = scope.get("pdf", {})
    published = dev.get("published", False)

    ownership_map = {
        "independent": "单独开发",
        "cooperative": "合作开发",
        "commissioned": "委托开发",
        "task": "下达任务开发",
    }
    applicant_type_map = {
        "enterprise": "企业法人",
        "institution": "事业法人",
        "individual": "自然人",
    }

    return [
        {
            "step": 2,
            "title": "软件申请信息",
            "fields": [
                {"label": "权利取得方式", "value": "原始取得", "type": "select"},
                {"label": "软件全称", "value": sw.get("full_name", ""), "type": "text"},
                {"label": "软件简称", "value": sw.get("short_name", ""), "type": "text"},
                {"label": "版本号", "value": sw.get("version", ""), "type": "text"},
                {"label": "权利范围", "value": "全部权利", "type": "select"},
            ],
        },
        {
            "step": 3,
            "title": "软件开发信息",
            "fields": [
                {"label": "软件分类", "value": "应用软件", "type": "select"},
                {"label": "软件说明", "value": "原创", "type": "select"},
                {"label": "开发方式", "value": ownership_map.get(own.get("type", "independent"), "单独开发"), "type": "select"},
                {"label": "开发完成日期", "value": dev.get("completed_date", ""), "type": "date"},
                {"label": "发表状态", "value": "已发表" if published else "未发表", "type": "select"},
                {"label": "首次发表日期", "value": dev.get("first_publish_date", "") if published else "（未发表留空）", "type": "date"},
                {"label": "著作权人类型", "value": applicant_type_map.get(app.get("type", "enterprise"), "企业法人"), "type": "select"},
                {"label": "著作权人名称", "value": app.get("name", ""), "type": "text"},
                {"label": "证件类型", "value": app.get("id_type", ""), "type": "text"},
                {"label": "证件号码", "value": app.get("id_number", ""), "type": "text"},
            ],
        },
        {
            "step": 4,
            "title": "软件功能与特点",
            "note": "详见下方字段卡片，逐项复制粘贴",
        },
        {
            "step": 5,
            "title": "鉴别材料上传",
            "fields": [
                {"label": "程序鉴别材料", "value": "一般交存", "type": "select"},
                {"label": "程序 PDF", "value": pdf.get("source_filename", ""), "type": "file"},
                {"label": "文档鉴别材料", "value": "一般交存", "type": "select"},
                {"label": "文档 PDF", "value": pdf.get("manual_filename", ""), "type": "file"},
                {"label": "上传说明", "value": "源程序与文档各上传一份 PDF（前30页+后30页合并）", "type": "hint"},
            ],
        },
    ]


def build_form_data(scope: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    dev = scope.get("development", {})
    form = scope.get("form_fields", {})
    langs = form.get("languages") or dev.get("languages") or []

    values: dict[str, Any] = {
        "hardware_dev": form.get("hardware_dev") or dev.get("hardware_dev", ""),
        "hardware_run": form.get("hardware_run") or dev.get("hardware_run", ""),
        "os_dev": form.get("os_dev") or dev.get("os_dev", ""),
        "dev_tools": form.get("dev_tools") or dev.get("dev_tools", ""),
        "os_run": form.get("os_run") or dev.get("os_run", ""),
        "support_env": form.get("support_env") or dev.get("support_env", ""),
        "languages": langs,
        "source_lines": form.get("source_lines") or stats.get("effective_lines", 0),
        "purpose": form.get("purpose") or dev.get("purpose", ""),
        "field": form.get("field") or dev.get("field", ""),
        "main_functions": _default_main_functions(scope),
        "tech_tags": _default_tech_tags(scope),
        "technical_features": _default_technical_features(scope),
    }

    fields: list[dict[str, Any]] = []
    for spec in FIELD_SPECS:
        fid = spec["id"]
        raw = values[fid]
        if spec.get("type") == "tags":
            buttons = [str(x) for x in (raw or [])]
            display = "、".join(buttons)
            length = _char_len(display)
            value_out = buttons
        elif spec.get("type") == "languages":
            if isinstance(raw, list):
                display = "、".join(str(x) for x in raw)
                buttons = raw
            else:
                display = str(raw)
                buttons = [x.strip() for x in display.replace("，", "、").split("、") if x.strip()]
            length = _char_len(display)
            value_out: Any = {"list": buttons, "text": display}
        elif spec.get("type") == "number":
            display = str(int(raw or 0))
            length = len(display)
            value_out = int(raw or 0)
        else:
            display = str(raw).strip()
            length = _char_len(display)
            value_out = display

        max_len = spec.get("max")
        min_len = spec.get("min")
        if spec.get("type") == "tags":
            ok = bool(value_out)
        elif max_len is None and min_len is None:
            ok = True
        elif min_len and max_len:
            ok = min_len <= length <= max_len
        elif min_len:
            ok = length >= min_len
        else:
            ok = length <= (max_len or 0)

        disp = display
        if spec.get("type") == "languages":
            disp = value_out.get("text", "")
        fields.append({
            **spec,
            "value": value_out,
            "display": disp,
            "length": length,
            "ok": ok,
        })

    software = scope.get("software", {})
    return {
        "generated_at": date.today().isoformat(),
        "form_url": "https://register.ccopyright.com.cn/r11.html#/features",
        "software": {
            "full_name": software.get("full_name", ""),
            "version": software.get("version", ""),
            "short_name": software.get("short_name", ""),
        },
        "applicant": scope.get("applicant", {}),
        "steps": _build_steps(scope),
        "source_stats": {
            "file_count": stats.get("file_count", 0),
            "effective_lines": stats.get("effective_lines", 0),
            "total_lines": stats.get("total_lines", 0),
        },
        "fields": fields,
        "all_ok": all(f["ok"] for f in fields if f.get("max") or f.get("min")),
    }


def write_markdown(data: dict[str, Any], path: Path) -> None:
    sw = data["software"]
    lines = [
        f"# 申请表字段草稿 — 第 4 步「软件功能与特点」",
        "",
        f"**软件**：{sw.get('full_name', '')} {sw.get('version', '')}  ",
        f"**生成日期**：{data.get('generated_at', '')}  ",
        f"**源程序有效行数**：{data['source_stats'].get('effective_lines', 0)}（{data['source_stats'].get('file_count', 0)} 个文件）",
        "",
        "> 在中国版权保护中心在线填报第 4 步逐项复制粘贴。带 ⚠️ 表示超出字数上限，请手工压缩。",
        "",
        "---",
        "",
    ]
    current_group = ""
    for f in data["fields"]:
        if f["group"] != current_group:
            current_group = f["group"]
            lines.extend(["", f"## {current_group}", ""])
        flag = "" if f["ok"] else " ⚠️ 超限"
        max_part = f"/{f['max']}" if f.get("max") else ""
        lines.append(f"### {f['label']}{flag}")
        lines.append("")
        if f.get("type") == "languages":
            lines.append(f"**勾选**：{', '.join(f['value']['list'])}")
            lines.append("")
            lines.append(f"**补充文本**：{f['value']['text']}")
        elif f.get("type") == "number":
            lines.append(f"**{f['display']}** 行")
        else:
            lines.append(f["display"])
        lines.append("")
        lines.append(f"*字数：{f['length']}{max_part}*")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_viewer_html(data: dict[str, Any], path: Path) -> None:
    template = VIEWER_TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False)
    html = template.replace("/*__FORM_DATA__*/", payload)
    path.write_text(html, encoding="utf-8")


def main() -> int:
    configure_stdio_utf8()
    parser = argparse.ArgumentParser(description="Generate application form fields for step 4")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--scope", type=str, default="soft-copyright/scope.yaml")
    parser.add_argument("--output", type=str, default="")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print JSON only (ASCII-escaped) on stdout for PowerShell parsing",
    )
    args = parser.parse_args()

    root = args.project_root.resolve()
    scope_path = root / args.scope
    scope = load_scope(scope_path)
    if not scope:
        print(f"Warning: scope not found or empty: {scope_path}", file=sys.stderr)

    stats = scan_project(root, scope)
    data = build_form_data(scope, stats)

    out_dir = Path(args.output) if args.output else root / scope.get("output", {}).get("dir", "soft-copyright/output")
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "application-form-fields.json"
    md_path = out_dir / "04-申请表字段草稿-第4步.md"
    html_path = out_dir / "application-form-viewer.html"

    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(data, md_path)
    write_viewer_html(data, html_path)

    result = {
        "json": str(json_path),
        "markdown": str(md_path),
        "viewer": str(html_path),
        "all_ok": data["all_ok"],
        "effective_lines": data["source_stats"]["effective_lines"],
        "software_name": data["software"].get("full_name", ""),
        "software_version": data["software"].get("version", ""),
    }

    if args.quiet:
        print(json.dumps(result, ensure_ascii=True))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if not data["all_ok"]:
        over = [f["label"] for f in data["fields"] if not f["ok"]]
        print(f"Warning: fields over limit: {', '.join(over)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
