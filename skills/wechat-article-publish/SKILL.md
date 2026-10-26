---
name: wechat-mp-publish
description: 把 Markdown 文章发到微信公众号，以及把草稿箱里积压的草稿批量发表。覆盖配图规格、转公众号行内样式 HTML、调官方 API 推草稿，以及在个人主体号拿不到 freepublish 权限时，用 CDP 驱动本机真 Chrome 自动完成草稿箱→发表（原创声明 / 合集 / 关闭群发通知 / 二维码扫码）。当用户说"把文章发到公众号""推送到微信公众号""公众号排版""上传草稿箱""草稿箱批量发表""把草稿发了""mp.weixin.qq.com 发布"时使用。
agent_created: true
---

# 微信公众号发布

把一篇 Markdown 文章变成能发进公众号的成品，或者把草稿箱里几十篇积压草稿批量发表出去。
核心难点是**微信的限制比想象中多**，下面每一条都是踩过的坑，照做即可。

---

## ⛔ 铁律（2026-10-08 实跑确定，不要再问、不要再试）

1. **默认不群发。发表时一律关闭「群发通知」。**
   - 订阅号**每天只能群发 1 次**，而草稿箱动辄几十篇——群发额度根本不够用，还会打扰粉丝。
   - 「不群发」的发表同样会生成**永久链接**、进公众号主页、可被搜索，只是**不推进粉丝订阅列表**。
   - 所以：`wxflow.mjs` 里必须**硬编码强制关闭**该开关，**不提供任何"打开群发"的入参**。
     代码现状见 §7.2 状态机 `massSwitchOn` 分支——`true` 就点掉，不判断用户意图。
   - 用户原话：「以后不用那个群发，那个默认我们不群发，因为反正只有一篇是可以群发的」。

2. **不要调 `freepublish/submit`。** 本账号 `wxe9dd6623b564d1d4`（RPA老刘，个人主体）恒返
   `errcode=48001 api unauthorized`，密钥/IP 都没问题，是**账号类型没这个权限**。详见 §1.1、§六。

3. **发表 = 浏览器自动化**（本机真 Chrome + CDP 远程调试端口）。这是目前**唯一跑通**的路径，见 §七。

4. **扫码绕不过**，每篇一次，由管理员/运营者扫码。**不要截图二维码**（跨域合成层截出来是纯色空白），
   要把整个页面**推到屏幕最前端**让扫码人直接扫。

5. **每篇发表都是对外可见、不可逆的操作。** 批量前先给用户看清单，先跑 1 篇验证链路，再批量。

---

## 0. 标准作业流程（本机实证，照这个顺序做）

```bash
# ⓪ 新文章：Markdown → 公众号 HTML → 推到草稿箱（本机 IP 未加白，必须走服务器，见 §6.3）
$PY scripts/build_wechat_html.py --theme both     # rich=粘贴用；lite=接口用，必须 <20000 字符
#   超限就按 §四 的「从结构上省字符」压，压完重跑本行看数字
#   再把 lite + 封面 + manifest.json scp 到服务器跑 scripts/wx_push_batch.py

# ① 启动独立 Chrome（不碰用户日常浏览器），用户扫码登录一次，cookie 留在 /tmp/wxchrome
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 --user-data-dir=/tmp/wxchrome \
  --no-first-run --no-default-browser-check https://mp.weixin.qq.com/

# ② 从后台 URL 里取 token（形如 token=978829597），拿草稿清单
#    服务端：.venv/bin/python scripts/wx_drafts.py list   → /tmp/wx_drafts.json
#    或直接看草稿箱列表页 URL 的 token 参数
#    再用 cdp.mjs 从列表页读每篇的 file_id（见 §六末"读 file_id"）
#    Page 里执行：
#      [...document.querySelectorAll('.weui-desktop-card__inner')] 取每张卡，
#      向上找 __vue__.$data.list[0].file_id / .title

# ③ 批量发表（默认关群发通知、自动设原创 + 合集，只在扫码时把页面推到前端）
cd <技能目录>/scripts
WX_TOKEN=978829597 WX_ALBUM="刘思学书画集" node wxflow.mjs FILE_ID_1,FILE_ID_2,...
# 结果落盘 /tmp/wxflow_result.json

# ④ 清理重复草稿（每组只留最新版并已发表后，删掉旧副本）
DRY=1 WX_TOKEN=978829597 node wxdel.mjs FILE_ID_1,FILE_ID_2   # 先干跑，只定位不点
WX_TOKEN=978829597   node wxdel.mjs FILE_ID_1,FILE_ID_2       # 确认真删
# 结果落盘 /tmp/wxdel_result.json

# ⑤ 只有「有篇文章是补发的」才需要：把它拖回系列原位 + 顺手改合集简介
#    合集是「正序」= 按发表时间排；今天补发的文章一定掉在最后，必须手动拖回。
CDP_MATCH="action=edit" node wxdrag.mjs --from "补发那篇的标题关键词" --to "它该待在哪篇的前/后面" \
    --mode before|after --scroll 900
#    改完顺序/简介，都要点编辑页底部的「发布」按钮才写回服务器（见 §七 末「合集排序与简介」）
```

