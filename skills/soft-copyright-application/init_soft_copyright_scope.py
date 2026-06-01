#!/usr/bin/env python3
"""Initialize soft-copyright/scope.yaml in the current project."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = args.project_root.resolve()
    skill_dir = Path(__file__).resolve().parent.parent
    template = skill_dir / "scope-template.yaml"
    target_dir = root / "soft-copyright"
    target = target_dir / "scope.yaml"

    if target.exists() and not args.force:
        print(f"Already exists: {target}")
        print("Use --force to overwrite.")
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(template, target)
    (target_dir / "output").mkdir(exist_ok=True)
    (target_dir / "manual").mkdir(exist_ok=True)

    readme = target_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            "# 软著申报材料\n\n"
            "1. 编辑 `scope.yaml` 填写软件名称、著作权人等\n"
            "2. 在 Cursor 中说：「按软著技能整理申报材料」\n"
            "3. 生成物在 `output/` 目录\n",
            encoding="utf-8",
        )

    print(f"Created {target}")
    print(f"Created {target_dir / 'output'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
