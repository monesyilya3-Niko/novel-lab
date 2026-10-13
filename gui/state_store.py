"""GUI 任务状态文件（``gui_state_{book_id}.json``）读写。

沿用 state_tracker 的「JSON 权威层 + 单调 state_revision + 原子写回」范式，
但追踪的是**分析进度**（章×批状态 + 断点 cursor + 资产索引），而非叙事连续性。

原子写：先写 ``.tmp`` 再 ``os.replace``，与 state_tracker.save_state 对齐。
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from gui import config, db
from gui.logging_setup import get_logger

# 原子写临时文件的唯一后缀计数器（见 _save_state_json 注释：CONC-01）。
# 用锁保护自增，保证同一进程内序号不重复；pid/tid 已能跨进程跨线程区分。
_TMP_COUNTER_LOCK = threading.Lock()
_TMP_COUNTER = [0]

# 按目标路径的写锁表（CONC-01）：Windows 对同一目标路径并发 os.replace
# 会返回 WinError 5，故同一路径的「写 tmp + 替换」必须串行化。
_PATH_LOCKS: dict[str, threading.Lock] = {}
_PATH_LOCKS_GUARD = threading.Lock()

_log = get_logger("state_store")

SCHEMA_VERSION = 1


def legacy_state_path_for(book_id: str) -> Path:
    """返回旧版（L2 修复前）状态文件路径：``gui_state/gui_state_{book_id}.json``。

    仅供**只读兼容**使用：历史 JSON 可能残留在运行时目录下。写路径一律走
    ``state_path_for()``（新目录），避免再写进被整目录 gitignore 的 ``gui_state/``。
    """
    return config.STATE_ROOT / f"gui_state_{book_id}.json"


def state_path_for(book_id: str) -> Path:
    """返回某本书的状态文件路径（落在独立的 ``STATE_JSON_DIR``）。

    ``gui/state/`` 是 SQLite（``gui_state/index.db``）的**派生镜像**，不入库
    （见 .gitignore）。与运行时目录 ``STATE_ROOT`` 分离，仅为保留运行时 JSON
    降级写入能力（库不可用/未初始化时仍可落盘与读取），不改变任何代码逻辑。
    """
    return config.STATE_JSON_DIR / f"gui_state_{book_id}.json"


def resolve_state_path(book_id: str) -> Path | None:
    """定位某本书**已存在**的状态文件：优先新目录，回退旧位置（兼容历史数据）。

    Returns:
        命中的状态文件路径；两处均不存在时返回 ``None``。
    """
    new_path = state_path_for(book_id)
    if new_path.is_file():
        return new_path
    legacy = legacy_state_path_for(book_id)
    if legacy.is_file():
        return legacy
    return None


def book_id_from_title(title: str, source_path: str) -> str:
    """由书名 + 源路径 hash 生成稳定的 book_id（A7 决策）。

    用书名 sanitize 后拼接路径的短 hash，保证同一文件重复导入得到同一 id。
    """
    import hashlib

    sanitized = "".join(c if (c.isalnum() or c in "-_") else "-" for c in title)
    sanitized = sanitized.strip("-") or "book"
    digest = hashlib.md5(source_path.encode("utf-8")).hexdigest()[:8]
    return f"{sanitized}-{digest}"


def new_state(book_id: str, title: str) -> dict[str, Any]:
    """构造空的任务状态骨架。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "book_id": book_id,
        "title": title,
        "state_revision": 0,
        "cursor": "",
        "chapter_states": {},
        "asset_index": {},
    }


def load_state(book_id: str) -> dict[str, Any]:
    """读取任务状态文件；不存在时返回空状态。

    读取顺序（L2 兼容）：新目录 ``STATE_JSON_DIR`` 优先，缺失时回退旧位置
    ``STATE_ROOT``（兼容 L2 修复前落在 ``gui_state/`` 的历史 JSON）。
    """
    path = resolve_state_path(book_id)
    if path is None:
        return new_state(book_id, "")
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning(f"状态文件损坏，按空白状态重建 book_id={book_id} ({path.name}): {exc}")
        return new_state(book_id, "")


