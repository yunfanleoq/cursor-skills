# WeChat Article Agent Server

资料 → Markdown → 微信 HTML → 草稿箱，HTTP 服务化。支持 **Webhook**、**Cron 定时**、**C++ 平台 HTTP 调用**。

## 快速启动

```powershell
cd wechat-agent-server
copy config.example.json config.json
# 编辑 config.json 中的 api_key
pip install -r requirements.txt
python app.py
# 或双击 start.cmd
```

服务默认监听 `http://0.0.0.0:8780`。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查（无需鉴权） |
| POST | `/api/v1/jobs` | 创建任务 |
| POST | `/api/v1/webhook` | Webhook 别名（同上） |
| GET | `/api/v1/jobs/{id}` | 查询任务状态 |
| GET | `/api/v1/jobs` | 任务列表 |

请求头（若配置了 `api_key`）：

```
X-API-Key: your-secret
Content-Type: application/json
```

### 创建任务示例

```bash
curl -X POST http://127.0.0.1:8780/api/v1/webhook \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me-to-a-long-random-secret" \
  -d '{
    "title": "Agentic Patterns 科普指南",
    "markdown_path": "articles/从零到一理解-Agentic-Patterns-科普版.md",
    "thumb_path": "articles/diagrams/ai-agent-roadmap.png",
    "publish": false,
    "async_mode": true
  }'
```

从原始资料生成（可选 LLM 写稿）：

```json
{
  "title": "新文章标题",
  "source_path": "articles/agentic-patterns-source.txt",
  "source_type": "text",
  "generate_article": true,
  "thumb_path": "articles/diagrams/ai-agent-roadmap.png"
}
```

需设置 `OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY`。

## 定时任务

在 `config.json` 的 `schedules` 数组中配置 cron（5 段：分 时 日 月 周）：

```json
{
  "id": "weekly-post",
  "enabled": true,
  "cron": "0 9 * * 1",
  "title": "每周一推送",
  "markdown_path": "articles/xxx.md",
  "thumb_path": "articles/diagrams/cover.png"
}
```

## 嵌入 C++ 编程平台

**推荐架构：Sidecar（旁路服务）**

```
┌─────────────────────┐     HTTP POST      ┌──────────────────────────┐
│  C++ 编程平台        │ ─────────────────► │  WeChat Agent (Python)   │
│  (OJ / IDE / 课程)   │ ◄───────────────── │  :8780                   │
└─────────────────────┘     JSON job_id      └──────────────────────────┘
                                                      │
                                                      ▼
                                              微信草稿 API
```

**为什么用 HTTP 而不是把 Python 嵌进 C++？**

| 方案 | 优点 | 缺点 |
|------|------|------|
| **HTTP Sidecar（推荐）** | 语言无关、易部署、微信 IP 白名单固定在一台服务器 | 多一个进程 |
| pybind11 嵌入 Python | 同进程 | 依赖重、打包难、GIL 与崩溃隔离差 |
| QProcess 调脚本 | 简单 | 无标准 API、难监控任务状态 |

C++ 示例见 `examples/cpp/wechat_agent_client.cpp`（WinHTTP，VS 可直接编译）。

平台集成步骤：

1. 服务器或本机常驻运行 `python app.py`（云服务器可固定 IP 解决微信白名单）
2. C++ 在用户「发布专栏 / 导出教程 / 定时推送」时调用 `POST /api/v1/webhook`
3. 轮询 `GET /api/v1/jobs/{job_id}` 直到 `status` 为 `succeeded`
4. 运营在 mp.weixin.qq.com 草稿箱预览后发表

## 微信凭据

与 CLI 相同：`~/.cursor/wechat-publish.json` 或环境变量 `WECHAT_APPID` / `WECHAT_APPSECRET`。

## 任务持久化

任务 JSON 保存在 `wechat-agent-server/data/jobs/`。
