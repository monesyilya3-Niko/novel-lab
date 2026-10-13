"""SQLite 持久化层：连接管理 + schema 初始化 + 版本化迁移 + 目录→库同步函数。

这是全项目唯一 import ``sqlite3`` 并接触 ``index.db`` 文件的地方（铁律三边界）。

设计要点（见 DESIGN_gui_persistence §1.3 / §2）：
- 每线程独立连接（不是进程级单连接）：``check_same_thread=False`` 允许任意线程
  关闭连接；连接按 ``threading.get_ident()`` 隔离存放。原因见下文
  “连接管理：每线程独立连接”注释——共享单连接时 sqlite3 的连接级事务语义会
  导致跨线程丢写/错写。``ThreadingHTTPServer`` 多线程并发下由 WAL 提升并发读写，
  写冲突时 ``busy_timeout=5000`` 等待锁释放。
- ``tx()`` 事务上下文：所有写路径统一走 ``with tx():``，失败回滚。
- ``apply_migrations()``：按 ``migrations/*.sql`` 文件名序号顺序执行缺失版本，
  记录到 ``schema_migrations`` 表，每条迁移在单事务内执行。
- ``close()``：``wal_checkpoint(TRUNCATE)`` 刷盘 + 关闭连接（优雅关闭用）。

仅依赖标准库：sqlite3 / contextlib / json / os / pathlib / datetime。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gui import config

# 供服务层标注「SQLite 行对象」用的类型别名。
#
# 背景：``gui/db.py`` 是唯一 import sqlite3 的层（AGENTS.md §2 依赖方向禁令）。
# 但服务层需要给「可能拿到 Row、也可能拿到 dict」的参数标类型，此前
# essence_service 为此自行 import sqlite3，构成对依赖方向的违反。
# 该导入仅用于标注（运行时不需要 sqlite3），故在此导出别名供各层复用：
# 服务层写 ``db.RowLike`` 即可，无需触碰 sqlite3 本身。
RowLike = sqlite3.Row | dict[str, Any]

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
_conns: dict[int, sqlite3.Connection] = {}   # threading.get_ident() -> Connection
_conns_lock = threading.Lock()
_conn_path: Path | None = None             # 当前所有连接绑定的库路径
_get_conn_calls: list[int] = [0]            # B3：死线程清理节流计数器


def db_path() -> Path:
    """动态解析库文件路径（Q1：gui_state/index.db）。

    不缓存为模块级常量：测试会 monkeypatch ``config.STATE_ROOT``，路径需在连接时
    动态求值，避免连接到测试隔离前的真实库。
    """
    return config.STATE_ROOT / "index.db"


def _new_conn(path: Path) -> sqlite3.Connection:
    """建立并配置一条新连接（PRAGMA 统一在此处设置）。

    B3：check_same_thread=False —— 允许任意线程关闭连接。
    事务隔离仍由「每线程独立连接」（_conns 按 tid 分池）保证，此处仅放行
    跨线程 close()，否则 _prune_dead_threads_locked() 会因 ProgrammingError
    静默失败导致 FD 泄漏。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
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
    线程互相污染事务边界（详见文件头注释）。每条连接仍只由其创建线程**使用**，
    但创建时设 ``check_same_thread=False`` 以允许任意线程执行 ``close()``
    （B3：否则跨线程关闭抛 ProgrammingError 被吞掉，FD 泄漏）。

    库路径变化时（测试 monkeypatch ``config.STATE_ROOT``）自动关闭旧连接重建。
    """
    global _conn_path
    path = db_path()
    tid = threading.get_ident()
    with _conns_lock:
        if _conn_path is not None and _conn_path != path:
            # STATE_ROOT 被切换（测试隔离场景）→ 丢弃全部旧连接
            _close_all_locked()
        # B3：清理死线程的残留连接（每 50 次调用检查一次，避免每次枚举开销）。
        _get_conn_calls[0] += 1
        if _get_conn_calls[0] % 50 == 0:
            _prune_dead_threads_locked()
        conn = _conns.get(tid)
        if conn is None:
            conn = _new_conn(path)
            _conns[tid] = conn
            if _conn_path is None:
                _conn_path = path
    return conn


def _prune_dead_threads_locked() -> None:
    """关闭已死亡线程的残留连接（B3：防止 fd/内存单调泄漏）。

    调用方必须持有 _conns_lock。
    """
    live_idents = {t.ident for t in threading.enumerate() if t.ident is not None}
    # 主线程的 ident 恒为 alive；当前线程也在 enumerate 内。
    dead = [tid for tid in _conns if tid not in live_idents]
    for tid in dead:
        try:
            _conns[tid].close()
        except sqlite3.Error:
            pass
        del _conns[tid]


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

    ⚠️ 不得用 ``executescript``（2026-10-13 审计修复 D13）：
    ``executescript`` 会先**隐式提交当前事务**再执行脚本。若调用方已在
    ``with db.tx()`` 里（例如业务逻辑中途确保 schema 存在），一次
    ``init_schema()`` 就会把那个事务提交掉——后续抛错时回滚失效，
    半成品数据留在库里。实测复现：事务内 INSERT 后调 init_schema，
    ``in_transaction`` 由 True 变 False，raise 触发 rollback 后该行仍残留。

    改为逐条 execute（复用 ``split_sql_statements``，与 apply_migrations 同口径），
    且**只在没有活动事务时才 commit**——DDL 的隐式提交已被避免，但显式
    ``commit()`` 同样会提交调用方的事务。实测：仅去掉 executescript 仍不够，
    末尾的 commit 照样把 in_transaction 由 True 变 False。
    """
    sql_path = Path(__file__).parent / "migrations" / "0001_init.sql"
    if not sql_path.is_file():
        return
    conn = get_conn()
    # 记录进入时的状态：若调用方已在事务中，我们不得提交它。
    had_tx = conn.in_transaction
    for stmt in split_sql_statements(sql_path.read_text(encoding="utf-8")):
        conn.execute(stmt)
    if not had_tx:
        conn.commit()


