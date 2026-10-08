"""M3 质检服务层：检查 / 全书质检 / qc(长任务) / 报告清单 / 章节目标解析。

分层边界：只经 ``engine_adapter`` 触碰 scripts/。
长任务并发上限 2（D6）；scratch 结束即删 + 启动自清理（D3）。
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from gui import config, engine_adapter
from gui.logging_setup import get_logger
from gui.services import ServiceError, assert_asset_kind

_log = get_logger("quality_service")

# ---------------------------------------------------------------------------
# 任务注册表
# ---------------------------------------------------------------------------
_QUALITY_TASKS: dict[str, dict[str, Any]] = {}
# RLock：qc() 提交路径在外层持锁后还会调 _active_quality_count()（同样拿锁），
# 非重入 Lock 会自死锁（GUI 质检台 QC 按钮曾因此完全不可用）。
_QUALITY_LOCK = threading.RLock()

_ACTIVE_STATUSES = frozenset({"pending", "running"})
_MAX_CONCURRENT_QUALITY = 2
_MAX_TERMINAL_TASKS = 50


def _safe_report_rel(path: Path) -> str:
    """报告路径转相对路径（相对 REPORTS_DIR）。P0 修复：用户数据目录
    （%LOCALAPPDATA%/暮冬念春 等）永不在 ROOT_DIR 下，旧代码
    path.relative_to(config.ROOT_DIR) 在生产环境必抛 ValueError，
    导致每个 QC 任务在落盘后崩溃、报告列表接口 500。"""
    try:
        return str(path.relative_to(config.REPORTS_DIR))
    except ValueError:
        return str(path)


def _prune_terminal_tasks() -> None:
    """清理终态任务，防止注册表无限增长。"""
    with _QUALITY_LOCK:
        terminal = {k: v for k, v in _QUALITY_TASKS.items()
                    if v.get("status") not in _ACTIVE_STATUSES}
        if len(terminal) > _MAX_TERMINAL_TASKS:
            # 按创建时间删除最旧的（task_id 是 uuid4 hex，无时间成分，不能按它排序）。
            to_remove = sorted(terminal.keys(),
                               key=lambda k: terminal[k].get("created_at", 0)
                               )[:len(terminal) - _MAX_TERMINAL_TASKS]
            for k in to_remove:
                del _QUALITY_TASKS[k]


_EXTERNAL_SCRATCH_PREFIX = "qc-external-"
# 外部路径隔离复制的三道上限：单个文件、单目录内的章节文件数、累计字节。
# 目录可以无限大（用户语料盘动辄几十 GB），而 scratch 落在用户数据目录里，
# 不设限就等于让一次质检把自己磁盘写满。
_EXTERNAL_MAX_FILE_BYTES = 50 * 1024 * 1024
_EXTERNAL_MAX_FILES = 2000
_EXTERNAL_MAX_BYTES = 200 * 1024 * 1024
#: 外部目录允许遍历的子目录数上限（防 target 填错成整盘/系统目录）。
_EXTERNAL_MAX_DIRS = 2000


def _external_scratch_task_dir(p: Path) -> Path | None:
    """p 若位于 ``scratch/qc-external-*/`` 隔离副本内，返回那个任务目录；否则 None。"""
    scratch_root = config.STATE_ROOT / "scratch"
    try:
        rel = p.relative_to(scratch_root)
    except ValueError:
        return None
    if not rel.parts or not rel.parts[0].startswith(_EXTERNAL_SCRATCH_PREFIX):
        return None
    return scratch_root / rel.parts[0]


def _is_external_scratch_copy(p: Path) -> bool:
    """判断是否为 resolve_chapter_target 产生的外部隔离副本（文件/目录副本都算）。

    目录副本会嵌套（``<id>/<书名>/子目录/章.txt``），所以按"是否在 qc-external-* 之下"
    判定，不能只看直接父目录名——否则副本认不出来，scratch 永久泄漏。
    """
    d = p if p.is_dir() else p.parent
    return _external_scratch_task_dir(d) is not None


def _cleanup_external_copy(p: Path | str | None) -> None:
    """删除整个外部隔离任务目录。

    P1-5 修复：旧实现只在启动时清 scratch，桌面端常驻会话中多次外部文件
    质检（单文件上限 50MB）可累积至 GB 级磁盘占用，会话内无回收。
    """
    if not p:
        return
    import shutil
    d = Path(p)
    task_dir = _external_scratch_task_dir(d if d.is_dir() else d.parent)
    if task_dir is None:
        return
    shutil.rmtree(task_dir, ignore_errors=True)


def _active_quality_count() -> int:
    with _QUALITY_LOCK:
        return sum(1 for t in _QUALITY_TASKS.values() if t.get("status") in _ACTIVE_STATUSES)


# ---------------------------------------------------------------------------
# 路径安全
# ---------------------------------------------------------------------------

def resolve_chapter_target(target: str, *, novel_dir: str | None = None) -> Path:
    """把前端 target 解析为磁盘上真实存在的章节文件/目录（防路径穿越）。

    - 相对路径：在 NOVEL_DIR / CORPUS_DIR 内查找。
    - 绝对路径在 novel/corpus 内：就地使用，不复制。
    - 绝对路径在 novel/corpus 外：**复制进 scratch 隔离目录**后使用，单文件和整个
      目录都支持（桌面端用户的书稿常在任意位置；复制隔离防 TOCTOU，用完由
      ``_cleanup_external_copy`` 回收）。目录只按章节加载器规则复制 ``*.txt``，
      并受 50MB/单章、2000 文件、200MB 累计三道上限约束。
    """
    import shutil
    import uuid
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
    if any(resolved.is_relative_to(r) for r in allowed_roots):
        if not resolved.exists():
            raise ServiceError(f"target 不存在: {target}", 404)
        return resolved

    # 绝对路径但不在 novel/corpus 内：复制到 scratch 隔离目录后使用
    if not resolved.exists():
        raise ServiceError(f"target 不存在: {target}", 404)
    scratch_dir = config.STATE_ROOT / "scratch" / f"qc-external-{uuid.uuid4().hex[:8]}"
    if resolved.is_file():
        if resolved.stat().st_size > _EXTERNAL_MAX_FILE_BYTES:
            raise ServiceError("文件超过 50MB 上限", 400)
        scratch_dir.mkdir(parents=True, exist_ok=True)
        dest = scratch_dir / resolved.name
        shutil.copy2(resolved, dest)
        return dest
    if resolved.is_dir():
        return _copy_external_chapter_dir(resolved, scratch_dir)
    raise ServiceError("target 既不是文件也不是目录", 400)


def _copy_external_chapter_dir(root: Path, scratch_dir: Path) -> Path:
    """把外部的章节目录按**章节加载器的规则**复制进隔离目录，返回副本根目录。

    为什么要复制而不是就地读：scratch 是稳定快照，避免"质检跑一半用户改文件"的
    TOCTOU，也让副本可被 `_cleanup_external_copy` 精确回收。
    只复制加载器真正会读的 ``*.txt``，并跳过它同样跳过的排除目录，因此质检结果
    与就地读等价；非 ``.txt``（设定笔记、图片、备份）本就不进质检，不复制。

    信任边界没有扩大：旧实现早已允许任意本机绝对路径的单文件进质检，这里只是把
    同一能力对齐到"整本书在一个目录里、且不在 novel/corpus 下"的真实场景。
    """
    import fnmatch
    import os
    import shutil

    pattern, excluded = engine_adapter.chapter_scan_rules()
    dest_root = scratch_dir / root.name
    copied = 0
    total_bytes = 0
    skipped_links = 0

    def _abort(msg: str) -> None:
        """超限/出错时把已经复制了一半的 scratch 副本删掉，别留垃圾。"""
        shutil.rmtree(scratch_dir, ignore_errors=True)
        raise ServiceError(msg, 400)

    walked_dirs = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        walked_dirs += 1
        if walked_dirs > _EXTERNAL_MAX_DIRS:
            # target 被填成 C:\Windows 或整个用户目录时，光走盘就要几十分钟，
            # 还会在深层子目录上撞 MAX_PATH。书稿目录不会有几千个子目录。
            _abort(f"目录子项过多（超过 {_EXTERNAL_MAX_DIRS} 个目录），"
                   f"请把 target 指向书稿目录而不是整个磁盘：{root}")
        rel_dir = Path(dirpath).relative_to(root)
        if any(part.casefold() in excluded for part in rel_dir.parts):
            dirnames[:] = []
            continue
        # 不进入符号链接目录（followlinks=False 已保证），顺手剪掉，避免绕出 root。
        dirnames[:] = [d for d in dirnames if not (Path(dirpath) / d).is_symlink()]
        for name in sorted(filenames):
            if not fnmatch.fnmatch(name, pattern):
                continue
            src = Path(dirpath) / name
            if src.is_symlink():
                skipped_links += 1
                continue
            rel = src.relative_to(root)
            try:
                size = src.stat().st_size
            except OSError as exc:
                _abort(f"读取章节失败: {rel}（{exc}）")
            if size > _EXTERNAL_MAX_FILE_BYTES:
                _abort(f"单章文件超过 50MB 上限：{rel}")
            if copied + 1 > _EXTERNAL_MAX_FILES or total_bytes + size > _EXTERNAL_MAX_BYTES:
                _abort(
                    f"外部目录超出上限（最多 {_EXTERNAL_MAX_FILES} 个章节文件、"
                    f"{_EXTERNAL_MAX_BYTES // 1048576}MB）：{root}")
            dest = dest_root / rel
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
            except OSError as exc:
                # 深层路径撞 MAX_PATH / 目标盘满 / 源文件被占用：都得变成
                # 400 并清掉半份副本，而不是 FileNotFoundError 冒到路由层变 500。
                _abort(f"复制章节失败: {rel}（{exc}）")
            copied += 1
            total_bytes += size

    if copied == 0:
        raise ServiceError(
            f"目录里没有可质检的章节文件（{pattern}）：{root}；"
            "确认章节是 .txt，且不在备份/build 这类被排除的子目录里", 400)
    _log.info(f"外部目录已隔离复制 {root} → {dest_root}（{copied} 章，{total_bytes} 字节）")
    return dest_root


def _materialize_text(text: str, task_id: str) -> Path:
    """把粘贴文本落到 scratch/<task_id>/ 子目录，避免跨任务污染。"""
    scratch_dir = config.STATE_ROOT / "scratch" / task_id
    scratch_dir.mkdir(parents=True, exist_ok=True)
    fp = scratch_dir / "input.txt"
    fp.write_text(text, encoding="utf-8")
    return fp


def clean_stale_scratch() -> int:
    """删除 STATE_ROOT/scratch/ 下全部残留任务目录/文件（进程启动时调用一次）。

    P2-9 修复：旧实现只清一层嵌套，二级以上残留会导致 rmdir 失败被吞掉而永久残留。
    """
    import shutil
    scratch_dir = config.STATE_ROOT / "scratch"
    if not scratch_dir.is_dir():
        return 0
    count = 0
    for item in scratch_dir.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
                count += 1
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                count += 1
        except OSError:
            pass
    return count


# ---------------------------------------------------------------------------
# 同步能力
# ---------------------------------------------------------------------------

def _safe_asset_path(ref: str) -> Path | None:
    """安全解析资产引用路径（防路径穿越）。"""
    name = ref.split(":")[-1]
    if not name or any(ch in name for ch in ("/", "\\", "..", "\x00", "\n", "\r")):
        return None
    fp = (config.ASSETS_ROOT / f"{name}.json").resolve()
    if not fp.is_relative_to(config.ASSETS_ROOT.resolve()):
        return None
    return fp if fp.is_file() else None


def _checked_asset_path(ref: str, expected: str) -> Path | None:
    """解析资产引用 → 读取 JSON → 内容契约校验，返回可用路径。

    - 引用非法 / 文件不存在 / JSON 损坏：返回 None（沿用调用方「跳过该资产」语义）；
    - 内容自证为其它 kind（distilled 当 voice、index 当 prose_card）：抛 ServiceError(400)。

    识别逻辑统一在 ``services.assert_asset_kind``，此处不重复实现。
    """
    fp = _safe_asset_path(ref)
    if fp is None:
        return None
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning(f"资产加载失败，跳过该资产 {fp.name}: {exc}")
        return None
    assert_asset_kind(data, expected, ref)
    return fp


def check(target: str | None = None, text: str | None = None,
          voice: str | None = None, genre_pack: str | None = None) -> dict[str, Any]:
    """单章双维度检查：质量 12 维 + 一致性 5 维。"""
    if not target and not text:
        raise ServiceError("需要 target 或 text", 400)
    if text is not None and not isinstance(text, str):
        # 再往下第一句就要遍历 text；请求体里塞个数字会变成 500，
        # 用户只看到"内部错误"，不知道是 text 这个参数错了。
        raise ServiceError("text 必须为字符串", 400)
    if target:
        fp = resolve_chapter_target(target)
        if fp.is_dir():
            raise ServiceError("check 需要单章文件，不是目录", 400)
        # P2-8：corpus/novel 内文件此前无大小限制，大文件会 read_text 到 MemoryError。
        # 与外部文件分支统一 50MB 上限。
        try:
            if fp.stat().st_size > 50 * 1024 * 1024:
                raise ServiceError("文件超过 50MB 上限", 400)
        except OSError as exc:
            raise ServiceError(f"读取章节失败: {exc}", 400) from exc
        try:
            # 走引擎侧的统一解码（UTF-8 → GBK）：只认 UTF-8 会把大量真稿判成"读不了"
            text = engine_adapter.read_chapter_text(fp)
        except (UnicodeError, OSError) as exc:
            raise ServiceError(f"读取章节失败: {exc}", 400) from exc
        finally:
            _cleanup_external_copy(fp)  # P1-5：外部隔离副本用后即删

    gp_data = None
    if genre_pack:
        gp_fp = _safe_asset_path(genre_pack)
        if gp_fp:
            try:
                gp_data = json.loads(gp_fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                _log.warning(f"题材包加载失败，本次检查不带题材约束 {gp_fp.name}: {exc}")

    qc = engine_adapter.chapter_check(text, gp_data)
    result: dict[str, Any] = {"quality": qc}

    if voice:
        voice_fp = _safe_asset_path(voice)
        if voice_fp:
            try:
                voice_data = json.loads(voice_fp.read_text(encoding="utf-8"))
                # 内容契约：voice 参数只接受 voice 卡（distilled/index 在此同步 400）。
                assert_asset_kind(voice_data, "voice", voice)
                cons = engine_adapter.score_text(voice_data, text, label=target or "粘贴文本")
                raw = cons.get("raw", {})
                result["consistency"] = {
                    "score": cons["score"],
                    "dims": {k: float(raw.get(k, 0)) for k in ("voice", "emotion", "narration", "banned", "imagery")},
                    "details": cons.get("details", []),
                }
            except (json.JSONDecodeError, OSError) as exc:
                _log.warning(f"voice-card 加载失败，跳过一致性打分 {voice_fp.name}: {exc}")

    return result


def book(target: str | None = None, text: str | None = None,
         voice: str | None = None) -> dict[str, Any]:
    """全书质检（重复/连贯/凑字数/乱编/AI味）。"""
    if not target and not text:
        raise ServiceError("需要 target 或 text", 400)
    if text is not None and not isinstance(text, str):
        # 再往下第一句就要遍历 text；请求体里塞个数字会变成 500，
        # 用户只看到"内部错误"，不知道是 text 这个参数错了。
        raise ServiceError("text 必须为字符串", 400)

    # 资产内容契约：voice 只接受 voice 卡。校验必须在 _materialize_text 建 scratch
    # **之前**完成——否则校验抛 400 时清理用的 try/finally 尚未进入，每次调用都会
    # 泄漏一个 scratch 目录（与 qc() 的前置校验对齐）。
    voice_path = None
    if voice:
        vfp = _checked_asset_path(voice, "voice")
        if vfp:
            voice_path = str(vfp)

    chapter_dir: str | None = None
    scratch_fp: Path | None = None
    external_fp: Path | None = None
    if target:
        fp = resolve_chapter_target(target)
        if _is_external_scratch_copy(fp):
            external_fp = fp
        if fp.is_file():
            chapter_dir = str(fp.parent)
        else:
            chapter_dir = str(fp)
    elif text:
        task_id = f"tmp-{uuid.uuid4().hex[:8]}"
        scratch_fp = _materialize_text(text, task_id)
        # HIGH：传单文件路径而非父目录（book_quality_check 支持 is_file）
        chapter_dir = str(scratch_fp)

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
        _cleanup_external_copy(external_fp)  # P1-5：外部隔离副本用后即删


def list_qc_reports() -> list[dict[str, Any]]:
    """列出 reports/qc/ 下的历史报告。"""
    qc_dir = config.REPORTS_DIR / "qc"
    reports = []
    if qc_dir.is_dir():
        for fp in sorted(qc_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                reports.append({
                    "name": fp.stem,
                    "path": _safe_report_rel(fp),
                    "verdict": data.get("verdict", "?"),
                    "total_score": data.get("total_score"),
                    "created_at": data.get("meta", {}).get("created_at"),
                })
            except (json.JSONDecodeError, OSError) as exc:
                _log.warning(f"跳过无法解析的质检报告 {fp.name}: {exc}")
                continue
    return reports


# ---------------------------------------------------------------------------
# W14 长任务：qc / qc_task_state
# ---------------------------------------------------------------------------

def qc(target: str | None = None, text: str | None = None,
       voice: str | None = None, genre_pack: str | None = None,
       asset: str | None = None, book: str | None = None,
       novel_dir: str | None = None, llm_hook: bool = False) -> dict[str, Any]:
    """启动 qc 长任务（四层十二维）。并发上限 2（D6）。"""
    task_id = f"q-{uuid.uuid4().hex[:12]}"

    # 资产内容契约：voice 只接受 voice 卡。校验必须在建 scratch / 登记任务 / 启动后台
    # 线程**之前**完成——否则错误会被吞进任务注册表，前端只能轮询到 error，而非同步 400。
    voice_path = None
    if voice:
        vfp = _checked_asset_path(voice, "voice")
        if vfp:
            voice_path = str(vfp)

    # 解析章节目录
    external_copy: str | None = None
    if target:
        fp = resolve_chapter_target(target)
        if _is_external_scratch_copy(fp):
            external_copy = str(fp)
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
    def _asset_path(ref: str | None) -> str | None:
        if not ref:
            return None
        name = ref.split(':')[-1]
        if not name or any(ch in name for ch in ("/", "\\", "..", "\x00", "\n", "\r")):
            return None
        p = (config.ASSETS_ROOT / f"{name}.json").resolve()
        if not p.is_relative_to(config.ASSETS_ROOT.resolve()):
            return None
        return str(p) if p.is_file() else None

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
            "created_at": time.time(),
            "target": display_target, "verdict": None, "total_score": None,
            "layers": [], "issues": [], "meta": {},
            "report_json": None, "report_md": None, "error": None,
        }

    thread = threading.Thread(
        target=_run_qc_task,
        args=(task_id, chapter_dir, voice_path, gp_path, asset_path, book_path, nd, llm_hook, display_target, external_copy),
        daemon=True, name=f"qc-{task_id}")
    try:
        thread.start()
    except RuntimeError as exc:
        # HIGH：start 失败必须释放并发槽位
        with _QUALITY_LOCK:
            _QUALITY_TASKS[task_id]["status"] = "error"
            _QUALITY_TASKS[task_id]["error"] = "线程启动失败"
        raise ServiceError("线程启动失败，请稍后重试", 500) from exc
    return {"task_id": task_id, "status": "running", "target": display_target}


def qc_task_state(task_id: str) -> dict[str, Any]:
    """查询 qc 任务状态。"""
    import copy
    with _QUALITY_LOCK:
        t = _QUALITY_TASKS.get(task_id)
        if not t:
            raise ServiceError(f"任务不存在: {task_id}", 404)
        return copy.deepcopy(t)


def _run_qc_task(task_id: str, chapter_dir: str, voice_path: str | None,
                 gp_path: str | None, asset_path: str | None,
                 book_path: str | None, novel_dir: str | None,
                 llm_hook: bool, display_target: str,
                 external_copy: str | None = None) -> None:
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
                "report_json": _safe_report_rel(json_fp),
                "report_md": _safe_report_rel(md_fp),
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
        # D3：任务结束即删 scratch 子目录。必须整棵删——逐层 unlink 只能清一层，
        # 带子目录的副本会让 rmdir 失败并被吞掉，形成永久残留（同 P2-9 的教训）。
        import shutil
        task_scratch = config.STATE_ROOT / "scratch" / task_id
        if task_scratch.is_dir():
            shutil.rmtree(task_scratch, ignore_errors=True)
        _cleanup_external_copy(external_copy)  # P1-5：外部隔离副本用后即删
