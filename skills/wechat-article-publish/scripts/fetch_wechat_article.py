#!/usr/bin/env python3
"""
增强版微信公众号文章抓取工具
- Playwright 浏览器模拟
- ddddocr 验证码自动识别
- 人类行为模拟（慢速滚动、随机延迟、鼠标轨迹）
- 系列文章链接自动发现
- 反反爬策略
"""

from __future__ import annotations
import argparse
import asyncio
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

# === 配置区 ===
HUMAN_DELAY_MIN = 1.5       # 最小人类延迟（秒）
HUMAN_DELAY_MAX = 4.0       # 最大人类延迟（秒）
SCROLL_PAUSE_MIN = 2.0      # 滚动间最小停顿
SCROLL_PAUSE_MAX = 5.0      # 滚动间最大停顿
SCROLL_STEP_MIN = 200       # 最小滚动步长（px）
SCROLL_STEP_MAX = 600       # 最大滚动步长（px）
OCR_RETRY_MAX = 3           # OCR 重试次数

def human_delay(msg: str = "") -> None:
    """随机人类延迟"""
    s = random.uniform(HUMAN_DELAY_MIN, HUMAN_DELAY_MAX)
    if msg:
        print(f"  ⏳ {msg} ({s:.1f}s)")
    time.sleep(s)

def human_scroll(page, target: str = "bottom") -> None:
    """模拟人类滚动行为"""
    # 获取页面高度
    import asyncio
    async def _scroll():
        for _ in range(random.randint(3, 8)):
            step = random.randint(SCROLL_STEP_MIN, SCROLL_STEP_MAX)
            await page.evaluate(f"window.scrollBy(0, {step})")
            await asyncio.sleep(random.uniform(0.3, 1.5))
        # 最后滚到目标位置
        if target == "bottom":
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        elif target == "top":
            await page.evaluate("window.scrollTo(0, 0)")

def human_mouse_move(page, x: int, y: int) -> None:
    """模拟人类鼠标移动（贝塞尔曲线）"""
    import asyncio
    async def _move():
        # 简单分段移动，后续可改为贝塞尔
        steps = random.randint(5, 15)
        for i in range(steps):
            t = (i + 1) / steps
            cx = int(x * t + random.randint(-5, 5))
            cy = int(y * t + random.randint(-5, 5))
            await page.mouse.move(cx, cy)
            await asyncio.sleep(random.uniform(0.01, 0.05))

def solve_captcha_ocr(page) -> bool:
    """
    使用 ddddocr 识别图片验证码
    返回 True 表示验证码已解决
    """
    try:
        from ddddocr import DdddOcr
        ocr = DdddOcr()
    except ImportError:
        print("  ⚠️  未安装 ddddocr，尝试手动处理验证码...")
        print("  安装命令: pip install ddddocr")
        return False

    import asyncio
    async def _solve():
        # 查找验证码图片
        captcha_img = await page.query_selector("img#verify_img, img#capImg, img.captcha, img[src*='captcha']")
        if not captcha_img:
            # 尝试查找所有可能的验证码图片
            imgs = await page.query_selector_all("img")
            for img in imgs:
                src = await img.get_attribute("src") or ""
                if any(kw in src.lower() for kw in ["captcha", "verify", "code", "seccode"]):
                    captcha_img = img
                    break
        
        if not captcha_img:
            print("  ℹ️  未检测到验证码图片")
            return False

        for attempt in range(OCR_RETRY_MAX):
            try:
                # 截取验证码图片
                img_bytes = await captcha_img.screenshot()
                result = ocr.classification(img_bytes)
                print(f"  🔍 OCR 识别结果: {result} (尝试 {attempt + 1}/{OCR_RETRY_MAX})")
                
                # 填入验证码
                captcha_input = await page.query_selector(
                    "input#verify_input, input#inputCaptcha, input.captcha_input, input[name='secInput']"
                )
                if not captcha_input:
                    captcha_input = await page.query_selector(
                        "input[placeholder*='验证码'], input[placeholder*='captcha']"
                    )
                
                if captcha_input and result and len(result) >= 4:
                    await captcha_input.click()
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                    await captcha_input.fill(result)
                    await asyncio.sleep(random.uniform(0.2, 0.5))
                    
                    # 点击确认/提交按钮
                    submit_btn = await page.query_selector(
                        "button#verify_btn, button#btnSubmit, button[type='submit'], "
                        "a#verify_btn, a.btn_verify, .btn_verify"
                    )
                    if submit_btn:
                        await submit_btn.click()
                        await asyncio.sleep(2)
                    
                    # 检查是否验证成功
                    if not await page.query_selector("img#verify_img, img#capImg"):
                        print("  ✅ 验证码识别成功！")
                        return True
                
            except Exception as e:
                print(f"  ⚠️  OCR 尝试 {attempt + 1} 失败: {e}")
                await asyncio.sleep(1)
        
        return False

