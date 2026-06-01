"""Build 操作说明书.md from scope, scenario, and captured screenshots."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def build_manual_markdown(
    project_root: Path,
    scope_path: Path,
    scenario_path: Path,
    manual_path: Path,
    capture_results: list[dict[str, Any]] | None = None,
) -> str:
    scope = _load_yaml(scope_path)
    scenario = _load_yaml(scenario_path)
    sw = scope.get("software", {})
    ap = scope.get("applicant", {})
    dev = scope.get("development", {})

    full_name = sw.get("full_name", "软件全称")
    version = sw.get("version", "V1.0")
    applicant = ap.get("name", "著作权人")
    purpose = dev.get("purpose", "")
    today = date.today().isoformat()

    cap_by_id = {r.get("id"): r for r in (capture_results or [])}

    def img(step_id: str, default: str, caption: str) -> str:
        r = cap_by_id.get(step_id, {})
        rel = r.get("path") or f"screenshots/{default}"
        if not rel.startswith("screenshots/"):
            rel = f"screenshots/{default}"
        return f"![{caption}]({rel})\n\n"

    def append_images(lines: list[str], sec: dict[str, Any], title: str) -> None:
        ids = sec.get("screenshot_ids") or []
        sid = sec.get("id", "")
        if not ids and sid:
            ids = [sid]
        for idx, shot_id in enumerate(ids):
            if shot_id in cap_by_id and cap_by_id[shot_id].get("ok"):
                cap = title if len(ids) == 1 else f"{title}（{idx + 1}）"
                lines.append(img(shot_id, "", cap))

    steps_doc = scenario.get("manual_steps", [])
    step_sections: list[str] = []
    for sec in steps_doc:
        sid = sec.get("id", "")
        title = sec.get("title", "")
        intro = sec.get("intro", "")
        bullets = sec.get("steps", [])
        lines = [f"### {title}\n", f"{intro}\n"]
        append_images(lines, sec, title)
        for i, b in enumerate(bullets, 1):
            lines.append(f"**步骤 {i}** {b}\n")
        lines.append(f"\n**预期结果** {sec.get('expected', '界面显示与描述一致。')}\n")
        step_sections.append("\n".join(lines))

    md = f"""# {full_name} {version} 用户操作手册

**著作权人**：{applicant}  
**文档版本**：{version}  
**编写日期**：{today}  
**文档类型**：用户操作手册（软件著作权登记鉴别材料）

---

## 目录

1. 引言  
2. 运行环境  
3. 安装与部署  
4. 系统登录  
5. 功能操作说明  
6. 常见问题  
附录 A 术语表  

---

## 第 1 章 引言

### 1.1 编写目的

本文档用于指导用户安装、配置与使用《{full_name}》（版本 {version}），帮助代理人、流程专员与管理员快速掌握系统各项功能。

### 1.2 软件概述

{full_name}（简称 {sw.get('short_name', '')}）面向知识产权代理行业，提供审查意见（OA）答复智能辅助、领域知识库检索、案件工作台与系统管理等功能。

**建设目标**：{purpose}

### 1.3 适用对象

专利代理机构代理人、流程专员、知识库管理员及系统管理员。

### 1.4 术语与缩略语

| 术语 | 说明 |
|------|------|
| WOA | 审查意见通知书答复（Office Action Response） |
| OA | 审查意见通知书 |
| RAG | 检索增强生成 |
| 工作台 | 单案三栏式答复编辑界面 |

---

## 第 2 章 运行环境

### 2.1 硬件环境

| 项目 | 最低配置 | 推荐配置 |
|------|----------|----------|
| 处理器 | x86_64 双核 | 四核及以上 |
| 内存 | 8 GB | 16 GB 及以上 |
| 磁盘 | 10 GB 可用空间 | SSD 50 GB 及以上 |

### 2.2 软件环境

| 组件 | 要求 |
|------|------|
| 操作系统 | {dev.get('os_run', 'Windows 10/11 或 Linux')} |
| 浏览器 | Chrome / Edge 120 及以上 |
| 数据库 | {dev.get('support_env', 'SQLite 或 PostgreSQL')} |
| 后端运行时 | Python 3.12（服务器部署） |
| 前端运行时 | Node.js 20+（构建部署阶段） |

### 2.3 网络环境

