#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信公众号草稿箱工具：列出草稿 / 把草稿提交「发表」。

注意：「发表」(freepublish) 生成永久链接、进公众号主页，**不推送粉丝、不占群发次数**；
      「群发」(mass/sendall) 才会推给粉丝。本工具只做「发表」。

用法：
    python wx_drafts.py list
    python wx_drafts.py publish --ids MEDIA_ID1,MEDIA_ID2 --dry-run
    python wx_drafts.py publish --ids MEDIA_ID1,MEDIA_ID2 --yes
    python wx_drafts.py publish --all --yes            # 发表全部草稿
    python wx_drafts.py publish --except MEDIA_ID3 --yes

说明：
    - 默认只 dry-run，必须显式加 --yes 才真的发表。
    - 每篇之间间隔 5 秒，避免触发频率限制。
"""
from __future__ import annotations

import argparse
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
TOKEN_CACHE = Path("/tmp/.wx_drafts_token.json")


def _j(resp) -> dict:
    """微信一律返回 UTF-8，但 Content-Type 常不带 charset，
    requests 会猜成 latin-1，导致中文变乱码。这里强制按 UTF-8 解码。"""
    return json.loads(resp.content.decode("utf-8"))

# freepublish/get 的 publish_status（按官方文档，注意 0 才是成功）
STATUS = {
    0: "成功",
    1: "发布中",
    2: "原创校验不通过",
    3: "常规失败",
    4: "平台审核不通过",
    5: "成功后用户删除所有文章",
    6: "成功后系统封禁所有文章",
}


def load_cfg(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise SystemExit("找不到配置文件: %s" % p)
    d = json.loads(p.read_text(encoding="utf-8"))
    appid = d.get("appid") or d.get("appId")
    secret = d.get("secret") or d.get("appsecret") or d.get("app_secret")
    if not appid or not secret:
        raise SystemExit("配置里缺 appid / secret")
    return {"appid": appid, "secret": secret, "author": d.get("author", "")}


def _fetch_token(cfg: dict, force: bool) -> dict:
    """优先走 stable_token：不传 force_refresh 时返回平台缓存的 token，
    不会把别的进程（比如线上 wechat-agent-server）正在用的 token 顶掉。
    失败再退回老的 /token 接口。"""
    try:
        r = _j(S.post(STABLE, data=json.dumps({
            "grant_type": "client_credential",
            "appid": cfg["appid"], "secret": cfg["secret"],
            "force_refresh": bool(force)}).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"}, timeout=30))
        if "access_token" in r:
            return r
    except Exception:
        pass
    return _j(S.get(f"{API}/token", params={
        "grant_type": "client_credential",
        "appid": cfg["appid"], "secret": cfg["secret"]}, timeout=30))


def get_token(cfg: dict, force: bool = False) -> str:
    if not force and TOKEN_CACHE.exists():
        try:
            c = json.loads(TOKEN_CACHE.read_text(encoding="utf-8"))
            if c.get("appid") == cfg["appid"] and c.get("expire_at", 0) > time.time() + 300:
                return c["token"]
        except Exception:
            pass
    r = _fetch_token(cfg, force)
    if "access_token" not in r:
        code = r.get("errcode")
        hint = {
            40125: "AppSecret 无效（配置里的密钥已失效，请到公众号后台重新复制）",
            40164: "本机 IP 不在公众号后台的 IP 白名单里",
            40013: "AppID 无效",
        }.get(code, "")
        raise SystemExit("获取 access_token 失败: %s\n  %s" % (json.dumps(r, ensure_ascii=False), hint))
    TOKEN_CACHE.write_text(json.dumps({
        "appid": cfg["appid"], "token": r["access_token"],
        "expire_at": time.time() + r.get("expires_in", 7200)}), encoding="utf-8")
    return r["access_token"]


def post(path: str, token: str, payload: dict, timeout: int = 60) -> dict:
    return _j(S.post(f"{API}/{path}", params={"access_token": token},
                     data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                     headers={"Content-Type": "application/json; charset=utf-8"},
                     timeout=timeout))


def api_post(cfg: dict, path: str, payload: dict, timeout: int = 60) -> dict:
    """带 token 自愈：碰到 40001（token 被别的进程顶掉 / 已过期）就强制重取再试一次。"""
    r = post(path, get_token(cfg), payload, timeout)
    if r.get("errcode") == 40001:
        r = post(path, get_token(cfg, force=True), payload, timeout)
    return r


def fetch_drafts(cfg: dict) -> list:
    offset, rows, total = 0, [], None
    while True:
        r = api_post(cfg, "draft/batchget", {"offset": offset, "count": 20, "no_content": 1})
        if r.get("errcode"):
            raise SystemExit("draft/batchget 失败: %s" % json.dumps(r, ensure_ascii=False))
        if total is None:
            total = r.get("total_count", 0)
        items = r.get("item") or []
        if not items:
            break
        for it in items:
            news = (it.get("content") or {}).get("news_item") or []
            n0 = news[0] if news else {}
            rows.append({
                "media_id": it.get("media_id"),
                "update_time": it.get("update_time"),
                "title": n0.get("title") or "（无标题）",
                "author": n0.get("author") or "",
                "n_items": len(news),
            })
        offset += len(items)
        if offset >= total:
            break
    return rows


def cmd_list(cfg, args):
    rows = fetch_drafts(cfg)
    print("公众号 : %s（作者 %r）" % (cfg["appid"], cfg.get("author")))
    print("草稿总数 : %d\n" % len(rows))
    print("%-4s %-18s %-10s %s" % ("#", "更新时间", "作者", "标题"))
    print("-" * 92)
    for i, x in enumerate(rows, 1):
        ts = x["update_time"]
        t = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "-"
        print("%-4d %-18s %-10s %s" % (i, t, (x["author"] or "")[:8], x["title"]))
        print("      media_id = %s" % x["media_id"])
    Path("/tmp/wx_drafts.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n清单已存 /tmp/wx_drafts.json")
    return 0


def publish_one(cfg, media_id: str, title: str, poll: int = 40) -> tuple:
    r = api_post(cfg, "freepublish/submit", {"media_id": media_id})
    if r.get("errcode"):
        code = r.get("errcode")
        msg = {
            48001: "该账号无『发表』接口权限（2025-07 起微信已回收个人主体/未认证账号的 freepublish）",
            53503: "草稿未通过发布检查",
            53504: "需前往公众平台官网操作",
            53505: "需先在公众号后台手动保存该草稿",
            45009: "接口调用频率超限",
        }.get(code, r.get("errmsg"))
        return False, "errcode=%s %s" % (code, msg), None

    publish_id = r.get("publish_id")
    for i in range(poll):
        time.sleep(3)
        st = api_post(cfg, "freepublish/get", {"publish_id": publish_id}, timeout=30)
        code = st.get("publish_status", -1)
        if code == 1:                       # 1 = 发布中，继续轮询
            continue
        if code == 0:                       # 0 = 成功
            items = (st.get("article_detail") or {}).get("item") or []
            url = items[0].get("article_url") if items else ""
            return True, "已发表 %s" % url, publish_id
        return False, "publish_status=%s %s" % (code, STATUS.get(code, "")), publish_id
    return False, "轮询超时（任务可能仍在处理，请到后台确认）", publish_id


def cmd_publish(cfg, args):
    rows = fetch_drafts(cfg)
    by_id = {x["media_id"]: x for x in rows}

    if args.all:
        chosen = [x for x in rows if x["media_id"] not in set(args.except_ or [])]
    else:
        ids = [i.strip() for i in (args.ids or "").split(",") if i.strip()]
        if not ids:
            raise SystemExit("请用 --ids 指定要发表的草稿，或加 --all 发表全部")
        chosen = []
        for i in ids:
            if i not in by_id:
                print("!! 跳过：草稿箱里找不到 media_id = %s" % i)
                continue
            chosen.append(by_id[i])

    if not chosen:
        print("没有选中任何草稿。")
        return 1

    print("即将处理 %d 篇：" % len(chosen))
    for i, x in enumerate(chosen, 1):
        print("  %d. %s  (%s)" % (i, x["title"], x["media_id"]))
    print()

    if args.dry_run or not args.yes:
        print("[dry-run] 未实际发表。确认无误后加 --yes 执行。")
        return 0

    ok, fail = [], []
    for i, x in enumerate(chosen, 1):
        print("[%d/%d] 发表：%s" % (i, len(chosen), x["title"]), flush=True)
        success, detail, pid = publish_one(cfg, x["media_id"], x["title"])
        print("        %s  %s" % ("OK " if success else "FAIL", detail), flush=True)
        (ok if success else fail).append((x, detail))
        if i < len(chosen):
            time.sleep(5)

    print("\n===== 结果 =====")
    print("成功 %d 篇：" % len(ok))
    for x, d in ok:
        print("  - %s  %s" % (x["title"], d))
    if fail:
        print("失败 %d 篇：" % len(fail))
        for x, d in fail:
            print("  - %s  → %s" % (x["title"], d))
    return 0 if not fail else 1


def main():
    ap = argparse.ArgumentParser(description="微信公众号草稿箱工具")
    ap.add_argument("--config", default=DEFAULT_CFG)
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("list", help="列出草稿箱全部草稿")

    pp = sub.add_parser("publish", help="把草稿提交发表（freepublish）")
    pp.add_argument("--ids", default="", help="逗号分隔的 media_id")
    pp.add_argument("--all", action="store_true", help="发表全部草稿")
    pp.add_argument("--except", dest="except_", action="append", default=[],
                    help="配合 --all，排除某些 media_id（可重复）")
    pp.add_argument("--dry-run", action="store_true")
    pp.add_argument("--yes", action="store_true", help="确认真的发表")

    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return 0
    cfg = load_cfg(args.config)
    return cmd_list(cfg, args) if args.cmd == "list" else cmd_publish(cfg, args)


if __name__ == "__main__":
    sys.exit(main())
