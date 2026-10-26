# Obsidian Web Clipper × 公众号发布（参考）

## 为什么用 Clipper

| 对比 | Playwright 抓取 | Obsidian Web Clipper |
|------|-----------------|----------------------|
| 微信「环境异常」 | 常需验证码 / headless 失败 | 在**真实 Chrome** 里打开，成功率高 |
| 正文质量 | 纯文本 + 图片 URL | 结构化 Markdown + 可选高亮 |
| 通用网页 | 需单独写规则 | 官方 Defuddle 引擎，适配多数站点 |
| 离线备份 | 仅 `articles/` 副本 | 同时进入 Obsidian 知识库 |

Clipper 与 Playwright **互补**：Clipper 作首选；批量/无人值守仍用 `fetch_wechat_article.py`。

## 前置条件

1. **Obsidian** 桌面版已安装并打开目标库（Clipper 通过 URI 写入）
2. **Obsidian Web Clipper** 已安装（Chrome 扩展 ID `cnjifjpddelmedmihgijeibhnjfabmlf`）
3. 扩展设置中确认 **Vault / 库** 与本地 Obsidian 库名一致
4. （推荐）在库中建立剪藏目录，如 `Clippings/wechat/`

## 推荐 Clipper 模板（微信公众号）

扩展设置 → Templates → 新建规则，URL 匹配 `*mp.weixin.qq.com*`：

```markdown
---
title: "{{title}}"
url: "{{url}}"
author: "{{author}}"
published: "{{published}}"
tags:
  - wechat-clip
  - 待整理公众号
source: wechat
---

# {{title}}

> 作者：{{author}} · {{published}}
> 原文：{{url}}

{{content}}
```

通用网页可将 `tags` 改为 `web-clip`，目录改为 `Clippings/web/`。

## 用户操作（约 10 秒）

1. Chrome 打开目标链接（公众号或其他文章）
2. 点击工具栏 **Obsidian Web Clipper**（或快捷键，见扩展设置）
3. 确认库、文件夹、模板 → **添加到 Obsidian**
4. 告诉 Agent 剪藏文件路径，或说「刚剪藏到 wechat 文件夹的最新一篇」

## Agent 后续命令

```bash
# 将 Obsidian 剪藏 MD 规范化为 pipeline 输入
python scripts/prepare_obsidian_clip.py "/path/to/vault/Clippings/wechat/文章标题.md"

# 产出：
#   articles/<slug>-from-obsidian.md
#   articles/<slug>-from-obsidian.meta.json
```

然后 Agent 阅读 `-from-obsidian.md`，撰写 `articles/<slug>-科普版.md`，再走远程/本地发布。

## 配置 `~/.cursor/wechat-clipper.json`

复制 `~/.cursor/wechat-clipper.example.json` 并填写：

| 字段 | 说明 |
|------|------|
| `obsidian_vault` | Obsidian 库根目录绝对路径 |
| `clip_inbox` | 剪藏子目录（相对 vault） |
| `articles_dir` | 可选，覆盖默认 `skill/articles` |

Agent 找「最新剪藏」时：

```bash
ls -t "$VAULT/$CLIP_INBOX"/*.md | head -1
python scripts/prepare_obsidian_clip.py "$(ls -t ... | head -1)"
```

## 与 MarkItDown 的关系

- **Obsidian Web Clipper**：浏览器内一键剪网页 → Obsidian MD（**本技能 Step 1 首选**）
- **MarkItDown**：本地 PDF/Office → MD（见 `gesp-exam-import` 等场景，非公众号主路径）

## 故障排除

| 现象 | 处理 |
|------|------|
| 点击添加无反应 | 确认 Obsidian 已启动；库名与扩展设置一致 |
| 剪藏内容过短 | 扩展中选「保存完整页面」而非仅选区 |
| 图片公众号不显示 | Clipper 1.8+ 可本地化图片；发布前 `prepare_obsidian_clip.py` 会复制相对路径图到 `articles/assets/` |
| 找不到剪藏文件 | 在 Obsidian 中打开刚创建笔记 → 右键「在 Finder 中显示」 |