客户端需能访问应用服务器 HTTP/HTTPS 端口；若启用大语言模型接口，服务器需能访问相应 API 网关（生产环境由管理员配置）。

---

## 第 3 章 安装与部署

### 3.1 获取软件

以源代码或部署包形式获取，解压至目标目录。

### 3.2 安装步骤

**步骤 1** 复制环境配置：将 `.env.example` 复制为 `.env` 并按需修改数据库与模型配置。  

**步骤 2** 安装后端依赖：在 `backend` 目录创建虚拟环境并执行 `pip install -e .`。  

**步骤 3** 安装前端依赖：在 `frontend` 目录执行 `npm install`。  

**步骤 4** 初始化演示数据（可选）：执行 `scripts/seed_demo.ps1` 导入示例案件与知识库。  

**步骤 5** 启动服务：执行 `scripts/dev.ps1`，分别启动后端（8000 端口）与前端（5173 端口）。  

**步骤 6** 浏览器访问 `http://localhost:5173` 验证登录页可打开。

### 3.3 卸载说明

停止前后端进程后删除安装目录即可；SQLite 数据位于 `.storage` 目录，可按需备份后删除。

---

## 第 4 章 系统登录

### 4.1 功能说明

系统采用账号密码登录，验证通过后根据用户所属租户与角色加载菜单与功能权限。登录成功后默认进入案件列表页。

| 角色 | 说明 | 主要权限 |
|------|------|----------|
| 租户管理员 | 管理本租户账号与配置 | 用户、部门、AI 流程、知识库源等设置 |
| 合伙人/部门负责人 | 统筹本部门案件与审核 | 案件管理、策略审核 |
| 专利代理人 | 办理 OA 答复案件 | 案件列表、工作台、知识库、AI 助手 |
| 流程专员 | 期限与流程监控 | 案件查阅、期限相关功能 |
| 知识库管理员 | 维护知识库内容 | 知识库管理、检索与入库 |
| 只读用户 | 查阅案件与知识 | 仅读权限 |

### 4.2 操作步骤

**步骤 1** 在浏览器地址栏输入系统地址，打开登录页面。  

**步骤 2** 在「账号」输入框填写用户名，在「密码」输入框填写密码。  

**步骤 3** 单击「进入工作台」按钮。  

**步骤 4** 登录成功后，左侧导航按角色显示菜单；右上方显示当前用户信息。

### 4.3 预期结果

系统跳转至案件列表页面，左侧显示导航菜单，右上方显示当前用户信息。

### 4.4 登录界面示意

{img('S01', '01-login/01-login-page.png', '登录界面')}

### 4.5 登录后案件列表

{img('S02', '01-login/02-home-after-login.png', '登录后案件列表')}

---

## 第 5 章 功能操作说明

{chr(10).join(step_sections)}

---

## 第 6 章 常见问题

本章汇总安装、登录与使用过程中可能遇到的问题及处理方法。

### 6.1 无法打开登录页

**现象**：浏览器访问系统地址后页面无法加载。

**可能原因**：前端未启动或端口占用。

**处理方法**：检查 5173 端口，重新运行 dev.ps1。

### 6.2 登录失败

**现象**：提示用户名或密码错误。

**可能原因**：账号密码错误或库未初始化。

**处理方法**：使用管理员账号或执行 seed_demo。

### 6.3 工作台无案件文档

**现象**：文档树为空。

**可能原因**：未导入演示数据。

**处理方法**：运行 seed_demo.ps1。

### 6.4 智能体运行失败

**现象**：流水线步骤失败或长时间无响应。

**可能原因**：LLM 未配置。

**处理方法**：在 .env 中配置 LLM_PROVIDER 与密钥。

---

## 附录 A 术语表

本附录汇总本手册及系统中常用术语与缩略语。

| 术语 | 说明 |
|------|------|
| WOA | 审查意见通知书答复（Office Action Response） |
| OA | 审查意见通知书 |
| RAG | 检索增强生成 |
| 工作台 | 单案三栏式答复编辑界面 |
| 智能体 | 按工作流执行 OA 解析、策略生成等任务的 AI 模块 |
| 知识库 | 存储法规、指南与案例的检索源 |

"""
    manual_path.parent.mkdir(parents=True, exist_ok=True)
    manual_path.write_text(md, encoding="utf-8")
    return md
