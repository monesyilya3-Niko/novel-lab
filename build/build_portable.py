#!/usr/bin/env python3
"""novel-lab 绿色版打包脚本（开发期工具，纯标准库）。

产物：dist/novel-lab-portable-v{版本}.zip
  novel-lab-portable/
  ├─ Start.bat              双击启动（用捆绑运行时，自动开浏览器）
  ├─ python-runtime/        捆绑的 CPython（取自本机 .niko 运行时）
  └─ app/                   git 追踪的全部源码（git archive——天然排除
                            密钥/语料/运行时数据等所有 gitignore 内容）

用法：python build/build_portable.py [--runtime <python目录>]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
DIST_DIR = BUILD_DIR / "dist"
DEFAULT_RUNTIME = Path(r"C:/Users/monesy/.niko/binaries/python/versions/3.13.12")

# 运行时目录里不需要随包的部分
RUNTIME_EXCLUDE = {"include", "Scripts", "share", "Tools", "__pycache__"}


def version_of() -> str:
    init = (ROOT / "gui" / "__init__.py").read_text(encoding="utf-8")
    for line in init.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("无法从 gui/__init__.py 解析版本号")


def git_archive(stage_app: Path) -> None:
    """按 git 追踪清单导出源码（自动排除 gitignore 的密钥/语料/运行时数据）。"""
    stage_app.mkdir(parents=True, exist_ok=True)
    tar = subprocess.run(
        ["git", "archive", "HEAD", "--format=tar.gz"],
        cwd=ROOT, check=True, capture_output=True,
    ).stdout
    import tarfile
    import io
    with tarfile.open(fileobj=io.BytesIO(tar), mode="r:gz") as tf:
        tf.extractall(stage_app)  # noqa: S202 — 内容来自本仓 git，受控


def copy_runtime(src: Path, dst: Path) -> None:
    shutil.copytree(
        src, dst,
        ignore=shutil.ignore_patterns(*RUNTIME_EXCLUDE, "*.pyc"),
        dirs_exist_ok=True,
    )


START_BAT = r"""@echo off
rem novel-lab portable launcher (bundled Python, ASCII-only for cmd codepage safety).
setlocal
cd /d "%~dp0"
set "PY=%~dp0python-runtime\python.exe"
if not exist "%PY%" (
    echo [novel-lab] bundled Python missing: %PY%
    pause
    exit /b 1
)
cd /d "%~dp0app"
"%PY%" -m gui.server
if errorlevel 1 pause
endlocal
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME,
                    help="捆绑的 CPython 目录（默认本机 .niko 运行时）")
    args = ap.parse_args()

    if sys.platform != "win32":
        print("仅支持 Windows 打包")
        return 1
    if not (args.runtime / "python.exe").is_file():
        print(f"运行时不存在: {args.runtime}")
        return 1

    version = version_of()
    name = f"novel-lab-portable-v{version}"
    stage = DIST_DIR / name
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    print(f"[1/4] 版本 {version}，暂存 {stage}")

    print("[2/4] 导出 git 追踪源码 → app/")
    git_archive(stage / "app")

    print("[3/4] 拷贝 Python 运行时 → python-runtime/")
    copy_runtime(args.runtime, stage / "python-runtime")
    (stage / "Start.bat").write_text(START_BAT, newline="\r\n", encoding="ascii")

    print("[4/4] 压缩 zip")
    zip_path = DIST_DIR / f"{name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in stage.rglob("*"):
            if p.is_file():
                zf.write(p, Path(name) / p.relative_to(stage))

    mb = zip_path.stat().st_size / 1024 / 1024
    print(f"完成: {zip_path} ({mb:.1f} MB)")

    # 安全自检：产物内不得有密钥/语料（Lib/secrets.py 是标准库模块，不在其列）
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        leak = [
            n for n in names
            if ("/config/.secrets" in n.replace("\\", "/"))
            or ("/corpus/" in n)
            or n.endswith("corpus")
        ]
        if leak:
            print(f"!! 安全告警，产物含敏感路径: {leak}")
            return 1
        print(f"安全自检通过（{len(names)} 个文件，无 secrets/corpus）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
