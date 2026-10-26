#!/usr/bin/env python3
"""Reusable WeChat article pipeline: source -> markdown -> HTML -> draft."""

from __future__ import annotations

import html as html_lib
import json
import os
import quopri
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from markdown_to_wechat_html import md_to_wechat_html  # noqa: E402
from wechat_publish import WeChatPublisher, load_config, resolve_draft_options  # noqa: E402


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class PipelineRequest:
    title: str
    digest: str = ""
    author: str = ""
    publish: bool = False
    markdown_path: str | None = None
    markdown_content: str | None = None
    source_path: str | None = None
    source_type: str = "auto"  # auto | markdown | mhtml | text | url
    thumb_path: str | None = None
    generate_article: bool = False
    wechat_config: str | None = None
    output_dir: str | None = None
    open_comment: bool | None = None
    fans_only_comment: bool | None = None
    content_source_url: str | None = None


@dataclass
class PipelineResult:
    job_id: str
    status: JobStatus
    title: str
    markdown_path: str | None = None
    html_path: str | None = None
    media_id: str | None = None
    publish_id: str | None = None
    error: str | None = None
    started_at: str = ""
    finished_at: str = ""
    steps: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_path(raw: str | None, base: Path) -> Path | None:
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = base / p
    return p.resolve()


def detect_source_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".md", ".markdown"}:
        return "markdown"
    if ext == ".mhtml":
        return "mhtml"
    if ext in {".txt", ".text"}:
        return "text"
    if ext in {".html", ".htm"}:
        return "html"
    return "text"


def extract_mhtml_text(mhtml_path: Path) -> str:
    raw = mhtml_path.read_bytes().decode("utf-8", errors="replace")

    def decode_qp(s: str) -> str:
        s = s.replace("=\n", "").replace("=\r\n", "")
        try:
            return quopri.decodestring(s.encode("latin-1")).decode("utf-8")
        except Exception:
            return s

    m = re.search(r'id=3D"js_content".*?</div>\s*<div id=3D"js_tags"', raw, re.DOTALL)
    if not m:
        m = re.search(r'id="js_content".*?</div>\s*<div id="js_tags"', raw, re.DOTALL)
    content = m.group(0) if m else raw

    parts = re.findall(r'<span leaf(?:=3D""|="")>(.*?)</span>', content, re.DOTALL)
    decoded: list[str] = []
    for part in parts:
        d = decode_qp(part)
        d = re.sub(r"<[^>]+>", "", d)
        d = html_lib.unescape(d.strip())
        if d and d not in ("&nbsp;", " "):
            decoded.append(d)

    h2s = re.findall(r'<h2[^>]*>.*?<span leaf(?:=3D""|="")>(.*?)</span>', content, re.DOTALL)
    for h in h2s:
        t = decode_qp(re.sub(r"<[^>]+>", "", h))
        t = html_lib.unescape(t.strip())
        if t and t not in decoded:
            decoded.insert(0, f"## {t}")

    return "\n".join(decoded)


def load_source_text(source_path: Path, source_type: str) -> str:
    st = source_type if source_type != "auto" else detect_source_type(source_path)
    if st == "mhtml":
        return extract_mhtml_text(source_path)
    if st in {"text", "html", "markdown"}:
        return source_path.read_text(encoding="utf-8")
    raise ValueError(f"unsupported source_type={st} for {source_path}")


