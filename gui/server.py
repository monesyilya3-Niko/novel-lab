"""HTTP 服务入口：起 ThreadingHTTPServer、挂路由、静态托管、SSE、优雅停机。

新增（W09）：单实例锁 + 常驻入口（``python -m gui.server``）+ 优雅关闭刷盘。
"""
from __future__ import annotations

import hmac
import json
import mimetypes
import os
import queue
import re
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

# 直接执行兼容：`python3 gui/server.py`（不走 `python -m gui.server`）时，
# 脚本目录是 gui/ 而非仓库根，手动把仓库根加入 sys.path；-m 方式下已存在则 no-op。
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from gui import admin, auto_backup, config, db, router, services
from gui.logging_setup import get_logger, setup_logging
from gui.services import ServiceError
from gui.services import unique_corpus_path as _unique_corpus_path
from gui.sse import broker

_log = get_logger("server")

# 访问日志里必须脱敏的查询参数。这些值本身就是凭据：
# - `auth`：NOVEL_LAB_TOKEN 的查询参数形式；
# - `handshake`：桌面端 main.js 用 `/?handshake=<token>` 把身份握手令牌交给前端，
#   这条 GET 请求行会被下面的访问日志原样记录；
# - `handshake_token`：EventSource 发不了自定义头，SSE 只能把同一个令牌放查询串。
# 令牌一旦落进 gui.log，读到日志的人就等于拿到桌面版的调用凭据。
_SENSITIVE_QUERY_RE = re.compile(r"([?&])(auth|handshake_token|handshake)=([^ \r\n&]*)", re.I)


def _mask_sensitive_query(line: str) -> str:
    """把请求行里的敏感查询参数值替换成 ``***``，保留参数名与其它参数。"""
    return _SENSITIVE_QUERY_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}=***", line)


def announce_initial_password(initial_pw: str) -> Path | None:
    """把管理员初始密码交到用户手上；成功返回指引文件路径，写不进去返回 None。

    密码只写进数据目录下的指引文件（改密后由 admin.change_password 自动删除），
    **不进日志**：gui.log 会随轮转长期留存，写进去等于把凭据另存一份没人负责清理的副本。
    只有指引文件写不出来时才退回日志——那时它是唯一还能把密码交付出去的通道。
    """
    hint_fp = config.STATE_ROOT / admin.ADMIN_HINT_FILE_NAME
    hint_text = "\n".join([
        "管理员初始账号",
        "================",
        "用户名：admin",
        "初始密码：" + initial_pw,
        "（该密码仅生成一次）",
        "",
        "操作：用上面的账号密码登录管理后台，立即修改密码。",
        "修改成功后本文件会被自动删除；也可手动删除。",
        "数据目录：" + str(config.STATE_ROOT),
        "",
    ]) + "\n"
    _log.warning("=" * 60)
    try:
        # STATE_ROOT 在极端时序下可能还没建出来，这里自己兜底而不是假设启动顺序。
            hint_fp.parent.mkdir(parents=True, exist_ok=True)
            hint_fp.write_text(hint_text, encoding="utf-8")
    except OSError as exc:
        _log.warning("写入初始密码指引文件失败: %s", exc)
        # 指引文件写不出来时，日志是唯一还能把密码交出去的路径，只能在此破例。
        _log.warning("管理员初始账号已创建：用户名 admin / 初始密码 %s", initial_pw)
        _log.warning("=" * 60)
        return None
    _log.warning("管理员初始账号已创建：用户名 admin（初始密码见数据目录下的 %s，改密后自动删除）",
                 admin.ADMIN_HINT_FILE_NAME)
    _log.warning("请立即登录管理后台修改密码（该密码仅显示一次）。")
    _log.warning("=" * 60)
    return hint_fp


def _safe_upload_filename(name: str) -> str:
    """上传文件名安全检查：去目录、去控制字符、仅允许 .txt。"""
    base = Path(name).name.strip()
    base = re.sub(r'[\x00-\x1f\x7f/\\]', "_", base)
    if not base or base in (".", ".."):
        raise ServiceError("文件名非法", 400)
    if not base.lower().endswith(".txt"):
        raise ServiceError("首版仅支持 .txt 导入", 400)
    # B8：限制文件名长度（200 字符），超长时 400 拒绝，避免 book_id 过长
    # 导致 gui_state 文件名超限（ext4 255 字节 / Windows MAX_PATH）。
    if len(base) > 200:
        raise ServiceError("文件名过长（最多 200 字符）", 400)
    return base


