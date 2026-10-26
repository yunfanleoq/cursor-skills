---
name: content-capture
description: >-
  自动采集写作素材：微信公众号链接、网页、Obsidian 剪藏、MHTML。采集结果供
  article-brainstorm 与 wechat-article-publish 使用。用户给 mp.weixin.qq.com
  链接、要求剪藏、抓取、采集素材时使用。
---

# 内容素材采集

> 常见组合见 [Skill Hub 实践](https://www.skill-cn.com/skill/12)（agent-browser）与公众号技能内的 Playwright / Obsidian 方案。

## 采集路径（按优先级）

```
用户给链接 / 网页
    │
    ├─ 用户能开 Chrome？
    │     └─ YES → Obsidian Web Clipper 剪藏（首选，少遇「环境异常」）
    │
    ├─ 微信公众号 mp.weixin.qq.com？
    │     └─ fetch_wechat_article.py（Playwright，无人值守）
    │
    ├─ 已有 .mhtml？
    │     └─ extract_mhtml.py
    │
    └─ 需登录 / 复杂交互？
          └─ Cursor browser MCP 或 agent-browser（填表、截图、抽正文）
```

## 1. Obsidian 剪藏（首选）

配置：`~/.cursor/wechat-clipper.json`

```bash
cd ~/.cursor/skills/wechat-article-publish
python scripts/prepare_obsidian_clip.py "/path/to/vault/Clippings/wechat/xxx.md"
```

产出：`articles/<slug>-from-obsidian.md` + `articles/assets/<slug>/` 图片

## 2. 微信公众号 Playwright 抓取

```bash
cd ~/.cursor/skills/wechat-article-publish
env -u http_proxy -u https_proxy NO_PROXY='*' \
  .venv/bin/pip install playwright  # 首次
.venv/bin/python -m playwright install chromium
env -u http_proxy -u https_proxy NO_PROXY='*' \
  .venv/bin/python scripts/fetch_wechat_article.py "https://mp.weixin.qq.com/s/xxxxx"
```

产出：`articles/<slug>-source.txt`、`.mhtml`

微信页「环境异常」时：改用 Obsidian Clipper，或 `--no-headless` 人工过验证。

## 3. 浏览器 MCP / agent-browser

- **Cursor IDE Browser**：页面快照、点击、滚动、抽正文
- **agent-browser**（[skill-cn #12](https://www.skill-cn.com/skill/12)）：适合要登录的后台、表单、批量截图

采集后保存为 `articles/<slug>-source.txt` 或 Markdown，勿直接当终稿。

## 4. 与下游技能衔接

```
content-capture → article-brainstorm（定角度）
                → 撰写初稿
                → humanizer-zh（去 AI 味）
                → wechat-article-publish（配图 + 草稿）
```

## 注意

- 转载需注明来源；科普改写勿大段照搬
- 采集 Skill 类文章（如 humanizer / brainstorming）时：提取 SKILL 要点并入 `~/.cursor/skills/`，不要整篇抄袭进公众号