def split_sql_statements(script: str) -> list[str]:
    """把 SQL 脚本切分为单条语句（供事务内逐条 execute）。

    【为何不用 ``executescript``】``executescript`` 会先隐式提交当前事务再执行脚本，
    导致「DDL + 版本登记」无法原子化：DDL 已落库但若版本登记失败，下次重跑会重复执行
    该迁移。故改为逐条 ``execute``，配合显式 BEGIN/COMMIT 保证原子性。

    切分规则：按 ``;`` 切分，并跳过 **行注释（``--``）**、**块注释（``/* */``）**
    与 **单/双引号字符串** 内部的分号（避免误切）。
    """
    stmts: list[str] = []
    buf: list[str] = []
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


def apply_migrations() -> list[int]:
    """按 ``migrations/*.sql`` 文件名序号顺序执行缺失版本，返回已执行版本列表。

    版本号取自文件名前导数字（如 ``0001_init.sql`` → 1）。已登记的版本跳过。
    **每条迁移在单事务内执行（DDL + 版本登记原子提交），失败整体回滚、不留半成品。**
    """
    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.is_dir():
        return []

    applied: list[int] = []
    files = _sorted_migration_files(migrations_dir)
    for version, name, sql_path in files:
        if _is_applied(version):
            continue
        # 整条迁移（DDL + 版本登记）在一个显式事务内执行。
        # 注意：不能用 executescript（会隐式提交，破坏原子性），改为逐条 execute。
        #
        # ⚠️ 必须用 BEGIN IMMEDIATE（2026-10-13 审计修复 D18）：
        # 裸 ``BEGIN`` 是 DEFERRED —— 它**不立即取写锁**，等到第一条写语句
        # 才尝试升级。两个进程并发迁移时（桌面版 + CLI 同时启动是真实场景），
        # 双方都可能先读到旧快照，随后一条升级锁失败 → ``database is locked``，
        # 迁移中断。IMMEDIATE 在 BEGIN 时就取写锁，把冲突前移到起点：
        # 后来者直接等锁（受 busy_timeout 约束），而不是走到一半才失败。
        conn = get_conn()
        conn.execute("BEGIN IMMEDIATE")
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