def generate_markdown_from_source(
    source_text: str,
    title: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> str:
    """Optional LLM step: turn raw source into科普 markdown."""
    import requests

    key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("generate_article=true 但未配置 OPENAI_API_KEY / DEEPSEEK_API_KEY")

    url = (base_url or os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model_name = model or os.environ.get("LLM_MODEL") or "gpt-4o-mini"
    prompt = (
        "你是技术科普作者。根据以下资料，写一篇面向技术爱好者的微信公众号科普文章。\n"
        "要求：结构清晰（概念、知识地图、模式详解、选型建议、总结）；通俗易懂；"
        "注明参考来源；不要大段照搬原文代码；使用 Markdown 格式；"
        f"标题用 # {title}\n\n---\n\n{source_text[:120000]}"
    )
    resp = requests.post(
        f"{url}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        },
        timeout=180,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    if not content.strip().startswith("#"):
        content = f"# {title}\n\n{content}"
    return content


def run_pipeline(req: PipelineRequest, job_id: str | None = None) -> PipelineResult:
    job_id = job_id or uuid.uuid4().hex[:12]
    result = PipelineResult(
        job_id=job_id,
        status=JobStatus.RUNNING,
        title=req.title,
        started_at=_now(),
    )

    try:
        out_dir = Path(req.output_dir) if req.output_dir else ROOT / "articles"
        out_dir.mkdir(parents=True, exist_ok=True)

        md_path: Path | None = None
        md_content: str | None = None

        if req.markdown_content:
            md_content = req.markdown_content
            result.steps.append("use_inline_markdown")
        elif req.markdown_path:
            md_path = _resolve_path(req.markdown_path, ROOT)
            if not md_path or not md_path.exists():
                raise FileNotFoundError(f"markdown not found: {req.markdown_path}")
            md_content = md_path.read_text(encoding="utf-8")
            result.steps.append(f"load_markdown:{md_path.name}")
        elif req.source_path:
            src = _resolve_path(req.source_path, ROOT)
            if not src or not src.exists():
                raise FileNotFoundError(f"source not found: {req.source_path}")
            source_text = load_source_text(src, req.source_type)
            result.steps.append(f"extract_source:{src.name}")
            if req.generate_article:
                md_content = generate_markdown_from_source(source_text, req.title)
                result.steps.append("llm_generate_markdown")
            else:
                slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", req.title).strip("-")[:40] or "article"
                md_path = out_dir / f"{slug}-auto.md"
                md_path.write_text(f"# {req.title}\n\n{source_text}", encoding="utf-8")
                md_content = md_path.read_text(encoding="utf-8")
                result.steps.append(f"wrap_source_as_markdown:{md_path.name}")
        else:
            raise ValueError("必须提供 markdown_path、markdown_content 或 source_path 之一")

        if md_content and not md_path:
            slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", req.title).strip("-")[:40] or "article"
            md_path = out_dir / f"{slug}.md"
            md_path.write_text(md_content, encoding="utf-8")
            result.steps.append(f"write_markdown:{md_path.name}")

        assert md_path is not None
        result.markdown_path = str(md_path)

        html_content = md_to_wechat_html(md_path.read_text(encoding="utf-8"), md_path.parent)
        html_path = md_path.with_suffix(".wechat.html")
        html_path.write_text(html_content, encoding="utf-8")
        result.html_path = str(html_path)
        result.steps.append("convert_wechat_html")

        cfg_path = Path(req.wechat_config) if req.wechat_config else Path.home() / ".cursor" / "wechat-publish.json"
        cfg = load_config(cfg_path if cfg_path.exists() else None)
        appid, secret = cfg.get("appid"), cfg.get("secret")
        author = req.author or cfg.get("author", "")
        if not appid or not secret:
            raise RuntimeError("未配置微信凭据 (~/.cursor/wechat-publish.json)")

        publisher = WeChatPublisher(appid, secret)
        body = publisher.replace_local_images(html_path.read_text(encoding="utf-8"))

        thumb = _resolve_path(req.thumb_path, ROOT)
        if not thumb or not thumb.exists():
            imgs = re.findall(r'data-local-path="([^"]+)"', html_path.read_text(encoding="utf-8"))
            thumb = Path(imgs[0]) if imgs else None
        if not thumb or not thumb.exists():
            raise RuntimeError("未找到封面图，请指定 thumb_path")

        thumb_id = publisher.upload_thumb(thumb)
        result.steps.append("upload_thumb")

        draft_opts = resolve_draft_options(
            cfg,
            open_comment=req.open_comment,
            fans_only_comment=req.fans_only_comment,
            content_source_url=req.content_source_url,
        )
        media_id = publisher.create_draft(
            req.title,
            author,
            req.digest,
            body,
            thumb_id,
            content_source_url=str(draft_opts["content_source_url"]),
            open_comment=bool(draft_opts["open_comment"]),
            fans_only_comment=bool(draft_opts["fans_only_comment"]),
        )
        result.media_id = media_id
        result.steps.append("create_draft")

        if req.publish:
            pub = publisher.publish_draft(media_id)
            result.publish_id = pub.get("publish_id")
            result.steps.append("submit_publish")

        result.status = JobStatus.SUCCEEDED
    except Exception as e:
        result.status = JobStatus.FAILED
        result.error = str(e)
    finally:
        result.finished_at = _now()

    return result


def result_to_dict(result: PipelineResult) -> dict[str, Any]:
    d = asdict(result)
    d["status"] = result.status.value
    return d
