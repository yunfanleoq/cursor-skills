# WeChat Article Publish

Cursor Agent 技能 + Python 工具链：把资料（MHTML / Markdown 等）整理成**微信公众号文章**，转换为微信兼容 HTML，并调用**草稿 API** 发布。

[![Install with skills CLI](https://img.shields.io/badge/install-npx%20skills%20add-blue)](https://skills.sh)

---

## 功能一览

| 能力 | 说明 |
|------|------|
| 资料提取 | MHTML / 文本 → 结构化原文 |
| 文章撰写 | 配合 Cursor Agent 生成科普/技术 Markdown |
| 配图 | Mermaid 思维导图、架构图 |
| 微信排版 | Markdown → 微信 HTML（避免 ul/blockquote 排版 bug） |
| 草稿发布 | 上传正文图、封面，创建草稿箱；可选自动发布 |
| HTTP Agent | 可选 Webhook / 定时任务（见 `wechat-agent-server/`） |

---

## 环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| [Cursor](https://cursor.sh) | 最新版 | 运行 Agent 技能 |
| Python | 3.9+ | 脚本与发布 API |
| Node.js | 18+（含 npx） | `npx skills add` 安装技能 |
| 微信公众号 | 已认证订阅号/服务号 | 草稿 API 权限 |

Python 依赖：

```powershell
pip install -r requirements.txt
```

主要包：`requests`、`Pillow`（封面压缩，可选但推荐）。

---

## 安装

### 方式 A：skills CLI 安装（推荐）

与 [book-to-skill](https://github.com/virgiliojr94/book-to-skill) 等社区技能相同，使用 [Vercel skills CLI](https://github.com/vercel-labs/skills)：

**当前项目安装（复制整包，含 scripts）：**

```powershell
npx skills add yunfanleoq/wechat-article-publish --skill wechat-article-publish --agent cursor --copy -y
```

**全局安装（所有 Cursor 项目可用）：**

```powershell
npx skills add yunfanleoq/wechat-article-publish --skill wechat-article-publish --agent cursor -g --copy -y
```

**安装前预览：**

```powershell
npx skills add yunfanleoq/wechat-article-publish --skill wechat-article-publish --agent cursor -l
```

| 参数 | 说明 |
|------|------|
| `--agent cursor` | 安装到 Cursor 技能目录 |
| `--copy` | 复制完整目录（含 `scripts/`，**强烈推荐**） |
| `-g, --global` | 安装到用户目录 `~/.cursor/skills/` |
| `-y` | 跳过交互确认 |

安装完成后**重启 Cursor 或新开对话**，Agent 即可识别该技能。

> 使用 `--copy` 时，技能会安装到项目的 `.agents/skills/wechat-article-publish/`（含全部脚本）。请在 Cursor 中**打开安装了技能的项目目录**作为工作区，Agent 才能正确执行 `python scripts/...`。

---

### 方式 B：Git 克隆 + 手动安装

适合需要改源码、或希望固定仓库路径的用户。

```powershell
git clone https://github.com/yunfanleoq/wechat-article-publish.git
cd wechat-article-publish
pip install -r requirements.txt
.\install.ps1
```

`install.ps1` 会：

1. 复制 `SKILL.md` → `%USERPROFILE%\.cursor\skills\wechat-article-publish\`
2. 若不存在，从 `config/wechat-publish.example.json` 生成本地凭据模板

在 Cursor 中**打开克隆下来的仓库目录**作为工作区。

---

## 配置微信公众号凭据

**切勿将 AppID / AppSecret 提交到 Git。**

### 1. 获取凭据

登录 [微信公众平台](https://mp.weixin.qq.com) → **开发** → **基本配置** → 复制 **AppID**、**AppSecret**。

### 2. 创建本地配置文件

```powershell
mkdir $env:USERPROFILE\.cursor -Force
Copy-Item config\wechat-publish.example.json $env:USERPROFILE\.cursor\wechat-publish.json
notepad $env:USERPROFILE\.cursor\wechat-publish.json
```

填入：

```json
{
  "appid": "wxXXXXXXXXXXXXXXXX",
  "secret": "你的AppSecret",
  "author": "作者笔名"
}
```

### 3. 环境变量（可选，优先级相同）

```powershell
$env:WECHAT_APPID = "wxXXXXXXXX"
$env:WECHAT_APPSECRET = "你的Secret"
$env:WECHAT_AUTHOR = "作者名"
```

### 4. 公众平台侧注意项

- 需已开通**草稿箱 / 发布能力**
- 若启用了 **IP 白名单**，需把运行脚本的服务器 IP 加入白名单；家庭宽带 IP 常变动，可暂时关闭白名单或部署到固定 IP 云服务器
- 标题限制约 **32 字节**（UTF-8），脚本已自动截断
- 摘要 `digest` 建议留空或 ≤120 字

---

## 使用方式

### 一、在 Cursor 里用 Agent（最省心）

安装技能并配置凭据后，在 Cursor 对话中直接说，例如：

```
阅读 article.mhtml，整理成微信公众号科普文章，生成思维导图，并创建草稿
```

或：

```
把 articles/my-post.md 转成微信 HTML 并发布到公众号草稿箱
```

Agent 会按 `SKILL.md` 自动执行：

```
资料提取 → 写 Markdown → Mermaid 配图 → 转微信 HTML → 上传图片 → 创建草稿
```

**触发词示例：** 微信公众号、公众号文章、wechat publish、MHTML 发布

---

### 二、命令行分步使用

以下命令均在**仓库根目录**执行（skills CLI `--copy` 安装则在 `.agents/skills/wechat-article-publish/` 下执行）。

#### 步骤 1：准备目录

```powershell
mkdir articles\diagrams -Force
```

#### 步骤 2：从 MHTML 提取原文（可选）

```powershell
python scripts\extract_mhtml.py "path\to\article.mhtml" -o articles\my-source.txt
```

#### 步骤 3：撰写 Markdown

自行编写或使用 Cursor 生成，保存为 `articles\my-article.md`。

文内引用配图：

```markdown
![知识地图](diagrams/roadmap.png)
```

#### 步骤 4：生成 Mermaid 配图（可选）

```powershell
cd articles\diagrams
npx -y @mermaid-js/mermaid-cli@11 -i roadmap.mmd -o roadmap.png -b white -w 1200
cd ..\..
```

#### 步骤 5：Markdown → 微信 HTML

```powershell
python scripts\markdown_to_wechat_html.py articles\my-article.md
```

生成 `articles\my-article.wechat.html`。

#### 步骤 6：创建微信草稿

```powershell
python scripts\wechat_publish.py `
  --html articles\my-article.wechat.html `
  --title "文章标题" `
  --digest "" `
  --thumb articles\diagrams\roadmap.png
```

加 `--publish` 可尝试自动提交发布（部分账号无 freepublish 权限，需到后台手动发）。

#### 一键流水线

```powershell
python scripts\wechat_article_pipeline.py `
  --markdown articles\my-article.md `
  --title "文章标题" `
  --digest "" `
  --author "作者"
```

#### IP 白名单重试

家庭网络 IP 变动导致 40164 时：

```powershell
python scripts\wechat_publish_retry.py `
  --html articles\my-article.wechat.html `
  --title "文章标题" `
  --thumb articles\diagrams\roadmap.png
```

每 15 秒重试，最多 36 次。

---

### 三、发布后在微信后台确认

1. 打开 [mp.weixin.qq.com](https://mp.weixin.qq.com)
2. **内容与互动** → **草稿箱**
3. 预览排版 → 确认无误后点击**发表**

---

## 文章 Markdown 模板

```markdown
# 文章标题

> 导语：一句话说明读者能学到什么

## 一、核心概念
（表格 / 类比说明）

## 二、知识地图
![思维导图](diagrams/roadmap.png)

## 三、详细说明
（分节展开）

## 四、怎么选 / 怎么用
（决策表或清单）

## 五、总结
```

---

## 目录结构

```
wechat-article-publish/
├── SKILL.md                          # Cursor Agent 技能（必需）
├── README.md                         # 本文件
├── install.ps1                       # Windows 手动安装脚本
├── requirements.txt                  # Python 依赖
├── config/
│   └── wechat-publish.example.json   # 凭据模板
├── scripts/
│   ├── extract_mhtml.py              # MHTML 提取
│   ├── markdown_to_wechat_html.py    # Markdown → 微信 HTML
│   ├── wechat_publish.py             # 上传图片、创建草稿
│   ├── wechat_publish_retry.py       # IP 白名单重试
│   ├── wechat_article_pipeline.py    # 一键流水线
│   └── wechat_pipeline_lib.py        # 可编程库
├── wechat-agent-server/              # 可选 HTTP Agent
└── articles/                         # 本地文章（自行创建，不提交 Git）
    └── diagrams/
```

---

## 可选：HTTP Agent 服务器

适合 Webhook、定时任务、C++ 等平台通过 HTTP 触发「资料 → 草稿」：

```powershell
cd wechat-agent-server
copy config.example.json config.json
pip install -r requirements.txt
python app.py
```

默认 `http://0.0.0.0:8780`，详见 [wechat-agent-server/README.md](wechat-agent-server/README.md)。

---

## 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| `Repository not found` | GitHub 用户名或仓库名错误 | 使用 `yunfanleoq/wechat-article-publish` |
| Agent 不触发技能 | 未重启 Cursor / 未安装技能 | 重新 `npx skills add ... --copy`，新开对话 |
| `scripts/` 找不到 | 工作区不是技能目录 | 打开安装了 `--copy` 技能的项目根目录 |
| `获取 access_token 失败 40164` | IP 不在白名单 | 公众平台加 IP 或关闭白名单；用 `wechat_publish_retry.py` |
| 正文显示 `\u4ece\u96f6` 乱码 | JSON 未 UTF-8 编码 | 脚本已修复，请用本仓库最新版 |
| `45003 title size` | 标题超长 | 缩短标题（≤32 字节） |
| `40007 invalid media_id` | 缺少封面 | 加 `--thumb cover.png` |
| `48001 api unauthorized` | 无自动发布权限 | 只创建草稿，后台手动发表 |
| 列表出现空 bullet | 旧版 HTML 用了 ul/li | 用本仓库 `markdown_to_wechat_html.py` 重新生成 |
| 图片不显示 | 未走 uploadimg 接口 | 必须用 `wechat_publish.py` 上传后发布 |

---

## 安全说明

| 文件 | 是否提交 Git |
|------|-------------|
| `config/wechat-publish.example.json` | ✅ 仅占位符 |
| `~/.cursor/wechat-publish.json` | ❌ 本地凭据，切勿上传 |
| `wechat-agent-server/config.json` | ❌ 含 api_key |
| `wechat-agent-server/data/` | ❌ 任务日志 |

AppSecret 泄露请立即在公众平台**重置**。

---

## 卸载

**skills CLI 安装：**

```powershell
npx skills remove wechat-article-publish --agent cursor -y
```

**手动安装：**

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.cursor\skills\wechat-article-publish"
Remove-Item -Recurse -Force ".\.agents\skills\wechat-article-publish"
```

凭据文件需自行删除：`%USERPROFILE%\.cursor\wechat-publish.json`

---

## 相关链接

- 仓库：https://github.com/yunfanleoq/wechat-article-publish
- skills CLI：https://github.com/vercel-labs/skills
- Cursor 技能生态：https://skills.sh/agent/cursor

## License

MIT