def _sorted_migration_files(migrations_dir: Path) -> list[tuple[int, str, Path]]:
    """扫描迁移目录，返回按版本号排序的 (version, name, path) 列表。"""
    entries: list[tuple[int, str, Path]] = []
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

def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """把 sqlite3.Row 转为普通 dict。"""
    return {k: row[k] for k in row.keys()}


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """把 sqlite3.Row 转为普通 dict（供各服务层使用的公开入口）。"""
    return _row_to_dict(row)


def rows_to_dicts(rows: Any) -> list[dict[str, Any]]:
    """把 Row 序列转为普通 dict 列表（供各服务层使用的公开入口）。"""
    return [_row_to_dict(r) for r in rows]


def table_exists(table_name: str) -> bool:
    """探测指定表在当前 SQLite 库中是否存在（只读元数据查询）。"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False


def _db_ready() -> bool:
    """判断 schema 是否已初始化（``assets`` 表存在即视为就绪）。

    只读探测：未建库（如旧测试 monkeypatch STATE_ROOT 后未 init_schema）时返回 False，
    让上层（asset_index / services / state_store）回退目录扫描 / JSON，避免 OperationalError。
    """
    return table_exists("assets")


def count_assets(kind: str | None = None, genre: str | None = None,
                 book_id: str | None = None) -> int:
    """按条件聚合资产计数（SQL COUNT）。未建库时返回 0（上层回退）。"""
    if not _db_ready():
        return 0
    conn = get_conn()
    where: list[str] = []
    params: list[Any] = []
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


def list_asset_rows(kind: str | None = None, genre: str | None = None,
                    book_id: str | None = None, offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
    """按条件 + 分页查询资产行（SQL WHERE + LIMIT/OFFSET）。未建库时返回空列表。"""
    if not _db_ready():
        return []
    conn = get_conn()
    where: list[str] = []
    params: list[Any] = []
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


def count_by_kind() -> dict[str, int]:
    """按 kind 聚合计数（SELECT kind, COUNT(*) GROUP BY kind）。未建库时返回空 dict。"""
    if not _db_ready():
        return {}
    conn = get_conn()
    rows = conn.execute("SELECT kind, COUNT(*) AS n FROM assets GROUP BY kind").fetchall()
    return {r["kind"]: int(r["n"]) for r in rows}


def get_asset_by_key(asset_key: str) -> dict[str, Any] | None:
    """按 asset_key 查询单条资产（供详情定位 path）。未建库时返回 None。"""
    if not _db_ready():
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM assets WHERE asset_key = ?", (asset_key,)).fetchone()
    return _row_to_dict(row) if row else None


def list_reports(book_id: str | None = None) -> list[dict[str, Any]]:
    """查询报告清单（可选按 book_id 过滤）。未建库时返回空列表（上层回退扫描）。"""
    if not _db_ready():
        return []
    conn = get_conn()
    if book_id:
        rows = conn.execute("SELECT * FROM reports WHERE book_id = ? ORDER BY path", (book_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM reports ORDER BY path").fetchall()
    return [_row_to_dict(r) for r in rows]


def get_books(status: str | None = None, book_id: str | None = None,
              genre: str | None = None) -> list[dict[str, Any]]:
    """查询书清单（可选按 status / book_id / genre 过滤，参数化防注入）。

    未建库时返回空列表（上层回退）。genre 按 books.genre 列精确匹配。
    """
    if not _db_ready():
        return []
    conn = get_conn()
    where: list[str] = []
    params: list[Any] = []
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


def get_genres() -> list[dict[str, Any]]:
    """查询题材字典表。未建库时返回空列表。"""
    if not _db_ready():
        return []
    conn = get_conn()
    rows = conn.execute("SELECT * FROM genres ORDER BY name").fetchall()
    return [_row_to_dict(r) for r in rows]


def get_task(book_id: str) -> dict[str, Any] | None:
    """按 book_id 查询分析任务。未建库时返回 None（上层回退 JSON）。"""
    if not table_exists("analysis_tasks"):
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM analysis_tasks WHERE book_id = ?", (book_id,)).fetchone()
    return _row_to_dict(row) if row else None


def upsert_task(task: dict[str, Any]) -> None:
    """UPSERT 分析任务（SQLite 权威写，见 state_store.upsert_task 双写入口）。

    task 需含 book_id；batch_state 用 JSON 字符串落库。
    """
    if not table_exists("analysis_tasks"):
        return
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

    优先走原生 ``Connection.backup`` API；失败时回退到**同时复制主库与 WAL**。
    ``migrate.backup()`` 调用本函数，不再自行 import sqlite3。

    ⚠️ 回退分支不能用裸 ``shutil.copy2(src, dst)``（2026-10-12 修）：
    WAL 模式下新写入的表/数据可能整个还在 ``-wal`` 文件里。实测——
    建表后立即 copy2 主库，备份文件打开报 "no such table: t"，因为
    表结构都在 WAL 中未合并。那种"备份"是无效的（虽然
    ``_verify_backup`` 会因缺关键表而拦下，但等于备份功能整体不可用）。
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
            # 复制主库 **与 WAL/SHM 边车文件**。只复制主库会丢数据：
            # WAL 模式下新写入的表/数据可能整个还在 -wal 里，裸 copy2 得到的
            # "备份"打开报 no such table（实测）。
            #
            # 注意：此处**不做** checkpoint。回退分支的触发条件本就是
            # "连接/备份 API 异常"，此时库上很可能有其它连接持锁，
            # 再尝试 wal_checkpoint(TRUNCATE) 会以 "database table is locked"
            # 失败并污染错误路径（2026-10-12 实测：导致 migrate 的三个测试
            # 在全量运行时报错）。直接连带边车文件复制即可——SQLite 打开
            # 备份时能自行从 -wal 恢复出完整内容。
            shutil.copy2(src, dst)
            for suffix in ("-wal", "-shm"):
                side = Path(str(src) + suffix)
                if side.is_file():
                    try:
                        shutil.copy2(side, Path(str(dst) + suffix))
                    except OSError:
                        # 边车文件可能正被其它连接持有（Windows 独占），
                        # 复制失败不致命：主库+已复制的部分仍可打开。
                        continue
    # 验证备份可用：损坏的备份比没有备份更危险（恢复时才发现）。
    _verify_backup(dst)


def _verify_backup(dst: Path) -> None:
    """校验备份文件可打开且完整；失败抛 RuntimeError。"""
    if not dst.is_file():
        raise RuntimeError(f"备份失败：{dst} 未生成")
    try:
        chk = sqlite3.connect(str(dst))
    except sqlite3.Error as e:
        raise RuntimeError(f"备份文件无法打开：{e}") from e
    try:
        try:
            row = chk.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.Error as e:
            raise RuntimeError(f"备份完整性校验失败：{e}") from e
        if not row or row[0] != "ok":
            raise RuntimeError(f"备份完整性校验失败：{row}")
        # 关键表存在性抽查
        tables = {r[0] for r in chk.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ("books", "assets", "reports"):
            if t not in tables:
                raise RuntimeError(f"备份缺关键表：{t}")
    finally:
        chk.close()


def reset_all() -> None:
    """清空所有表（测试隔离用，非生产接口）。

    ⚠️ 表清单**动态发现**，不再手写（2026-10-13 审计修复 D20）：
    原实现硬编码 6 张表（assets/reports/books/analysis_tasks/genres/
    schema_migrations），而迁移 0002~0004 又加了 9 张（essence_* ×4、
    writing_* ×5）。实测：往各表插一行后调 reset_all，6 张老表归零、
    **9 张新表各残留 1 行**——测试隔离不彻底，数据跨轮累积
    （项目历史上有过同类事故：gui/state 泄漏导致测试持续失败）。

    改为查 sqlite_master 清空全部业务表：新增迁移时自动覆盖，
    不会再出现"加了表忘了加进清单"。
    """
    conn = get_conn()
    tables = [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
    ]
    with tx() as c:
        for t in tables:
            c.execute(f"DELETE FROM {t}")   # noqa: S608 — 表名来自 sqlite_master，非用户输入
