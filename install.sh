#!/usr/bin/env bash
# Install Cursor global skills from this monorepo to ~/.cursor/skills/
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILLS_ROOT="$REPO_ROOT/skills"
DEST_ROOT="${HOME}/.cursor/skills"
SKILL="${1:-all}"

ALL_SKILLS=(
  frontend-code-review
  jeecg-e2e-doc-capture
  jeecg-webapp-security-scan
  soft-copyright-application
  wechat-article-publish
)

install_one() {
  local name="$1"
  local src="$SKILLS_ROOT/$name"
  local dest="$DEST_ROOT/$name"

  if [[ ! -d "$src" ]]; then
    echo "[SKIP] $name — source not found"
    return
  fi

  mkdir -p "$DEST_ROOT"
  rm -rf "$dest"
  rsync -a --exclude='.git' --exclude='.github' --exclude='__pycache__' "$src/" "$dest/"
  echo "[OK] $name -> $dest"

  if [[ -f "$dest/requirements.txt" ]]; then
    echo "     Installing Python deps for $name..."
    python3 -m pip install -r "$dest/requirements.txt" || echo "     [WARN] pip install failed"
  fi
}

echo "cursor-skills installer"
echo "  Source: $SKILLS_ROOT"
echo "  Target: $DEST_ROOT"
echo

if [[ "$SKILL" == "all" ]]; then
  for s in "${ALL_SKILLS[@]}"; do
    install_one "$s"
  done
else
  found=0
  for s in "${ALL_SKILLS[@]}"; do
    if [[ "$s" == "$SKILL" ]]; then found=1; break; fi
  done
  if [[ "$found" -eq 0 ]]; then
    echo "[ERROR] Unknown skill: $SKILL"
    echo "Available: ${ALL_SKILLS[*]}"
    exit 1
  fi
  install_one "$SKILL"
fi

echo
echo "Done. Restart Cursor to reload skills."