def _parse_upload_batch_size(value: str | None) -> int | None:
    """上传表单的 batch_size：缺省走服务端默认；非法值 400（不透传成 500）。"""
    if value is None or not value.strip():
        return None
    value = value.strip()
    if not value.isdigit() or int(value) <= 0:
        raise ServiceError("batch_size 必须为正整数", 400)
    return int(value)


class _Handler(BaseHTTPRequestHandler):
    """请求处理器：API 路由 + SSE + 静态文件。"""

    server_version = "novel-lab-gui/1.0"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------
    def _get_cookie(self, name: str) -> str | None:
        """从 Cookie 请求头解析单个 cookie 值。"""
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            if k.strip() == name:
                return unquote(v.strip())
        return None

    def _check_auth(self) -> bool:
        """鉴权总闸。

        /api/admin/* 走管理员会话（Cookie），其中 /api/admin/login 豁免
        （有独立的登录频率限制）；其余 /api/* 走既有的 NOVEL_LAB_TOKEN 机制。
        Electron 模式（handshake_token 非空）额外要求 /api/* 携带正确的
        X-Handshake-Token 头，防止端口被抢占后伪造 /api/overview。
        """
        path = unquote(urlparse(self.path).path)
        if path == "/api/admin/login":
            return True
        # 身份握手（Electron 模式）：/api/* 必须携带正确的握手 token。
        # 静态文件（/）豁免，前端 HTML 加载不需要 token。
        # EventSource（SSE）发不了自定义头，/api/events 允许经 ?handshake_token=
        # 查询参数传递（与 X-Handshake-Token 头等效，hmac 常量时间比对）。
        handshake = getattr(self.server, "handshake_token", None)
        if handshake and (path == "/api" or path.startswith("/api/")):
            supplied = self.headers.get("X-Handshake-Token", "")
            if not supplied and path == "/api/events":
                qs = parse_qs(urlparse(self.path).query)
                supplied = (qs.get("handshake_token") or [""])[0]
            if not supplied or not hmac.compare_digest(supplied, handshake):
                self._send_json(router.err(403, "握手失败：非法客户端"), 403)
                return False
        # CSRF 纵深防御（非 Electron 模式）：/api/* 写操作要求 Origin 来自本机。
        # Electron 模式已有握手 token，浏览器直连模式靠此挡 CSRF。
        # 无 Origin 的视为非浏览器客户端（curl/脚本），不受影响。
        if not handshake and self.command in ("POST", "PUT", "DELETE"):
            if path == "/api" or path.startswith("/api/"):
                origin = self.headers.get("Origin") or self.headers.get("Referer") or ""
                if origin and not self._is_same_host_origin(origin):
                    self._send_json(router.err(403, "跨站请求被拒绝"), 403)
                    return False
        if path == "/api/admin" or path.startswith("/api/admin/"):
            sid = self._get_cookie(admin.SESSION_COOKIE)
            user = admin.get_session_user(sid)
            if user:
                self._admin_user = user
                self._admin_sid = sid or ""
                self._admin_ip = self.client_address[0]
                # 强制改密网关：处于 must_change_password 状态时，只允许
                # me（查询状态）/ logout（退出）/ change-password（改密），
                # 其余管理接口一律 403，防止绕过改密直接调用管理 API。
                if admin.needs_password_change(user) and path not in (
                    "/api/admin/me",
                    "/api/admin/logout",
                    "/api/admin/change-password",
                ):
                    self._send_json(router.err(403, "请先修改初始密码"), 403)
                    return False
                # CSRF 防护：管理端写操作（POST/PUT/DELETE，登录除外）要求
                # Origin/Referer 来自本机。浏览器 fetch 一定带 Origin；
                # 无 Origin 的视为非浏览器客户端（curl 等），不受 CSRF 影响。
                if self.command in ("POST", "PUT", "DELETE"):
                    origin = self.headers.get("Origin") or self.headers.get("Referer") or ""
                    if origin and not self._is_same_host_origin(origin):
                        self._send_json(router.err(403, "跨站请求被拒绝"), 403)
                        return False
                return True
            self._send_json(router.err(401, "管理员未登录"), 401)
            return False
        token = config.API_TOKEN
        if not token:
            auto_backup.daily_backup_if_due()
            return True
        if not (path == "/api" or path.startswith("/api/")):
            return True
        supplied = self.headers.get("X-Auth-Token", "")
        query = parse_qs(urlparse(self.path).query)
        if not supplied and "auth" in query:
            supplied = query["auth"][0]
        if supplied and hmac.compare_digest(supplied, token):
            auto_backup.daily_backup_if_due()
            return True
        self._send_json(router.err(401, "缺少或非法访问令牌（NOVEL_LAB_TOKEN 已启用）"), 401)
        return False

    def do_GET(self) -> None:
        if not self._check_auth():
            return
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        self._inject_admin_ctx(path, query)

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
            # 安全：异常原文只记服务端日志（含堆栈），不返回给前端，
            # 避免路径/SQL 等内部细节泄漏。
            _log.exception("请求处理异常: %s %s", self.command, self.path)
            self._send_json(router.err(500, "内部错误，请稍后重试"), 500)
            return

        # 静态文件
        self._serve_static(path)

    def do_POST(self) -> None:
        if not self._check_auth():
            return
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/api/import-upload":
            # P0-3：浏览器文件上传导入（multipart），不走 JSON body。
            self._handle_import_upload()
            return
        if path == "/api/admin/login":
            self._handle_admin_login()
            return
        if path == "/api/admin/logout":
            self._handle_admin_logout()
            return
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        self._inject_admin_ctx(path, query)

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
            # 安全：异常原文只记服务端日志（含堆栈），不返回给前端，
            # 避免路径/SQL 等内部细节泄漏。
            _log.exception("请求处理异常: %s %s", self.command, self.path)
            self._send_json(router.err(500, "内部错误，请稍后重试"), 500)

    def do_PUT(self) -> None:
        """CRITICAL：M4 资产更新需要 PUT 支持。"""
        if not self._check_auth():
            return
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        self._inject_admin_ctx(path, query)
        try:
            body = router.read_body(self)
            payload, _ = router.dispatch("PUT", path, body, query)
            if payload is not None:
                self._send_json(payload)
                return
            self._send_json(router.err(404, f"未找到接口: {path}"), 404)
        except ServiceError as exc:
            self._send_json(router.err(exc.code, exc.message), exc.code)
        except Exception as exc:  # noqa: BLE001
            # 安全：异常原文只记服务端日志（含堆栈），不返回给前端，
            # 避免路径/SQL 等内部细节泄漏。
            _log.exception("请求处理异常: %s %s", self.command, self.path)
            self._send_json(router.err(500, "内部错误，请稍后重试"), 500)

    def do_DELETE(self) -> None:
        """CRITICAL：M4 资产删除需要 DELETE 支持。"""
        if not self._check_auth():
            return
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        self._inject_admin_ctx(path, query)
        try:
            payload, _ = router.dispatch("DELETE", path, {}, query)
            if payload is not None:
                self._send_json(payload)
                return
            self._send_json(router.err(404, f"未找到接口: {path}"), 404)
        except ServiceError as exc:
            self._send_json(router.err(exc.code, exc.message), exc.code)
        except Exception as exc:  # noqa: BLE001
            # 安全：异常原文只记服务端日志（含堆栈），不返回给前端，
            # 避免路径/SQL 等内部细节泄漏。
            _log.exception("请求处理异常: %s %s", self.command, self.path)
            self._send_json(router.err(500, "内部错误，请稍后重试"), 500)

    # ------------------------------------------------------------------
    # 管理员登录 / 登出（Cookie 会话，需在 router 分发前处理 Set-Cookie）
    # ------------------------------------------------------------------
    def _session_cookie_header(self, session_id: str | None) -> dict[str, str]:
        if session_id is None:
            value = f"{admin.SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
        else:
            value = (f"{admin.SESSION_COOKIE}={session_id}; Path=/; HttpOnly; "
                     f"SameSite=Lax; Max-Age={admin.SESSION_TTL_SECONDS}")
        return {"Set-Cookie": value}

    def _handle_admin_login(self) -> None:
        ip = self.client_address[0]
        try:
            body = router.read_body(self)
            username = str((body or {}).get("username", "")).strip()
            password = str((body or {}).get("password", ""))
            result = admin.authenticate(username, password, ip)
        except ServiceError as exc:
            self._send_json(router.err(exc.code, exc.message), exc.code)
            return
        except Exception as exc:  # noqa: BLE001
            # 安全：异常原文只记服务端日志（含堆栈），不返回给前端，
            # 避免路径/SQL 等内部细节泄漏。
            _log.exception("请求处理异常: %s %s", self.command, self.path)
            self._send_json(router.err(500, "内部错误，请稍后重试"), 500)
            return
        self._send_json(
            router.ok({"username": result["username"],
                       "mustChangePassword": result["must_change_password"]}),
            200, self._session_cookie_header(result["session_id"]))

    def _handle_admin_logout(self) -> None:
        admin.logout(self._get_cookie(admin.SESSION_COOKIE), self.client_address[0])
        self._send_json(router.ok({"loggedOut": True}), 200,
                        self._session_cookie_header(None))

    def _inject_admin_ctx(self, path: str, query: dict[str, Any]) -> None:
        """给 /api/admin/* 路由注入管理员上下文（用户名/会话ID/IP），供 handler 审计用。"""
        if path == "/api/admin" or path.startswith("/api/admin/"):
            query["_admin_user"] = getattr(self, "_admin_user", "")
            query["_admin_sid"] = getattr(self, "_admin_sid", "")
            query["_admin_ip"] = getattr(self, "_admin_ip", "")

    # ------------------------------------------------------------------
    def _is_same_host_origin(self, origin: str) -> bool:
        """判断 Origin 是否属于本机（localhost / 127.0.0.1 / [::1]），允许同机不同端口。"""
        try:
            from urllib.parse import urlparse
            host = (urlparse(origin).hostname or "").lower()
        except Exception:  # noqa: BLE001
            return False
        # 安全：空 hostname（Origin: null，如 sandboxed iframe）不放行。
        return host in ("localhost", "127.0.0.1", "::1", "[::1]")

    def _handle_import_upload(self) -> None:
        """POST /api/import-upload：multipart 文件上传导入。

        流程：解析 multipart → 文件名安全检查 → 存入 corpus/ →
        调 services.import_book。全部错误转为统一 JSON 错误体。
        """
        try:
            ctype = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in ctype:
                raise ServiceError("Content-Type 必须为 multipart/form-data", 400)
            raw_len = self.headers.get("Content-Length", "0") or "0"
            try:
                length = int(raw_len)
            except ValueError as exc:
                raise ServiceError("Content-Length 非法", 400) from exc
            if length <= 0:
                raise ServiceError("请求体为空", 400)
            if length > router._MAX_UPLOAD_BYTES:
                raise ServiceError("上传文件过大（上限 100MB）", 413)
            raw = self.rfile.read(length)
            filename, file_bytes, fields = router.parse_multipart_upload(raw, ctype)
            safe_name = _safe_upload_filename(filename)
            config.CORPUS_DIR.mkdir(parents=True, exist_ok=True)
            dest = _unique_corpus_path(safe_name)
            dest.write_bytes(file_bytes)
            batch_size = _parse_upload_batch_size(fields.get("batch_size"))
            # 内存：上传缓冲（raw + file_bytes 约 2x 文件大小）已落盘，
            # 先释放再跑导入，避免与导入期（text + chapters 约 2x）的峰值叠加。
            del raw, file_bytes
            try:
                result = services.import_book(str(dest), batch_size)
            except Exception:
                # P2-2：导入失败删掉已落盘的副本，不在 corpus 留垃圾文件。
                try:
                    dest.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            self._send_json(router.ok(result))
        except ServiceError as exc:
            self._send_json(router.err(exc.code, exc.message), exc.code)
        except Exception as exc:  # noqa: BLE001
            # 安全：异常原文只记服务端日志（含堆栈），不返回给前端，
            # 避免路径/SQL 等内部细节泄漏。
            _log.exception("请求处理异常: %s %s", self.command, self.path)
            self._send_json(router.err(500, "内部错误，请稍后重试"), 500)

    def _send_json(self, payload: dict, status: int = 200,
                   extra_headers: dict[str, str] | None = None) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
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
        """SSE 长连接：订阅 broker，持续推送 progress 事件直到客户端断开。

        W15：支持 task_id / task_type 过滤（写作/质检任务不绑 book_id）。
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        # HIGH：SSE 也必须走本机 Origin 回显，不能 ACAO: *（与 M8 一致）
        origin = self.headers.get("Origin", "")
        if origin and self._is_same_host_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
        self.end_headers()

        book_id = query.get("book_id")
        task_id = query.get("task_id")
        task_type = query.get("task_type")
        q: queue.Queue = broker.subscribe()
        try:
            self.wfile.write(f"data: {json.dumps({'status': 'connected', 'book_id': book_id, 'task_id': task_id}, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()
            while True:
                try:
                    event = q.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                # W15：task_id 优先过滤；否则 book_id；再否则 task_type
                if task_id and event.get("task_id") != task_id:
                    continue
                if not task_id and book_id and event.get("book_id") != book_id:
                    continue
                if not task_id and not book_id and task_type and event.get("task_type") != task_type:
                    continue
                self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode())
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
        # 缓存策略：index.html 不缓存；带哈希的资源文件可长期缓存
        if target.name == "index.html":
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        elif "/assets/" in str(target) and any(c in target.name for c in "-_"):
            # Vite 产出的资源文件名含哈希，内容变更时文件名也会变
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        # HTTP 访问日志：INFO 级落盘（gui_state/logs/gui.log），不刷控制台。
        # 凭据类查询参数（auth / handshake / handshake_token）一律脱敏：桌面版把身份
        # 握手令牌交给前端走 `/?handshake=`，SSE 又只能用 `?handshake_token=`，
        # 原样落进 gui.log 就等于把调用凭据写给任何能读到日志的人。
        line = _mask_sensitive_query(format % args)
        _log.info("http %s %s", self.address_string(), line)


def main(argv: list[str] | None = None) -> int:
    """常驻入口（W09）：``python -m gui.server`` 阻塞运行，重复启动被单实例锁拦截。"""
    import argparse
    from pathlib import Path as _P

    # 确保项目根在 sys.path 上（``python gui/server.py`` 直接执行也可）。
    _root = _P(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

    setup_logging()
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


def _win_pid_is_alive(pid: int) -> bool | None:
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


def _read_lock_pid(path: Path) -> int | None:
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

    def __init__(self, preferred_port: int | None = None, handshake_token: str | None = None) -> None:
        self.preferred_port = preferred_port
        self._lock_fd: int | None = None
        # 身份握手 token（Electron 模式）：/api/* 请求必须携带正确的
        # X-Handshake-Token 头，否则 403。浏览器直连模式为 None，不校验。
        self.handshake_token = handshake_token

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

    def _clear_stale_lock(self, lock_path: Path, observed_pid: int | None) -> bool:
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
        _log.info("检测到 stale lock（pid=%s 已退出），已清理", shown)
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
        # P2-4 修复：获锁后任一步抛异常都必须释放锁，否则锁文件残留。
        # （_acquire_lock 有 stale 自愈可覆盖进程退出场景；这里覆盖同进程内重复 start 的测试/嵌入场景。）
        try:
            return self._start_inner()
        except Exception:
            self._release_lock()
            raise

    def _start_inner(self) -> tuple[str, int]:

        # 初始化持久化层 + 迁移（幂等），保证 analysis_tasks 表就绪。
        try:
            db.init_schema()
            db.apply_migrations()
        except Exception as exc:  # noqa: BLE001 — 库损坏不阻断服务，降级为内存/扫描。
            _log.warning("持久化层初始化失败（降级运行）: %s", exc)

        # 自动备份：启动时一次（每日备份由请求闸点触发，见 auto_backup）
        auto_backup.startup_backup()

        # 内置资产增量同步（2026-09-29）：把随包新增的内置资产卡补进用户数据
        # 目录（只补缺失、永不覆盖）。失败只记日志，不阻断启动。
        from gui import builtin_sync
        builtin_sync.sync_at_startup()

        # 管理员系统：首次启动生成随机初始密码（只打印一次）。
        # P1-2 修复（2026-09-29）：桌面端无控制台窗口（windowsHide），只写日志
        # 用户无从得知。首次生成时同步写入数据目录下的明文指引文件，
        # 改密成功后自动删除。
        initial_pw = admin.ensure_initialized()
        if initial_pw:
            announce_initial_password(initial_pw)

        # W15/D3：启动自清理 scratch 残留
        try:
            from gui import quality_service
            n = quality_service.clean_stale_scratch()
            if n:
                _log.info("启动清理 scratch 残留 %d 个文件", n)
        except Exception as exc:  # noqa: BLE001
            _log.warning("启动清理 scratch 失败（不影响服务启动）: %s", exc)

        host, port = self._bind_port()
        self._httpd = ThreadingHTTPServer((host, port), _Handler)
        self._httpd.daemon_threads = True
        # 身份握手：把 token 挂到 httpd 实例上，Handler 可经 self.server 访问。
        self._httpd.handshake_token = self.handshake_token
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
        except Exception as exc:  # noqa: BLE001
            _log.warning("关闭时 SQLite 刷盘失败: %s", exc)
        self._release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
