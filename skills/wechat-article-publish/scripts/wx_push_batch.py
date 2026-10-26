#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wx_push_batch.py —— 批量把本地 HTML 推入公众号草稿箱（draft/add）。

为什么放在服务器上跑：
    公众号后台有 IP 白名单，本机家宽 IP 常变且不在名单里（errcode 40164）。
    这台服务器的公网 IP 101.201.65.123 已在白名单，所以推草稿一律走服务器。

与 wx_drafts.py 保持一致：token 走 /stable_token 且不 force_refresh，
不会把线上微信服务正在用的 token 顶掉。

用法：
    python wx_push_batch.py            # 读同目录 manifest.json
    python wx_push_batch.py --dry-run  # 只校验，不真的建草稿

manifest.json 格式：
    [{"html": "01.lite.html", "thumb": "cover-01.png",
      "title": "...", "digest": "..."}]
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

import requests

S = requests.Session()
S.trust_env = False  # 绕过代理

API = "https://api.weixin.qq.com/cgi-bin"
STABLE = f"{API}/stable_token"
DEFAULT_CFG = "/www/wwwroot/wechat-agent-server/config/wechat-publish.json"
CONTENT_LIMIT = 20000          # draft/add 的 content 字符上限
THUMB_LIMIT = 64 * 1024        # 缩略图（thumb）永久素材 64KB 上限


def _j(resp) -> dict:
    """微信返回 UTF-8 但 Content-Type 常不带 charset，requests 会猜成 latin-1
    把中文弄乱码，这里强制按 UTF-8 解码。"""
    return json.loads(resp.content.decode("utf-8"))


def load_cfg(path: str) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    appid = d.get("appid") or d.get("appId")
    secret = d.get("secret") or d.get("appsecret") or d.get("app_secret")
    if not appid or not secret:
        raise SystemExit("配置里缺 appid / secret: %s" % path)
    return {"appid": appid, "secret": secret, "author": d.get("author", "")}


def get_token(cfg: dict) -> str:
    r = _j(S.post(STABLE, data=json.dumps({
        "grant_type": "client_credential",
        "appid": cfg["appid"], "secret": cfg["secret"],
        "force_refresh": False}).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}, timeout=30))
    if "access_token" not in r:
        raise SystemExit("获取 access_token 失败: %s" % json.dumps(r, ensure_ascii=False))
    return r["access_token"]


def upload_thumb(token: str, p: Path) -> str:
    """封面 -> 永久缩略图素材。>64KB 先用 PIL 压到 64KB 以内。"""
    data = p.read_bytes()
    mime = "image/png"
    name = p.name
    if len(data) > THUMB_LIMIT:
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(data)).convert("RGB")
            for q in (85, 70, 55, 40, 25):
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=q)
                if buf.tell() <= THUMB_LIMIT:
                    data, mime, name = buf.getvalue(), "image/jpeg", p.stem + ".thumb.jpg"
                    break
        except ImportError:
            pass

    r = S.post(f"{API}/material/add_material",
               params={"access_token": token, "type": "thumb"},
               files={"media": (name, data, mime)}, timeout=60)
    d = _j(r)
    if "media_id" in d:
        return d["media_id"]

    # 缩略图不合规时退回普通图片素材（同样可作为 thumb_media_id）
    r2 = S.post(f"{API}/material/add_material",
                params={"access_token": token, "type": "image"},
                files={"media": (name, data, mime)}, timeout=60)
    d2 = _j(r2)
    if "media_id" not in d2:
        raise RuntimeError("封面上传失败 %s: thumb=%s image=%s" % (p.name, d, d2))
    return d2["media_id"]


def add_draft(token: str, article: dict) -> dict:
    return _j(S.post(f"{API}/draft/add", params={"access_token": token},
                     data=json.dumps({"articles": [article]}, ensure_ascii=False).encode("utf-8"),
                     headers={"Content-Type": "application/json; charset=utf-8"},
                     timeout=60))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--config", default=DEFAULT_CFG)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.dir)
    cfg = load_cfg(args.config)
    items = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

    print("AppID  : %s（作者 %r）" % (cfg["appid"], cfg.get("author") or ""))
    print("待处理 : %d 篇\n" % len(items))

    # 先做一遍静态校验，避免跑到一半才发现超限
    bad = []
    for it in items:
        html = (root / it["html"]).read_text(encoding="utf-8")
        thumb = root / it["thumb"]
        n = len(html)
        flag = "OK" if n < CONTENT_LIMIT else "超限"
        if n >= CONTENT_LIMIT or not thumb.exists():
            bad.append(it["title"])
        print("  [%s] %-40s 正文 %5d 字  封面 %s" % (
            flag, it["title"][:38], n,
            "%.0fKB" % (thumb.stat().st_size / 1024) if thumb.exists() else "缺失"))
    if bad:
        print("\n以下篇目不满足条件，先修好再推：")
        for t in bad:
            print("  -", t)
        return 1
    if args.dry_run:
        print("\n[dry-run] 校验通过，未创建草稿。")
        return 0

    token = get_token(cfg)
    print("\naccess_token : %s…\n" % token[:12])

    out = []
    for i, it in enumerate(items, 1):
        title = it["title"]
        print("[%d/%d] %s" % (i, len(items), title), flush=True)
        try:
            html = (root / it["html"]).read_text(encoding="utf-8")
            thumb_id = upload_thumb(token, root / it["thumb"])
            article = {
                "article_type": "news",
                "title": title[:64],
                "author": (cfg.get("author") or "")[:8],
                "digest": (it.get("digest") or "")[:120],
                "content": html,
                "content_source_url": "",
                "need_open_comment": 1,
                "only_fans_can_comment": 0,
                "thumb_media_id": thumb_id,
            }
            d = add_draft(token, article)
            if d.get("media_id"):
                print("        OK  media_id=%s" % d["media_id"], flush=True)
                out.append({"title": title, "ok": True, "media_id": d["media_id"],
                            "chars": len(html)})
            else:
                print("        FAIL %s" % json.dumps(d, ensure_ascii=False), flush=True)
                out.append({"title": title, "ok": False, "err": json.dumps(d, ensure_ascii=False)})
        except Exception as e:
            print("        FAIL %s" % e, flush=True)
            out.append({"title": title, "ok": False, "err": str(e)})
        if i < len(items):
            time.sleep(1.5)

    (root / "result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n================ 汇总 ================")
    for o in out:
        print("%-5s %-42s %s" % ("OK" if o["ok"] else "FAIL", o["title"][:40],
                                 o.get("media_id") or o.get("err", "")))
    ok = sum(1 for o in out if o["ok"])
    print("成功 %d / %d   （清单已存 %s）" % (ok, len(out), root / "result.json"))
    return 0 if ok == len(out) else 1


if __name__ == "__main__":
    sys.exit(main())
