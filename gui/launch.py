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

    # 名字直接从模块对象派生。原先另抄一份 names 字符串列表与模块列表 zip：
    # 加模块时漏改 names 就会静默少打一行自检结果，让自检报告看起来是绿的。
    for mod in (engine_adapter, router, server, services, sse, state_store):
        print(f"[check] import {mod.__name__} ... OK")

    if config.DIST_DIR.is_dir():
        print(f"[check] 静态目录存在: {config.DIST_DIR}")
    else:
        print(f"[check] 警告: 未找到前端构建产物 {config.DIST_DIR}（先 npm run build）")

    # 校验 scripts/ 原子函数可被 adapter 直接调用。
    ok = engine_adapter.adapter_self_check()
    print(f"[check] engine_adapter 自检: {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


def _start_parent_watchdog(server) -> None:
    """Electron 模式下看护父进程，父死则自行退出（2026-10-13 审计修复 ELE-03）。

    为什么需要：桌面版主进程被**强杀**（任务管理器结束进程、崩溃、断电）时，
    Electron 的 ``before-quit`` / ``window-all-closed`` 都不会触发——
    ``stopBackend()`` 没机会执行，后端变成**孤儿进程**。它仍持有单实例锁
    （gui_state/.lock）与端口，于是此后每次启动都报"后端服务未能启动"，
    用户既不知道原因也无从恢复（后端 pid 是活的，stale 锁清理不会介入）。

    修法：后端自己盯着父进程 pid，**定期探活**；父进程消失就主动
    ``server.shutdown()``，让进程正常退出并释放锁与端口。

    为什么由后端做而不是 Electron 做：Electron 侧无法覆盖"自己被强杀"
    这种场景——钩子根本没机会跑。只有被监护方能可靠感知监护者消失。

    ⚠️ 必须用**探活**而不是比较 ``os.getppid()``（实测发现）：
    Windows 上父进程退出后 ``getppid()`` **仍返回原 pid**（不像 Linux 会
    变成 1 或 0）——实测子进程在父死后连续 12 次采样都读到同一个已死 pid。
    故只能主动探活那个 pid，用 ``server._pid_is_alive``（它内部走
    ctypes OpenProcess，对僵尸进程与权限受限都有正确处理）。

    仅在 ``--no-browser``（Electron 模式）下启用：浏览器直连模式没有
    "父进程"概念（用户直接跑 python gui/launch.py），误判会杀掉正常服务。
    """
    import os
    import threading
    import time

    parent_pid = os.getppid()
    if parent_pid <= 1:
        print("[GUI] 父进程 pid 异常，跳过看护")
        return

    from gui import server as _server_mod
    is_alive = _server_mod._pid_is_alive

    def _watch() -> None:
        while True:
            time.sleep(2.0)
            try:
                if not is_alive(parent_pid):
                    print("[GUI] 父进程已退出，后端自动停止（释放锁与端口）")
                    server.shutdown()
                    return
            except Exception:  # noqa: BLE001 — 看护失败不应影响服务
                return

    threading.Thread(target=_watch, daemon=True, name="parent-watchdog").start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="novel-lab GUI 启动脚本")
    parser.add_argument("--port", type=int, default=None, help="指定端口（默认 8000，占用自动 +1）")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动弹浏览器")
    parser.add_argument("--check", action="store_true", help="只做自检，不起服务")
    args = parser.parse_args(argv)

    if args.check:
        return run_check()

    _ensure_sys_path()

    import secrets

    from gui.server import GuiServer

    # Electron 模式（--no-browser）：生成身份握手 token，防止端口被抢占伪造。
    handshake_token = secrets.token_urlsafe(32) if args.no_browser else None

    server = GuiServer(preferred_port=args.port, handshake_token=handshake_token)
    host, port = server.start()
    url = f"http://{host}:{port}/"
    print(f"[GUI] 暮冬念春 服务已启动: {url}")
    if handshake_token:
        print(f"[GUI] 握手令牌: {handshake_token}")
    print("[GUI] 按 Ctrl+C 停止。")

    # Electron 模式：看护父进程，避免主进程被强杀后成为孤儿占锁（ELE-03）。
    if args.no_browser:
        _start_parent_watchdog(server)

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
