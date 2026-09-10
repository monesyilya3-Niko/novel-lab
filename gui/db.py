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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from gui import config

# 进程级单连接 + 其绑定的库路径（用于检测 STATE_ROOT 被 monkeypatch 后重建连接）。
_conn: Optional[sqlite3.Connection] = None
_conn_path: Optional[Path] = None


def db_path() -> Path:
    """动态解析库文件路径（Q1：gui_state/index.db）。

    不缓存为模块级常量：测试会 monkeypatch ``config.STATE_ROOT``，路径需在连接时
    动态求值，避免连接到测试隔离前的真实库。
    """
    return config.STATE_ROOT / "index.db"


def get_conn() -> sqlite3.Connection:
    """返回进程级单连接；首次调用时建立并配置 PRAGMA。

    配置项：``row_factory=sqlite3.Row``（dict-like 取值）、``journal_mode=WAL``、
    ``foreign_keys=ON``、``busy_timeout=5000``。``check_same_thread=False`` 允许多线程共享。
    """
    global _conn, _conn_path
    if _conn is None or _conn_path != db_path():
        if _conn is not None:
            try:
                _conn.close()
            except sqlite3.Error:
                pass
        config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(db_path()), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _conn.execute("PRAGMA busy_timeout=5000")
        _conn_path = db_path()
    return _conn


def _reset_conn() -> None:
    """关闭并清空进程级连接（供测试隔离：切换 STATE_ROOT 后重建连接）。"""
    global _conn, _conn_path
    if _conn is not None:
        try:
            _conn.close()
        except sqlite3.Error:
            pass
        _conn = None
    _conn_path = None


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


def apply_migrations() -> List[int]:
    """按 ``migrations/*.sql`` 文件名序号顺序执行缺失版本，返回已执行版本列表。

    版本号取自文件名前导数字（如 ``0001_init.sql`` → 1）。已登记的版本跳过，
    每条迁移在单事务内执行，失败回滚（不留半成品）。
    """
    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.is_dir():
        return []

    applied: List[int] = []
    files = _sorted_migration_files(migrations_dir)
    for version, name, sql_path in files:
        if _is_applied(version):
            continue
        # 整条迁移在一个事务内执行。
        with tx() as conn:
            conn.executescript(sql_path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (version, name),
            )
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
    """优雅关闭：wal_checkpoint(TRUNCATE) 刷盘 + 关闭连接。"""
    global _conn, _conn_path
    if _conn is not None:
        try:
            _conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass
        try:
            _conn.close()
        except sqlite3.Error:
            pass
        _conn = None
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


def reset_all() -> None:
    """清空所有表（测试隔离用，非生产接口）。"""
    conn = get_conn()
    with tx() as c:
        for t in ("assets", "reports", "books", "analysis_tasks", "genres", "schema_migrations"):
            c.execute(f"DELETE FROM {t}")
