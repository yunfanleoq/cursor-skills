#!/usr/bin/env bash
# Install Anthropic OpenSkills to a project (cannot be vendored in cursor-skills — proprietary license).
# Usage: ./scripts/install-openskills.sh [project_dir]
set -euo pipefail

TARGET="${1:-.}"
SOURCE="${OPEN_SKILLS_SOURCE:-anthropics/skills}"

if ! command -v openskills >/dev/null 2>&1; then
  echo "openskills CLI not found. Install: npm install -g openskills"
  exit 1
fi

cd "$TARGET"
mkdir -p .agent/skills

echo "==> Installing ${SOURCE} to ${TARGET}/.agent/skills (universal)"
openskills install "$SOURCE" --universal -y

if [[ -d .claude/skills ]]; then
  echo "==> Removing legacy .claude/skills"
  rm -rf .claude/skills
  rmdir .claude 2>/dev/null || true
fi

if [[ -f AGENTS.md ]]; then
  echo "==> Syncing AGENTS.md"
  openskills sync -y
fi

echo "==> Installed:"
openskills list
echo "Done. pptx/docx/pdf/xlsx 等技能位于 .agent/skills/ — 勿提交到公开仓库（Anthropic 专有许可）。"
