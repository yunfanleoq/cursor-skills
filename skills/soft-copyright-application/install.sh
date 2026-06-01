#!/usr/bin/env bash
# 安装到 Cursor 全局技能目录：~/.cursor/skills/soft-copyright-application/
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${HOME}/.cursor/skills/soft-copyright-application"

echo "安装 soft-copyright-application Skill"
echo "  源: ${SRC}"
echo "  目标: ${DEST}"

mkdir -p "${HOME}/.cursor/skills"
rm -rf "${DEST}"
mkdir -p "${DEST}"

shopt -s dotglob
for item in "${SRC}"/*; do
  base="$(basename "${item}")"
  case "${base}" in
    .git|.github|install.ps1|install.sh|README.md) continue ;;
  esac
  cp -R "${item}" "${DEST}/"
done

echo "安装 Python 依赖..."
python3 -m pip install -r "${DEST}/requirements.txt"

echo ""
echo "完成。请重启 Cursor，或在项目中运行："
echo "  python3 ${DEST}/scripts/init_soft_copyright_scope.py"
