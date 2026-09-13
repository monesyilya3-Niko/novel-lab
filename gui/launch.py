#!/usr/bin/env python3
"""GUI 启动脚本：``python gui/launch.py``。

职责：解析端口 → 起 ThreadingHTTPServer → 自动弹浏览器 → 阻塞运行 → 优雅停机。

支持 ``--check`` 自检模式：只做 import 与路径校验，不起服务、不弹浏览器，
供 CI / 交付前冒烟测试使用。
"""
from __future__ import annotations

import argparse
import sys
import webbrowser


def _ensure_sys_path() -> None:
    """确保项目根目录在 sys.path 上，使 ``from gui import ...`` 可解析。

    必须最先调用（在任何 ``from gui import`` 之前），否则 ``python gui/launch.py``
    直接执行时 sys.path 里只有 ``gui/`` 而没有项目根目录。
    """
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


_ensure_sys_path()

from gui import config  # noqa: E402


def run_check() -> int:
    """自检：import 全部后端模块，校验路径，不弹浏览器。"""
    from gui import engine_adapter, router, server, services, sse, state_store

    mods = [engine_adapter, router, server, services, sse, state_store]
    names = ["engine_adapter", "router", "server", "services", "sse", "state_store"]
    for name, mod in zip(names, mods):
        print(f"[check] import gui.{name} ... OK")

    if config.DIST_DIR.is_dir():
        print(f"[check] 静态目录存在: {config.DIST_DIR}")
    else:
        print(f"[check] 警告: 未找到前端构建产物 {config.DIST_DIR}（先 npm run build）")

    # 校验 scripts/ 原子函数可被 adapter 直接调用。
    ok = engine_adapter.adapter_self_check()
    print(f"[check] engine_adapter 自检: {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="novel-lab GUI 启动脚本")
    parser.add_argument("--port", type=int, default=None, help="指定端口（默认 8000，占用自动 +1）")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动弹浏览器")
    parser.add_argument("--check", action="store_true", help="只做自检，不起服务")
    args = parser.parse_args(argv)

    if args.check:
        return run_check()

    _ensure_sys_path()

    from gui.server import GuiServer

    server = GuiServer(preferred_port=args.port)
    host, port = server.start()
    url = f"http://{host}:{port}/"
    print(f"[GUI] novel-lab 书籍分析服务已启动: {url}")
    print("[GUI] 按 Ctrl+C 停止。")

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception as exc:  # noqa: BLE001 — 弹窗失败不阻断服务。
            print(f"[GUI] 自动打开浏览器失败（可手动访问 {url}）: {exc}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[GUI] 收到中断，正在停止 ...")
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