def solve_slider_captcha(page) -> bool:
    """
    解决滑块验证码
    """
    import asyncio
    async def _solve():
        # 检测滑块
        slider = await page.query_selector(
            ".slide-verify-slider, .nc_iconfont.btn_slide, "
            "#nc_1_n1z, .slider-btn, .captcha-slider-btn"
        )
        if not slider:
            # 尝试更通用的选择器
            slider = await page.query_selector("[class*='slide'], [id*='slide']")
        
        if not slider:
            return False
        
        print("  🖱️  检测到滑块验证码，尝试自动滑动...")
        
        try:
            box = await slider.bounding_box()
            if not box:
                return False
            
            start_x = box['x'] + box['width'] / 2
            start_y = box['y'] + box['height'] / 2
            
            # 找到滑轨宽度
            track = await page.query_selector(".slide-verify-slider-track, .nc-lang-cnt, .slider-track")
            if track:
                track_box = await track.bounding_box()
                if track_box:
                    target_x = track_box['x'] + track_box['width'] - box['width'] / 2
                else:
                    target_x = start_x + random.randint(250, 350)
            else:
                target_x = start_x + random.randint(250, 350)
            
            # 模拟人类拖动（非匀速）
            await page.mouse.move(start_x, start_y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.mouse.down()
            
            steps = random.randint(30, 60)
            for i in range(steps):
                t = (i + 1) / steps
                # 使用正弦波模拟加速-减速
                progress = t - 0.1 * __import__('math').sin(t * __import__('math').pi * 2)
                progress = max(0, min(1, progress))
                cx = start_x + (target_x - start_x) * progress + random.uniform(-1, 1)
                cy = start_y + random.uniform(-2, 2)
                await page.mouse.move(cx, cy)
                await asyncio.sleep(random.uniform(0.005, 0.02))
            
            await page.mouse.move(target_x, start_y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.mouse.up()
            await asyncio.sleep(2)
            
            # 检查是否成功
            if not await page.query_selector(".slide-verify-slider, .nc_iconfont.btn_slide"):
                print("  ✅ 滑块验证通过！")
                return True
            
        except Exception as e:
            print(f"  ⚠️  滑块处理失败: {e}")
        
        return False

def extract_article_content(page) -> dict:
    """提取文章内容"""
    import asyncio
    async def _extract():
        # 等待文章加载
        await asyncio.sleep(2)
        
        # 提取标题
        title = ""
        title_el = await page.query_selector("#activity-name, .rich_media_title, h1.title")
        if title_el:
            title = await title_el.inner_text()
        
        # 提取作者/公众号名
        author = ""
        author_el = await page.query_selector("#js_name, .rich_media_meta_nickname, #js_author_name")
        if author_el:
            author = await author_el.inner_text()
        
        # 提取发布时间
        pub_date = ""
        date_el = await page.query_selector("#publish_time, .rich_media_meta_text")
        if date_el:
            pub_date = await date_el.inner_text()
        
        # 提取正文
        content_el = await page.query_selector("#js_content, .rich_media_content")
        content_html = ""
        if content_el:
            content_html = await content_el.inner_html()
        
        # 提取纯文本
        content_text = ""
        if content_el:
            content_text = await content_el.inner_text()
        
        # 提取图片
        images = []
        if content_el:
            imgs = await content_el.query_selector_all("img")
            for img in imgs:
                src = await img.get_attribute("data-src") or await img.get_attribute("src") or ""
                if src and not src.startswith("data:"):
                    images.append(src)
        
        # 提取文章内链接（系列文章发现）
        links = []
        if content_el:
            anchors = await content_el.query_selector_all("a")
            for a in anchors:
                href = await a.get_attribute("href") or ""
                text = await a.inner_text() or ""
                if "mp.weixin.qq.com" in href:
                    links.append({"url": href, "text": text.strip()[:80]})
        
        return {
            "title": title.strip(),
            "author": author.strip(),
            "pub_date": pub_date.strip(),
            "content_html": content_html,
            "content_text": content_text.strip(),
            "images": images,
            "series_links": links,
        }

def save_article(article: dict, output_dir: Path, slug: str) -> None:
    """保存文章内容"""
    # 保存纯文本
    txt_path = output_dir / f"{slug}-source.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"标题: {article['title']}\n")
        f.write(f"作者: {article['author']}\n")
        f.write(f"发布时间: {article['pub_date']}\n")
        f.write(f"{'=' * 60}\n\n")
        f.write(article['content_text'])
    print(f"  📄 纯文本保存: {txt_path}")
    
    # 保存图片列表
    if article['images']:
        img_path = output_dir / f"{slug}-images.json"
        with open(img_path, "w", encoding="utf-8") as f:
            json.dump(article['images'], f, ensure_ascii=False, indent=2)
        print(f"  🖼️  图片列表保存: {img_path} ({len(article['images'])} 张)")
    
    # 保存系列文章链接
    if article['series_links']:
        links_path = output_dir / f"{slug}-links.json"
        with open(links_path, "w", encoding="utf-8") as f:
            json.dump(article['series_links'], f, ensure_ascii=False, indent=2)
        print(f"  🔗 系列文章链接: {links_path} ({len(article['series_links'])} 篇)")

async def crawl_wechat_article(url: str, output_dir: Path, wait: int = 15, headless: bool = True) -> Optional[dict]:
    """主抓取函数"""
    from playwright.async_api import async_playwright
    
    print(f"\n{'=' * 60}")
    print(f"🔍 开始抓取: {url}")
    print(f"{'=' * 60}")
    
    # 提取 slug
    slug = url.rstrip("/").split("/")[-1].split("?")[0]
    
    async with async_playwright() as p:
        # 启动浏览器（模拟移动端微信环境，减少反爬检测）
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )
        
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},  # iPhone 14 尺寸
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Mobile/15E148 MicroMessenger/8.0.42 NetType/WIFI Language/zh_CN"
            ),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        
        # 注入反检测脚本
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            delete navigator.__proto__.webdriver;
        """)
        
        page = await context.new_page()
        
        try:
            # 第1步：访问文章
            print("  🌐 正在加载页面...")
            human_delay("页面加载前随机等待")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # 等待内容加载
            await asyncio.sleep(wait)
            
            # 第2步：检测并处理验证码
            print("  🔒 检测验证码...")
            
            # 先尝试 OCR 图片验证码
            captcha_solved = await solve_captcha_ocr(page)
            if not captcha_solved:
                # 尝试滑块
                captcha_solved = await solve_slider_captcha(page)
            
            if captcha_solved:
                await asyncio.sleep(3)  # 等待验证完成后页面刷新
            
            # 第3步：重新等待内容加载
            await asyncio.sleep(2)
            
            # 第4步：模拟人类滚动阅读
            print("  📜 模拟人类滚动...")
            # 先慢速滚一点
            await page.evaluate("window.scrollBy(0, 300)")
            await asyncio.sleep(random.uniform(1, 2))
            
            # 滚动到底部
            for i in range(random.randint(4, 8)):
                step = random.randint(200, 500)
                await page.evaluate(f"window.scrollBy(0, {step})")
                await asyncio.sleep(random.uniform(1.5, 3.0))
            
            # 滚回顶部
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1)
            
            # 第5步：提取内容
            print("  📝 提取文章内容...")
            article = await extract_article_content(page)
            
            if not article['title'] and not article['content_text']:
                # 可能是"环境异常"页面
                page_text = await page.inner_text("body")
                if "环境异常" in page_text or "请在微信客户端打开" in page_text:
                    print("  ❌ 检测到「环境异常」页面，请尝试以下方法：")
                    print("     1. 去掉 --headless 参数，手动完成验证")
                    print("     2. 增加 --wait 参数到 30 秒")
                    print("     3. 在手机微信中打开链接后，用 Playwright 扫码登录")
                return None
            
            # 第6步：保存结果
            print(f"\n  📋 提取结果:")
            print(f"     标题: {article['title'][:60]}")
            print(f"     作者: {article['author']}")
            print(f"     图片: {len(article['images'])} 张")
            print(f"     系列链接: {len(article['series_links'])} 个")
            
            output_dir.mkdir(parents=True, exist_ok=True)
            save_article(article, output_dir, slug)
            
            # 第7步：如果发现系列文章链接，输出
            if article['series_links']:
                print(f"\n  📚 发现系列文章链接:")
                for i, link in enumerate(article['series_links'][:10], 1):
                    print(f"     {i}. {link['text'][:50]}")
                    print(f"        {link['url']}")
                if len(article['series_links']) > 10:
                    print(f"     ... 还有 {len(article['series_links']) - 10} 篇")
            
            return article
            
        except Exception as e:
            print(f"  ❌ 抓取出错: {e}")
            # 出错时保存截图便于调试
            try:
                screenshot_path = output_dir / f"{slug}-error.png"
                await page.screenshot(path=str(screenshot_path))
                print(f"  📸 错误截图已保存: {screenshot_path}")
            except:
                pass
            return None
        finally:
            await browser.close()

def main():
    parser = argparse.ArgumentParser(
        description="增强版微信公众号文章抓取 - 支持验证码识别 + 人类行为模拟"
    )
    parser.add_argument("url", help="微信公众号文章 URL (mp.weixin.qq.com/s/...)")
    parser.add_argument("-o", "--output-dir", default="articles", help="输出目录")
    parser.add_argument("--wait", type=int, default=15, help="页面加载等待时间（秒）")
    parser.add_argument("--headless", action="store_true", default=True, help="无头模式")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口（用于手动处理验证码）")
    parser.add_argument("--crawl-series", action="store_true", help="自动爬取系列文章")
    
    args = parser.parse_args()
    
    headless = not args.no_headless
    output_dir = Path(args.output_dir)
    
    # 验证 URL 格式
    if "mp.weixin.qq.com" not in args.url:
        print("⚠️  警告: URL 似乎不是微信公众号链接，尝试继续...")
    
    # 主抓取
    import asyncio
    article = asyncio.run(crawl_wechat_article(args.url, output_dir, args.wait, headless))
    
    if not article:
        print("\n❌ 抓取失败")
        sys.exit(1)
    
    # 如果指定了系列文章爬取
    if args.crawl_series and article.get('series_links'):
        print(f"\n{'=' * 60}")
        print(f"📚 开始爬取系列文章 ({len(article['series_links'])} 篇)")
        print(f"{'=' * 60}")
        
        crawled = 0
        for i, link in enumerate(article['series_links'], 1):
            print(f"\n--- [{i}/{len(article['series_links'])}] ---")
            # 避免太快
            human_delay(f"请求间隔")
            try:
                sub_article = asyncio.run(
                    crawl_wechat_article(link['url'], output_dir, args.wait, headless)
                )
                if sub_article:
                    crawled += 1
            except Exception as e:
                print(f"  ⚠️  跳过: {e}")
                continue
        
        print(f"\n✅ 系列文章爬取完成: {crawled}/{len(article['series_links'])} 篇成功")
    
    print(f"\n✅ 完成！文章内容已保存到 {output_dir}/")

if __name__ == "__main__":
    main()
