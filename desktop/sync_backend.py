#!/usr/bin/env python3
"""从源码自动同步 desktop/backend/（禁止手工复制）。

同步内容：
- gui/ → desktop/backend/gui/（Python 后端，排除 __pycache__）
- scripts/ → desktop/backend/scripts/（引擎脚本）
- gui/web/dist/ → desktop/backend/gui/web/dist/（预构建前端）
- assets/、corpus/、reports/ → desktop/backend/（内置数据，随首次启动迁移到用户目录）
- assets-manifest.json → desktop/backend/assets-manifest.json（内置资产版本清单）
- build/python-win/ → desktop/backend/python-win/（Windows embeddable Python；
  main.js 打包后 spawn resources/backend/python-win/python.exe，缺失则安装包
  启动即失败，因此缺失时直接报错退出，不静默跳过）

用法：python3 desktop/sync_backend.py
（正式构建走 npm run dist，其 predist 会自动先跑 fetch-python-win.py 再跑本脚本）
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "desktop" / "backend"


def _fix_windows_console() -> None:
    """Windows 控制台默认编码（如 runner 的 cp1252）打不出中文会直接崩；
    启动时把 stdout/stderr 切到 UTF-8，保证任何 locale 下打印中文都不
    UnicodeEncodeError。非 Windows 下本就是 UTF-8，调用无影响。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


_fix_windows_console()


# 安装包排除：开发期文件，不随包发布。
# 背景（2026-09-29 安装包开箱审计）：云端构建的 exe 经 7z 解剖发现，
# gui/web/src（前端源码）、gui/web/e2e（Playwright 用例）、vite/eslint 等
# 配置文件、scripts/*_isolated.sh（开发期隔离脚本）都被打进了安装包。
# 安装版运行时只需要 gui/web/dist（预构建前端），这些纯属体积与源码暴露。
EXCLUDE_REL_DIRS = {
    Path("gui/web/src"),
    Path("gui/web/e2e"),
}
EXCLUDE_REL_FILES = {
    Path("gui/web/package.json"),
    Path("gui/web/package-lock.json"),
    Path("gui/web/vite.config.ts"),
    Path("gui/web/tsconfig.json"),
    Path("gui/web/eslint.config.js"),
    Path("gui/web/playwright.config.ts"),
    Path("gui/web/postcss.config.js"),
    Path("gui/web/tailwind.config.ts"),
    Path("gui/web/.prettierrc.json"),
    Path("gui/web/.gitignore"),
    Path("gui/web/index.html"),  # vite 开发入口；运行时只 serves dist/index.html
    Path("scripts/e2e_isolated.sh"),
    Path("scripts/perf_isolated.sh"),
}


def _excluded(rel_from_root: Path) -> bool:
    """rel_from_root 为相对仓库根的路径；命中排除表则不进安装包。"""
    if rel_from_root in EXCLUDE_REL_FILES:
        return True
    return any(d in rel_from_root.parents for d in EXCLUDE_REL_DIRS)


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
            if _excluded(item.relative_to(ROOT)):
                continue
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
    # 模型配置：repo 根 config/ -> backend/config/（config.py 注释"随包发布"，
    # asset_index._model_configured 按 CONFIG_DIR 实时读取；漏同步则安装版
    # 永远显示"未配置模型"。2026-09-29 安装包开箱审计发现缺失，补上）
    total += sync_dir(ROOT / "config", BACKEND / "config", "config/")
    # 内置数据资产：repo 根 assets/ -> backend/assets/（首次启动迁移到用户目录）
    total += sync_dir(ROOT / "assets", BACKEND / "assets", "assets/")
    # 语料与报告：corpus/、reports/ 同理
    total += sync_dir(ROOT / "corpus", BACKEND / "corpus", "corpus/")
    total += sync_dir(ROOT / "reports", BACKEND / "reports", "reports/")
    # 内置资产版本清单：repo 根 assets-manifest.json -> backend/assets-manifest.json
    # （builtin_sync.load_manifest 按 ROOT_DIR 实时读取；缺失则降级为旧行为，
    #  但会丢失"官方旧版可升级"分类，因此打包必须携带）
    manifest = ROOT / "assets-manifest.json"
    if manifest.is_file():
        shutil.copy2(manifest, BACKEND / "assets-manifest.json")
        print(f"assets-manifest.json → { (BACKEND / 'assets-manifest.json').relative_to(ROOT) }")
        total += 1
    else:
        print("警告：assets-manifest.json 不存在（请先跑 python -m gui.builtin_sync --write-manifest）",
              file=sys.stderr)
    # dist 已在 gui/ 同步中包含，单独确认
    dist = BACKEND / "gui" / "web" / "dist" / "index.html"
    if not dist.exists():
        print(f"错误：dist 未同步到 {dist}", file=sys.stderr)
        return 1
    # Windows embeddable Python：build/python-win/ -> backend/python-win/
    # （main.js 打包后 spawn resources/backend/python-win/python.exe；缺失则
    #  安装包启动即报"后端服务未能启动"，必须 fail fast，不能静默跳过）
    pywin = ROOT / "desktop" / "build" / "python-win"
    if not (pywin / "python.exe").is_file():
        print(f"错误：{(pywin / 'python.exe')} 不存在；"
              "请先跑 python desktop/fetch-python-win.py", file=sys.stderr)
        return 1
    total += sync_dir(pywin, BACKEND / "python-win", "python-win/")

    print(f"同步完成，共 {total} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
