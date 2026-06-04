# 第三方与许可说明

## 未收录（不可再分发）：Anthropic OpenSkills

`anthropics/skills` 中的 `pptx`、`docx`、`pdf`、`xlsx` 等技能，其 `LICENSE.txt` 明确禁止再分发与衍生。因此 **本仓库不包含这些技能文件**。

在新机器或项目中安装：

```bash
npm install -g openskills
./scripts/install-openskills.sh /path/to/your-project
```

技能清单见 [manifest/openskills.json](manifest/openskills.json)。安装结果位于项目 `.agent/skills/`，请加入 `.gitignore`。

## 已收录：第三方 PPT 技能

| 目录 | 上游 | 许可 |
|------|------|------|
| `skills/baoyu-slide-deck/` | [JimLiu/baoyu-skills](https://github.com/JimLiu/baoyu-skills) | 见上游 LICENSE |
| `skills/ppt-master/` | [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) | MIT |
| `skills/pptx-convert/` | [claude-office-skills/skills](https://github.com/claude-office-skills/skills) `pptx-manipulation` | MIT |

各子目录 `SOURCE.md` 记录同步方式。

## 子目录独立许可

| 目录 | 许可 |
|------|------|
| `skills/soft-copyright-application/` | MIT（见子目录 LICENSE） |
| `skills/wechat-article-publish/` | MIT（见子目录 LICENSE） |
| 其余 `skills/*/` | MIT（本仓库根 LICENSE） |

## 历史独立仓库

以下仓库内容已合并至本 monorepo，建议在新机器上克隆本仓库而非旧地址：

- https://github.com/yunfanleoq/soft-copyright-application-skill
- https://github.com/yunfanleoq/wechat-article-publish