跑之前先确认：

- **合集名必须真实存在**（`WX_ALBUM`），状态机在合集下拉里找不到会直接抛错；
  批量前先去 `appmsgalbummgr?action=list` 核对合集名。
- **合集排序 = 按发布时间「正序」（从早到晚）**，所以**按系列顺序发表**（第 1 篇先发、最后一篇后发），
  读者端打开合集就是从头读到尾。想确认某合集的实际顺序 / 拿合集 id：合集列表页点该行「编辑」→
  打开 `appmsgalbummgr?action=edit&type=0&id=<合集id>` 读页面文本（会显示「正序/倒序」与实际列表）。
  已知 id：「寒武纪MLU开发」`4728808293601558534`、「git用法详解」`4550457048794054660`、
  「智能体AGENT」`4552283171060367361`、「人工智能」`3619472170616455174`（2024 老 RPA，别往里放）。
  ⚠️ **批量发表中途失败、第二天才补发的那几篇，一定会掉到合集最末**（发表时间最晚）。
  发表全部收尾后**必须回合集编辑页核对一遍顺序**，用 `wxdrag.mjs` 把补发的拖回原位（2026-10-09 踩过）。
- **合集读者端链接**：`https://mp.weixin.qq.com/mp/appmsgalbum?action=getalbum&album_id=<id>&__biz=MzkyNDc1MzQ2Mg==#wechat_redirect`
  （`__biz` 可在任意公众号后台页面的 HTML 里正则取到）。
- **重复草稿先剔掉**（同标题多份只留最新一版，见 §六 末节「同名重复草稿的处理」）。
- 一次别塞太多：10~15 篇一批，跑完看 `/tmp/wxflow_result.json` 再续下一批。
- 扫码超时默认 180s，可用 `WX_SCAN_TIMEOUT` 调整。

---

## 一、必须先知道的微信限制

| 限制 | 数值 / 行为 | 应对 |
|------|------------|------|
| `draft/add` 的 `content` | **< 20000 字符**，< 1MB | 行内样式会把正文撑大 10 倍，必须准备"精简档" |
| 正文图片 | 单张 < 1MB | 压缩到 1080 宽、< 900KB |
| 封面 | jpg/png < 2MB，推荐 900×383（2.35:1） | 裁成 2.35:1 |
| 正文图片 URL | **必须是 `media/uploadimg` 返回的 mmbiz URL** | 外链会被静默过滤 |
| 封面 | **必须是永久素材 media_id**（`material/add_material`） | 传 URL 无效 |
| 调用 IP | 必须在后台 IP 白名单 | 否则 errcode 40164 |
| 编辑器 CSS | 只认 `style="..."`；`<style>`/`class`/`<script>` 全被剥离 | 排版全部内联 |
| Mermaid | 不渲染 | 提前导出 PNG |
| `<details>` 折叠 | 不支持 | 降级成"题目 + 答案"卡片 |

其他报错：`45002` 正文超限 · `40007` thumb_media_id 无效 · `48001` 账号无该接口权限 · `40164` IP 不在白名单。

### 1.1 草稿 / 发布 / 群发是三个不同动作（极其容易搞混）

| 动作 | 接口 | 效果 | 次数限制 | 账号门槛 |
|------|------|------|---------|---------|
| 建草稿 | `draft/add` | 只是存进草稿箱，没人看得到 | 无 | 门槛低，订阅号/服务号均可 |
| **发布** | `freepublish/submit` | 生成**永久链接**、进公众号主页，**不推送粉丝** | 不占群发次数 | **仅企业主体 + 已微信认证** |
| 群发 | `message/mass/sendall` | 真正推送到粉丝订阅列表 | 订阅号 1 次/天，服务号 4 次/月 | 需相应权限 |

**关键变更：2025 年 7 月起，微信回收了【个人主体账号】【企业主体未认证账号】及不支持认证账号的 `freepublish` 接口权限。**
个人订阅号无法微信认证 → 落入"不支持认证" → **调 `freepublish/submit` 必返回 48001**。
所以对个人号，"草稿箱全自动"能做到，**"发表"这一步必须人工到后台点**。

发布是**异步**的：`errcode=0` 只代表任务提交成功，要用 `freepublish/get` 传 `publish_id` 轮询，
`publish_status` 0=成功/1=发布中/2=原创失败/3=常规失败/4=审核不通过/5=文章被删/6=被封禁。
另有 `53503`（草稿未过发布检查）、`53504`（必须去官网操作）、`53505`（需先在后台手动保存一次）三个坑。

## 二、三条路线，按优先级判断

**路线 0：先用「言序」连接器（如果当前会话能调到它的工具）**
言序能一站式做完"查绑定公众号 → 按主题排版建稿 → 推草稿箱"。
先用 ToolSearch 确认工具可见再决定，**别按连接器状态想当然**：
MCP 连接器的工具是在**会话启动时**载入的，会话中途才连上的连接器，
本会话内 `ToolSearch` 无论按关键词、中文名还是工具全名都查不到，
必须让用户**新开一个会话**才能调用。
判断方法：`connector-status` 里显示 `connected` 不代表工具可用，
一定要 ToolSearch 实际查一次。

