#!/usr/bin/env python3
"""WeChat Article Agent Server — Webhook + Cron + REST API for C++ / any HTTP client."""

from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from wechat_pipeline_lib import (  # noqa: E402
    JobStatus,
    PipelineRequest,
    PipelineResult,
    result_to_dict,
    run_pipeline,
)

SERVER_DIR = Path(__file__).resolve().parent
DATA_DIR = SERVER_DIR / "data"
JOBS_DIR = DATA_DIR / "jobs"
CONFIG_PATH = SERVER_DIR / "config.json"

app = FastAPI(
    title="WeChat Article Agent",
    description="资料 → 文章 → 微信草稿，支持 Webhook / 定时任务 / C++ HTTP 调用",
    version="1.0.0",
)
executor = ThreadPoolExecutor(max_workers=2)
_scheduler = None
_lock = threading.Lock()


class JobCreateBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=64)
    digest: str = ""
    author: str = ""
    publish: bool = False
    markdown_path: Optional[str] = None
    markdown_content: Optional[str] = None
    source_path: Optional[str] = None
    source_type: str = "auto"
    thumb_path: Optional[str] = None
    generate_article: bool = False
    wechat_config: Optional[str] = None
    output_dir: Optional[str] = None
    async_mode: bool = True


class ScheduleItem(BaseModel):
    id: str = ""
    enabled: bool = True
    cron: str = Field(..., description="APScheduler cron，如 0 9 * * 1 表示每周一 9:00")
    title: str
    digest: str = ""
    markdown_path: Optional[str] = None
    source_path: Optional[str] = None
    thumb_path: Optional[str] = None
    publish: bool = False
    generate_article: bool = False


def load_server_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    example = SERVER_DIR / "config.example.json"
    if example.exists():
        return json.loads(example.read_text(encoding="utf-8"))
    return {"host": "0.0.0.0", "port": 8780, "api_key": "", "schedules": []}


def save_job(result: PipelineResult) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    path = JOBS_DIR / f"{result.job_id}.json"
    path.write_text(json.dumps(result_to_dict(result), ensure_ascii=False, indent=2), encoding="utf-8")


def load_job(job_id: str) -> Optional[Dict[str, Any]]:
    path = JOBS_DIR / f"{job_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(JOBS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for f in files[:limit]:
        out.append(json.loads(f.read_text(encoding="utf-8")))
    return out


def verify_api_key(x_api_key: str = Header(default="")) -> None:
    cfg = load_server_config()
    expected = cfg.get("api_key") or os.environ.get("WECHAT_AGENT_API_KEY", "")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid X-API-Key")


def _body_to_request(body: JobCreateBody) -> PipelineRequest:
    return PipelineRequest(
        title=body.title,
        digest=body.digest,
        author=body.author,
        publish=body.publish,
        markdown_path=body.markdown_path,
        markdown_content=body.markdown_content,
        source_path=body.source_path,
        source_type=body.source_type,
        thumb_path=body.thumb_path,
        generate_article=body.generate_article,
        wechat_config=body.wechat_config,
        output_dir=body.output_dir,
    )


def _execute_job(job_id: str, req: PipelineRequest) -> PipelineResult:
    pending = PipelineResult(
        job_id=job_id,
        status=JobStatus.RUNNING,
        title=req.title,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    save_job(pending)
    result = run_pipeline(req, job_id=job_id)
    save_job(result)
    return result


@app.get("/api/health")
def health():
    cfg = load_server_config()
    return {
        "ok": True,
        "service": "wechat-article-agent",
        "version": "1.0.0",
        "scheduler": _scheduler is not None,
        "schedules": len(cfg.get("schedules", [])),
    }


@app.get("/api/v1/jobs", dependencies=[Depends(verify_api_key)])
def get_jobs(limit: int = 50):
    return {"jobs": list_jobs(limit=limit)}


@app.get("/api/v1/jobs/{job_id}", dependencies=[Depends(verify_api_key)])
def get_job(job_id: str):
    job = load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.post("/api/v1/jobs", dependencies=[Depends(verify_api_key)])
def create_job(body: JobCreateBody, background_tasks: BackgroundTasks):
    job_id = uuid.uuid4().hex[:12]
    req = _body_to_request(body)

    if not body.async_mode:
        result = _execute_job(job_id, req)
        if result.status == JobStatus.FAILED:
            raise HTTPException(status_code=500, detail=result.error)
        return result_to_dict(result)

    pending = PipelineResult(
        job_id=job_id,
        status=JobStatus.PENDING,
        title=req.title,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    save_job(pending)

    def _run():
        _execute_job(job_id, req)

    background_tasks.add_task(_run)
    return {"job_id": job_id, "status": "pending", "poll": f"/api/v1/jobs/{job_id}"}


@app.post("/api/v1/webhook", dependencies=[Depends(verify_api_key)])
def webhook(body: JobCreateBody, background_tasks: BackgroundTasks):
    """Alias for external triggers (GitHub Actions, 企业微信, C++ platform)."""
    body.async_mode = True
    return create_job(body, background_tasks)


@app.get("/api/v1/schedules", dependencies=[Depends(verify_api_key)])
def get_schedules():
    cfg = load_server_config()
    return {"schedules": cfg.get("schedules", [])}


def _run_scheduled(item: Dict[str, Any]) -> None:
    req = PipelineRequest(
        title=item["title"],
        digest=item.get("digest", ""),
        publish=item.get("publish", False),
        markdown_path=item.get("markdown_path"),
        source_path=item.get("source_path"),
        thumb_path=item.get("thumb_path"),
        generate_article=item.get("generate_article", False),
    )
    job_id = f"sched-{item.get('id', 'auto')}-{uuid.uuid4().hex[:6]}"
    _execute_job(job_id, req)


def setup_scheduler() -> None:
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        return

    cfg = load_server_config()
    schedules = [s for s in cfg.get("schedules", []) if s.get("enabled", True)]
    if not schedules:
        return

    _scheduler = BackgroundScheduler()
    for item in schedules:
        parts = item["cron"].split()
        if len(parts) != 5:
            continue
        minute, hour, day, month, day_of_week = parts
        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
        )
        _scheduler.add_job(_run_scheduled, trigger, args=[item], id=item.get("id") or item["title"])
    _scheduler.start()


@app.on_event("startup")
def on_startup():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    setup_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def main():
    import uvicorn

    cfg = load_server_config()
    host = os.environ.get("WECHAT_AGENT_HOST", cfg.get("host", "0.0.0.0"))
    port = int(os.environ.get("WECHAT_AGENT_PORT", cfg.get("port", 8780)))
    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