def _save_state_json(state: dict[str, Any]) -> None:
    """原子写回任务状态文件（JSON 降级副本，纯文件写入）。

    ⚠️ 必须按路径加锁（2026-10-13 审计修复 CONC-01）：
    并发写同一 book_id 时（后台分析线程 + HTTP 线程同时保存状态），
    原实现用固定 tmp 名 ``<path>.tmp``，实测 30 线程产生 22 个
    ``PermissionError: WinError 32``（一个线程正写 tmp 时另一个的
    ``os.replace`` 撞上文件占用）。

    仅改唯一 tmp 名**不够**：实测仍有 18 个 ``WinError 5 拒绝访问``——
    那是 Windows 对**同一目标路径**并发 ``os.replace`` 的限制
    （多线程同时替换同一个目标文件，系统拒绝）。
    故按路径持锁串行化「写 tmp + 替换」，唯一 tmp 名作为第二层防御保留
    （防止锁失效或跨进程场景下的互相窃取）。
    """
    book_id = state.get("book_id", "")
    if not book_id:
        raise ValueError("state 缺 book_id，无法定位状态文件")
    path = state_path_for(book_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 唯一临时名：pid + 线程 id + 单调计数器。
    #
    # 注：在**同进程内**，下面的按路径锁已足以避免冲突——本行是第二层
    # 防御，针对锁覆盖不到的场景：跨进程写同一状态文件（如 CLI 与 GUI
    # 同时运行）。那种场景下两个进程各自的锁互不可见，固定 tmp 名会让
    # 它们互相窃取临时文件；唯一名让每个写者各写各的，os.replace 仍是
    # 原子的（Windows 上跨进程同目标并发 replace 可能失败，但那是
    # 罕见场景且失败是显式的——不会静默丢数据）。
    with _TMP_COUNTER_LOCK:
        _TMP_COUNTER[0] += 1
        seq = _TMP_COUNTER[0]
    tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}.{threading.get_ident()}.{seq}.tmp")
    with _path_lock(path):
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(state, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            os.replace(tmp, path)
        except Exception:
            # 失败时清掉自己的临时文件，避免残留堆积（尽力而为，不掩盖原异常）。
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise


@contextmanager
def _path_lock(path: Path) -> Iterator[None]:
    """按目标路径取进程内互斥锁（Windows 下 os.replace 同目标并发会失败）。"""
    key = str(path)
    with _PATH_LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PATH_LOCKS[key] = lock
    with lock:
        yield


def save_state(state: dict[str, Any]) -> None:
    """原子写回任务状态：**SQLite 权威优先，JSON 降级副本其次**。

    ⚠️ 顺序与失败语义（2026-10-13 审计修复 D10）：
    原实现是「先 ``_save_state_json``（无 try）→ 后 ``upsert_task``（被 try 吞）」，
    与设计**正好相反**——设计见下方 ``upsert_task`` 的文档「先写 SQLite（权威），
    后原子写 JSON（降级副本）」。实测后果：JSON 副本写失败（磁盘满、权限、
    路径异常）会**抛出并阻断 SQLite 权威写**，权威库丢更新——而 JSON 只是
    可再生的降级副本，让它拖垮权威源是本末倒置。

    另外原实现实际写了 **2 次 JSON**：``_save_state_json`` 一次，
    ``upsert_task`` 内部又一次（它自带 JSON 副本写）。

    现改为直接委托 ``upsert_task``（它已是权威优先的完整实现）。
    仅当 SQLite 不可用（库未初始化/损坏）时才回退为「只写 JSON」——
    保留原实现的降级能力（旧测试与迁移前环境依赖它）。
    """
    book_id = state.get("book_id", "")
    if not book_id:
        raise ValueError("state 缺 book_id，无法定位状态文件")
    try:
        upsert_task(state)
        return
    except Exception as exc:  # noqa: BLE001 — 库不可用时降级为纯 JSON
        _log.warning(
            "SQLite 权威写入失败，降级为纯 JSON 副本 book_id=%s: %s", book_id, exc)
    # 降级路径：SQLite 不可用，但状态仍须落盘（可备份/可读）。
    # ⚠️ 这里也要容错（2026-10-13 实测）：upsert_task 内部是
    # 「先 db.upsert_task 再 _save_state_json」，若**权威写成功但 JSON 副本写失败**，
    # 异常同样冒泡到这里——此时权威库其实已更新，再试一次 JSON 只会再失败一次
    # 并把异常抛给调用方（状态明明已落库，调用方却以为整个保存失败）。
    # 副本是**可再生的降级数据**，写不出来只记日志，不向上抛。
    try:
        _save_state_json(state)
    except Exception as exc:  # noqa: BLE001
        _log.warning("JSON 降级副本写入失败（权威库可能已更新）book_id=%s: %s",
                     book_id, exc)


def bump_revision(state: dict[str, Any]) -> dict[str, Any]:
    """单调递增 state_revision 并返回 state（原地修改）。"""
    state["state_revision"] = state.get("state_revision", 0) + 1
    return state


def batch_id(chapter_index: int, batch_index: int) -> str:
    """批次 ID 编码：``c{chapter}-b{batch}``。"""
    return f"c{chapter_index}-b{batch_index}"


def parse_cursor(cursor: str) -> tuple[int, int] | None:
    """解析 cursor 字符串 ``c{ch}-b{batch}`` 为 (chapter_index, batch_index)。

    非法或空字符串返回 None。
    """
    if not cursor:
        return None
    parts = cursor.split("-")
    if len(parts) != 2:
        return None
    c_part, b_part = parts
    if not (c_part.startswith("c") and b_part.startswith("b")):
        return None
    try:
        ch = int(c_part[1:])
        bi = int(b_part[1:])
    except ValueError:
        return None
    return ch, bi


def set_batch_state(
    state: dict[str, Any],
    chapter_index: int,
    batch_index: int,
    status: str,
    asset: str | None = None,
) -> dict[str, Any]:
    """记录某批的状态并推进 cursor（原地修改，调用方负责 save_state）。

    cursor 指向「下一个待处理批」：本批成功后，cursor 推进到下一批；失败/跳过
    也推进（失败批由 retry-failed 单独处理，不阻塞串行流）。
    """
    key = batch_id(chapter_index, batch_index)
    state.setdefault("chapter_states", {})[key] = {
        "status": status,
        "asset": asset,
        "ts": int(time.time()),
    }
    if asset:
        state.setdefault("asset_index", {}).setdefault(f"c{chapter_index}", [])
        if key not in state["asset_index"][f"c{chapter_index}"]:
            state["asset_index"][f"c{chapter_index}"].append(key)
    # 推进 cursor 到下一批
    state["cursor"] = batch_id(chapter_index, batch_index + 1)
    bump_revision(state)
    return state


def asset_path(book_id: str, chapter_index: int, batch_index: int, pass_name: str) -> Path:
    """资产落盘路径：``assets/{book_id}/c{ch}-b{bi}-{pass}.json``。"""
    return config.ASSETS_ROOT / book_id / f"c{chapter_index}-b{batch_index}-{pass_name}.json"


def list_asset_ids_for_chapter(state: dict[str, Any], chapter_index: int) -> list[str]:
    """返回某章的批次 ID 列表（有资产记录的）。"""
    return state.get("asset_index", {}).get(f"c{chapter_index}", [])


def _iter_state_files() -> list[Path]:
    """枚举所有状态 JSON 文件：新目录 + 旧位置（L2 兼容），去重（新目录优先）。

    同一 book_id 若新旧两处都存在，只保留新目录的（load_state 的读取顺序一致）。
    """
    seen: dict[str, Path] = {}
    # 旧位置先收集，新目录后收集 → 后者覆盖前者（新优先）。
    for root in (config.STATE_ROOT, config.STATE_JSON_DIR):
        if not root.is_dir():
            continue
        for fp in root.glob("gui_state_*.json"):
            seen[fp.name] = fp
    return list(seen.values())


def list_books_summary() -> list[dict[str, Any]]:
    """扫描状态 JSON 目录，返回「已拆 N 本」概览清单（供首页）。

    返回每本书的 book_id / title / status / cursor / done 批数，按文件 mtime 倒序
    （最近拆的书在前）。不解析失败/损坏的状态文件（跳过）。

    L2：同时覆盖新目录 ``STATE_JSON_DIR`` 与旧位置 ``STATE_ROOT``（兼容历史数据）。
    """
    summaries: list[dict[str, Any]] = []
    for fp in _iter_state_files():
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning(f"跳过无法解析的状态文件 {fp.name}: {exc}")
            continue
        if not isinstance(data, dict) or "book_id" not in data:
            continue
        chapter_states = data.get("chapter_states", {})
        done = sum(1 for v in chapter_states.values()
                   if isinstance(v, dict) and v.get("status") == "success")
        summaries.append({
            "book_id": data.get("book_id", ""),
            "title": data.get("title", ""),
            "status": data.get("status", "idle"),
            "cursor": data.get("cursor", ""),
            "done": done,
            "mtime": fp.stat().st_mtime,
        })
    summaries.sort(key=lambda s: s.get("mtime", 0), reverse=True)
    for s in summaries:
        s.pop("mtime", None)
    return summaries


# ---------------------------------------------------------------------------
# 分析进度双写（SQLite 权威 + gui_state/*.json 降级副本）
# ---------------------------------------------------------------------------

def upsert_task(task: dict[str, Any]) -> None:
    """分析任务双写：先写 SQLite（权威），后原子写 JSON（降级副本）。

    ``task`` 需含 ``book_id``；``chapter_states`` 映射为 SQLite 的 ``batch_state``
    （JSON 字符串），``cursor``/``status``/``genre``/``model_id``/``batch_size``/
    ``state_revision`` 一并落库。运行态（线程/控制标志）不落库（D3）。
    """
    book_id = task.get("book_id", "")
    if not book_id:
        raise ValueError("task 缺 book_id")

    # 兼容 state 结构：batch_state 取 chapter_states（state_store 范式）。
    chapter_states = task.get("chapter_states", {})
    db_task = {
        "book_id": book_id,
        "status": task.get("status", "idle"),
        "genre": task.get("genre"),
        "model_id": task.get("model_id"),
        "batch_size": task.get("batch_size"),
        "cursor": task.get("cursor", ""),
        "batch_state": chapter_states if isinstance(chapter_states, (dict, list)) else {},
        "state_revision": int(task.get("state_revision", 0)),
        "last_error": task.get("last_error"),
    }
    # SQLite 权威写。
    db.upsert_task(db_task)

    # JSON 降级副本（复用原子写，避免再走 save_state 的二次 upsert 递归）。
    _save_state_json(task)


def load_task(book_id: str) -> dict[str, Any]:
    """读取分析任务：优先 SQLite，缺失回退 JSON（state_store.load_state）。

    返回统一结构（含 book_id/status/cursor/batch_state/state_revision 等）。
    """
    row = db.get_task(book_id)
    if row is not None:
        batch_state = row.get("batch_state", "{}")
        if isinstance(batch_state, str):
            try:
                batch_state = json.loads(batch_state) if batch_state else {}
            except json.JSONDecodeError as exc:
                _log.warning(f"SQLite batch_state 损坏，批进度丢失 book_id={book_id}: {exc}")
                batch_state = {}
        return {
            "book_id": row.get("book_id", book_id),
            "status": row.get("status", "idle"),
            "genre": row.get("genre"),
            "model_id": row.get("model_id"),
            "batch_size": row.get("batch_size"),
            "cursor": row.get("cursor", ""),
            "chapter_states": batch_state if isinstance(batch_state, dict) else {},
            "state_revision": int(row.get("state_revision", 0)),
            "last_error": row.get("last_error"),
            "asset_index": {},  # L1：SQLite 路径无此列，显式返回空 dict 保持字段存在
        }
    # 回退 JSON。
    return load_state(book_id)