言序的四个工具：`list_wechat_accounts` / `list_theme_styles` / `create_article` / `publish_article`。
⚠️ **`publish_article` 的名字有误导性——它只写到草稿箱，不做正式发表**。
言序不吃 HTML，要喂结构化 blocks（`paragraph` / `image` / `list` / `table` 四种，章节平级不嵌套），
把 Markdown 转成这个结构即可。约束：`title` ≤30 字、`abstract` ≤100 字、
封面 ≤2MB、正文单图 ≤1MB；正文图超 2 张时为**异步发布**。

**路线 1：手动复制粘贴（排版最完整，无长度限制）**
浏览器打开生成的 HTML → ⌘A → ⌘C → 粘进公众号编辑器。
*接口的 2 万字符上限过不去富排版，所以这条路是最稳的兜底。*

**路线 2：官方 API 推草稿（全自动，但排版必须精简到 2 万字符以内）**
`--publish` 停在草稿箱；账号若是企业主体已认证，加 `--publish-live` 可一路发表。
个人主体号走 `--publish`，发表留人工。

## 三、执行步骤

```bash
cd <文章目录>
PY=<venv>/bin/python

# 1. 配图处理：封面裁 2.35:1、正文图压到 1080 宽 / <900KB
$PY scripts/prepare_images.py            # --anchor 0.22 控制封面纵向裁切位置

# 2. 转 HTML：同时产出 rich（粘贴用）和 lite（接口用，<2万字符）
$PY scripts/build_wechat_html.py         # 输出到 dist/

# 3a. 手动路线：浏览器打开 dist/wechat-article.html，全选复制粘贴
# 3b. 接口路线：
$PY scripts/push_to_wechat.py --check          # 会打印本机公网 IP，拿去加白名单
$PY scripts/push_to_wechat.py --publish        # 传图 + 建草稿（停在草稿箱）
$PY scripts/push_to_wechat.py --publish-live   # 再进一步：正式发表（仅企业认证号）
```

密钥来源：公众号后台 → 设置与开发 → 基本配置 → AppID / AppSecret。
用环境变量 `WECHAT_APPID` / `WECHAT_APPSECRET`，或 `dist/wechat.config.json`
（记得 gitignore，别把密钥提交进仓库）。

## 四、脚本说明

- `prepare_images.py` — 按预算压缩，PNG 超限自动退化成 JPEG；封面额外输出 900×900 方形备用图。
- `build_wechat_html.py` — 自制 Markdown→HTML 转换器（不能用通用渲染器，因为要内联样式）。
  两套样式档位：`RICH`（精致）与 `LITE`（精简）。**改排版改这两个 dict 即可。**
  LITE 压体积的主要手段，按性价比排序：
  1. `<strong>` 不带 style（省最多，约 2k 字符）
  2. 表格去掉每格边框，只在 `<tr>` 上加 `border-bottom`（横向分隔线，约 1.9k）
  3. `<li>` 不逐条加 margin，靠根节点 line-height 撑行距
  4. 句间分隔线（`hr`）直接省略，靠 h2 的左侧色条区分章节
  5. 字号/颜色/行高下沉到根 `<section>` 继承，子元素不重复声明
  6. 行内 `<code>` 只留 `color`，不加 background/padding

  **改样式还不够时，从「结构」上省字符**（2026-10-08 实测：第 03 篇 20196 → 19277）：
  - 一个代码块 / 引用块**光行内样式就要 80~105 字符**，同类小片段优先合并成一块、用注释分行
    （例：把 6 个独立的 stride 示例并成 2 个代码块，省掉 4 层包裹）。
  - 占位用的 `> 提示` 引用块样式最贵（`quote` 一行 ~83 字符 + 外层 `<section>`），
    内容能并进正文段落就并进去。
  - `h3` 小标题每个也要 ~60 字符，相邻小节能合就合。
  - 只精简**结构**、别删走心内容：把这些装饰性结构合并，读者反而更好读。
- `push_to_wechat.py` — 带 token 本地缓存（避免刷掉线上 token）；
  `--check / --upload-only / --publish / --publish-live` 四档，推送前自检字符数。
  `--publish-live` 会在建草稿后调 `freepublish/submit` 并轮询 `freepublish/get`，
  对 48001 / 53503 / 53504 / 53505 都有中文提示（个人号会卡在 48001，属预期）。

## 五、验证

