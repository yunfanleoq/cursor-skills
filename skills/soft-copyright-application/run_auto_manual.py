#!/usr/bin/env python3
"""One-shot: start servers (optional), seed demo, capture screenshots, build manual MD/PDF."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from auto_manual.build_manual import build_manual_markdown  # noqa: E402
from auto_manual.capture import run_capture  # noqa: E402
from auto_manual.server import (  # noqa: E402
    run_seed_demo,
    start_servers,
    stop_process,
    wait_for_servers,
)


def _load_scope(scope_path: Path) -> dict:
    import yaml

    return yaml.safe_load(scope_path.read_text(encoding="utf-8")) or {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto capture screenshots and build soft-copyright manual")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--scenario", type=Path, default="soft-copyright/automation/scenario.yaml")
    parser.add_argument("--scope", type=Path, default="soft-copyright/scope.yaml")
    parser.add_argument("--start-servers", action="store_true", help="Start backend+frontend if not up")
    parser.add_argument("--seed-demo", action="store_true", help="Run seed_demo before capture")
    parser.add_argument("--no-capture", action="store_true", help="Only build MD from existing screenshots")
    parser.add_argument("--no-pdf", action="store_true", help="Skip operation manual PDF generation")
    parser.add_argument("--headed", action="store_true", help="Show browser window during capture")
    args = parser.parse_args()

    root = args.project_root.resolve()
    scenario_path = args.scenario if args.scenario.is_absolute() else root / args.scenario
    scope_path = args.scope if args.scope.is_absolute() else root / args.scope
    manual_dir = root / "soft-copyright" / "manual"
    screenshots_dir = manual_dir / "screenshots"
    manual_md = manual_dir / "操作说明书.md"

    if not scenario_path.is_file():
        print(f"Scenario not found: {scenario_path}", file=sys.stderr)
        return 1

    backend_proc = None
    frontend_proc = None
    started = False

    try:
        fe_url = "http://127.0.0.1:5173"
        be_url = "http://127.0.0.1:8000/api/health"

        if args.start_servers:
            print("Starting backend and frontend...")
            backend_proc, frontend_proc = start_servers(root)
            started = True
            wait_for_servers(fe_url, be_url, timeout_sec=120)
            print("Servers ready.")

        if args.seed_demo:
            print("Seeding demo data...")
            run_seed_demo(root)

        capture_results = []
        if not args.no_capture:
            print("Capturing screenshots with Playwright...")
            capture_results = asyncio.run(
                run_capture(
                    root,
                    scenario_path,
                    screenshots_dir,
                    headless=not args.headed,
                )
            )
            ok = sum(1 for r in capture_results if r.get("ok"))
            print(f"Captured {ok}/{len(capture_results)} screenshots.")
            failed = [r for r in capture_results if not r.get("ok")]
            if failed:
                print("Failed steps:", json.dumps(failed, ensure_ascii=False, indent=2), file=sys.stderr)

        print("Building 操作说明书.md...")
        build_manual_markdown(root, scope_path, scenario_path, manual_md, capture_results)
        print(f"Written: {manual_md}")

        if not args.no_pdf:
            gen_pdf = SCRIPT_DIR / "generate_manual_pdf.py"
            subprocess.run(
                [
                    sys.executable,
                    str(gen_pdf),
                    "--project-root",
                    str(root),
                    "--scope",
                    str(scope_path.relative_to(root) if scope_path.is_relative_to(root) else scope_path),
                    "--manual",
                    str(manual_md),
                ],
                check=False,
            )

        print("Done. Review screenshots and export final PDF via Word per pdf-format-spec.md §三.")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        if started:
            print("Stopping started servers...")
            stop_process(frontend_proc)
            stop_process(backend_proc)


if __name__ == "__main__":
    raise SystemExit(main())
