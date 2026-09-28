"""管理员系统：账号认证、会话管理、审计日志、仪表盘、书库/资产管理。

安全设计（纯标准库）：
- 密码：PBKDF2-HMAC-SHA256（200k 轮）+ 16 字节随机盐，只存哈希。
- 会话：secrets.token_urlsafe(32) 会话 ID，经 HttpOnly + SameSite=Lax Cookie 下发；
  服务端内存表保存，会话有效期 12 小时。Cookie 本身不携带任何身份信息。
- 登录频率限制：同一 IP 连续 5 次失败 → 锁定 5 分钟。
- 首次启动无管理员账号时生成随机初始密码，只打印一次到服务端日志，
  要求管理员首次登录后立即修改。

路径说明：全部经 ``from gui import config`` 在调用期读取 ``config.STATE_ROOT`` 等，
以便测试用 ``tests/_isolation.py::isolate_paths`` 重定向（禁止在导入期固化路径）。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gui import config
from gui.services import ServiceError

VERSION = "1.1.2"

ADMIN_FILE_NAME = "admin.json"
AUDIT_FILE_NAME = "admin_audit.jsonl"
SESSION_COOKIE = "nl_admin_session"
SESSION_TTL_SECONDS = 12 * 3600
_PBKDF2_ITERATIONS = 200_000
_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_LOCK_SECONDS = 5 * 60
_MIN_PASSWORD_LEN = 8

_STARTED_AT = time.time()

_lock = threading.RLock()
# session_id -> {"username": str, "created_at": float, "expires_at": float, "ip": str}
_sessions: dict[str, dict[str, Any]] = {}
# ip -> {"count": int, "locked_until": float}
_failed_logins: dict[str, dict[str, Any]] = {}

_BOOK_ID_RE = re.compile(r"^[\w\-]+$", re.UNICODE)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 路径（调用期解析，支持测试隔离）
# ---------------------------------------------------------------------------

def _admin_file() -> Path:
    return config.STATE_ROOT / ADMIN_FILE_NAME


def _audit_file() -> Path:
    return config.STATE_ROOT / AUDIT_FILE_NAME


# ---------------------------------------------------------------------------
# 密码
# ---------------------------------------------------------------------------

def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return dk.hex()


def _load_admin() -> dict[str, Any] | None:
    fp = _admin_file()
    if not fp.is_file():
        return None
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _save_admin(data: dict[str, Any]) -> None:
    fp = _admin_file()
    fp.parent.mkdir(parents=True, exist_ok=True)
    tmp = fp.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(fp)


def ensure_initialized() -> str | None:
    """确保管理员账号存在。首次创建时返回随机初始密码（调用方负责告知用户），否则返回 None。"""
    with _lock:
        if _load_admin() is not None:
            return None
        initial_password = secrets.token_urlsafe(12)
        salt = secrets.token_bytes(16)
        _save_admin({
            "username": "admin",
            "salt": salt.hex(),
            "password_hash": _hash_password(initial_password, salt),
            "created_at": _utcnow_iso(),
            "must_change_password": True,
        })
        audit("system", "-", "admin.init", "创建默认管理员账号 admin")
        return initial_password


# ---------------------------------------------------------------------------
# 会话
# ---------------------------------------------------------------------------

def _check_rate_limit(ip: str) -> None:
    now = time.time()
    # 顺带清理过期条目：防止失败不足 5 次的 IP 记录永久堆积。
    stale = [k for k, v in _failed_logins.items()
             if now - v.get("updated_at", 0) > _LOGIN_LOCK_SECONDS]
    for k in stale:
        del _failed_logins[k]
    entry = _failed_logins.get(ip)
    if entry and entry["count"] >= _MAX_LOGIN_ATTEMPTS:
        if now < entry["locked_until"]:
            raise ServiceError("登录失败次数过多，请 5 分钟后再试", 429)
        del _failed_logins[ip]


def _record_failed_login(ip: str) -> None:
    entry = _failed_logins.setdefault(ip, {"count": 0, "locked_until": 0.0})
    entry["count"] += 1
    entry["updated_at"] = time.time()
    if entry["count"] >= _MAX_LOGIN_ATTEMPTS:
        entry["locked_until"] = time.time() + _LOGIN_LOCK_SECONDS


def authenticate(username: str, password: str, ip: str) -> dict[str, Any]:
    """校验账号密码，成功返回 {"session_id", "username"}，失败抛 ServiceError(401)。"""
    with _lock:
        _check_rate_limit(ip)
        data = _load_admin()
        ok = False
        if data and username == data.get("username"):
            salt = bytes.fromhex(data["salt"])
            ok = hmac.compare_digest(
                _hash_password(password, salt), data.get("password_hash", ""))
        if not ok:
            _record_failed_login(ip)
            audit(username or "-", ip, "admin.login.failed", "用户名或密码错误")
            raise ServiceError("用户名或密码错误", 401)
        _failed_logins.pop(ip, None)
        session_id = secrets.token_urlsafe(32)
        now = time.time()
        _sessions[session_id] = {
            "username": data["username"],
            "created_at": now,
            "expires_at": now + SESSION_TTL_SECONDS,
            "ip": ip,
        }
        audit(data["username"], ip, "admin.login", "登录成功")
        return {"session_id": session_id, "username": data["username"],
                "must_change_password": bool(data.get("must_change_password"))}


def get_session_user(session_id: str | None) -> str | None:
    """会话有效返回用户名，否则返回 None（同时清理过期会话）。"""
    if not session_id:
        return None
    with _lock:
        sess = _sessions.get(session_id)
        if not sess:
            return None
        if time.time() > sess["expires_at"]:
            _sessions.pop(session_id, None)
            return None
        return sess["username"]


def logout(session_id: str | None, ip: str = "-") -> None:
    with _lock:
        sess = _sessions.pop(session_id, None) if session_id else None
    if sess:
        audit(sess["username"], ip, "admin.logout", "退出登录")


def list_sessions(current_sid: str = "") -> list[dict[str, Any]]:
    """列出当前有效会话（token 只展示前 8 位前缀，不可用于鉴权）。
    current_sid 匹配的会话标记 current=True，前端用于标识"当前会话"。"""
    now = time.time()
    out = []
    with _lock:
        expired = [sid for sid, s in _sessions.items() if now > s["expires_at"]]
        for sid in expired:
            _sessions.pop(sid, None)
        for sid, s in _sessions.items():
            out.append({
                "id": sid[:8],
                "current": bool(current_sid and sid == current_sid),
                "username": s["username"],
                "ip": s["ip"],
                "createdAt": datetime.fromtimestamp(s["created_at"], tz=timezone.utc).isoformat(timespec="seconds"),
                "expiresAt": datetime.fromtimestamp(s["expires_at"], tz=timezone.utc).isoformat(timespec="seconds"),
            })
    out.sort(key=lambda x: x["createdAt"], reverse=True)
    return out


def revoke_session(id_prefix: str, by_user: str, ip: str) -> None:
    """按 ID 前缀吊销一个会话（前缀需唯一匹配）。"""
    if not id_prefix or len(id_prefix) < 4:
        raise ServiceError("会话 ID 前缀太短", 400)
    with _lock:
        matched = [sid for sid in _sessions if sid.startswith(id_prefix)]
        if not matched:
            raise ServiceError("会话不存在或已过期", 404)
        if len(matched) > 1:
            raise ServiceError("前缀匹配多个会话，请提供更长的前缀", 400)
        sess = _sessions.pop(matched[0])
    audit(by_user, ip, "admin.session.revoke",
          f"吊销会话 {matched[0][:8]}（用户 {sess['username']}，IP {sess['ip']}）")


def reset_password() -> str:
    """本地 CLI 紧急重置：生成新随机密码，吊销全部会话，强制下次登录改密。

    只能通过本机 shell 调用（服务仅绑定 127.0.0.1），调用者即被信任。
    返回新密码（明文，仅输出到本地终端一次）。
    """
    new_password = secrets.token_urlsafe(18)
    with _lock:
        data = _load_admin()
        if not data:
            raise ServiceError("管理员账号不存在，请先启动服务完成初始化", 404)
        new_salt = secrets.token_bytes(16)
        data["salt"] = new_salt.hex()
        data["password_hash"] = _hash_password(new_password, new_salt)
        data["must_change_password"] = True
        _save_admin(data)
        _sessions.clear()
    audit(data.get("username", "admin"), "localhost",
          "admin.password.reset", "经本地 CLI 重置密码，全部会话已吊销")
    return new_password


def change_password(username: str, old_password: str, new_password: str, ip: str) -> None:
    if not new_password or len(new_password) < _MIN_PASSWORD_LEN:
        raise ServiceError(f"新密码至少 {_MIN_PASSWORD_LEN} 位", 400)
    with _lock:
        data = _load_admin()
        if not data or username != data.get("username"):
            raise ServiceError("账号不存在", 404)
        salt = bytes.fromhex(data["salt"])
        if not hmac.compare_digest(_hash_password(old_password, salt), data.get("password_hash", "")):
            audit(username, ip, "admin.change_password.failed", "原密码错误")
            raise ServiceError("原密码错误", 401)
        new_salt = secrets.token_bytes(16)
        data["salt"] = new_salt.hex()
        data["password_hash"] = _hash_password(new_password, new_salt)
        data["must_change_password"] = False
        _save_admin(data)
        # 密码变更后吊销该用户全部会话（防旧会话残留）。
        for sid in [s for s, v in _sessions.items() if v["username"] == username]:
            _sessions.pop(sid, None)
    audit(username, ip, "admin.change_password", "密码已修改，历史会话已吊销")


# ---------------------------------------------------------------------------
# 审计日志（JSONL 追加写）
# ---------------------------------------------------------------------------

def audit(username: str, ip: str, action: str, detail: str = "") -> None:
    try:
        fp = _audit_file()
        fp.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "ts": _utcnow_iso(), "username": username, "ip": ip,
            "action": action, "detail": detail,
        }, ensure_ascii=False)
        with fp.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        # 审计写失败不阻断业务，但必须可见：打到 stderr 进服务日志
        print(f"[admin-audit] 写入失败 ({action}): {e}", file=sys.stderr)


def read_audit(limit: int = 100, action: str = "", username: str = "") -> list[dict[str, Any]]:
    """读取审计日志（最新的在前）。在最近 2000 条内先过滤再截断；
    大文件时从尾部倒读，避免全量载入内存。"""
    limit = max(1, min(limit, 500))
    fp = _audit_file()
    if not fp.is_file():
        return []
    try:
        lines = _tail_lines(fp, 2000)
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if action and entry.get("action") != action:
            continue
        if username and entry.get("username") != username:
            continue
        out.append(entry)
    return list(reversed(out[-limit:]))


def _tail_lines(fp: Path, n: int) -> list[str]:
    """取文件最后 n 行（大文件友好：从尾部块倒读）。"""
    with fp.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        # 每次向前读 8KB，直到凑够 n+1 行或到文件头
        buf = b""
        pos = size
        while pos > 0 and buf.count(b"\n") <= n:
            step = min(8192, pos)
            pos -= step
            f.seek(pos)
            buf = f.read(step) + buf
        text = buf.decode("utf-8", errors="replace")
    lines = text.splitlines()
    return lines[-n:]


# ---------------------------------------------------------------------------
# 仪表盘
# ---------------------------------------------------------------------------

def _dir_size(path: Path) -> int:
    total = 0
    if not path.is_dir():
        return 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            continue
    return total


def get_dashboard() -> dict[str, Any]:
    """系统概览：版本/运行/数据统计/磁盘占用。只读聚合，不触发重型计算。

    注意：不用 services.get_overview()，它会经 engine_adapter 触发 llm_client
    导入（外部模型链路），管理仪表盘不应依赖它。改为直调
    asset_index.index.get_overview()（与首页同一口径，不经过模型链路）。
    """
    import sys

    from gui import asset_index, services, state_store  # 延迟导入，避免循环依赖

    books = state_store.list_books_summary()
    try:
        overview = asset_index.index.get_overview()
    except Exception:  # noqa: BLE001
        overview = {}
    items = []
    for b in books[:10]:
        try:
            total = services.get_book(b.get("book_id", "")).get("totalChapters", 0)
        except Exception:  # noqa: BLE001
            total = 0
        items.append({"bookId": b.get("book_id"), "title": b.get("title"),
                      "status": b.get("status"), "totalChapters": total})
    data_dirs = {
        "corpus": config.CORPUS_DIR,
        "assets": config.ASSETS_ROOT,
        "reports": config.REPORTS_DIR,
        "gui_state": config.STATE_ROOT,
    }
    disk = {name: _dir_size(p) for name, p in data_dirs.items()}
    return {
        "version": VERSION,
        "python": sys.version.split()[0],
        "startedAt": datetime.fromtimestamp(_STARTED_AT, tz=timezone.utc).isoformat(timespec="seconds"),
        "uptimeSeconds": int(time.time() - _STARTED_AT),
        "books": {
            "total": len(books),
            "analyzing": sum(1 for b in books if b.get("status") == "analyzing"),
            "items": items,
        },
        "assetsTotal": overview.get("total_assets", 0),
        "reportsTotal": overview.get("total_reports", 0),
        "assetsByKind": overview.get("assets_by_kind", {}),
        "diskBytes": disk,
        "diskTotalBytes": sum(disk.values()),
        "recentAudit": read_audit(10),
    }


# ---------------------------------------------------------------------------
# 书库管理
# ---------------------------------------------------------------------------

def _validate_book_id(book_id: str) -> str:
    if not book_id or not _BOOK_ID_RE.match(book_id):
        raise ServiceError("非法 book_id", 400)
    return book_id


def _safe_unlink(path: Path, base: Path, label: str) -> bool:
    """仅当 path 解析后位于 base 内时删除，返回是否删除。

    越界时返回 False（跳过）而不抛错：调用方（如删书）应继续清理
    其余部分，不能因一个外部文件导致整个删除中断。
    """
    try:
        resolved = path.resolve()
    except OSError:
        return False
    if not resolved.is_relative_to(base.resolve()):
        return False
    if resolved.is_file():
        resolved.unlink()
        return True
    return False


def delete_book(book_id: str, username: str, ip: str) -> dict[str, Any]:
    """删除书籍：状态文件（新旧位置）、corpus 原文（仅限 corpus 目录内）、
    assets/{book_id}/、内存缓存、SQLite 相关行。返回删除清单。"""
    from gui import services  # 延迟导入，避免循环依赖

    book_id = _validate_book_id(book_id)
    removed: list[str] = []

    # 1) 读状态拿 source_path（先读后删）。
    state = None
    for fp in (config.STATE_JSON_DIR / f"gui_state_{book_id}.json",
               config.STATE_ROOT / f"gui_state_{book_id}.json"):
        if fp.is_file():
            try:
                state = json.loads(fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                state = {}
            break
    if state is None:
        raise ServiceError(f"书籍不存在: {book_id}", 404)

    # 分析中的书籍禁止删除（避免与后台任务竞态；前端按钮只是第一道防线）。
    if isinstance(state, dict) and state.get("status") == "analyzing":
        raise ServiceError("书籍正在分析中，无法删除", 409)

    # 2) corpus 原文：仅当解析后位于 CORPUS_DIR 内才删。
    src = (state or {}).get("source_path", "")
    if src:
        if _safe_unlink(Path(src), config.CORPUS_DIR, "原文"):
            removed.append("corpus")

    # 3) 状态文件（新旧两处）。
    for fp in (config.STATE_JSON_DIR / f"gui_state_{book_id}.json",
               config.STATE_ROOT / f"gui_state_{book_id}.json"):
        if fp.is_file():
            fp.unlink()
            removed.append(fp.name)

    # 4) assets/{book_id}/ 整目录（book_id 已校验无分隔符）。
    book_assets = config.ASSETS_ROOT / book_id
    if book_assets.is_dir():
        shutil.rmtree(book_assets)
        removed.append(f"assets/{book_id}/")

    # 5) 内存缓存。
    services._BOOKS.pop(book_id, None)

    # 6) SQLite：books / assets / reports / analysis_tasks 中 book_id 相关的行。
    db_removed = 0
    try:
        from gui import db
        if db._db_ready():
            with db.tx() as conn:
                for table in ("books", "assets", "reports", "analysis_tasks"):
                    try:
                        cur = conn.execute(f"DELETE FROM {table} WHERE book_id = ?", (book_id,))
                        db_removed += cur.rowcount or 0
                    except Exception:  # noqa: BLE001 - 表结构差异时跳过
                        continue
        removed.append(f"sqlite:{db_removed}行")
    except Exception:  # noqa: BLE001 - DB 不可用时不阻断删除
        pass

    audit(username, ip, "admin.book.delete", f"{book_id}（{removed}）")
    return {"bookId": book_id, "removed": removed}