改完排版一定要**渲染截图核对**，别只看 HTML 源码：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --no-sandbox --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --window-size=760,15000 --screenshot="$PWD/_shot.png" "file://$PWD/wechat-article.html"
```

注意：headless Chrome 在沙箱里会 `sandbox initialization failed`，需要放开沙箱；
截图存 `/tmp` 可能被拦，写到项目目录里更稳。截完整页后按高度切成几段再看。

最终成品至少交付：`wechat-article.html`（预览/复制源）、lite 片段、压缩后的配图、发布说明。

## 六、用户自建的远程发布通道（既有资产，优先复用）

用户机器上**早就有一套跑通的公众号发布服务**，不要再从零搭。涉及三个位置：

| 资产 | 路径 |
|------|------|
| 本地技能/客户端 | `~/cursorProjects/cursor-skills/skills/wechat-article-publish/`（含 MEMORY.md 运维记忆） |
| 服务端代码副本 | `~/cursorProjects/pc-pilot/wechat-agent-server/` |
| 远程服务 | `http://wechat.yclub.xin`（`/api/health` 可探活，返回 `{"ok":true,...}`） |
| 客户端配置 | `~/.cursor/wechat-agent-client.json`（含 `api_key`，**不是** AppSecret） |
| 服务端 SSH | `ssh -i ~/.ssh/cpp_server_key dev@101.201.65.123` |
| 服务端根目录 | `/www/wwwroot/wechat-agent-server`（venv: `.venv/bin/python`，3.11） |
| 微信凭据 | 服务端 `config/wechat-publish.json`（另有 `config/users/<id>.json` 副本） |

### ⛔ 该账号实测无发表权限（2026-10-08 实调，必须记住）

账号 `wxe9dd6623b564d1d4`（RPA老刘）实调 `freepublish/submit` → **`errcode=48001 api unauthorized`**。
草稿接口（`draft/batchget` / `draft/get`）正常，所以**不是**密钥、IP、配置问题，
而是**账号类型没有这个接口权限**。

官方文档「适用范围」原文：`freepublish` 系列**仅允许企业主体已认证账号调用**。

> **推论**：服务端 `scripts/wechat_publish.py` 用的同样是 `freepublish/submit` + 同一个 AppID，
> 所以它这条发布链路**同样是瘫的**。以前能跑通，是 2025-07 之后被微信回收了权限。
> 不要在服务端调这个接口上浪费时间；"服务端在用 freepublish"**不能**推断"这个号有权限"
> ——这是曾经写错过的结论。

**能做的事**：草稿箱可以全自动写入；**发表/群发只能人工后台操作**（见 §1.1）。

### 排障要点

- **`40125 invalid appsecret`**：凭据过期/被重置。**这不是 IP 问题**（IP 问题报 `40164`）。
  本地和服务端配置都会同时失效，必须让用户去公众号后台重新复制 AppSecret。
- **`40001 access_token is invalid or not latest`**：有另一个进程刚取了新 token。
  用 `cgi-bin/stable_token`（**不传** `force_refresh`）可避免互顶；普通 `/cgi-bin/token`
  每调一次就会把上一个顶掉。**排查时别再用只读脚本单独取 token**——会把正在跑的发布任务弄挂。
- **`publish_status` 别写反**：`0=成功`、`1=发布中`（官方文档）。曾把 `1` 当成功，导致成功判成超时。
- **必须先实调一次再下结论**：配置存在 ≠ 能用。凭据可能几个月前就废了。
- 命令行注意：**zsh 默认不做变量分词**，`ssh $OPTS host` 会把整串当成一个参数而失败
  （表现为 ssh 拿不到密钥、转而要求输密码，或 `env` 打印全部环境变量）。
  一律**内联写全** `ssh -i ... -o ... user@host`，或改用 `ssh host 'bash -s' < script.sh` 管道方式。
- 远程执行脚本前先本地 `py_compile` 校验，再 `ssh host "cat > path" < local.py` 上传。
- 远程终端可能把中文显示乱码：**让脚本把结果写 JSON，再 `ssh host "cat file" > local.json` 拉回本地解析**。
- `requests` 会把微信返回的 UTF-8 误判成 latin-1 → 中文标题乱码。用
  `json.loads(resp.content.decode("utf-8"))`，别直接 `.json()`。

### 现成工具

服务端 `scripts/wx_drafts.py`（本地副本：技能 `scripts/` 与本机 `~/cursorProjects/cursor-skills/skills/wechat-article-publish/scripts/`）：

```bash
cd /www/wwwroot/wechat-agent-server
.venv/bin/python scripts/wx_drafts.py list                          # 列草稿箱
.venv/bin/python scripts/wx_drafts.py publish --ids ID1,ID2 --dry-run
.venv/bin/python scripts/wx_drafts.py publish --ids ID1,ID2 --yes    # 真发表
```

设计要点（复用这套模式）：默认 dry-run，必须 `--yes` 才动手；逐篇发表、间隔 5 秒防限频；
`freepublish/get` 轮询到终态才算成功（`errcode=0` 只代表提交成功）；
把 `48001/53503/53504/53505/45009` 都翻译成中文原因。

### 批量推草稿到草稿箱（本机 IP 不在白名单 → 走服务器）

**症状**：本机调 `draft/add` 报 `errcode=40164 invalid ip 182.48.107.86`。
家宽公网 IP 会变，加白名单不现实 → **改在服务器上推**（服务器 IP `101.201.65.123` 已在白名单）。

本技能新增 `scripts/wx_push_batch.py`，一条命令把一整个系列推进草稿箱：

