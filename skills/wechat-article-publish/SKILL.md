---
name: wechat-article-publish
description: >-
  Converts source materials (MHTML, WeChat article URLs via Playwright, PDF,
  markdown) into WeChat Official Account articles and publishes via remote
  Agent (wechat.yclub.xin) or local draft API. Use when the user asks to
  read/fetch 微信公众号链接 (mp.weixin.qq.com), write/publish 公众号文章,
  auto-publish to WeChat, wechat.yclub.xin, or mentions wechat article
  publishing workflow.
---

# 微信公众号文章整理与自动发布

## 触发场景

- 用户提供资料（**微信公众号链接** / MHTML / 网页 / PDF / Markdown），要求整理成公众号文章
- 用户给出 `https://mp.weixin.qq.com/s/...` 并要求阅读、改写、转载科普
- 用户要求自动发布到微信公众号
- 用户提到「公众号」「wechat publish」「wechat.yclub.xin」「远程发布」「文章发布技能」

## 工作流

```
Task Progress:
- [ ] Step 1: 解析原始资料
- [ ] Step 2: 撰写科普/技术文章（Markdown）
- [ ] Step 3: 生成思维导图/架构图（Mermaid PNG）
- [ ] Step 4: 转换为微信 HTML（远程发布可跳过，服务端自动转换）
- [ ] Step 5: 发布（优先远程 Agent，其次本地 API）
```

### Step 1: 解析原始资料

| 格式 | 方法 |
|------|------|
| **微信公众号链接** `mp.weixin.qq.com/s/...` | **首选** `python scripts/fetch_wechat_article.py "<URL>"`（Playwright，见下节） |
| `.mhtml` | `python scripts/extract_mhtml.py`（或 `fetch` 已生成的 `.mhtml`） |
| 其他网页 URL | WebFetch；微信域仍建议用 Playwright |
| `.md` | 直接阅读 |
| `.pdf` | pdfplumber 提取 |

输出保存到 `articles/<slug>-source.txt`（及可选 `.mhtml` / `.html`）供 Step 2 参考。

#### 读取微信公众号链接（Playwright，必会）

微信正文无法被 WebFetch 稳定读取（常返回「环境异常」）。**Agent 必须运行抓取脚本**，不要假装已读过链接。

**一次性环境**（仓库根目录执行）：

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

**抓取命令**（Windows 建议在 Cursor 终端执行）：

```powershell
python scripts/fetch_wechat_article.py "https://mp.weixin.qq.com/s/xxxxxxxx"
python scripts/fetch_wechat_article.py "https://mp.weixin.qq.com/s/xxxxxxxx" -o articles --wait 20
```

**产出文件**（`<slug>` 为 URL 最后一段）：

| 文件 | 用途 |
|------|------|
| `articles/<slug>-source.txt` | 提取正文 + 标题，**Step 2 主要阅读此文件** |
| `articles/<slug>.mhtml` | 单文件网页备份 |
| `articles/<slug>.html` | 原始 DOM，排错用 |

**Agent 注意**：

1. 抓取后先读 `-source.txt`，写稿时**注明参考来源 URL**，勿大段照搬原文。
2. 正文尾部可能混入「赞赏 / 留言 / 精选」等，写稿时截断或忽略。
3. 若只有「环境异常」：去掉 `--headless`，让用户在弹出浏览器中完成验证后回车重试。

### Step 2: 撰写文章

- **风格**：科普、通俗易懂；可按受众调整（技术爱好者 / 青少年等）
- **结构**：概念 → 知识地图 → 模式详解 → 选型建议 → 总结表
- **篇幅**：3000–6000 字为宜
- **合规**：注明参考来源；不照搬原文大段代码
- 保存为 `articles/<slug>-科普版.md`

### Step 3: 生成配图

在 `articles/diagrams/` 创建 `.mmd` 文件，渲染 PNG：

```powershell
cd articles/diagrams
npx -y @mermaid-js/mermaid-cli@11 -i <name>.mmd -o <name>.png -b white -w 1200
```

Markdown 中引用：`![说明](diagrams/xxx.png)`

### Step 4: 转换微信 HTML（本地发布时需要）

```bash
python scripts/markdown_to_wechat_html.py articles/<slug>-科普版.md
```

生成 `articles/<slug>-科普版.wechat.html`。**远程 Agent 发布可跳过此步**，服务端流水线会自动转换。

---

## Step 5: 发布（两种方式）

### 方式 A：远程 Agent 发布（推荐，已部署 wechat.yclub.xin 时优先）

本地家庭宽带 IP 常不在微信白名单，**优先走已部署的 WeChat Agent 服务器**（服务器 IP 已在白名单）。

#### 客户端配置

复制 `%USERPROFILE%\.cursor\wechat-agent-client.example.json` 为 `wechat-agent-client.json`：

```json
{
  "url": "http://wechat.yclub.xin",
  "api_key": "从服务器 config.json 复制，约43字符含-_",
  "caller_name": "cursor-local",
  "verify_ssl": false
}
```

| 配置项 | 说明 | 常见错误 |
|--------|------|----------|
| `url` | **用 HTTP**，不要用 HTTPS（当前 HTTPS 反代未配好会 404） | |
| `api_key` | 服务器 `grep api_key /www/wwwroot/wechat-agent-server/config.json` | 误填 AppSecret（32位hex）→ 401 |
| `caller_name` | 审计标识，可选 | |

