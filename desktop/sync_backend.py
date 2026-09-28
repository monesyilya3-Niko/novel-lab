#!/usr/bin/env python3
"""从源码自动同步 desktop/backend/（禁止手工复制）。

同步内容：
- gui/ → desktop/backend/gui/（Python 后端，排除 __pycache__）
- scripts/ → desktop/backend/scripts/（引擎脚本）
- gui/web/dist/ → desktop/backend/gui/web/dist/（预构建前端）

用法：python3 desktop/sync_backend.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "desktop" / "backend"


def sync_dir(src: Path, dst: Path, label: str) -> int:
    """同步目录，返回复制的文件数。"""
    if not src.exists():
        print(f"跳过 {label}：源不存在 {src}", file=sys.stderr)
        return 0
    if dst.exists():
        shutil.rmtree(dst)
    count = 0
    for item in src.rglob("*"):
        if "__pycache__" in item.parts:
            continue
        if "node_modules" in item.parts:
            continue
        if item.is_file():
            rel = item.relative_to(src)
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            count += 1
    print(f"{label}：{count} 个文件 → {dst.relative_to(ROOT)}")
    return count


def main() -> int:
    if not (ROOT / "gui" / "web" / "dist" / "index.html").exists():
        print("错误：gui/web/dist/ 未构建，请先跑 npm run build", file=sys.stderr)
        return 1

    total = 0
    total += sync_dir(ROOT / "gui", BACKEND / "gui", "gui/")
    total += sync_dir(ROOT / "scripts", BACKEND / "scripts", "scripts/")
    # dist 已在 gui/ 同步中包含，单独确认
    dist = BACKEND / "gui" / "web" / "dist" / "index.html"
    if not dist.exists():
        print(f"错误：dist 未同步到 {dist}", file=sys.stderr)
        return 1

    print(f"同步完成，共 {total} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