```bash
# 物料目录放：NN.lite.html + cover-NN.png + manifest.json + wx_push_batch.py
# manifest.json: [{"html":"01.lite.html","thumb":"cover-01.png","title":"...","digest":"..."}]

scp -i ~/.ssh/cpp_server_key -q <物料目录>/* dev@101.201.65.123:/tmp/cncv-push/
ssh -i ~/.ssh/cpp_server_key dev@101.201.65.123 \
  "cd /tmp/cncv-push && /www/wwwroot/wechat-agent-server/.venv/bin/python wx_push_batch.py --dry-run"
ssh -i ~/.ssh/cpp_server_key dev@101.201.65.123 \
  "cd /tmp/cncv-push && /www/wwwroot/wechat-agent-server/.venv/bin/python wx_push_batch.py"
# 结果（含 media_id）写 /tmp/cncv-push/result.json
```

要点：
- **token 用 `/cgi-bin/stable_token` 且 `force_refresh:false`**，避免把线上服务正在用的 token 顶掉
  （直接 `/cgi-bin/token` 每调一次就顶掉上一个，会让在跑的线上任务报 40001）。
- `requests` 必须 `S.trust_env=False`（绕代理），并用 `json.loads(resp.content.decode("utf-8"))`
  而不是 `.json()`，否则中文标题乱码。
- 封面走 `material/add_material?type=thumb`（>64KB 先 PIL 压到 64KB 内），失败回退 `type=image`。
- 脚本**先做一遍静态校验**（正文 <20000 字符、封面存在），再逐篇推，避免跑到一半才发现超限。
- **草稿接口不写合集**。合集只在后面的浏览器自动化发表阶段（`wxflow.mjs` 的 `WX_ALBUM`）设置，
  所以两条链路要配合：先服务器推草稿 → 再从草稿箱列表读 `file_id` → `wxflow.mjs` 发表并挂合集。

2026-10-08 实操：CNCV 系列 8 篇 → 8/8 建草稿成功，随后 8/8 发表成功挂进「寒武纪MLU开发」。

**批量发表属于对外可见的不可逆操作**：先 `list` 给用户看清单 → 用户勾选 → 再 `--yes` 执行，
不要一上来就 `--all --yes`。**先拿 1 篇试发**验证权限，比闷头跑 40 篇再一起失败划算得多。

### 同名重复草稿的处理

批量发表前先按标题找出重复项（同一标题多份），**逐版比对正文**再定：
`draft/get` 取 `news_item[0].content`，比较纯文字 MD5、图片数、封面 `thumb_media_id`、图片 alt。
纯文字一致时，挑**最新一版**（通常封面 alt 已同步成新标题）；旧副本跳过不发表，
留在草稿箱里什么都没丢，选错了再补发成本极低。

**确认要清掉旧副本时**，用 `wxdel.mjs`。删除入口与发表在同一根操作栏：
hover 卡片 → `.weui-desktop-publish__opr` 里的**垃圾桶图标**（`a.weui-desktop-icon-btn`，20×20，
**没有文字**，所以不能用「按文字找按钮」那套）→ 弹 `.weui-desktop-popover` → 点其
`button.weui-desktop-btn_primary`（=「删除」；`btn_default` 是「取消」）。

- 定位 wrapper 要**按 tooltip 文字找**（`w.querySelector('.weui-desktop-tooltip')` 文本为「删除」），
  **不要按顺序取** —— 编辑/删除的先后可能变。已封装在 `DEL_WRP_EXPR`。
- 确认框原文：**「确定删除？删除该内容不会删除已发表的内容」** ——
  **删草稿不动线上文章**，所以"发表完再删旧副本"是安全的顺序。
- 删完卡片会消失，**序号会整体前移**，所以每篇都重新按 `file_id` 定位，不要缓存下标。
- 改完选择器**先 `DRY=1` 干跑**一次验证能定位到图标，再真删。

2026-10-08 实操：书画集 16 篇全部发表完毕后，用 `wxdel.mjs` 删掉
「牛赞」旧副本 2 篇（100000484/100000488）与「8个头不是8种职务」旧副本 2 篇（100000817/100000821），
草稿箱 26 → 22，4/4 成功。

---

## 七、接口走不通时的兜底：浏览器自动化代劳（CDP 直连真 Chrome）

个人主体 / 未认证账号没有 `freepublish` 权限（恒返 `48001`），草稿→发表只能走后台页面。
这时用**远程调试端口驱动本机已装的真 Chrome**，比装 Playwright 轻得多，也更不容易被判成机器人。

### 起步

```bash
# 独立配置目录启动，不碰用户日常浏览器
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 --user-data-dir=/tmp/wxchrome \
  --no-first-run --no-default-browser-check https://mp.weixin.qq.com/
# 用户在弹出的窗口里扫码登录一次，之后会话 cookie 就在这个独立目录里
```

