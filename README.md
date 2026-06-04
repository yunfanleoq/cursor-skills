# cursor-skills

个人 [Cursor Agent Skills](https://cursor.com/docs/context/skills) 合集，统一管理 `~/.cursor/skills/` 下的全局技能。

## 技能目录

| 技能 | 说明 | 触发词示例 |
|------|------|-----------|
| [jeecg-webapp-security-scan](skills/jeecg-webapp-security-scan/) | JeecgBoot 类 Web 应用安全扫描（Shiro/JWT、IDOR、报表、Druid 等） | 漏洞扫描、渗透测试、JeecgBoot 安全 |
| [jeecg-e2e-doc-capture](skills/jeecg-e2e-doc-capture/) | JeecgBoot Vue3 E2E：多角色登录、验证码 OCR、截图采集、软著操作手册 | E2E 测试、doc-capture、操作说明书采集 |
| [soft-copyright-application](skills/soft-copyright-application/) | 中国软件著作权登记材料（源程序 PDF、操作手册、申请表） | 软著、鉴别材料 PDF、操作说明书 |
| [wechat-article-publish](skills/wechat-article-publish/) | 微信公众号文章整理与远程/本地发布 | 公众号、mp.weixin.qq.com、wechat.yclub.xin |
| [frontend-code-review](skills/frontend-code-review/) | 前端代码审查清单（.tsx/.ts/.js） | code review、前端审查 |
| [baoyu-slide-deck](skills/baoyu-slide-deck/) | 长文档拆 PPT、自动配图、导出 PPTX/PDF | 做 PPT、述职汇报、slide deck |
| [ppt-master](skills/ppt-master/) | 多模板、自然语言改单页、批量配色，原生可编辑 PPTX | 从 PDF/MD 生成 PPT、改配色 |
| [pptx-convert](skills/pptx-convert/) | 修改已有 PPTX、增删页、提取内容复用模板 | 改 PPT、增删幻灯片、OOXML |

> **OpenSkills（Anthropic）**：`pptx`/`docx`/`pdf` 等 **不可纳入本仓库**（专有许可）。请用 [scripts/install-openskills.sh](scripts/install-openskills.sh) 在项目中安装，见 [manifest/openskills.json](manifest/openskills.json)。

## 快速安装

### 安装全部技能（推荐）

**Windows（PowerShell）：**

```powershell
git clone https://github.com/yunfanleoq/cursor-skills.git
cd cursor-skills
.\install.ps1
```

**macOS / Linux：**

```bash
git clone https://github.com/yunfanleoq/cursor-skills.git
cd cursor-skills
chmod +x install.sh
./install.sh
```

安装目标：`~/.cursor/skills/<skill-name>/`（Windows：`%USERPROFILE%\.cursor\skills\`）

安装完成后**重启 Cursor**，或在对话中提及对应触发词，Agent 会自动加载 `SKILL.md`。

### 安装单个技能

```powershell
.\install.ps1 -Skill jeecg-webapp-security-scan
```

```bash
./install.sh jeecg-webapp-security-scan
```

### Python 依赖（按需）

部分技能需要额外依赖，安装脚本会提示；也可手动执行：

```powershell
# 软著
py -3.12 -m pip install -r skills/soft-copyright-application/requirements.txt

# 公众号
py -3.12 -m pip install -r skills/wechat-article-publish/requirements.txt
py -3.12 -m playwright install chromium

# PPT Master（生成/编辑 PPTX 脚本）
pip install -r skills/ppt-master/requirements.txt
```

## 仓库结构

```
cursor-skills/
├── README.md
├── install.ps1 / install.sh      # 一键安装到 ~/.cursor/skills/
├── scripts/
│   └── install-openskills.sh     # 项目内安装 Anthropic OpenSkills（不可入库）
├── manifest/
│   └── openskills.json           # OpenSkills 清单与说明
├── publish-github.ps1            # 维护者推送脚本
├── skills/
│   ├── baoyu-slide-deck/
│   ├── ppt-master/
│   ├── pptx-convert/
│   ├── jeecg-webapp-security-scan/
│   ├── jeecg-e2e-doc-capture/
│   ├── soft-copyright-application/
│   ├── wechat-article-publish/
│   └── frontend-code-review/
└── THIRD_PARTY_NOTICES.md
```

## 与旧独立仓库的关系

以下技能曾单独发布，现已并入本 monorepo：

| 旧仓库 | 状态 |
|--------|------|
| [soft-copyright-application-skill](https://github.com/yunfanleoq/soft-copyright-application-skill) | 归档，以本仓库 `skills/soft-copyright-application/` 为准 |
| [wechat-article-publish](https://github.com/yunfanleoq/wechat-article-publish) | 归档，以本仓库 `skills/wechat-article-publish/` 为准 |

## 维护

```powershell
# 修改 skills/ 下内容后
git add .
git commit -m "update: ..."
.\publish-github.ps1
```

## 许可证

- 本仓库原创技能（Jeecg 安全扫描、E2E 采集、前端审查等）：MIT，见 [LICENSE](LICENSE)
- `soft-copyright-application`：MIT（见子目录 LICENSE）
- `wechat-article-publish`：MIT（见子目录 LICENSE）
- `pptx`：未收录，Anthropic 专有许可
