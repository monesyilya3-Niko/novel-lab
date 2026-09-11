"""SQLite 持久化层：连接管理 + schema 初始化 + 版本化迁移 + 目录→库同步函数。

这是全项目唯一 import ``sqlite3`` 并接触 ``index.db`` 文件的地方（铁律三边界）。

设计要点（见 DESIGN_gui_persistence §1.3 / §2）：
- 进程级单连接：``check_same_thread=False`` 让单连接跨线程共享，靠 SQLite 自身
  锁串行化写；``ThreadingHTTPServer`` 多线程并发下由 WAL 提升并发读写。
- ``tx()`` 事务上下文：所有写路径统一走 ``with tx():``，失败回滚。
- ``apply_migrations()``：按 ``migrations/*.sql`` 文件名序号顺序执行缺失版本，
  记录到 ``schema_migrations`` 表，每条迁移在单事务内执行。
- ``close()``：``wal_checkpoint(TRUNCATE)`` 刷盘 + 关闭连接（优雅关闭用）。

仅依赖标准库：sqlite3 / contextlib / json / os / pathlib / datetime。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from gui import config

# ---------------------------------------------------------------------------
# 连接管理：每线程独立连接（不是进程级单连接）
#
# 【为何必须每线程一条】sqlite3 的事务状态是「连接级」的：``commit()`` 提交的是
# 该连接上所有未提交的 DML，``rollback()`` 同理。GUI 用 ThreadingHTTPServer，写路径
# 来自多个并发线程（每本书一个分析线程 + 若干 HTTP 线程）。若共享一条连接：
#   - 线程 A 执行 DML 隐式 BEGIN 后，线程 B 的 DML 不会新开事务而是并入同一事务；
#   - B 的 rollback() 会把 A 已写入的数据一并回滚，A 的 commit() 又会提交 B 的半成品。
# 结果是任务状态/资产记录可能丢写、错写或跨请求串写。WAL 只提升并发读，
# 解决不了「共享连接的事务语义」问题。
# ---------------------------------------------------------------------------
_conns: Dict[int, sqlite3.Connection] = {}   # threading.get_ident() -> Connection
_conns_lock = threading.Lock()
_conn_path: Optional[Path] = None             # 当前所有连接绑定的库路径


def db_path() -> Path:
    """动态解析库文件路径（Q1：gui_state/index.db）。

    不缓存为模块级常量：测试会 monkeypatch ``config.STATE_ROOT``，路径需在连接时
    动态求值，避免连接到测试隔离前的真实库。
    """
    return config.STATE_ROOT / "index.db"


def _new_conn(path: Path) -> sqlite3.Connection:
    """建立并配置一条新连接（PRAGMA 统一在此处设置）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _close_all_locked() -> None:
    """关闭全部连接（调用方必须已持有 ``_conns_lock``）。"""
    global _conn_path
    for conn in _conns.values():
        try:
            conn.close()
        except sqlite3.Error:
            pass
    _conns.clear()
    _conn_path = None


def get_conn() -> sqlite3.Connection:
    """返回**当前线程**的连接；该线程首次调用时建立并配置 PRAGMA。

    配置项：``row_factory=sqlite3.Row``（dict-like 取值）、``journal_mode=WAL``、
    ``foreign_keys=ON``、``busy_timeout=5000``。

    **每线程独立连接**：事务的 commit/rollback 是连接级操作，共享连接会让并发
    线程互相污染事务边界（详见文件头注释）。这里不再使用 ``check_same_thread=False``，
    每条连接只由其创建线程使用，天然安全。

    库路径变化时（测试 monkeypatch ``config.STATE_ROOT``）自动关闭旧连接重建。
    """
    global _conn_path
    path = db_path()
    tid = threading.get_ident()
    with _conns_lock:
        if _conn_path is not None and _conn_path != path:
            # STATE_ROOT 被切换（测试隔离场景）→ 丢弃全部旧连接
            _close_all_locked()
        conn = _conns.get(tid)
        if conn is None:
            conn = _new_conn(path)
            _conns[tid] = conn
            if _conn_path is None:
                _conn_path = path
    return conn