- `scripts/cdp.mjs` — 零依赖 CDP 客户端（Node 内置 WebSocket/fetch，**不装 Playwright**）。
  子命令：`tabs / eval / nav / shot / shotel / hover / realclick / rclicktext / hovertext / click / clicktext / type / pubclick / front / newtab`
  选择器支持 `@N:selector` 取第 N 个匹配元素；普通选择器**优先取真正可见的**（页面里同名隐藏副本极多）。
- `scripts/wxflow.mjs` — 草稿箱批量发表状态机：`node wxflow.mjs <file_id,file_id,...>`
  环境变量 `WX_TOKEN`（后台 token，必填）、`WX_ALBUM`（合集名，必填）、`WX_SCAN_TIMEOUT`（默认 180s）、`CDP_PORT`（默认 9222）。
  结果写 `/tmp/wxflow_result.json`（`[{ok,title,reason}]`）。
- `scripts/wxtietu.mjs` — **贴图**草稿批量发表状态机（图文那套强依赖「原创+合集」，贴图没有，会卡死）。
  `node wxtietu.mjs list` 列草稿；`node wxtietu.mjs <file_id,…|标题关键词,…>` 发表。
  内置列表页自愈 + 单篇重试。详见 §八。
- `scripts/wxdel.mjs` — 草稿箱批量删除：`node wxdel.mjs <file_id,...>`，`DRY=1` 只定位不点（**改选择器后一律先 DRY**）。
  结果写 `/tmp/wxdel_result.json`。删除入口见 §6.2。

> **改脚本时的红线**：`stepConfigure()` 的 `massSwitchOn` 分支**只能关闭**开关，
> 不许加"是否需要群发"的参数。草稿箱批量场景下群发额度必然不够，这是产品决策不是配置项。

### 发表链路（后台草稿箱）

列表 `appmsg?begin=0&count=50&type=77&action=list_card&token=<T>`（count=50 一页拉全）→
悬停卡片 → 点 `.publish_enable_button a` → **新开编辑页标签** →
①关掉自动弹出的发表框 ②「原创」行（`.setting-group__title`）→ 文字原创 + 勾协议 → 确定
③`#js_article_tags_area .js_article_tags_label` → 合集下拉 → 确认
④`#js_send` → **关掉「群发通知」**（`.mass_send__notify` 的 switch 必须 off，见铁律 1）→ 发表 →
二次确认「继续发表」→
**「微信验证」二维码**（`img.qrcode.js_qrcode`）→ 管理员/运营者扫码 → 编辑页自动关闭 = 成功。
核实：`appmsgpublish?sub=list` 发表记录（先「审核中」，随后「已发表」+ 原创标）。

**扫码绕不过**：每一篇都要扫一次，无法一次性授权批量过。

### 必踩的坑（这几条不照做一定卡住）

| 现象 | 根因 | 正解 |
|---|---|---|
| 点发表按钮毫无反应 | 列表标签是 `hidden`（非当前活动标签），hover 工具栏不出现 | 操作前 `Page.bringToFront` |
| hover 后点不到「发表」 | `scrollIntoView` 会让 hover 失效、工具栏重新隐藏 | 悬停→重测坐标→点击，一次调用内完成 |
| 判「弹窗已关」但所有点击被吞 | 弹窗外层容器**高度恒为 0**（`.new_mass_send_dialog` w=1067 h=0），宽高双判误判为关闭 | 判据改为**「弹窗内部的确定按钮是否可见」** |
| 点右上角 X 关不干净 | X 只收起内容，`weui-desktop-dialog__wrp` 遮罩仍拦截点击 | 必须点弹窗内的**「取消」**（`button.weui-desktop-btn_default`） |
| 点到隐藏副本 | 页面大量同名元素（宽>0 高=0） | 选择器统一「取第一个真正可见的」 |
| 卡片顺序与接口时间顺序不一致 | 前端排序不稳定 | 用 Vue 实例 `__vue__.$data.list[0].file_id` 精确定位，不靠位置 |
| 二维码截图是空白纯色图 | 跨域图片按元素区域 `clip` 截图，合成层没画出来 | **别截图**，`Page.bringToFront` + `osascript -e 'tell application "Google Chrome" to activate'` 把整页推到用户屏幕前端让他直接扫 |
| 合集弹窗开着、输入框空、选项查不到，反复点 `select-input` 卡死 | 合集下拉的 `.select-opt-li` 是 **body 下的浮层（portal）**，不在 `.album-setting-dialog` 内部；按弹窗内部查永远判"没打开" → 点了开又点关 | 选项**全局查**：`document.querySelectorAll('.select-opt-li')` + 可见性过滤（2026-10-08 修，见 `wxflow.mjs`） |
| 起草稿后「合集」一栏是「未添加」而卡死 | 同上；该篇原先没设过合集，走的分支略不同 | 同上，全局查选项即可恢复 |
| 批量跑完，草稿箱里**还剩刚发表的那一两篇** | 发表成功后**草稿条目从草稿箱移除是异步的**，有几分钟延迟 | **别急着当成失败**。先看 `appmsgpublish?sub=list` 发表记录——只要显「已发表」就是成了。等 1~3 分钟重载草稿箱即消失（2026-10-08 实测：最后一篇先是残留，随后草稿箱变「暂无素材」） |
| `wxflow.mjs` 秒退，报 `没有匹配的页面: action=list_card` | 草稿列表页那个标签被关掉了（清理标签时容易误关），CDP 找不到落点 | 先 `cdp.mjs newtab "…appmsg?begin=0&count=50&type=77&action=list_card&token=<T>…"` 把草稿列表页开回来，再跑 `wxflow.mjs`（2026-10-09 踩过） |
| 批量发表偶发某一篇 `等待超时: 编辑页打开`（约 40s 后抛） | 编辑页加载/弹窗时序抖动，**不是内容问题**（该篇草稿、原创、合集都正常） | **原样重跑那一篇即可**，第二次通常 40~70s 过。别去改 `wxflow.mjs`（2026-10-09：9 篇里挂 2 篇，重跑即过） |