也可设环境变量：`WECHAT_AGENT_URL`、`WECHAT_AGENT_API_KEY`、`WECHAT_AGENT_CALLER_NAME`。

**服务器端**还需正确配置微信凭据（与客户端 api_key 不同）：

```
/www/wwwroot/wechat-agent-server/config/wechat-publish.json
→ appid + secret（微信公众号 AppSecret，非 Agent api_key）
```

同步本机凭据到服务器：

```powershell
scp $env:USERPROFILE\.cursor\wechat-publish.json cpp-server:/www/wwwroot/wechat-agent-server/config/wechat-publish.json
```

#### 远程发布命令

```powershell
python scripts/wechat_remote_publish.py `
  --markdown "articles/<slug>-科普版.md" `
  --title "文章标题" `
  --digest "摘要120字内" `
  --author "作者"
```

脚本行为：提交 Markdown → 服务端转 HTML → 上传图片 → 创建微信草稿 → 轮询 job 状态。

加 `--publish` 可直接提交发布（默认仅草稿箱）。加 `--no-wait` 仅提交不轮询。

#### 远程 API 参考

| 接口 | 说明 |
|------|------|
| `GET http://wechat.yclub.xin/api/health` | 健康检查，无需 Key |
| `POST /api/v1/webhook` | 提交发布任务，Header: `X-API-Key` |
| `GET /api/v1/jobs/{job_id}` | 轮询任务状态 |
| `http://wechat.yclub.xin/` | 管理后台，查看任务审计 |

详细接入文档：`wechat-agent-server/docs/INTEGRATION.md`

---

### 方式 B：本地直连微信 API（备选）

仅当本机 IP 已在微信白名单，或未部署远程 Agent 时使用。

#### 配置 `%USERPROFILE%\.cursor\wechat-publish.json`

```json
{
  "appid": "wxXXXXXXXX",
  "secret": "your_app_secret",
  "author": "作者笔名"
}
```

#### 本地流水线

```powershell
python scripts/wechat_article_pipeline.py `
  --markdown "articles/<slug>-科普版.md" `
  --title "标题" `
  --digest "摘要" `
  --author "作者"
```

---

## 发布路径决策

```
用户要发布公众号文章
        │
        ├─ 已部署 wechat.yclub.xin / 用户提到远程服务？
        │       └─ YES → wechat_remote_publish.py（方式 A）
        │
        └─ NO → wechat_article_pipeline.py（方式 B，需本机 IP 白名单）
```

## 常见问题

| 问题 | 处理 |
|------|------|
| 微信链接「环境异常」 | `fetch_wechat_article.py` 且不要 `--headless` |
| 远程 `401 Unauthorized` | `api_key` 填错；应是服务器 `config.json` 的 key（~43字符），**不是** AppSecret |
| 远程 `40125 invalid appsecret` | 服务器 `config/wechat-publish.json` 的 AppSecret 错误或过期；到 mp.weixin.qq.com 重置后更新 |
| 本地 `40164 IP 不在白名单` | 改用远程 Agent 发布，或把本机 IP 加入微信白名单 |
| `https://wechat.yclub.xin` 404 | 改用 `http://wechat.yclub.xin` |
| 图片不显示 | 远程/本地脚本均会通过 uploadimg 上传后替换 src |
| 正文乱码 `\u4ece\u96f6` | 确保 `json.dumps(..., ensure_ascii=False)`（脚本已内置） |

## 脚本索引

| 脚本 | 用途 |
|------|------|
| `scripts/fetch_wechat_article.py` | Playwright 抓取微信链接 |
| `scripts/extract_mhtml.py` | 从 MHTML 提取正文 |
| `scripts/markdown_to_wechat_html.py` | Markdown → 微信 HTML |
| `scripts/wechat_remote_publish.py` | **远程 Agent 发布（推荐）** |
| `scripts/wechat_publish.py` | 本地：上传图片、创建草稿 |
| `scripts/wechat_article_pipeline.py` | 本地端到端流水线 |
| `scripts/wechat_pipeline_lib.py` | 可编程流水线库 |
| `wechat-agent-server/app.py` | Agent HTTP 服务 |
| `wechat-agent-server/deploy/sync-to-baota.ps1` | 同步代码与凭据到服务器 |

## 示例

### 示例 A：微信链接 → 科普稿 → 远程发布

**用户**：阅读 `https://mp.weixin.qq.com/s/xxxxx`，写一篇面向青少年的公众号并发布

**Agent 动作**：
1. `python scripts/fetch_wechat_article.py "<URL>"`
2. 阅读 `articles/<slug>-source.txt`，撰写 `articles/<slug>-科普版.md`，生成 Mermaid 图
3. 确认 `~/.cursor/wechat-agent-client.json` 已配置
4. `python scripts/wechat_remote_publish.py --markdown ... --title ... --author ...`
5. 成功后提示到 mp.weixin.qq.com 草稿箱预览

### 示例 B：本地 MHTML → 本地发布

**Agent 动作**：
1. `python scripts/extract_mhtml.py article.mhtml -o articles/xxx-source.txt`
2. 撰写 Markdown + 配图
3. `python scripts/wechat_article_pipeline.py --markdown ... --title ...`

## 记忆文档

长期配置、服务器路径、已验证踩坑见同目录 **`MEMORY.md`**（或项目内 `.agents/skills/wechat-article-publish/MEMORY.md`）。
