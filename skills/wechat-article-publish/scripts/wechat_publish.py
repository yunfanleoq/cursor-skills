#!/usr/bin/env python3
"""Publish WeChat Official Account article via draft API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
UPLOAD_IMG_URL = "https://api.weixin.qq.com/cgi-bin/media/uploadimg"
ADD_MATERIAL_URL = "https://api.weixin.qq.com/cgi-bin/material/add_material"
DRAFT_ADD_URL = "https://api.weixin.qq.com/cgi-bin/draft/add"
FREE_PUBLISH_URL = "https://api.weixin.qq.com/cgi-bin/freepublish/submit"
DRAFT_GET_URL = "https://api.weixin.qq.com/cgi-bin/draft/get"


def post_json(url: str, payload: dict, timeout: int = 60) -> dict:
    """POST JSON with UTF-8 Chinese (avoid \\uXXXX escapes that WeChat stores literally)."""
    resp = requests.post(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=timeout,
    )
    return resp.json()


def truncate_title(title: str, max_bytes: int = 32) -> str:
    out = []
    size = 0
    for ch in title:
        n = len(ch.encode("utf-8"))
        if size + n > max_bytes:
            break
        out.append(ch)
        size += n
    return "".join(out) or title[:1]


class WeChatPublisher:
    def __init__(self, appid: str, secret: str):
        self.appid = appid
        self.secret = secret
        self._token: str | None = None
        self._token_expire = 0.0

    def get_access_token(self) -> str:
        if self._token and time.time() < self._token_expire - 60:
            return self._token
        resp = requests.get(
            TOKEN_URL,
            params={"grant_type": "client_credential", "appid": self.appid, "secret": self.secret},
            timeout=30,
        )
        data = resp.json()
        if "access_token" not in data:
            if data.get("errcode") == 40164:
                raise RuntimeError(
                    f"获取 access_token 失败（IP 不在白名单）: {data}\n"
                    "请到 mp.weixin.qq.com → 开发接口管理 → IP白名单，添加报错中的 IP；"
                    "家庭宽带 IP 常变动，可暂时关闭 IP 白名单后再试。"
                )
            raise RuntimeError(f"获取 access_token 失败: {data}")
        self._token = data["access_token"]
        self._token_expire = time.time() + int(data.get("expires_in", 7200))
        return self._token

    def upload_image(self, image_path: Path) -> str:
        token = self.get_access_token()
        with image_path.open("rb") as f:
            resp = requests.post(
                f"{UPLOAD_IMG_URL}?access_token={token}",
                files={"media": (image_path.name, f, "image/png")},
                timeout=60,
            )
        data = resp.json()
        if "url" not in data:
            raise RuntimeError(f"上传图片失败 {image_path}: {data}")
        return data["url"]

    def replace_local_images(self, html: str) -> str:
        def repl(match: re.Match) -> str:
            local_path = match.group(1)
            url = self.upload_image(Path(local_path))
            tag = match.group(0)
            return re.sub(r'data-local-path="[^"]*"', f'src="{url}"', tag)

        return re.sub(r'<img[^>]*data-local-path="([^"]+)"[^>]*/?>', repl, html)

    def _ensure_thumb_jpg(self, image_path: Path) -> Path:
        out = image_path.with_suffix(".thumb.jpg")
        try:
            from PIL import Image
            import io

            img = Image.open(image_path).convert("RGB")
            img.thumbnail((900, 500))
            for quality in (85, 70, 55, 40, 25):
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality)
                if buf.tell() <= 64000:
                    out.write_bytes(buf.getvalue())
                    return out
        except ImportError:
            pass
        return image_path

    def upload_thumb(self, image_path: Path) -> str:
        token = self.get_access_token()
        thumb = self._ensure_thumb_jpg(image_path)
        mime = "image/jpeg" if thumb.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        with thumb.open("rb") as f:
            resp = requests.post(
                f"{ADD_MATERIAL_URL}?access_token={token}&type=thumb",
                files={"media": (thumb.name, f, mime)},
                timeout=60,
            )
        data = resp.json()
        if "media_id" in data:
            return data["media_id"]
        with thumb.open("rb") as f:
            resp2 = requests.post(
                f"{ADD_MATERIAL_URL}?access_token={token}&type=image",
                files={"media": (thumb.name, f, mime)},
                timeout=60,
            )
        data2 = resp2.json()
        if "media_id" not in data2:
            raise RuntimeError(f"上传封面失败 {image_path}: thumb={data}, image={data2}")
        return data2["media_id"]

    def create_draft(self, title: str, author: str, digest: str, content_html: str, thumb_media_id: str) -> str:
        token = self.get_access_token()
        article = {
            "title": truncate_title(title),
            "author": author[:8] if author else "",
            "digest": digest[:120] if digest else "",
            "content": content_html,
            "content_source_url": "",
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
            "thumb_media_id": thumb_media_id,
        }

        data = post_json(
            f"{DRAFT_ADD_URL}?access_token={token}",
            {"articles": [article]},
        )
        if data.get("errcode", 0) != 0 and "media_id" not in data:
            raise RuntimeError(f"创建草稿失败: {data}")
        return data["media_id"]

    def publish_draft(self, media_id: str) -> dict:
        token = self.get_access_token()
        data = post_json(
            f"{FREE_PUBLISH_URL}?access_token={token}",
            {"media_id": media_id},
        )
        if data.get("errcode", 0) != 0 and "publish_id" not in data:
            raise RuntimeError(f"发布失败: {data}")
        return data


def load_config(config_path: Path | None) -> dict:
    cfg: dict = {}
    env_map = {
        "appid": "WECHAT_APPID",
        "secret": "WECHAT_APPSECRET",
        "author": "WECHAT_AUTHOR",
    }
    for k, env in env_map.items():
        if os.environ.get(env):
            cfg[k] = os.environ[env]

    if config_path and config_path.exists():
        cfg.update(json.loads(config_path.read_text(encoding="utf-8")))

    return cfg


def main():
    parser = argparse.ArgumentParser(description="Publish article to WeChat Official Account")
    parser.add_argument("--html", type=Path, required=True, help="WeChat HTML file")
    parser.add_argument("--title", required=True)
    parser.add_argument("--digest", default="", help="Article summary")
    parser.add_argument("--author", default="")
    parser.add_argument("--thumb", type=Path, help="Cover image for draft (png/jpg)")
    parser.add_argument("--config", type=Path, default=Path.home() / ".cursor" / "wechat-publish.json")
    parser.add_argument("--publish", action="store_true", help="Submit freepublish after draft")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)
    appid = cfg.get("appid")
    secret = cfg.get("secret")
    author = args.author or cfg.get("author", "")

    if not appid or not secret:
        print(
            "错误: 未配置微信公众号凭据。\n"
            "请创建 ~/.cursor/wechat-publish.json:\n"
            '{\n  "appid": "你的AppID",\n  "secret": "你的AppSecret",\n  "author": "作者名"\n}\n'
            "或设置环境变量 WECHAT_APPID / WECHAT_APPSECRET",
            file=sys.stderr,
        )
        sys.exit(1)

    html = args.html.read_text(encoding="utf-8")
    publisher = WeChatPublisher(appid, secret)

    if args.dry_run:
        print("[dry-run] 配置有效，HTML 长度:", len(html))
        imgs = re.findall(r'data-local-path="([^"]+)"', html)
        print(f"[dry-run] 待上传图片: {len(imgs)}")
        return

    html = publisher.replace_local_images(html)

    thumb_path = args.thumb
    if not thumb_path:
        imgs = re.findall(r'data-local-path="([^"]+)"', args.html.read_text(encoding="utf-8"))
        thumb_path = Path(imgs[0]) if imgs else None
    if not thumb_path or not thumb_path.exists():
        print("错误: 未找到封面图，请用 --thumb 指定", file=sys.stderr)
        sys.exit(1)

    thumb_id = publisher.upload_thumb(thumb_path)
    print(f"封面上传成功 thumb_media_id={thumb_id}")

    media_id = publisher.create_draft(args.title, author, args.digest, html, thumb_id)
    print(f"草稿已创建 media_id={media_id}")

    if args.publish:
        result = publisher.publish_draft(media_id)
        print(f"已提交发布 publish_id={result.get('publish_id')}")
    else:
        print("提示: 草稿已保存，登录 mp.weixin.qq.com 预览后发布；或加 --publish 自动发布")


if __name__ == "__main__":
    main()
