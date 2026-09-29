#!/usr/bin/env python3
"""准备 Windows embeddable Python（构建机用，用户机器不需要）。

目标：desktop/build/python-win/python.exe（gitignored，不入库）。
已存在则直接跳过；缺失时从 python.org FTP 取最新 3.12.x embed-amd64 包解压。

为什么是 3.12：后端要求 Python >= 3.12（实测语法基线），且与开发环境一致；
embed-amd64 是官方"Windows embeddable package"，解压即用，无需安装。

用法：python desktop/fetch-python-win.py
（npm run dist 的 predist 会自动调用；也可单独跑）
"""
from __future__ import annotations

import re
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

DESKTOP = Path(__file__).resolve().parent
TARGET = DESKTOP / "build" / "python-win"
FTP_INDEX = "https://www.python.org/ftp/python/"
WANT_MAJOR_MINOR = (3, 12)


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


def _latest_312() -> str | None:
    """从 python.org FTP 目录页解析出最新的 3.12.x 版本号。"""
    with urllib.request.urlopen(FTP_INDEX, timeout=30) as resp:
        html = resp.read().decode("utf-8", "replace")
    versions: set[tuple[int, int, int]] = set()
    for m in re.finditer(r'href="(\d+)\.(\d+)\.(\d+)/"', html):
        v = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if v[:2] == WANT_MAJOR_MINOR:
            versions.add(v)
    if not versions:
        return None
    return ".".join(str(x) for x in sorted(versions)[-1])


def main() -> int:
    if (TARGET / "python.exe").is_file():
        print(f"python-win 已就绪：{TARGET}（跳过下载）")
        return 0
    try:
        vstr = _latest_312()
    except OSError as exc:
        print(f"错误：无法访问 {FTP_INDEX}（{exc}）；请检查网络后重试", file=sys.stderr)
        return 1
    if not vstr:
        print("错误：FTP 目录页中未找到 3.12.x 版本", file=sys.stderr)
        return 1
    url = f"https://www.python.org/ftp/python/{vstr}/python-{vstr}-embed-amd64.zip"
    print(f"下载 {url} ...")
    TARGET.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            zp = Path(tmp) / "embed.zip"
            urllib.request.urlretrieve(url, zp)
            with zipfile.ZipFile(zp) as zf:
                zf.extractall(TARGET)
    except OSError as exc:
        print(f"错误：下载/解压失败（{exc}）", file=sys.stderr)
        return 1
    if not (TARGET / "python.exe").is_file():
        print(f"错误：解压后未找到 {TARGET / 'python.exe'}", file=sys.stderr)
        return 1
    print(f"python-win 就绪：{TARGET}（CPython {vstr} embeddable）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
