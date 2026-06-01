#!/usr/bin/env python3
"""Validate that all screenshots referenced in 操作说明书.md exist on disk."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate manual screenshot references")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()
    manual = root / "soft-copyright/manual/操作说明书.md"
    shots_dir = root / "soft-copyright/manual/screenshots"

    if not manual.is_file():
        print(f"Manual not found: {manual}", file=sys.stderr)
        return 1

    refs = sorted(set(re.findall(r"screenshots/([^)]+)", manual.read_text(encoding="utf-8"))))
    missing = [r for r in refs if not (shots_dir / r.replace("/", "\\")).is_file()]

    print(f"Referenced: {len(refs)}")
    print(f"Missing: {len(missing)}")
    for m in missing:
        print(f"  - {m}")

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
