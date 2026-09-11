"""M3 质检服务层：检查 / 全书质检 / qc(长任务) / 报告清单 / 章节目标解析。

分层边界：只经 ``engine_adapter`` 触碰 scripts/。
长任务并发上限 2（D6）；scratch 结束即删 + 启动自清理（D3）。
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from gui import config, engine_adapter
from gui.services import ServiceError

# ---------------------------------------------------------------------------
# 任务注册表
# ---------------------------------------------------------------------------
_QUALITY_TASKS: Dict[str, Dict[str, Any]] = {}
_QUALITY_LOCK = threading.Lock()

_ACTIVE_STATUSES = frozenset({"pending", "running"})
_MAX_CONCURRENT_QUALITY = 2
_MAX_TERMINAL_TASKS = 50


def _prune_terminal_tasks() -> None:
    """清理终态任务，防止注册表无限增长。"""
    with _QUALITY_LOCK:
        terminal = {k: v for k, v in _QUALITY_TASKS.items()
                    if v.get("status") not in _ACTIVE_STATUSES}
        if len(terminal) > _MAX_TERMINAL_TASKS:
            to_remove = sorted(terminal.keys())[:len(terminal) - _MAX_TERMINAL_TASKS]
            for k in to_remove:
                del _QUALITY_TASKS[k]


def _active_quality_count() -> int:
    with _QUALITY_LOCK:
        return sum(1 for t in _QUALITY_TASKS.values() if t.get("status") in _ACTIVE_STATUSES)


# ---------------------------------------------------------------------------
# 路径安全
# ---------------------------------------------------------------------------

def resolve_chapter_target(target: str, *, novel_dir: Optional[str] = None) -> Path:
    """把前端 target 解析为磁盘上真实存在的章节文件/目录（防路径穿越）。

    只允许解析到 NOVEL_DIR / CORPUS_DIR 之内；越界 → 400。
    """
    if not target:
        raise ServiceError("target 不能为空", 400)
    p = Path(target)
    if not p.is_absolute():
        # 相对路径：先试 NOVEL_DIR，再试 CORPUS_DIR
        for root in (config.NOVEL_DIR, config.CORPUS_DIR):
            candidate = root / target
            if candidate.exists():
                p = candidate
                break
        else:
            raise ServiceError(f"target 不存在: {target}", 404)

    resolved = p.resolve()
    allowed_roots = [config.NOVEL_DIR.resolve(), config.CORPUS_DIR.resolve()]
    if not any(resolved.is_relative_to(r) for r in allowed_roots):
        raise ServiceError("target 必须在 novel/ 或 corpus/ 目录内", 400)
    if not resolved.exists():
        raise ServiceError(f"target 不存在: {target}", 404)
    return resolved


def _materialize_text(text: str, task_id: str) -> Path:
    """把粘贴文本落到 scratch/<task_id>/ 子目录，避免跨任务污染。"""
    scratch_dir = config.STATE_ROOT / "scratch" / task_id
    scratch_dir.mkdir(parents=True, exist_ok=True)
    fp = scratch_dir / "input.txt"
    fp.write_text(text, encoding="utf-8")
    return fp


def clean_stale_scratch() -> int:
    """删除 STATE_ROOT/scratch/ 下全部残留任务目录/文件（进程启动时调用一次）。"""
    scratch_dir = config.STATE_ROOT / "scratch"
    if not scratch_dir.is_dir():
        return 0
    count = 0
    for item in scratch_dir.iterdir():
        try:
            if item.is_file():
                item.unlink()
                count += 1
            elif item.is_dir():
                for fp in item.iterdir():
                    fp.unlink()
                item.rmdir()
                count += 1
        except OSError:
            pass
    return count


# ---------------------------------------------------------------------------
# 同步能力
# ---------------------------------------------------------------------------

def _safe_asset_path(ref: str) -> Optional[Path]:
    """安全解析资产引用路径（防路径穿越）。"""
    name = ref.split(":")[-1]
    if not name or any(ch in name for ch in ("/", "\\", "..", "\x00", "\n", "\r")):
        return None
    fp = (config.ASSETS_ROOT / f"{name}.json").resolve()
    if not fp.is_relative_to(config.ASSETS_ROOT.resolve()):
        return None
    return fp if fp.is_file() else None


def check(target: Optional[str] = None, text: Optional[str] = None,
          voice: Optional[str] = None, genre_pack: Optional[str] = None) -> Dict[str, Any]:
    """单章双维度检查：质量 12 维 + 一致性 5 维。"""
    if not target and not text:
        raise ServiceError("需要 target 或 text", 400)
    if target:
        fp = resolve_chapter_target(target)
        if fp.is_dir():
            raise ServiceError("check 需要单章文件，不是目录", 400)
        try:
            text = fp.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            raise ServiceError(f"读取章节失败: {exc}", 400)

    gp_data = None
    if genre_pack:
        gp_fp = _safe_asset_path(genre_pack)
        if gp_fp:
            try:
                gp_data = json.loads(gp_fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

    qc = engine_adapter.chapter_check(text, gp_data)
    result: Dict[str, Any] = {"quality": qc}

    if voice:
        voice_fp = _safe_asset_path(voice)
        if voice_fp:
            try:
                voice_data = json.loads(voice_fp.read_text(encoding="utf-8"))
                cons = engine_adapter.score_text(voice_data, text, label=target or "粘贴文本")
                raw = cons.get("raw", {})
                result["consistency"] = {
                    "score": cons["score"],
                    "dims": {k: float(raw.get(k, 0)) for k in ("voice", "emotion", "narration", "banned", "imagery")},
                    "details": cons.get("details", []),
                }
            except (json.JSONDecodeError, OSError):
                pass

    return result


def book(target: Optional[str] = None, text: Optional[str] = None,
         voice: Optional[str] = None) -> Dict[str, Any]:
    """全书质检（重复/连贯/凑字数/乱编/AI味）。"""
    if not target and not text:
        raise ServiceError("需要 target 或 text", 400)

    chapter_dir: Optional[str] = None
    scratch_fp: Optional[Path] = None
    if target:
        fp = resolve_chapter_target(target)
        if fp.is_file():
            chapter_dir = str(fp.parent)
        else:
            chapter_dir = str(fp)
    elif text:
        task_id = f"tmp-{uuid.uuid4().hex[:8]}"
        scratch_fp = _materialize_text(text, task_id)
        # HIGH：传单文件路径而非父目录（book_quality_check 支持 is_file）
        chapter_dir = str(scratch_fp)

    voice_path = None
    if voice:
        vfp = config.ASSETS_ROOT / f"{voice.split(':')[-1]}.json"
        if vfp.is_file():
            voice_path = str(vfp)

    try:
        return engine_adapter.book_quality_check(chapter_dir, voice_card_path=voice_path)
    finally:
        # MEDIUM：book() 的 scratch 也要清理（D3）
        if scratch_fp and scratch_fp.is_file():
            try:
                scratch_fp.unlink()
                scratch_fp.parent.rmdir()
            except OSError:
                pass


def list_qc_reports() -> List[Dict[str, Any]]:
    """列出 reports/qc/ 下的历史报告。"""
    qc_dir = config.REPORTS_DIR / "qc"
    reports = []
    if qc_dir.is_dir():
        for fp in sorted(qc_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                reports.append({
                    "name": fp.stem,
                    "path": str(fp.relative_to(config.ROOT_DIR)),
                    "verdict": data.get("verdict", "?"),
                    "total_score": data.get("total_score"),
                    "created_at": data.get("meta", {}).get("created_at"),
                })
            except (json.JSONDecodeError, OSError):
                continue
    return reports


# ---------------------------------------------------------------------------
# W14 长任务：qc / qc_task_state
# ---------------------------------------------------------------------------

def qc(target: Optional[str] = None, text: Optional[str] = None,
       voice: Optional[str] = None, genre_pack: Optional[str] = None,
       asset: Optional[str] = None, book: Optional[str] = None,
       novel_dir: Optional[str] = None, llm_hook: bool = False) -> Dict[str, Any]:
    """启动 qc 长任务（四层十二维）。并发上限 2（D6）。"""
    task_id = f"q-{uuid.uuid4().hex[:12]}"

    # 解析章节目录
    if target:
        fp = resolve_chapter_target(target)
        chapter_dir = str(fp if fp.is_dir() else fp)
        display_target = target
    elif text:
        scratch_fp = _materialize_text(text, task_id)
        # HIGH：传子目录路径（scratch/<task_id>/），避免共享 scratch/ 污染
        chapter_dir = str(scratch_fp.parent)
        display_target = f"scratch/{task_id}"
    else:
        raise ServiceError("需要 target 或 text", 400)

    # 解析资产路径
    def _asset_path(ref: Optional[str]) -> Optional[str]:
        if not ref:
            return None
        name = ref.split(':')[-1]
        if not name or any(ch in name for ch in ("/", "\\", "..")):
            return None
        p = (config.ASSETS_ROOT / f"{name}.json").resolve()
        if not p.is_relative_to(config.ASSETS_ROOT.resolve()):
            return None
        return str(p) if p.is_file() else None

    voice_path = _asset_path(voice)
    gp_path = _asset_path(genre_pack)
    asset_path = _asset_path(asset)
    book_path = _asset_path(book)
    nd = str(resolve_chapter_target(novel_dir)) if novel_dir else None

    # MEDIUM：先清理终态任务
    _prune_terminal_tasks()

    # HIGH：并发上限检查 + 登记必须在同一临界区（TOCTOU 修复）
    with _QUALITY_LOCK:
        if _active_quality_count() >= _MAX_CONCURRENT_QUALITY:
            raise ServiceError(f"质检任务已达上限 {_MAX_CONCURRENT_QUALITY}，请等待当前任务完成", 429)
        _QUALITY_TASKS[task_id] = {
            "task_id": task_id, "status": "running", "phase": "qc",
            "target": display_target, "verdict": None, "total_score": None,
            "layers": [], "issues": [], "meta": {},
            "report_json": None, "report_md": None, "error": None,
        }

    thread = threading.Thread(
        target=_run_qc_task,
        args=(task_id, chapter_dir, voice_path, gp_path, asset_path, book_path, nd, llm_hook, display_target),
        daemon=True, name=f"qc-{task_id}")
    try:
        thread.start()
    except RuntimeError:
        # HIGH：start 失败必须释放并发槽位
        with _QUALITY_LOCK:
            _QUALITY_TASKS[task_id]["status"] = "error"
            _QUALITY_TASKS[task_id]["error"] = "线程启动失败"
        raise ServiceError("线程启动失败，请稍后重试", 500)
    return {"task_id": task_id, "status": "running", "target": display_target}


def qc_task_state(task_id: str) -> Dict[str, Any]:
    """查询 qc 任务状态。"""
    import copy
    with _QUALITY_LOCK:
        t = _QUALITY_TASKS.get(task_id)
        if not t:
            raise ServiceError(f"任务不存在: {task_id}", 404)
        return copy.deepcopy(t)


def _run_qc_task(task_id: str, chapter_dir: str, voice_path: Optional[str],
                 gp_path: Optional[str], asset_path: Optional[str],
                 book_path: Optional[str], novel_dir: Optional[str],
                 llm_hook: bool, display_target: str) -> None:
    """后台线程：跑 qc 并落盘报告。"""
    from gui import sse

    try:
        sse.broker.publish({"task_type": "quality", "task_id": task_id, "phase": "running"})

        result = engine_adapter.run_qc(
            chapter_dir, voice_card_path=voice_path, genre_pack_path=gp_path,
            asset_path=asset_path, book_path=book_path, novel_dir=novel_dir,
            enable_llm_hook=llm_hook)

        report = result.get("report", {})
        markdown = result.get("markdown", "")

        # 落盘报告
        qc_dir = config.REPORTS_DIR / "qc"
        qc_dir.mkdir(parents=True, exist_ok=True)
        safe_name = display_target.replace("/", "_").replace("\\", "_").replace("..", "")[:60]
        # MEDIUM：文件名加 task_id 防止并发同名覆盖
        json_fp = qc_dir / f"{safe_name}-{task_id}-qc.json"
        md_fp = qc_dir / f"{safe_name}-{task_id}-qc.md"
        json_fp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        md_fp.write_text(markdown, encoding="utf-8")

        with _QUALITY_LOCK:
            _QUALITY_TASKS[task_id].update({
                "status": "done",
                "verdict": report.get("verdict", "?"),
                "total_score": report.get("total_score"),
                "layers": report.get("layers", []),
                "issues": report.get("issues", [])[:50],
                "meta": report.get("meta", {}),
                "report_json": str(json_fp.relative_to(config.ROOT_DIR)),
                "report_md": str(md_fp.relative_to(config.ROOT_DIR)),
            })

        sse.broker.publish({
            "task_type": "quality", "task_id": task_id, "phase": "done",
            "verdict": report.get("verdict"), "total_score": report.get("total_score"),
        })

    except Exception as exc:  # noqa: BLE001
        with _QUALITY_LOCK:
            _QUALITY_TASKS[task_id]["status"] = "error"
            _QUALITY_TASKS[task_id]["error"] = str(exc)
        sse.broker.publish({
            "task_type": "quality", "task_id": task_id, "phase": "error", "error": str(exc),
        })

    finally:
        # D3：任务结束即删 scratch 子目录
        task_scratch = config.STATE_ROOT / "scratch" / task_id
        if task_scratch.is_dir():
            for fp in task_scratch.iterdir():
                try:
                    fp.unlink()
                except OSError:
                    pass
            try:
                task_scratch.rmdir()
            except OSError:
                pass