### 合集排序与简介（补发的文章会掉到最后）

合集默认「正序」= 按发表时间从早到晚。**批量发表中途失败、事后补发的那几篇，发表时间最晚，
一定落在合集最末**——发表收尾时必须回编辑页核对顺序（2026-10-09 BANG 系列：02、06 补发后
掉到第 17、18 位，读者从第 1 篇读下去会断掉）。

排序方式：编辑页的文章列表是**拖拽列表**（`div.weui-desktop-drag-list__item.album__list-item`），
每行**行尾**有拖拽手柄 `.album__list-action-move`。

```bash
CDP_MATCH="action=edit" node wxdrag.mjs --from "源标题关键词" --to "目标标题关键词" \
    --mode before|after --scroll 900     # scroll 调到让源项落在视口中间，别贴着底边
```

**四条硬性前提（不满足就拖不动，只会看到文字被选中）**：

1. **起手必须按在行尾的拖拽手柄上**（x≈1199），按在行中央 = 开始选文本。脚本已自动取手柄中心。
2. 先 `Page.bringToFront`——否则 Input 域的鼠标事件被丢弃甚至挂起（表现为脚本卡死）。
3. **源项不能落在视口底部 100px 内**，也不能压在右下角「问题反馈」悬浮球上（会挡住手柄）。
   靠 `--scroll` 把源项挪到视口中间重试。
4. **合成 DOM 事件（MouseEvent / PointerEvent，`isTrusted=false`）一律无效**，这个库不收；
   只能用 CDP 的 `Input.dispatchMouseEvent` 发真实鼠标序列（按下 → 多帧平滑移动 → 抬起）。

⚠️ `--mode` 的语义**与直觉相反**（实测）：落点在目标**上半区** → 源项插到目标**后面**；
落点在**下半区** → 插到目标**前面**。每拖一次都读一遍列表确认，往往要再微调一格。

**改合集简介**（同一页）：

```js
// textarea.weui-desktop-form__textarea，用原生 setter 绕过 Vue 的 value 追踪
const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
setter.call(ta, "新简介");
ta.dispatchEvent(new Event("input", { bubbles: true }));
```

顺序 + 简介改完，**都要点编辑页底部的「发布」按钮**（文案是「发布」不是「保存」，
`button.weui-desktop-btn_primary`）才写回服务器；成功后自动跳回合集列表页。
验证：重新打开 `appmsgalbummgr?action=edit&type=0&id=<id>`，读 `textarea.value` 与列表顺序。

### 安全与礼貌

- 默认**先跑 1 篇**验证链路，再批量。
- 批量发表是**对外可见、不可逆**的操作：先给用户看清单 + 讲清后果（不推粉丝、不占群发次数）再动手。
- 状态机一定要带**熔断**（同一状态重复 N 次就抛错），否则会在错误的页面上空转。

---

## 八、「贴图」（图片消息 / newspic）的建草稿与发表

「贴图」= 微信的**图片消息**：最多 20 张图 + 标题 + ≤1000 字描述，正文靠图片承载。
它和图文是**两套完全不同的编辑器和发表流程**——别拿 `wxflow.mjs` 硬套，会卡死。

### 8.1 建草稿：必须走接口，网页上传控件注不进去

- **网页上传这条路走不通**（2026-10-09 实测）：贴图编辑器的 `input[type=file]` 被 WebUploader 接管，
  `DOM.setFileInputFiles` 之后 `input.files.length` 恒为 **0**，图片传不进去，页面一直停在空的选择框
  （脚本还会误报「上传完成 9/9」）。这条已弃用。
- **正解**是官方接口原生支持：
  1. 每张图 `POST /cgi-bin/material/add_material?type=image`（**必须永久素材**，临时素材不行）→ `media_id`
  2. `POST /cgi-bin/draft/add`，`article_type: "newspic"`：

     ```json
     { "articles": [{
         "article_type": "newspic",
         "title": "≤20 字",
         "content": "纯文本描述",
         "need_open_comment": 0, "only_fans_can_comment": 0,
         "image_info": { "image_list": [ { "image_media_id": "..." } ] }
     }]}
     ```

     `image_list` **最多 20 张，首张即封面**；newspic 下 `content` 只支持纯文本。
