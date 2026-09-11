"""HTTP 服务入口：起 ThreadingHTTPServer、挂路由、静态托管、SSE、优雅停机。

新增（W09）：单实例锁 + 常驻入口（``python -m gui.server``）+ 优雅关闭刷盘。
"""
from __future__ import annotations

import json
import mimetypes
import os
import queue
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, parse_qs, unquote

from gui import config, router
from gui import db
from gui.sse import broker
from gui.services import ServiceError


class _Handler(BaseHTTPRequestHandler):
    """请求处理器：API 路由 + SSE + 静态文件。"""

    server_version = "novel-lab-gui/1.0"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        # SSE 长连接
        if path == "/api/events":
            self._handle_sse(query)
            return

        try:
            payload, marker = router.dispatch("GET", path, {}, query)
            if marker == "__sse__":
                self._handle_sse(query)
                return
            if payload is not None:
                self._send_json(payload)
                return
        except ServiceError as exc:
            self._send_json(router.err(exc.code, exc.message), exc.code)
            return
        except Exception as exc:  # noqa: BLE001
            self._send_json(router.err(500, f"内部错误: {exc}"), 500)
            return

        # 静态文件
        self._serve_static(path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        try:
            body = router.read_body(self)
            payload, marker = router.dispatch("POST", path, body, query)
            if payload is not None:
                self._send_json(payload)
                return
            self._send_json(router.err(404, f"未找到接口: {path}"), 404)
        except ServiceError as exc:
            self._send_json(router.err(exc.code, exc.message), exc.code)
        except Exception as exc:  # noqa: BLE001
            self._send_json(router.err(500, f"内部错误: {exc}"), 500)

    # ------------------------------------------------------------------
    def _is_same_host_origin(self, origin: str) -> bool:
        """判断 Origin 是否属于本机（localhost / 127.0.0.1 / [::1]），允许同机不同端口。"""
        try:
            from urllib.parse import urlparse
            host = (urlparse(origin).hostname or "").lower()
        except Exception:  # noqa: BLE001
            return False
        return host in ("localhost", "127.0.0.1", "::1", "[::1]", "")

    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        # 【修复 M8】不再无条件返回 `Access-Control-Allow-Origin: *`。
        # 本服务绑定 127.0.0.1 且无任何鉴权；通配 CORS 会让任意网站在用户浏览器里
        # 读取本服务响应（/api/import 会回吐整书正文），构成**本地文件外泄**。
        # 前端由本服务同源托管，dev 模式下 vite 也把 /api 代理到本机，本就不需要 CORS。
        # 仅当请求来自本机时才回显 Origin（保留同机跨端口开发的可用性）。
        origin = self.headers.get("Origin")
        if origin and self._is_same_host_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(data)

    def _handle_sse(self, query: dict) -> None:
        """SSE 长连接：订阅 broker，持续推送 progress 事件直到客户端断开。"""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        book_id = query.get("book_id")
        q: queue.Queue = broker.subscribe()
        try:
            # 立即发送一条 connected，确认连接建立。
            self.wfile.write(f"data: {json.dumps({'status': 'connected', 'book_id': book_id}, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()
            while True:
                try:
                    event = q.get(timeout=15)
                except queue.Empty:
                    # 心跳保活
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                if book_id and event.get("book_id") != book_id:
                    continue
                self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            broker.unsubscribe(q)

    def _serve_static(self, path: str) -> None:
        """托管前端 dist 静态文件。"""
        # 【修复 M3】未知 /api/* 路径不得走 SPA 回退返回 index.html(HTTP 200)。
        # 原先 GET /api/nonexistent 会回退成 HTML 200，前端当 JSON 解析即报错；
        # 而 POST 未知接口返回 404 JSON，同一「接口不存在」在 GET/POST 下表现不一致。
        _rel = path.lstrip("/")
        if _rel == "api" or _rel.startswith("api/"):
            self._send_json(router.err(404, "Not Found"), 404)
            return

        if not config.DIST_DIR.is_dir():
            self._send_json(router.err(500, "未找到前端构建产物，请先运行 npm run build"), 500)
            return

        rel = path.lstrip("/")
        if rel in ("", "index.html"):
            target = config.DIST_DIR / "index.html"
        else:
            target = config.DIST_DIR / rel
            # 防止路径穿越
            try:
                target.resolve().relative_to(config.DIST_DIR.resolve())
            except ValueError:
                self._send_json(router.err(404, "Not Found"), 404)
                return

        if not target.is_file():
            # SPA 回退：非文件路径回 index.html
            target = config.DIST_DIR / "index.html"
            if not target.is_file():
                self._send_json(router.err(404, "Not Found"), 404)
                return

        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        # 精简日志，避免刷屏。
        pass


def main(argv: Optional[list[str]] = None) -> int:
    """常驻入口（W09）：``python -m gui.server`` 阻塞运行，重复启动被单实例锁拦截。"""
    import argparse
    import sys
    from pathlib import Path as _P

    # 确保项目根在 sys.path 上（``python gui/server.py`` 直接执行也可）。
    _root = _P(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

    parser = argparse.ArgumentParser(description="novel-lab GUI 常驻服务")
    parser.add_argument("--port", type=int, default=None, help="指定端口（默认 8000，占用自动 +1）")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动弹浏览器")
    args = parser.parse_args(argv)

    server = GuiServer(preferred_port=args.port)
    try:
        host, port = server.start()
    except RuntimeError as exc:
        print(f"[GUI] 启动失败: {exc}", file=sys.stderr)
        return 1

    url = f"http://{host}:{port}/"
    print(f"[GUI] novel-lab 书籍分析服务已启动: {url}")
    print("[GUI] 按 Ctrl+C 停止。")

    if not args.no_browser:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as exc:  # noqa: BLE001
            print(f"[GUI] 自动打开浏览器失败（可手动访问 {url}）: {exc}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[GUI] 收到中断，正在停止 ...")
    finally:
        server.shutdown()
    return 0


def _win_pid_is_alive(pid: int) -> Optional[bool]:
    """Windows 专用存活探测：``OpenProcess`` + ``GetExitCodeProcess``（仅 ctypes 标准库）。

    相比 ``os.kill(pid, 0)`` 更可靠——实测本机（Windows + CPython 3.13）`os.kill`
    会对**存活进程**误报 ``OSError[WinError 87]``（false negative，会误清活锁），
    也会对**已退出但残留句柄的僵尸进程**误报「存活」（false positive，会永久阻塞启动）。
    ``OpenProcess`` 能准确区分：

    - 打开成功且退出码为 ``STILL_ACTIVE``(259) → 存活（True）；
    - 打开成功但退出码非 259（含僵尸进程）→ 已退出（False）；
    - 打开失败且 ``GetLastError == ERROR_ACCESS_DENIED``(5) → 无权限探测 → **保守
      视为存活**（True），绝不误清他人仍在使用的锁；
    - 打开失败其它错误（如 ``ERROR_INVALID_PARAMETER``(87) = 进程不存在）→ 已退出。

    Args:
        pid: 目标进程 id（正整数）。

    Returns:
        True/False 为判定结果；``None`` 表示 ctypes 探测不可用（调用方回退 ``os.kill``）。
    """
    try:
        import ctypes
        from ctypes import wintypes
    except (ImportError, AttributeError):
        return None

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    ERROR_ACCESS_DENIED = 5

    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return None

    # 显式声明签名：Win64 下 HANDLE 为指针宽度，默认 c_int 会截断句柄。
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    ctypes.set_last_error(0)
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        err = ctypes.get_last_error()
        return True if err == ERROR_ACCESS_DENIED else False
    try:
        code = wintypes.DWORD(0)
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return None  # 查询失败 → 交回调用方回退。
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _pid_is_alive(pid: int) -> bool:
    """判断 pid 对应进程是否存活（跨平台，仅标准库）。

    平台策略：

    - **Windows**：以 ``_win_pid_is_alive``（``OpenProcess`` + ``GetExitCodeProcess``）
      精确判定为准。实测 ``os.kill(pid, 0)`` 在本机对存活进程误报 ``OSError[87]``、
      对僵尸进程误报存活，故 Windows 下不单独依赖它；ctypes 不可用时回退 ``os.kill``。
    - **其它平台**：``os.kill(pid, 0)`` 无副作用探测，按异常区分：

      - ``ProcessLookupError`` → 进程已退出 → False（stale）；
      - ``PermissionError`` → 进程存在但无权限探测 → **保守视为存活**（True）；
      - 其它 ``OSError`` → 视为已退出。

    Args:
        pid: 目标进程 id。

    Returns:
        True 表示存活，False 表示已退出（stale）。
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        probed = _win_pid_is_alive(pid)
        if probed is not None:
            return probed
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _read_lock_pid(path: Path) -> Optional[int]:
    """读取锁文件内容并解析为 pid；文件缺失/为空/非数字/非正数一律返回 None。"""
    try:
        raw = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not raw:
        return None
    try:
        pid = int(raw)
    except ValueError:
        return None
    return pid if pid > 0 else None


class GuiServer:
    """封装 ThreadingHTTPServer 的启动 / 停机。"""

    def __init__(self, preferred_port: Optional[int] = None) -> None:
        self.preferred_port = preferred_port
        self._lock_fd: Optional[int] = None

    def _acquire_lock(self) -> bool:
        """单实例锁（W09）：``gui_state/.lock`` 用 O_CREAT|O_EXCL 独占创建。

        返回 True 表示成功获得锁；False 表示已有实例在运行。

        增强（stale lock 自动清理）：独占创建因锁已存在而失败时，读取锁内 pid 判断
        其是否存活——硬杀/崩溃导致进程退出但锁文件残留时，视为 stale，原子清理后
        重试获取，避免「一次非正常退出永久阻塞后续启动」。
        """
        lock_path = config.LOCK_PATH
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        # 最多两轮：首轮直接创建；失败则判 stale → 清理 → 次轮重试。
        for _ in range(2):
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode("ascii"))
                self._lock_fd = fd
                return True
            except FileExistsError:
                pass  # 锁已存在，进入 stale 判定。

            pid = _read_lock_pid(lock_path)
            if pid is not None and _pid_is_alive(pid):
                # 真正运行中的实例 → 拒绝二次启动（保持原行为）。
                return False

            # stale（pid 已退出 / 内容非法/为空）：原子清理后重试。
            if not self._clear_stale_lock(lock_path, pid):
                # 清理期间与并发启动竞态，锁被他人抢走 → 承认冲突。
                return False

        # 清理后重试仍被抢占（并发启动）→ 承认冲突。
        return False

    def _clear_stale_lock(self, lock_path: Path, observed_pid: Optional[int]) -> bool:
        """原子清理 stale 锁：先 rename 到本进程专属临时名，复核后再删除。

        直接 ``unlink`` 会与并发启动进程产生「双删双获取」竞态。改为：

        1. ``os.replace`` 把 ``.lock`` 重命名为 ``.lock.stale-{本进程 pid}``
           （原子 rename，目标名唯一不冲突）；
        2. 复核临时文件内容是否仍等于我们观察到的 stale pid——若不等且该 pid 存活，
           说明期间有并发进程刚取得锁，把临时文件``os.replace`` 放回原路，承认冲突；
        3. 确认确为 stale 后删除临时文件并打日志，返回 True（调用方可安全重试创建）。

        Args:
            lock_path: 锁文件路径。
            observed_pid: 判定 stale 时读到的 pid（内容非法/为空时为 None）。

        Returns:
            True 表示已清理（调用方应重试获取）；False 表示发生竞态（放弃获取）。
        """
        tmp = lock_path.with_name(f"{lock_path.name}.stale-{os.getpid()}")
        try:
            os.replace(str(lock_path), str(tmp))
        except FileNotFoundError:
            # 期间已被其它进程清理 → 视为可重试。
            return True
        except OSError:
            return False

        # 复核：避免误删并发进程刚创建的新锁。
        actual_pid = _read_lock_pid(tmp)
        if actual_pid is not None and actual_pid != observed_pid and _pid_is_alive(actual_pid):
            try:
                os.replace(str(tmp), str(lock_path))  # 放回，让真正持有者继续。
            except OSError:
                pass
            return False

        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        shown = observed_pid if observed_pid is not None else "非法内容"
        print(f"[server] 检测到 stale lock（pid={shown} 已退出），已清理")
        return True

    def _release_lock(self) -> None:
        """释放单实例锁（关 fd + 删除锁文件）。"""
        if self._lock_fd is not None:
            try:
                os.close(self._lock_fd)
            except OSError:
                pass
            self._lock_fd = None
        try:
            config.LOCK_PATH.unlink(missing_ok=True)
        except OSError:
            pass

    def _bind_port(self) -> tuple[str, int]:
        """解析端口，被占用则 +1 递增（A5 决策）。"""
        host = "127.0.0.1"
        port = config.resolve_port(self.preferred_port)
        for _ in range(100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((host, port))
                return host, port
            except OSError:
                port += 1
        raise RuntimeError("无法找到可用端口（8000-8099 均被占用）")

    def start(self) -> tuple[str, int]:
        # 单实例锁：已有实例则拒绝二次启动。
        if not self._acquire_lock():
            raise RuntimeError("novel-lab GUI 已在运行中（单实例锁 gui_state/.lock 存在）")

        # 初始化持久化层 + 迁移（幂等），保证 analysis_tasks 表就绪。
        try:
            db.init_schema()
            db.apply_migrations()
        except Exception as exc:  # noqa: BLE001 — 库损坏不阻断服务，降级为内存/扫描。
            print(f"[GUI] 警告: 持久化层初始化失败（降级运行）: {exc}")

        host, port = self._bind_port()
        self._httpd = ThreadingHTTPServer((host, port), _Handler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return host, port

    def serve_forever(self) -> None:
        """阻塞主线程直到停机（供 launch.py 调用）。"""
        try:
            self._thread.join()
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self) -> None:
        if getattr(self, "_httpd", None):
            self._httpd.shutdown()
            self._httpd.server_close()
        # 优雅关闭：刷盘 SQLite（wal_checkpoint）。
        try:
            db.close()
        except Exception:  # noqa: BLE001
            pass
        self._release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
