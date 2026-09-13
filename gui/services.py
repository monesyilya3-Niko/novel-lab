"""服务层业务编排：导入 / 切批 / 分析执行 / 暂停 / 续传 / 重试。

分层：路由层 → 服务层 → 引擎适配层。本模块不 import novel-lab 脚本，
只调用 engine_adapter 与 state_store。
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from gui import config, engine_adapter, state_store, asset_index
from gui.logging_setup import get_logger
from gui import db
from gui.sse import broker

_log = get_logger("services")

# 每个 pass 分析的 kind 名（串行顺序）。
PASS_ORDER = ("pass1_structure", "pass2_character", "pass3_style", "pass4_commercial")


class ServiceError(Exception):
    """服务层业务错误，携带 HTTP 状态码。"""

    def __init__(self, message: str, code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


# ---------------------------------------------------------------------------
# 运行时全局（进程内单例）
# ---------------------------------------------------------------------------

# 已导入书籍：book_id -> {title, source_path, chapters:[(title, body)], metrics}
_BOOKS: Dict[str, Dict[str, Any]] = {}

# 分析运行时：book_id -> 分析上下文（线程 + 控制标志）
_runtime: Dict[str, Dict[str, Any]] = {}
_runtime_lock = threading.Lock()


def _books_dir() -> Path:
    return config.STATE_ROOT


# ---------------------------------------------------------------------------
# 导入
# ---------------------------------------------------------------------------

def import_book(path: str, batch_size: Optional[int] = None) -> Dict[str, Any]:
    """读 txt → 切章 → 切批 → 生成 book_id → 建状态文件 → 返回 Book。

    返回的 Book 章节列表只含批次元信息（不含正文），正文按需由 chapter 接口返回。
    路径安全校验由路由层（router._h_import）负责，本函数保持对内部调用友好。
    """
    src = Path(path)
    if not src.exists():
        raise ServiceError(f"文件不存在: {path}", 404)
    if src.suffix.lower() != ".txt":
        raise ServiceError("首版仅支持 .txt 导入", 400)

    try:
        text = src.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # 尝试 gbk（中文 txt 常见编码）
        try:
            text = src.read_text(encoding="gbk")
        except UnicodeDecodeError:
            raise ServiceError("文件编码无法识别（仅支持 UTF-8 / GBK）", 400)

    chapters_raw = engine_adapter.split_chapters(text)
    if not chapters_raw:
        raise ServiceError("未解析到任何章节（请确认文件为章节体 txt）", 400)

    bs = batch_size or config.batch_size_from_env()
    title = src.stem
    book_id = state_store.book_id_from_title(title, str(src))

    # 计算每章批次（只存元信息；正文不入响应，按需由 chapter 接口返回）。
    chapters_meta: List[Dict[str, Any]] = []
    for i, (ctitle, cbody) in enumerate(chapters_raw, start=1):
        batches = engine_adapter.split_batches(cbody, bs)
        chapters_meta.append({
            "index": i,
            "title": ctitle,
            "batch_count": len(batches),
            "batches": [{
                "chapter_index": i,
                "batch_index": b["batch_index"],
                "char_start": b["char_start"],
                "char_end": b["char_end"],
                "status": "pending",
            } for b in batches],
        })

    # 整书量化指标（缓存复用，供单批分析）。
    metrics = engine_adapter.compute_metrics(text)

    _BOOKS[book_id] = {
        "title": title,
        "source_path": str(src),
        "chapters": chapters_raw,
        "metrics": metrics,
    }

    # 建/复用状态文件。
    state = state_store.load_state(book_id)
    state["title"] = title
    state_store.save_state(state)

    return {
        "book_id": book_id,
        "title": title,
        "source_path": str(src),
        "total_chapters": len(chapters_raw),
        "chapters": chapters_meta,
    }


def get_book(book_id: str) -> Dict[str, Any]:
    """返回 Book 摘要（章节 + 批元信息，不含正文全文）。"""
    book = _get_book_or_raise(book_id)
    chapters_meta = _chapters_meta(book_id, book)
    return {
        "book_id": book_id,
        "title": book["title"],
        "source_path": book["source_path"],
        "total_chapters": len(book["chapters"]),
        "chapters": chapters_meta,
    }


def get_chapter(book_id: str, idx: int) -> Dict[str, Any]:
    """返回单章（含全文 + 批切分结果）。"""
    book = _get_book_or_raise(book_id)
    chapters = book["chapters"]
    if idx < 1 or idx > len(chapters):
        raise ServiceError(f"章节 {idx} 不存在（共 {len(chapters)} 章）", 404)
    ctitle, cbody = chapters[idx - 1]
    batches = split_chapter_batches(book_id, idx)
    return {
        "index": idx,
        "title": ctitle,
        "text": cbody,
        "batch_count": len(batches),
        "batches": batches,
    }


def split_chapter_batches(book_id: str, idx: int, batch_size: Optional[int] = None) -> List[Dict[str, Any]]:
    """切批薄封装，可配置 batch_size。"""
    book = _get_book_or_raise(book_id)
    chapters = book["chapters"]
    if idx < 1 or idx > len(chapters):
        raise ServiceError(f"章节 {idx} 不存在", 404)
    _, cbody = chapters[idx - 1]
    bs = batch_size or config.batch_size_from_env()
    batches = engine_adapter.split_batches(cbody, bs)
    return [{
        "chapter_index": idx,
        "batch_index": b["batch_index"],
        "char_start": b["char_start"],
        "char_end": b["char_end"],
        "text": b["text"],
        "status": "pending",
    } for b in batches]


def _get_book_or_raise(book_id: str) -> Dict[str, Any]:
    book = _BOOKS.get(book_id)
    if book is None:
        raise ServiceError(f"书籍 {book_id} 未导入（请先 import）", 404)
    return book


def _chapters_meta(book_id: str, book: Dict[str, Any]) -> List[Dict[str, Any]]:
    """构造章节元信息（批数 + 状态，从状态文件同步状态）。"""
    state = state_store.load_state(book_id)
    chapter_states = state.get("chapter_states", {})
    metas = []
    for i, (ctitle, cbody) in enumerate(book["chapters"], start=1):
        batches = engine_adapter.split_batches(cbody, config.batch_size_from_env())
        batch_metas = []
        for b in batches:
            key = state_store.batch_id(i, b["batch_index"])
            st = chapter_states.get(key, {}).get("status", "pending")
            batch_metas.append({
                "chapter_index": i,
                "batch_index": b["batch_index"],
                "char_start": b["char_start"],
                "char_end": b["char_end"],
                "text": "",
                "status": st,
            })
        metas.append({
            "index": i,
            "title": ctitle,
            "batch_count": len(batches),
            "batches": batch_metas,
        })
    return metas


# ---------------------------------------------------------------------------
# 分析执行（串行：章→批→pass）
# ---------------------------------------------------------------------------

def start_analysis(book_id: str, genre: str, model_id: Optional[str] = None,
                   batch_size: Optional[int] = None) -> Dict[str, Any]:
    """开始/重启分析。串行跑，后台线程执行，SSE 推送进度。"""
    book = _get_book_or_raise(book_id)
    if not engine_adapter.any_model_configured():
        raise ServiceError("未配置外部模型，请先运行 model_config.py 配置（PRD Q7：首版 GUI 仅支持已配置模型）", 400)

    bs = batch_size or config.batch_size_from_env()

    # 【修复 M6】「检查 + 建 ctx + 建线程 + 登记 + 启动」必须在一个临界区内完成。
    # 原先分两段加锁且 thread 在锁外赋值，两个并发 start 可同时通过 is_alive 检查
    # （都看到无线程），各自起一个分析线程并发写同一状态与资产。
    with _runtime_lock:
        rt = _runtime.get(book_id)
        if rt and rt.get("thread") and rt["thread"].is_alive():
            raise ServiceError("分析已在运行中", 409)

        state = state_store.load_state(book_id)
        state["genre"] = genre
        state["model_id"] = model_id
        state["batch_size"] = bs
        # 【修复 H3】必须把 status 重置为 running 并清掉上一次的 report_error。
        # 否则重跑一本已分析完（status="done"）的书时，报告监听线程 _watch 首次
        # 轮询就读到残留的 "done"，立刻用旧/半成品资产生成报告，并与新启动的
        # 分析线程并发读写同一批资产卡；返回体却仍声称 status:"running"。
        state["status"] = "running"
        state.pop("report_error", None)
        state_store.save_state(state)

        # 启动后台线程（在锁内完成登记与启动，保证并发安全）
        stop_flag = threading.Event()
        ctx = {"stop_flag": stop_flag, "paused": threading.Event(), "thread": None}
        _runtime[book_id] = ctx
        thread = threading.Thread(
            target=_run_analysis,
            args=(book_id, genre, model_id, bs, ctx),
            daemon=True,
            name=f"analysis-{book_id}",
        )
        ctx["thread"] = thread
        thread.start()

    # 返回持久化的真实 cursor（断点），而非硬编码 c1-b0。
    state = state_store.load_state(book_id)
    cursor = state.get("cursor") or state_store.batch_id(1, 0)
    return {"task_id": book_id, "cursor": cursor, "status": "running"}


def _run_analysis(book_id: str, genre: str, model_id: Optional[str], batch_size: int, ctx: Dict[str, Any]) -> None:
    """后台串行分析主循环。"""
    book = _BOOKS.get(book_id)
    if book is None:
        return
    chapters = book["chapters"]
    metrics = book["metrics"]
    total_batches = _count_total_batches(chapters, batch_size)
    done = 0

    try:
        for ci, (ctitle, cbody) in enumerate(chapters, start=1):
            batches = engine_adapter.split_batches(cbody, batch_size)
            for b in batches:
                bi = b["batch_index"]
                key = state_store.batch_id(ci, bi)

                # 断点续传：已 success 的批直接跳过，不重复分析（设计 §3.3/§5）。
                existing = state_store.load_state(book_id).get("chapter_states", {}).get(key)
                if existing and existing.get("status") == "success":
                    done += 1
                    continue

                _wait_if_paused(ctx)
                if ctx["stop_flag"].is_set():
                    _publish(book_id, ci, bi, "paused", done, total_batches, ctx)
                    return

                _publish(book_id, ci, bi, "running", done, total_batches, ctx)
                # 标记 running 落盘
                state = state_store.load_state(book_id)
                state_store.set_batch_state(state, ci, bi, "running")
                state_store.save_state(state)

                # 串行跑四个 pass
                batch_results = {}
                last_asset = None
                try:
                    for pass_name in PASS_ORDER:
                        out = engine_adapter.run_batch(
                            pass_name, ci, ctitle, b["text"], metrics,
                            dry_run=False, model_id=model_id,
                        )
                        batch_results[pass_name] = out
                        # 每个 pass 落一个资产文件
                        ap = state_store.asset_path(book_id, ci, bi, pass_name)
                        ap.parent.mkdir(parents=True, exist_ok=True)
                        ap.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
                        # 资产相对路径以 ASSETS_ROOT 为基准（不假设 ASSETS_ROOT 在 ROOT_DIR 下，
                        # 兼容测试/自定义目录隔离），供前端按 book_id/ch/batch/pass 定位。
                        try:
                            last_asset = str(ap.relative_to(config.ASSETS_ROOT))
                        except ValueError:
                            last_asset = str(ap)
                except Exception as exc:  # noqa: BLE001
                    state = state_store.load_state(book_id)
                    state_store.set_batch_state(state, ci, bi, "failed")
                    state["last_error"] = str(exc)[:500]
                    state_store.save_state(state)
                    done += 1
                    _publish(book_id, ci, bi, "failed", done, total_batches, ctx)
                    continue

                # 记录成功（资产取 pass1 作为代表，asset_index 只记批）
                state = state_store.load_state(book_id)
                state_store.set_batch_state(state, ci, bi, "success", asset=last_asset)
                state_store.save_state(state)
                done += 1
                _publish(book_id, ci, bi, "success", done, total_batches, ctx)

        # 全部完成
        state = state_store.load_state(book_id)
        state["status"] = "done"
        state_store.save_state(state)
        _publish(book_id, 0, 0, "done", done, total_batches, ctx)
    except Exception as exc:  # noqa: BLE001
        state = state_store.load_state(book_id)
        state["status"] = "error"
        state["last_error"] = str(exc)[:500]
        state_store.save_state(state)


def _wait_if_paused(ctx: Dict[str, Any]) -> None:
    """暂停时阻塞，直到 resume 或 stop。"""
    while ctx["paused"].is_set() and not ctx["stop_flag"].is_set():
        time.sleep(0.2)


def _publish(book_id: str, ci: int, bi: int, status: str, done: int, total: int, ctx: Dict[str, Any]) -> None:
    broker.publish({
        "book_id": book_id,
        "cursor": state_store.batch_id(ci, bi),
        "chapter_index": ci,
        "batch_index": bi,
        "status": status,
        "done": done,
        "total": total,
    })


def _count_total_batches(chapters: List[Any], batch_size: int) -> int:
    total = 0
    for _, cbody in chapters:
        total += len(engine_adapter.split_batches(cbody, batch_size))
    return total


# ---------------------------------------------------------------------------
# 暂停 / 续传 / 重试
# ---------------------------------------------------------------------------

def pause(book_id: str) -> Dict[str, Any]:
    """暂停（当前批完成后停）。"""
    ctx = _runtime.get(book_id)
    if ctx is None:
        raise ServiceError("没有运行中的分析任务", 404)
    ctx["paused"].set()
    state = state_store.load_state(book_id)
    state["status"] = "paused"
    state_store.save_state(state)
    return {"cursor": state.get("cursor", "")}


def resume(book_id: str, genre: Optional[str] = None, model_id: Optional[str] = None) -> Dict[str, Any]:
    """从中断批续传（跳过已 success 批，幂等）。"""
    book = _get_book_or_raise(book_id)
    ctx = _runtime.get(book_id)
    if ctx and ctx.get("thread") and ctx["thread"].is_alive():
        # 若处于 paused，则解除暂停继续。
        if ctx["paused"].is_set():
            ctx["paused"].clear()
            return {"cursor": state_store.load_state(book_id).get("cursor", "")}
        raise ServiceError("分析已在运行中", 409)

    state = state_store.load_state(book_id)
    g = genre or state.get("genre", "unknown")
    mid = model_id or state.get("model_id")
    bs = state.get("batch_size", config.batch_size_from_env())
    return start_analysis(book_id, g, mid, bs)


def retry_failed(book_id: str) -> Dict[str, Any]:
    """重试所有失败批（P1）。把失败批状态重置为 pending，再触发续传。"""
    state = state_store.load_state(book_id)
    failed = [k for k, v in state.get("chapter_states", {}).items() if v.get("status") == "failed"]
    if not failed:
        return {"retried": 0}
    for key in failed:
        state["chapter_states"][key]["status"] = "pending"
    state_store.save_state(state)
    # L2：线程存活时主循环会按 pending 重扫，不必（也不能）再 resume。
    rt = _runtime.get(book_id)
    if rt and rt.get("thread") and rt["thread"].is_alive():
        return {"retried": len(failed), "note": "线程运行中，将在当前循环内重扫"}
    resume(book_id)
    return {"retried": len(failed)}


# ---------------------------------------------------------------------------
# 状态查询
# ---------------------------------------------------------------------------

def get_asset(book_id: str, chapter_index: int, batch_index: int, pass_name: str) -> Dict[str, Any]:
    """读取某批某个 pass 的资产 JSON 内容。

    pass_name 允许传入任意值，但会做白名单校验以防路径穿越；
    资产不存在时返回空 dict（前端显示「暂无结果」）。
    """
    _get_book_or_raise(book_id)
    if pass_name not in PASS_ORDER:
        raise ServiceError(f"未知 pass: {pass_name}", 400)
    ap = state_store.asset_path(book_id, chapter_index, batch_index, pass_name)
    if not ap.is_file():
        return {}
    try:
        return json.loads(ap.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning(f"pass 资产加载失败，按空结果返回 {ap.name}: {exc}")
        return {}


def get_status(book_id: Optional[str] = None) -> Dict[str, Any]:
    """返回 TaskState（含 cursor + chapter_states）。

    优先从 ``state_store.load_task``（SQLite 权威 + JSON 降级）读取，保证进程重启后
    仍可恢复 cursor/batch_state（W08 验收点）。
    """
    if not book_id:
        # 返回第一个已导入的书，或空状态。
        if not _BOOKS:
            return {"book_id": None, "status": "idle", "cursor": "", "done": 0, "total": 0}
        book_id = next(iter(_BOOKS))

    state = state_store.load_task(book_id)
    book = _BOOKS.get(book_id)
    total = 0
    if book:
        total = _count_total_batches(book["chapters"], state.get("batch_size", config.batch_size_from_env()))
    done = sum(1 for v in state.get("chapter_states", {}).values() if v.get("status") == "success")
    return {
        "book_id": book_id,
        "status": state.get("status", "idle"),
        "cursor": state.get("cursor", ""),
        "done": done,
        "total": total,
        "chapter_states": state.get("chapter_states", {}),
        "asset_index": state.get("asset_index", {}),
    }


# ---------------------------------------------------------------------------
# 阶段一：概览 / 资产 / 报告 / 拆书结果 / 一键分析
# ---------------------------------------------------------------------------

def get_overview() -> Dict[str, Any]:
    """首页概览聚合：SQL 聚合计数 + 已拆书本数 + 模型状态。"""
    ov = asset_index.index.get_overview()
    # 「已拆 N 本」来自 SQLite books 表（status='done'）优先，回退 gui_state 目录。
    done_books = db.get_books(status="done")
    if done_books:
        ov["total_books"] = len(done_books)
    else:
        books = state_store.list_books_summary()
        ov["total_books"] = len(books)
    ov["model_configured"] = engine_adapter.any_model_configured() or ov.get("model_configured", False)
    return ov


def list_assets(kind: Optional[str] = None, genre: Optional[str] = None,
                book_id: Optional[str] = None, offset: int = 0, limit: int = 50) -> Dict[str, Any]:
    """资产清单分页（kind/genre/book_id 可选组合筛选）。"""
    try:
        return asset_index.index.list_assets(kind, genre, book_id, offset, limit)
    except ValueError as exc:
        raise ServiceError(str(exc), 400)


def get_asset_detail(kind: str, asset_id: str) -> Dict[str, Any]:
    """资产详情（只读，白名单校验）。"""
    try:
        return asset_index.index.get_asset_detail(kind, asset_id)
    except ValueError as exc:
        raise ServiceError(str(exc), 400)
    except KeyError as exc:
        raise ServiceError(str(exc), 404)


def list_reports() -> List[Dict[str, Any]]:
    """报告清单（拆书报告 + 笔法分析），优先 SQLite，空则回退扫描。"""
    rows = db.list_reports()
    if rows:
        out = []
        for r in rows:
            path = r.get("path", "")
            stem = Path(path).stem if path else r.get("title", "")
            out.append({
                "id": f"report:{stem}",
                "name": stem,
                "kind": r.get("type", "book"),
                "book_id": r.get("book_id", ""),
                "size": None,
            })
        return out
    # 回退扫描（迁移前）。
    items = [it for it in asset_index.index.scan()["items"] if it["kind"] == "report"]
    out = []
    for it in items:
        out.append({
            "id": it["id"],
            "name": it["name"],
            "kind": it.get("report_kind", "book"),
            "book_id": it.get("book_id", ""),
            "size": it["size"],
        })
    return out


def get_stats() -> Dict[str, Any]:
    """关系统计（P1）：书→资产/报告计数、题材→卡片计数、kind 分布。

    返回结构：
    {
        "books": [{book_id, title, status, asset_count, report_count}, ...],
        "genres": [{genre, asset_count}, ...],
        "by_kind": {kind: count},
        "totals": {books, assets, reports},
    }
    """
    books = db.get_books()
    ready = db._db_ready()
    if not ready:
        # 库未就绪：回退目录扫描（兼容迁移前的旧测试/环境）。
        books = []
        totals = {"books": 0, "assets": 0, "reports": 0}
    else:
        conn = db.get_conn()
        totals = {
            "books": len(books),
            "assets": conn.execute("SELECT COUNT(*) AS n FROM assets").fetchone()["n"],
            "reports": conn.execute("SELECT COUNT(*) AS n FROM reports").fetchone()["n"],
        }

    book_stats = []
    if ready:
        conn = db.get_conn()
        for b in books:
            bid = b["book_id"]
            n_assets = conn.execute("SELECT COUNT(*) AS n FROM assets WHERE book_id = ?", (bid,)).fetchone()["n"]
            n_reports = conn.execute("SELECT COUNT(*) AS n FROM reports WHERE book_id = ?", (bid,)).fetchone()["n"]
            book_stats.append({
                "book_id": bid,
                "title": b.get("title", bid),
                "status": b.get("status", "idle"),
                "genre": b.get("genre"),
                "asset_count": n_assets,
                "report_count": n_reports,
            })
        genre_rows = conn.execute(
            "SELECT genre, COUNT(*) AS n FROM assets WHERE genre IS NOT NULL AND genre != '' "
            "GROUP BY genre ORDER BY n DESC"
        ).fetchall()
        genres = [{"genre": r["genre"], "asset_count": r["n"]} for r in genre_rows]
    else:
        genres = []

    # M7：by_kind 与 totals 共用同一就绪判据，避免空库中间态下数字打架。
    by_kind = asset_index.index.count_by_kind() if ready else {}
    return {"books": book_stats, "genres": genres, "by_kind": by_kind, "totals": totals}


def get_report(report_id: str) -> Dict[str, Any]:
    """报告 Markdown 原文（前端 react-markdown 渲染）。"""
    # report_id 形如 ``report:<name>``。
    try:
        detail = asset_index.index.get_asset_detail("report", report_id)
    except (ValueError, KeyError) as exc:
        raise ServiceError(str(exc), 404)
    return {"id": report_id, "name": detail["name"], "markdown": detail["markdown"]}


def _load_assembled_card(book_id: str, card_type: str) -> Dict[str, Any]:
    """从 assets/{book_id}/ 或 assets/ 根目录定位组装卡。

    阶段一沿用旧 DESIGN A6：整书跑完统一组装，命名 ``{book_id}-{card_type}.json``，
    落在 assets/ 根目录下（当前资产落盘即 assets/ 根目录）；若缺失返回空 dict 降级。
    """
    mapping = {
        "voice": ("voice-card", "voice-card-distilled"),
        "structure": ("structure-obs", "structure-obs-distilled"),
        "commercial": ("commercial-obs", "commercial-obs-distilled"),
        "craft": ("craft-card", "craft-card-distilled"),
    }
    candidates = mapping.get(card_type, ())
    # 优先 assets/{book_id}/ 子目录，其次 assets/ 根目录。
    search_dirs = [config.ASSETS_ROOT / book_id, config.ASSETS_ROOT]
    for suffix in candidates:
        for d in search_dirs:
            fp = d / f"{book_id}-{suffix}.json"
            if fp.is_file():
                try:
                    return json.loads(fp.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError) as exc:
                    _log.warning(f"资产卡加载失败 {fp.name}: {exc}")
                    continue
    return {}


def get_book_results(book_id: str) -> Dict[str, Any]:
    """某书拆书结构化结果（组装卡 + 章节打分 + 报告关联）。

    阶段一：voice-card/structure/commercial 缺失时降级返回批级 pass 原始 JSON 聚合
    （见 DESIGN §8 D1）；章节打分为空列表（打分属阶段二 consistency，见 D2）。
    """
    voice = _load_assembled_card(book_id, "voice")
    structure = _load_assembled_card(book_id, "structure")
    commercial = _load_assembled_card(book_id, "commercial")
    craft = _load_assembled_card(book_id, "craft")

    title = (voice.get("meta") or {}).get("source_title", book_id)

    # 报告关联：reports 目录下 {book_id}-拆书报告.md / {book_id}-笔法分析.md。
    report_ids = []
    for name in (f"{book_id}-拆书报告", f"{book_id}-笔法分析"):
        if (config.REPORTS_DIR / f"{name}.md").is_file():
            report_ids.append(f"report:{name}")

    return {
        "book_id": book_id,
        "title": title,
        "voice_card": voice,
        "structure": structure,
        "commercial": commercial,
        "craft_card": craft,
        "chapter_scores": _collect_chapter_scores(book_id, voice),
        "report_ids": report_ids,
    }


def _collect_chapter_scores(book_id: str, voice: Dict[str, Any]) -> List[Dict[str, Any]]:
    """章节打分（阶段一尽力而为）。

    若组装卡含一致性相关分数则提取；否则扫描批级 pass 结果 JSON，尝试读取内嵌的
    一致性/质量分。阶段一通常返回空列表（打分属阶段二）。
    """
    scores: List[Dict[str, Any]] = []
    assets_dir = config.ASSETS_ROOT / book_id
    if not assets_dir.is_dir():
        return scores
    # 扫描批级 pass JSON，按章节聚合（尽力而为提取 quality/consistency 字段）。
    seen: Dict[int, Dict[str, Any]] = {}
    for fp in sorted(assets_dir.glob("c*-b*-pass*.json")):
        # 文件名形如 c{ch}-b{bi}-{pass}.json。
        stem = fp.stem  # e.g. c3-b2-pass1_structure
        try:
            ch_str = stem.split("-b")[0][1:]  # 去掉前缀 'c'
            chapter_index = int(ch_str)
        except (ValueError, IndexError):
            continue
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning(f"跳过无法解析的批状态 {fp.name}: {exc}")
            continue
        if not isinstance(data, dict):
            continue
        entry = seen.setdefault(chapter_index, {"chapter_index": chapter_index,
                                                "title": f"第{chapter_index}章",
                                                "consistency": 0.0, "quality": 0.0})
        # 尽力提取分数。
        for key in ("consistency", "consistency_score", "score"):
            if isinstance(data.get(key), (int, float)):
                entry["consistency"] = float(data[key])
        for key in ("quality", "quality_score"):
            if isinstance(data.get(key), (int, float)):
                entry["quality"] = float(data[key])
    if seen:
        scores = [seen[k] for k in sorted(seen)]
    return scores


def get_book_scores(book_id: str) -> List[Dict[str, Any]]:
    """章节打分数据（供章节打分对比图）。"""
    return get_book_results(book_id)["chapter_scores"]


def run_full_analysis(book_id: str, genre: str, model_id: Optional[str] = None) -> Dict[str, Any]:
    """一键「分析」：拆书 + 拆书报告 + 笔法报告串联。

    拆书阶段复用现有 ``start_analysis``（后台线程 + SSE）；报告阶段在拆书线程
    done 后由 ``_generate_reports`` 回调生成。返回 ``{task_id, cursor, status}``，
    与 ``/api/analyze/start`` 一致，前端沿用既有 SSE 进度订阅。
    """
    book = _get_book_or_raise(book_id)
    if not engine_adapter.any_model_configured():
        raise ServiceError("未配置外部模型，请先运行 model_config.py 配置", 400)

    # 复用现有 start_analysis（内部起后台线程）。
    result = start_analysis(book_id, genre, model_id)

    # 报告生成采用「拆书 done 后回调」：轮询状态，done 后触发报告生成。
    _schedule_report_generation(book_id, book)
    return result


def _schedule_report_generation(book_id: str, book: Dict[str, Any]) -> None:
    """拆书线程完成后回调生成两份报告（拆书报告 + 笔法分析，尽力而为）。

    用独立守护线程轮询拆书状态，done 后调用 ``_generate_reports``。不阻塞
    ``run_full_analysis`` 返回（前端已拿到 task_id 继续走 SSE）。
    """
    def _watch() -> None:
        deadline = time.time() + 24 * 3600  # 上限 24h，避免永久占用。
        while time.time() < deadline:
            st = state_store.load_state(book_id)
            if st.get("status") in ("done", "error"):
                if st.get("status") == "done":
                    try:
                        _generate_reports(book_id, book)
                    except Exception as exc:  # noqa: BLE001
                        st = state_store.load_state(book_id)
                        st["report_error"] = str(exc)[:500]
                        state_store.save_state(st)
                return
            time.sleep(1.0)

    threading.Thread(target=_watch, daemon=True, name=f"report-{book_id}").start()


def _generate_reports(book_id: str, book: Dict[str, Any]) -> None:
    """组装拆书报告 + 笔法报告，写 reports/{book_id}-*.md，并 invalidate 资产索引。

    尽力而为（DESIGN §8 D3）：craft-card 缺失时笔法报告留空并在结果提示，不阻断。
    """
    voice = _load_assembled_card(book_id, "voice")
    structure = _load_assembled_card(book_id, "structure")
    commercial = _load_assembled_card(book_id, "commercial")
    craft = _load_assembled_card(book_id, "craft")

    title = (voice.get("meta") or {}).get("source_title", book.get("title", book_id))
    reports_dir = config.REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 拆书报告（voice/structure/commercial 任一存在即尝试生成）。
    if voice or structure or commercial:
        md = engine_adapter.build_report(voice or {}, structure or {}, commercial or {},
                                         title_override=title)
        (reports_dir / f"{book_id}-拆书报告.md").write_text(md, encoding="utf-8")

    # 笔法报告（craft-card 缺失则留空提示，不阻断）。
    if craft:
        md = engine_adapter.render_craft_report(craft)
        (reports_dir / f"{book_id}-笔法分析.md").write_text(md, encoding="utf-8")

    # 刷新资产索引。
    asset_index.index.invalidate()

    # ---- 铁律二：合计 ≥10000 字符硬校验（与 CLI 共用同一实现）-------------------
    # 历史缺陷：GUI 此前直接生成并发布 report_ready，完全不做合计校验，
    # 铁律二在 GUI 路径被整条绕过（低于门槛的报告照样当合格品交付）。
    # 现在与 novel.py 共用 engine_adapter.check_report_min_length（单一来源）。
    chk = engine_adapter.check_report_min_length(reports_dir, book_id)
    if not chk.get("ok"):
        msg = (f"铁律二未通过：拆书报告 {chk['book_chars']} 字 + 笔法分析 "
               f"{chk['craft_chars']} 字 = 合计 {chk['total']} 字 < 硬门槛 "
               f"{chk['min_chars']} 字（不发布 report_ready）")
        st = state_store.load_state(book_id)
        st["report_error"] = msg
        state_store.save_state(st)
        broker.publish({
            "book_id": book_id,
            "status": "report_error",
            "chapter_index": 0,
            "batch_index": 0,
            "done": 0,
            "total": 0,
            "message": msg,
        })
        return

    # SSE 推送 report_ready 事件。
    broker.publish({
        "book_id": book_id,
        "status": "report_ready",
        "chapter_index": 0,
        "batch_index": 0,
        "done": 0,
        "total": 0,
        "report_ids": [f"report:{book_id}-拆书报告", f"report:{book_id}-笔法分析"],
        "report_chars": chk.get("total", 0),
    })