- **标题网页端限 20 字**（编辑器里显示 `20/20`，超了报「标题长度不能超过20字」）。
  `draft/add` 文档虽写 32 字，但**按 20 字准备**，否则用户在网页端改不动。
- 脚本：`scripts/wx_push_tietu.py`（**跑在白名单服务器上**，本机 IP 会被 40164 挡）。
  参数 `--plan --root [--only N] [--skip N] [--dry-run] [--out]`；>20 张或缺图的条目自动跳过。
  实测 9~17 张/篇，单篇 19~35s，17 篇约 8 分钟。

### 8.2 发表：弹窗比图文简单，但压根没有群发开关

贴图的发表弹窗**和图文不是一回事**（2026-10-09 实测）：

- 只有「**定时发表**」一个开关（默认关），**没有「群发通知」**——弹窗原文写着
  「发表贴图**无需开启**群发通知」。所以贴图发表天然不推粉丝，等价于图文的「关群发」。
- **没有「原创」设置，也没有「合集」入口** → 贴图进不了合集，不参与系列排序。
- 从草稿卡片点「发表」，编辑页打开后**发表弹窗会自动弹出**，不用再去点 `#js_send`。

流程：卡片 hover → `.publish_enable_button a` → 编辑页 → 发表弹窗（确认「定时发表」是关的）→
`button.weui-desktop-btn_primary` → 二次确认 `.double_check_dialog` → **微信验证二维码**（每篇扫一次）。

脚本：`scripts/wxtietu.mjs`

```bash
node wxtietu.mjs list                                # 列草稿（file_id + 标题）
node wxtietu.mjs 100001003,100001018                 # 按 file_id 批量发表
node wxtietu.mjs "CNCV 的句柄,写下第一个 BANG 程序"     # 也支持按标题关键词定位
```

环境变量：`WX_TOKEN`（后台 token，必填）、`WX_SCAN_TIMEOUT`（默认 180s）、`CDP_PORT`（默认 9222）、
`WX_RESULT_OUT`（结果 JSON 路径，默认 `/tmp/wxtietu_result.json`）。

### 8.3 贴图特有的坑（这几条不处理会整批失败）

| 现象 | 根因 | 正解 |
|---|---|---|
| 第 1 篇发完，后面**几十篇全秒退** `没有匹配的页面: action=list_card` | 发表成功后**草稿列表页那个标签被连带关掉**，后续找不到落点 | 每篇开跑前先查 `action=list_card` 标签在不在，不在就 `PUT /json/new?<url>` 重开（`wxtietu.mjs` 的 `ensureListPage()` 已内置，并对单篇再重试一次） |
| 草稿箱里明明有，却报 `已无 file_id=xxx` | **发表失败的那次尝试会把草稿重存一遍**，Vue 里 `$data.list[0].file_id` 变成占位值 **0** | 改用**标题匹配**定位卡片（`wxtietu.mjs` 传标题关键词即可）。别信 file_id 的稳定性——判「失败」后一定要回草稿箱看一眼真伪 |
| 发表弹窗一直点不动，状态机判「卡死」 | `clickIn` 原来只按**宽度**判可见性，点到了「宽>0 但高=0」的隐藏副本 | 先 `[...root.querySelectorAll(sel)].find(_vis)`（宽高都 >0），取不到再退回第一个 |
| 偶发 `等待超时: 编辑页打开` | 点卡片到编辑页弹出的时序抖动，与内容无关 | 清理残留编辑页 + 重开列表页 + 重新点一次卡片（`wxtietu.mjs` 已内置一次重试） |
| 一篇报「扫码超时」，其实用户后来扫上了 | 状态机超时后先行判失败，而草稿已被消费掉 | 事后回草稿箱核对：草稿**消失**=发表成功；草稿仍在=真失败，再补跑 |

### 8.4 微信会自己把图文转成贴图草稿（平台行为，别混淆）

2026-10-09 发现：**已发表的图文**，在发表记录里会附一条
「**已自动将文章生成为贴图草稿**，发布后优先推荐给非粉丝用户，触达更多新读者」，
草稿箱里也会相应多出贴图草稿。

所以当用户说「我的文章怎么都变成贴图草稿了」——**这是平台行为，不是脚本干的**。
手工做的贴图（走 8.1 的接口）和平台自动生成的贴图，在草稿箱里是**两批不同的条目**。

### 8.5 环境：本机命令「集体跑不动」时先查运行时路径

托管 Node 的版本目录形如 `~/.workbuddy/binaries/node/versions/<ver>/`。
版本被替换后**旧目录会被删掉**，所有依赖它的包装命令（`ls`/`head`/`node`…）会集体报
`No such file or directory`，或干脆被 `SIGTERM` 杀掉、**没有任何输出**。

遇到这种「命令全都跑不了」的情况：先 `ls ~/.workbuddy/binaries/node/versions/` 看实际版本号，
或直接用系统 Node（`/opt/homebrew/bin/node`）。2026-10-09 实际踩过：`22.22.2-3` → `22.22.2-6`，
中途整个 Chrome 的标签页也被清空（重开后登录态仍在，草稿箱正常）。