def _reset_conn() -> None:
    """关闭并清空全部连接（供测试隔离：切换 STATE_ROOT 后重建连接）。"""
    with _conns_lock:
        _close_all_locked()


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """事务上下文：正常提交，异常回滚并重新抛出。写路径统一走这里。"""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_schema() -> None:
    """确保 ``schema_migrations`` 与各表存在（幂等 CREATE IF NOT EXISTS）。

    直接执行建表 SQL（等价于 0001_init.sql 的 DDL），保证即便迁移登记表为空、
    基础 schema 也能先落地；后续 ``apply_migrations`` 再按版本号执行缺失迁移。
    """
    _exec_sql_file(Path(__file__).parent / "migrations" / "0001_init.sql")


def split_sql_statements(script: str) -> List[str]:
    """把 SQL 脚本切分为单条语句（供事务内逐条 execute）。

    【为何不用 ``executescript``】``executescript`` 会先隐式提交当前事务再执行脚本，
    导致「DDL + 版本登记」无法原子化：DDL 已落库但若版本登记失败，下次重跑会重复执行
    该迁移。故改为逐条 ``execute``，配合显式 BEGIN/COMMIT 保证原子性。

    切分规则：按 ``;`` 切分，并跳过 **行注释（``--``）**、**块注释（``/* */``）**
    与 **单/双引号字符串** 内部的分号（避免误切）。
    """
    stmts: List[str] = []
    buf: List[str] = []
    i, n = 0, len(script)
    while i < n:
        ch = script[i]
        # 行注释：忽略到行尾
        if ch == "-" and script.startswith("--", i):
            j = script.find("\n", i)
            if j == -1:
                break
            i = j + 1
            continue
        # 块注释：忽略到 */
        if ch == "/" and script.startswith("/*", i):
            j = script.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        # 单引号字符串（'' 为转义）
        if ch == "'":
            j = i + 1
            while j < n:
                if script[j] == "'":
                    if j + 1 < n and script[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            buf.append(script[i:j + 1])
            i = j + 1
            continue
        # 双引号标识符（"" 为转义）
        if ch == '"':
            j = i + 1
            while j < n:
                if script[j] == '"':
                    if j + 1 < n and script[j + 1] == '"':
                        j += 2
                        continue
                    break
                j += 1
            buf.append(script[i:j + 1])
            i = j + 1
            continue
        if ch == ";":
            stmts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if "".join(buf).strip():
        stmts.append("".join(buf))
    return [s.strip() for s in stmts if s.strip()]


def apply_migrations() -> List[int]:
    """按 ``migrations/*.sql`` 文件名序号顺序执行缺失版本，返回已执行版本列表。

    版本号取自文件名前导数字（如 ``0001_init.sql`` → 1）。已登记的版本跳过。
    **每条迁移在单事务内执行（DDL + 版本登记原子提交），失败整体回滚、不留半成品。**
    """
    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.is_dir():
        return []

    applied: List[int] = []
    files = _sorted_migration_files(migrations_dir)
    for version, name, sql_path in files:
        if _is_applied(version):
            continue
        # 整条迁移（DDL + 版本登记）在一个显式事务内执行。
        # 注意：不能用 executescript（会隐式提交，破坏原子性），改为逐条 execute。
        conn = get_conn()
        conn.execute("BEGIN")
        try:
            for stmt in split_sql_statements(sql_path.read_text(encoding="utf-8")):
                conn.execute(stmt)
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (version, name),
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            raise
        applied.append(version)
    return applied


def _sorted_migration_files(migrations_dir: Path) -> List[tuple[int, str, Path]]:
    """扫描迁移目录，返回按版本号排序的 (version, name, path) 列表。"""
    entries: List[tuple[int, str, Path]] = []
    for fp in sorted(migrations_dir.glob("*.sql")):
        name = fp.name
        # 提取前导数字作为版本号。
        digits = ""
        for ch in name:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            continue
        entries.append((int(digits), name, fp))
    entries.sort(key=lambda e: e[0])
    return entries


def _is_applied(version: int) -> bool:
    """查询 schema_migrations 判断某版本是否已执行。"""
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
    ).fetchone()
    return row is not None


