"""Playwright screenshot capture driven by scenario YAML."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import yaml

from auto_manual.overlay import apply_overlays, clear_overlays


async def run_capture(
    project_root: Path,
    scenario_path: Path,
    screenshots_dir: Path,
    *,
    headless: bool = True,
) -> list[dict[str, Any]]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise SystemExit(
            "Playwright not installed. Run:\n"
            "  py -3.12 -m pip install playwright pyyaml\n"
            "  py -3.12 -m playwright install chromium"
        ) from e

    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8")) or {}
    base_url = scenario.get("base_url", "http://127.0.0.1:5173").rstrip("/")
    auth = scenario.get("auth", {})
    viewport = scenario.get("viewport", {"width": 1440, "height": 900})
    demo_case_id = scenario.get("demo_case_id", "demo-case-woa-001")
    steps = scenario.get("steps", [])
    wait_default = int(scenario.get("wait_after_nav_ms", 1500))

    screenshots_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": int(viewport.get("width", 1440)), "height": int(viewport.get("height", 900))},
            locale="zh-CN",
        )
        page = await context.new_page()
        logged_in = False

        async def do_login() -> None:
            nonlocal logged_in
            await page.goto(f"{base_url}/login", wait_until="networkidle", timeout=60000)
            await page.get_by_placeholder("请输入账号").fill(auth.get("username", "admin"))
            await page.get_by_placeholder("请输入密码").fill(auth.get("password", "Admin@123456"))
            await page.get_by_role("button", name="进入工作台").click()
            await page.wait_for_url("**/cases**", timeout=30000)
            logged_in = True

        async def ensure_logged_in() -> None:
            if not logged_in:
                await do_login()

        async def assert_not_login_page(step_id: str, expected_hint: str = "") -> None:
            if await page.locator(".zone-login-card").count() > 0:
                hint = f" ({expected_hint})" if expected_hint else ""
                raise RuntimeError(f"Step {step_id}: expected app page but got login page{hint}")

        async def shot(rel_path: str, full_page: bool = True) -> Path:
            dest = screenshots_dir / rel_path.replace("/", "\\").replace("\\", "/")
            dest.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(dest), full_page=full_page)
            return dest

        for step in steps:
            sid = step.get("id", "")
            name = step.get("name", sid)
            rel = step.get("screenshot", "")
            action = step.get("action", "navigate")
            wait_ms = int(step.get("wait_ms", wait_default))
            full_page = bool(step.get("full_page", True))
            record: dict[str, Any] = {"id": sid, "name": name, "screenshot": rel, "ok": False}

            try:
                if action == "navigate":
                    path = step.get("path", "/")
                    if not path.startswith("/login"):
                        await ensure_logged_in()
                    await page.goto(f"{base_url}{path}", wait_until="networkidle", timeout=60000)
                    await page.wait_for_timeout(wait_ms)
                    if not path.startswith("/login"):
                        await assert_not_login_page(sid, path)

                elif action == "login":
                    await do_login()
                    await page.wait_for_timeout(wait_ms)

                elif action == "open_demo_workbench":
                    await ensure_logged_in()
                    await page.evaluate(
                        """() => {
                        localStorage.setItem('ipagent.layout.navCollapsed', 'false');
                        localStorage.setItem('ipagent.workbench.leftVisible', 'true');
                        localStorage.setItem('ipagent.workbench.rightVisible', 'true');
                    }"""
                    )
                    await page.goto(f"{base_url}/cases/{demo_case_id}", wait_until="networkidle", timeout=60000)
                    await page.wait_for_selector(".zone-case, .zone-center-tabs", timeout=30000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "click_tab":
                    label = step.get("tab_label", "")
                    btn = page.locator(".zone-center-tab-btn").filter(has_text=label)
                    if await btn.count() == 0:
                        btn = page.get_by_role("tab", name=label)
                    await btn.first.click(timeout=10000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "click_text":
                    text = step.get("text", "")
                    await page.get_by_text(text, exact=False).first.click(timeout=10000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "click_selector":
                    sel = step.get("selector", "")
                    await page.locator(sel).first.click(timeout=10000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "open_assistant":
                    fab = page.locator(".ai-assistant-fab")
                    await fab.wait_for(timeout=10000)
                    panel = page.locator(".ai-assistant-panel")
                    if await panel.count() == 0:
                        await fab.click(timeout=10000)
                    if await panel.count() == 0:
                        await fab.click(timeout=10000)
                    await panel.wait_for(timeout=15000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "assistant_tab":
                    label = step.get("tab_label", "AI 问答")
                    tab = page.locator(".ai-assistant-panel__tab").filter(has_text=label)
                    await tab.first.click(timeout=10000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "select_text":
                    selector = step.get("selector", ".zone-panel-card-oa p")
                    await page.wait_for_selector(selector, timeout=15000)
                    await page.evaluate(
                        """(sel) => {
                        const el = document.querySelector(sel);
                        if (!el) throw new Error('select_text: not found ' + sel);
                        const range = document.createRange();
                        range.selectNodeContents(el);
                        const selection = window.getSelection();
                        selection.removeAllRanges();
                        selection.addRange(range);
                        el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
                    }""",
                        selector,
                    )
                    await page.wait_for_timeout(int(step.get("select_wait_ms", 600)))

                elif action == "click_selection_action":
                    label = step.get("text", "提问")
                    btn = page.locator(".ai-selection-menu__item").filter(has_text=label)
                    await btn.first.click(timeout=10000)
                    await page.wait_for_selector(".ai-assistant-panel", timeout=15000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "assistant_send":
                    message = step.get("message", "请简要说明本条审查意见的核心缺陷。")
                    textarea = page.locator(".ai-assistant-panel textarea").first
                    await textarea.wait_for(timeout=10000)
                    await textarea.fill(message)
                    send_btn = page.locator(".ai-assistant-panel").get_by_role("button", name="发送")
                    await send_btn.click(timeout=10000)
                    reply_ms = int(step.get("wait_reply_ms", 12000))
                    try:
                        await page.locator(".ai-chat-tab__bubble--assistant").first.wait_for(
                            timeout=reply_ms
                        )
                    except Exception:
                        pass
                    await page.wait_for_timeout(wait_ms)

                elif action == "oa_ask_ai":
                    btn = page.locator(".zone-panel-card-oa").get_by_role("button", name="向 AI 提问")
                    await btn.first.click(timeout=10000)
                    await page.wait_for_selector(".ai-assistant-panel", timeout=15000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "toggle_panel":
                    label = step.get("panel_label", "案件信息")
                    btn = page.locator(f'button.panel-layout-toggle[aria-label*="{label}"]')
                    await btn.first.click(timeout=10000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "workbench_layout":
                    cfg = {
                        "nav": bool(step.get("nav", True)),
                        "left_panel": bool(step.get("left_panel", True)),
                        "right_panel": bool(step.get("right_panel", True)),
                    }
                    await page.evaluate(
                        """(c) => {
                        localStorage.setItem('ipagent.layout.navCollapsed', String(!c.nav));
                        localStorage.setItem('ipagent.workbench.leftVisible', String(c.left_panel));
                        localStorage.setItem('ipagent.workbench.rightVisible', String(c.right_panel));
                    }""",
                        cfg,
                    )
                    await page.reload(wait_until="networkidle", timeout=60000)
                    await page.wait_for_selector(".zone-center-tabs", timeout=30000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "close_assistant":
                    close_btn = page.locator(".ai-assistant-panel__size-btn--close")
                    if await close_btn.count():
                        await close_btn.click(timeout=5000)
                    await page.wait_for_timeout(int(step.get("wait_ms", 400)))

                elif action == "kb_ask_tab":
                    await page.goto(f"{base_url}/kb/search", wait_until="networkidle", timeout=60000)
                    tab = page.get_by_role("tab", name="AI 问答")
                    if await tab.count():
                        await tab.click()
                    await page.wait_for_timeout(wait_ms)

                elif action == "dict_select_type":
                    await ensure_logged_in()
                    name = step.get("type_name", "")
                    btn = page.locator("button").filter(has_text=name)
                    await btn.first.click(timeout=10000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "dict_open_edit":
                    await ensure_logged_in()
                    table = page.locator(".el-table").filter(
                        has=page.locator("th", has_text="字典值")
                    )
                    if await table.count() == 0:
                        table = page.locator(".el-table").last
                    edit = table.first.get_by_role("button", name="编辑")
                    await edit.first.click(timeout=10000)
                    await page.wait_for_selector(".el-dialog", timeout=10000)
                    await page.wait_for_selector(".el-dialog .el-form-item", timeout=10000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "open_response_preview":
                    await ensure_logged_in()
                    case_id = step.get("case_id", demo_case_id)
                    response_id = step.get("response_id", "demo-woa-response-001")
                    await page.goto(
                        f"{base_url}/cases/{case_id}/response/{response_id}/preview",
                        wait_until="networkidle",
                        timeout=60000,
                    )
                    await page.wait_for_selector(".argument-editor, .zone-editor-aside", timeout=30000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "scroll_pipeline_step":
                    title = step.get("step_title", "")
                    if title:
                        card = page.locator(".zone-ai-step").filter(has_text=title)
                        await card.first.scroll_into_view_if_needed(timeout=10000)
                    await page.wait_for_timeout(wait_ms)

                elif action == "wait":
                    await page.wait_for_timeout(wait_ms)

                else:
                    raise ValueError(f"Unknown action: {action}")

                overlays = step.get("overlays") or step.get("highlights")
                if rel and overlays:
                    await apply_overlays(page, overlays)

                if rel:
                    dest = await shot(rel, full_page=full_page)
                    if overlays:
                        await clear_overlays(page)
                    try:
                        record["path"] = str(dest.relative_to(screenshots_dir.parent)).replace("\\", "/")
                    except ValueError:
                        record["path"] = f"screenshots/{rel}"
                    record["ok"] = True
                else:
                    record["ok"] = True
            except Exception as e:
                record["error"] = str(e)

            results.append(record)

        await browser.close()

    manifest = screenshots_dir.parent / "capture-manifest.json"
    import json

    manifest.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results