def _exec_sql_file(sql_path: Path) -> None:
    """执行单个 SQL 文件（幂等 DDL，可在事务外运行）。"""
    if not sql_path.is_file():
        return
    conn = get_conn()
    conn.executescript(sql_path.read_text(encoding="utf-8"))
    conn.commit()


def close() -> None:
    """优雅关闭：对每条连接 wal_checkpoint(TRUNCATE) 刷盘 + 关闭。"""
    with _conns_lock:
        for conn in _conns.values():
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:
                pass
            try:
                conn.close()
            except sqlite3.Error:
                pass
        _conns.clear()
        global _conn_path
        _conn_path = None


# ---------------------------------------------------------------------------
# 查询辅助（供 asset_index / services / migrate 复用，均走 SQLite）
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """把 sqlite3.Row 转为普通 dict。"""
    return {k: row[k] for k in row.keys()}


def _db_ready() -> bool:
    """判断 schema 是否已初始化（``assets`` 表存在即视为就绪）。

    只读探测：未建库（如旧测试 monkeypatch STATE_ROOT 后未 init_schema）时返回 False，
    让上层（asset_index / services / state_store）回退目录扫描 / JSON，避免 OperationalError。
    """
    conn = get_conn()
    try:
        conn.execute("SELECT 1 FROM assets LIMIT 1").fetchone()
        return True
    except sqlite3.Error:
        return False


def count_assets(kind: Optional[str] = None, genre: Optional[str] = None,
                 book_id: Optional[str] = None) -> int:
    """按条件聚合资产计数（SQL COUNT）。未建库时返回 0（上层回退）。"""
    if not _db_ready():
        return 0
    conn = get_conn()
    where: List[str] = []
    params: List[Any] = []
    if kind:
        where.append("kind = ?")
        params.append(kind)
    if genre:
        where.append("genre = ?")
        params.append(genre)
    if book_id:
        where.append("book_id = ?")
        params.append(book_id)
    sql = "SELECT COUNT(*) AS n FROM assets"
    if where:
        sql += " WHERE " + " AND ".join(where)
    row = conn.execute(sql, params).fetchone()
    return int(row["n"]) if row else 0


def list_asset_rows(kind: Optional[str] = None, genre: Optional[str] = None,
                    book_id: Optional[str] = None, offset: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
    """按条件 + 分页查询资产行（SQL WHERE + LIMIT/OFFSET）。未建库时返回空列表。"""
    if not _db_ready():
        return []
    conn = get_conn()
    where: List[str] = []
    params: List[Any] = []
    if kind:
        where.append("kind = ?")
        params.append(kind)
    if genre:
        where.append("genre = ?")
        params.append(genre)
    if book_id:
        where.append("book_id = ?")
        params.append(book_id)
    sql = "SELECT * FROM assets"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY name LIMIT ? OFFSET ?"
    params.extend([int(limit), int(offset)])
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def count_by_kind() -> Dict[str, int]:
    """按 kind 聚合计数（SELECT kind, COUNT(*) GROUP BY kind）。未建库时返回空 dict。"""
    if not _db_ready():
        return {}
    conn = get_conn()
    rows = conn.execute("SELECT kind, COUNT(*) AS n FROM assets GROUP BY kind").fetchall()
    return {r["kind"]: int(r["n"]) for r in rows}


def get_asset_by_key(asset_key: str) -> Optional[Dict[str, Any]]:
    """按 asset_key 查询单条资产（供详情定位 path）。未建库时返回 None。"""
    if not _db_ready():
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM assets WHERE asset_key = ?", (asset_key,)).fetchone()
    return _row_to_dict(row) if row else None


def list_reports(book_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """查询报告清单（可选按 book_id 过滤）。未建库时返回空列表（上层回退扫描）。"""
    if not _db_ready():
        return []
    conn = get_conn()
    if book_id:
        rows = conn.execute("SELECT * FROM reports WHERE book_id = ? ORDER BY path", (book_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM reports ORDER BY path").fetchall()
    return [_row_to_dict(r) for r in rows]


def get_books(status: Optional[str] = None, book_id: Optional[str] = None,
              genre: Optional[str] = None) -> List[Dict[str, Any]]:
    """查询书清单（可选按 status / book_id / genre 过滤，参数化防注入）。

    未建库时返回空列表（上层回退）。genre 按 books.genre 列精确匹配。
    """
    if not _db_ready():
        return []
    conn = get_conn()
    where: List[str] = []
    params: List[Any] = []
    if status:
        where.append("status = ?")
        params.append(status)
    if book_id:
        where.append("book_id = ?")
        params.append(book_id)
    if genre:
        where.append("genre = ?")
        params.append(genre)
    sql = "SELECT * FROM books"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY book_id"
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_genres() -> List[Dict[str, Any]]:
    """查询题材字典表。未建库时返回空列表。"""
    if not _db_ready():
        return []
    conn = get_conn()
    rows = conn.execute("SELECT * FROM genres ORDER BY name").fetchall()
    return [_row_to_dict(r) for r in rows]


def get_task(book_id: str) -> Optional[Dict[str, Any]]:
    """按 book_id 查询分析任务。未建库时返回 None（上层回退 JSON）。"""
    if not _db_ready():
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM analysis_tasks WHERE book_id = ?", (book_id,)).fetchone()
    return _row_to_dict(row) if row else None


def upsert_task(task: Dict[str, Any]) -> None:
    """UPSERT 分析任务（SQLite 权威写，见 state_store.upsert_task 双写入口）。

    task 需含 book_id；batch_state 用 JSON 字符串落库。
    """
    book_id = task.get("book_id", "")
    if not book_id:
        raise ValueError("task 缺 book_id")
    batch_state = task.get("batch_state", {})
    batch_state_json = json.dumps(batch_state, ensure_ascii=False) if not isinstance(batch_state, str) else batch_state
    now = datetime.now(timezone.utc).isoformat()
    with tx() as conn:
        conn.execute(
            """
            INSERT INTO analysis_tasks
                (book_id, status, genre, model_id, batch_size, cursor, batch_state,
                 state_revision, last_error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(book_id) DO UPDATE SET
                status = excluded.status,
                genre = excluded.genre,
                model_id = excluded.model_id,
                batch_size = excluded.batch_size,
                cursor = excluded.cursor,
                batch_state = excluded.batch_state,
                state_revision = excluded.state_revision,
                last_error = excluded.last_error,
                updated_at = excluded.updated_at
            """,
            (
                book_id,
                task.get("status", "idle"),
                task.get("genre"),
                task.get("model_id"),
                task.get("batch_size"),
                task.get("cursor", ""),
                batch_state_json,
                int(task.get("state_revision", 0)),
                task.get("last_error"),
                task.get("created_at", now),
                now,
            ),
        )


def backup_to(dst: Path) -> None:
    """把当前库在线备份到 *dst*（正确处理 WAL 未 checkpoint 的写入）。

    优先走原生 ``Connection.backup`` API；失败时回退 ``shutil.copy2``。
    ``migrate.backup()`` 调用本函数，不再自行 import sqlite3。
    """
    import shutil

    conn = get_conn()
    try:
        conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        bak_conn = sqlite3.connect(str(dst))
        try:
            conn.backup(bak_conn)
        finally:
            bak_conn.close()
    except Exception:  # noqa: BLE001 — 连接异常时退化为文件拷贝
        src = db_path()
        if src.is_file():
            shutil.copy2(src, dst)


def reset_all() -> None:
    """清空所有表（测试隔离用，非生产接口）。"""
    conn = get_conn()
    with tx() as c:
        for t in ("assets", "reports", "books", "analysis_tasks", "genres", "schema_migrations"):
            c.execute(f"DELETE FROM {t}")
