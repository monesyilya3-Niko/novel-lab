"""M2 写作服务层：注入 / 写作(长任务) / 打分 / 组装 / 手动入库 / 项目列举。

分层边界：只经 ``engine_adapter`` 触碰 scripts/，不直接 import 任何脚本。
长任务并发上限 2（D6）；写入路径唯一为 NOVEL_DIR/<project>（D1）。
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from gui import config, engine_adapter, migrate
from gui.logging_setup import get_logger
from gui.services import ServiceError, assert_asset_kind

_log = get_logger("writing_service")

# ---------------------------------------------------------------------------
# 任务注册表（进程内，不落库）
# ---------------------------------------------------------------------------
_WRITING_TASKS: Dict[str, Dict[str, Any]] = {}
_WRITING_LOCK = threading.Lock()

_ACTIVE_STATUSES = frozenset({"pending", "running", "scoring", "rewriting"})
_MAX_CONCURRENT_WRITING = 2
_MAX_TERMINAL_TASKS = 50  # 终态任务最多保留 N 个


def _prune_terminal_tasks() -> None:
    """清理终态任务，防止注册表无限增长。"""
    with _WRITING_LOCK:
        terminal = {k: v for k, v in _WRITING_TASKS.items()
                    if v.get("status") not in _ACTIVE_STATUSES}
        if len(terminal) > _MAX_TERMINAL_TASKS:
            # 按 task_id 排序（含时间戳），删除最旧的
            to_remove = sorted(terminal.keys())[:len(terminal) - _MAX_TERMINAL_TASKS]
            for k in to_remove:
                del _WRITING_TASKS[k]


def _active_writing_count() -> int:
    with _WRITING_LOCK:
        return sum(1 for t in _WRITING_TASKS.values() if t.get("status") in _ACTIVE_STATUSES)


def _sanitize_project(project: str) -> str:
    """校验项目名：非空、无 / \\ .. 与控制字符；非法 → ServiceError(400)。"""
    if not project or not project.strip():
        raise ServiceError("project 不能为空", 400)
    p = project.strip()
    if any(ch in p for ch in ("/", "\\", "..", "\x00", "\n", "\r")):
        raise ServiceError(f"非法项目名: {project!r}", 400)
    if p == "default":
        raise ServiceError("default 为 CLI 只读项目，请在 GUI 新建项目", 400)
    return p


def _load_asset_json(ref: str) -> Dict[str, Any]:
    """把 '<kind>:<id>' 资产引用解析为 JSON dict。CRITICAL：防路径穿越。"""
    if not ref or ":" not in ref:
        raise ServiceError(f"非法资产引用: {ref!r}", 400)
    kind, _, asset_id = ref.partition(":")
    name = asset_id[len(f"{kind}:"):] if asset_id.startswith(f"{kind}:") else asset_id
    # CRITICAL：拒绝路径穿越字符
    if not name or any(ch in name for ch in ("/", "\\", "..", "\x00", "\n", "\r")):
        raise ServiceError(f"非法资产引用: {ref!r}", 400)
    fp = (config.ASSETS_ROOT / f"{name}.json").resolve()
    # CRITICAL：resolve 后必须仍在 ASSETS_ROOT 内
    if not fp.is_relative_to(config.ASSETS_ROOT.resolve()):
        raise ServiceError(f"非法资产引用: {ref!r}", 400)
    if not fp.is_file():
        raise ServiceError(f"资产不存在: {ref}", 404)
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ServiceError(f"资产文件损坏: {exc}", 500)


def _load_asset_of_kind(ref: str, expected: str) -> Dict[str, Any]:
    """加载资产引用并按**内容契约**校验 kind。

    文件名不保证与内容一致（蒸馏卡历史上落成 ``*-voice-card-distilled.json``），
    因此 distilled 当 voice、index 当 prose_card 等错配必须在此同步拒绝（400），
    而不是把错误资产塞进 prompt。识别逻辑统一在 ``services.assert_asset_kind``。
    """
    data = _load_asset_json(ref)
    assert_asset_kind(data, expected, ref)
    return data


# ---------------------------------------------------------------------------
# 同步能力
# ---------------------------------------------------------------------------

def list_projects() -> List[Dict[str, Any]]:
    """枚举 NOVEL_DIR 下项目；裸 NOVEL_DIR 作为只读项目 default 追加（D1）。"""
    projects: List[Dict[str, Any]] = []
    nd = config.NOVEL_DIR
    if nd.is_dir():
        for child in sorted(nd.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                state_file = child / "state.json"
                name = child.name
                if state_file.is_file():
                    try:
                        name = json.loads(state_file.read_text(encoding="utf-8")).get("name", child.name)
                    except (json.JSONDecodeError, OSError):
                        pass
                projects.append({"id": child.name, "name": name, "read_only": False})
    # 裸 novel/ 作为只读 default 项目
    if nd.is_dir():
        projects.append({"id": "default", "name": "default（CLI 只读）", "read_only": True})
    return projects


def inject(voice: str, structure: Optional[str] = None, commercial: Optional[str] = None,
           genre_pack: Optional[str] = None, craft: Optional[str] = None,
           distilled: Optional[str] = None, prose_card: Optional[str] = None,
           context_intent: Optional[str] = None, tracking_state: Optional[str] = None,
           save: bool = False) -> Dict[str, Any]:
    """资产 → 写作 system prompt。

    每个资产参数只接受对应 kind 的内容：distilled 必须走 ``distilled`` 参数
    （不得塞进 voice/structure/commercial/craft），``prose_card`` 必须是文风卡本身
    而非题材索引；错配由 ``_load_asset_of_kind`` 同步拒绝为 400。
    """
    voice_data = _load_asset_of_kind(voice, "voice")
    prompt = engine_adapter.build_writing_prompt(
        voice_data,
        structure=_load_asset_of_kind(structure, "structure") if structure else None,
        commercial=_load_asset_of_kind(commercial, "commercial") if commercial else None,
        genre_pack=_load_asset_json(genre_pack) if genre_pack else None,
        craft_card=_load_asset_of_kind(craft, "craft") if craft else None,
        distilled=_load_asset_of_kind(distilled, "distilled") if distilled else None,
        context_intent=context_intent,
        tracking_state=_load_asset_json(tracking_state) if tracking_state else None,
        genre_prose_card=_load_asset_of_kind(prose_card, "prose_card") if prose_card else None,
    )
    injected_kinds = ["voice"]
    if structure:
        injected_kinds.append("structure")
    if commercial:
        injected_kinds.append("commercial")
    if genre_pack:
        injected_kinds.append("genre_pack")
    if craft:
        injected_kinds.append("craft")
    if distilled:
        injected_kinds.append("distilled")
    if prose_card:
        injected_kinds.append("prose_card")

    saved_path = None
    if save:
        config.PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        title = voice_data.get("meta", {}).get("title", "writing")
        safe = re.sub(r'[^\w\-]', '_', title)[:60]
        fp = config.PROMPTS_DIR / f"{safe}-writing-prompt.md"
        fp.write_text(prompt, encoding="utf-8")
        saved_path = str(fp.relative_to(config.ROOT_DIR))

    return {
        "prompt": prompt,
        "char_count": len(prompt),
        "injected_kinds": injected_kinds,
        "meta": {
            "source_title": voice_data.get("meta", {}).get("title", ""),
            "genre": voice_data.get("meta", {}).get("genre", ""),
            "saved_path": saved_path,
        },
    }


def score(voice: str, text: Optional[str] = None, chapter_path: Optional[str] = None,
          label: str = "", genre_pack: Optional[str] = None) -> Dict[str, Any]:
    """双维度打分：一致性五维 + 章节质量十二维。"""
    if not text and not chapter_path:
        raise ServiceError("需要 text 或 chapter_path", 400)
    if chapter_path:
        # HIGH：路径必须在 NOVEL_DIR 内
        fp = Path(chapter_path).resolve()
        if not fp.is_relative_to(config.NOVEL_DIR.resolve()):
            raise ServiceError("chapter_path 必须在 novel/ 目录内", 400)
        if not fp.is_file():
            raise ServiceError(f"章节文件不存在: {chapter_path}", 404)
        try:
            text = fp.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            raise ServiceError(f"读取章节失败: {exc}", 400)

    voice_data = _load_asset_of_kind(voice, "voice")
    cons = engine_adapter.score_text(voice_data, text, label=label)
    raw = cons.get("raw", {})
    dims = {
        "voice": float(raw.get("voice", 0)),
        "emotion": float(raw.get("emotion", 0)),
        "narration": float(raw.get("narration", 0)),
        "banned": float(raw.get("banned", 0)),
        "imagery": float(raw.get("imagery", 0)),
    }
    radar = {
        "indicators": [
            {"name": "声线", "max": 35}, {"name": "情绪", "max": 20},
            {"name": "叙述", "max": 15}, {"name": "禁忌", "max": 20},
            {"name": "意象", "max": 10},
        ],
        "series": [{"name": label or "章节", "value": [dims["voice"], dims["emotion"], dims["narration"], dims["banned"], dims["imagery"]]}],
    }

    genre_pack_data = _load_asset_json(genre_pack) if genre_pack else None
    qc = engine_adapter.chapter_check(text, genre_pack_data)
    pass_line, _ = engine_adapter.resolve_thresholds(genre_pack_data)

    cons_score = cons["score"]
    quality_score = qc.get("score", 0)
    verdict = qc.get("verdict", "FAIL")
    if cons_score < 60:
        verdict = "FAIL"

    return {
        "consistency": {"score": cons_score, "dims": dims, "details": cons.get("details", []), "radar": radar},
        "quality": qc,
        "verdict": verdict,
        "pass_line": pass_line,
    }


def assemble(name: str, genre: str, skip_craft: bool = False) -> Dict[str, Any]:
    """组装 pass1-5 → 4 类资产入库。genre 必填（D7）。"""
    if not genre or not genre.strip():
        raise ServiceError("genre 不能为空（铁律一：题材隔离）", 400)
    genre = genre.strip()
    # HIGH：name 用于拼路径，必须消毒
    if not name or any(ch in name for ch in ("/", "\\", "..", "\x00", "\n", "\r")):
        raise ServiceError(f"非法书名: {name!r}", 400)
    raw_dir = (config.CORPUS_DIR / "raw" / name).resolve()
    if not raw_dir.is_relative_to(config.CORPUS_DIR.resolve()):
        raise ServiceError(f"非法书名: {name!r}", 400)
    if not raw_dir.is_dir():
        raise ServiceError(f"pass 输出目录不存在: {raw_dir}", 404)

    def _load_pass(fname: str) -> Optional[Dict[str, Any]]:
        fp = raw_dir / fname
        if not fp.is_file():
            return None
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    pass1 = _load_pass("pass1_structure.json")
    pass2 = _load_pass("pass2_character.json")
    pass3 = _load_pass("pass3_style.json")
    pass4 = _load_pass("pass4_commercial.json")
    pass5 = _load_pass("pass5_craft.json")

    if not pass1:
        raise ServiceError("pass1_structure.json 缺失或损坏", 400)

    metrics_fp = config.CORPUS_DIR / "metrics" / f"{name}.json"
    metrics = {}
    if metrics_fp.is_file():
        try:
            metrics = json.loads(metrics_fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning(f"量化指标加载失败，注入提示将不含统计画像 {metrics_fp.name}: {exc}")

    written: List[str] = []

    # voice-card
    if pass2 and pass3:
        voices = engine_adapter.normalize_pass2(pass2)
        narration, dialogue, emotion, imagery, banned = engine_adapter.normalize_pass3(pass3)
        vc = engine_adapter.assemble_asset_voice_card(
            name, genre, {"title": name}, metrics, voices,
            narration, dialogue, emotion, imagery, banned)
        vc_fp = config.ASSETS_ROOT / f"{name}-voice-card.json"
        vc_fp.write_text(json.dumps(vc, ensure_ascii=False, indent=2), encoding="utf-8")
        migrate.sync_asset(vc_fp)
        written.append(str(vc_fp.name))

    # structure-obs
    if pass1:
        so = engine_adapter.assemble_asset_obs("structure", name, genre, pass1)
        so_fp = config.ASSETS_ROOT / f"{name}-structure-obs.json"
        so_fp.write_text(json.dumps(so, ensure_ascii=False, indent=2), encoding="utf-8")
        migrate.sync_asset(so_fp)
        written.append(str(so_fp.name))

    # commercial-obs
    if pass4:
        co = engine_adapter.assemble_asset_obs("commercial", name, genre, pass4)
        co_fp = config.ASSETS_ROOT / f"{name}-commercial-obs.json"
        co_fp.write_text(json.dumps(co, ensure_ascii=False, indent=2), encoding="utf-8")
        migrate.sync_asset(co_fp)
        written.append(str(co_fp.name))

    # craft-card
    if pass5 and not skip_craft:
        cc = engine_adapter.assemble_asset_craft_card(name, genre, {"title": name}, metrics, pass5)
        cc_fp = config.ASSETS_ROOT / f"{name}-craft-card.json"
        cc_fp.write_text(json.dumps(cc, ensure_ascii=False, indent=2), encoding="utf-8")
        migrate.sync_asset(cc_fp)
        written.append(str(cc_fp.name))

    return {"name": name, "genre": genre, "written": written}


def assemble_candidates() -> List[Dict[str, Any]]:
    """列出 corpus/raw/ 下可组装的书（有 pass1 即可组装）。"""
    raw_root = config.CORPUS_DIR / "raw"
    candidates = []
    if raw_root.is_dir():
        for child in sorted(raw_root.iterdir()):
            if child.is_dir() and (child / "pass1_structure.json").is_file():
                passes = [p.name for p in child.glob("pass*.json")]
                candidates.append({"name": child.name, "passes": sorted(passes)})
    return candidates


# ---------------------------------------------------------------------------
# W12 长任务：generate / task_state / import_chapter
# ---------------------------------------------------------------------------

def generate(voice: str, project: str, chapter_no: int, task: str,
             novel_name: Optional[str] = None, prompt: Optional[str] = None,
             genre_pack: Optional[str] = None, words: int = 2400,
             target_score: int = 90, quality_target: Optional[int] = None,
             save_prompt: bool = False) -> Dict[str, Any]:
    """开始写作任务。无模型时同步返回降级指引；有模型时后台线程跑改写循环。"""
    project = _sanitize_project(project)
    if chapter_no < 1:
        raise ServiceError("chapter_no 必须 ≥ 1", 400)

    voice_data = _load_asset_of_kind(voice, "voice")
    novel_dir = config.NOVEL_DIR / project
    engine_adapter.ensure_novel_structure(str(novel_dir), novel_name or project)

    # 构建 system prompt
    if not prompt:
        gp_data = _load_asset_json(genre_pack) if genre_pack else None
        system = engine_adapter.build_writing_prompt(voice_data, genre_pack=gp_data)
    else:
        system = prompt

    pass_line, _ = engine_adapter.resolve_thresholds(
        _load_asset_json(genre_pack) if genre_pack else None)

    task_id = f"w-{uuid.uuid4().hex[:12]}"

    # 无模型降级（同步返回，不占并发额度）
    if not engine_adapter.any_model_configured():
        chapter_path = novel_dir / "chapters" / "arc-1" / f"chapter-{chapter_no:03d}.txt"
        guide = _build_degrade_guide(
            {"project": project, "chapter_no": chapter_no, "task": task,
             "target_score": target_score, "pass_line": pass_line},
            system, chapter_path, pass_line)
        guide_path = novel_dir / "AI接管写作任务.md"
        guide_path.write_text(guide, encoding="utf-8")
        with _WRITING_LOCK:
            _WRITING_TASKS[task_id] = {
                "task_id": task_id, "status": "degraded", "mode": "no_model",
                "chapter_no": chapter_no, "target_score": target_score,
                "pass_line": pass_line, "prompt": system,
                "guide_markdown": guide,
                "guide_path": str(guide_path.relative_to(config.ROOT_DIR)),
                "chapter_path": str(chapter_path.relative_to(config.ROOT_DIR)),
                "notice": "未配置外部模型：请把指引与 prompt 交给会话内智能写作，写完后用「手动入库」贴回。",
                "error": None,
            }
        return _WRITING_TASKS[task_id]

    # MEDIUM：先清理终态任务，防止注册表无限增长
    _prune_terminal_tasks()

    # HIGH：并发上限检查 + 登记必须在同一临界区（TOCTOU 修复）
    with _WRITING_LOCK:
        if _active_writing_count() >= _MAX_CONCURRENT_WRITING:
            raise ServiceError(f"写作任务已达上限 {_MAX_CONCURRENT_WRITING}，请等待当前任务完成", 429)
        req = {
            "project": project, "chapter_no": chapter_no, "task": task,
            "novel_name": novel_name or project, "genre_pack": genre_pack,
            "words": words, "target_score": target_score,
            "quality_target": quality_target or pass_line, "pass_line": pass_line,
        }
        _WRITING_TASKS[task_id] = {
            "task_id": task_id, "status": "running", "mode": "llm",
            "chapter_no": chapter_no, "attempt": 0, "score": None,
            "quality_score": None, "target_score": target_score,
            "pass_line": pass_line, "chapter_path": None,
            "message": "开始生成初稿", "attempts": [], "error": None,
        }

    thread = threading.Thread(
        target=_run_generate, args=(task_id, voice_data, system, req),
        daemon=True, name=f"writing-{task_id}")
    try:
        thread.start()
    except RuntimeError:
        # HIGH：start 失败必须释放并发槽位，否则永久占用
        with _WRITING_LOCK:
            _WRITING_TASKS[task_id]["status"] = "error"
            _WRITING_TASKS[task_id]["error"] = "线程启动失败"
        raise ServiceError("线程启动失败，请稍后重试", 500)
    return {"task_id": task_id, "status": "running", "mode": "llm", "chapter_no": chapter_no}


def task_state(task_id: str) -> Dict[str, Any]:
    """查询写作任务状态。"""
    import copy
    with _WRITING_LOCK:
        t = _WRITING_TASKS.get(task_id)
        if not t:
            raise ServiceError(f"任务不存在: {task_id}", 404)
        # MEDIUM：锁内 deepcopy，避免嵌套列表被并发修改
        return copy.deepcopy(t)


def import_chapter(project: str, chapter_no: int, content: str,
                   novel_name: Optional[str] = None, voice: Optional[str] = None,
                   genre_pack: Optional[str] = None) -> Dict[str, Any]:
    """手动入库：用户贴回会话内写好的正文 → 落盘 + 双维度打分。"""
    project = _sanitize_project(project)
    if chapter_no < 1:
        raise ServiceError("chapter_no 必须 ≥ 1", 400)
    if not content or not content.strip():
        raise ServiceError("content 不能为空", 400)

    novel_dir = config.NOVEL_DIR / project
    engine_adapter.ensure_novel_structure(str(novel_dir), novel_name or project)
    chapter_path = engine_adapter.save_chapter(str(novel_dir), chapter_no, content)

    result: Dict[str, Any] = {
        "chapter_path": str(chapter_path.relative_to(config.ROOT_DIR)),
        "chapter_no": chapter_no, "char_count": len(content),
    }

    if voice:
        voice_data = _load_asset_of_kind(voice, "voice")
        cons = engine_adapter.score_text(voice_data, content, label=f"第{chapter_no}章")
        qc = engine_adapter.chapter_check(content, None)
        pass_line, _ = engine_adapter.resolve_thresholds(
            _load_asset_json(genre_pack) if genre_pack else None)
        result["consistency_score"] = cons["score"]
        result["quality_score"] = qc.get("score", 0)
        result["quality_verdict"] = qc.get("verdict", "?")
        result["pass_line"] = pass_line

    return result


def _run_generate(task_id: str, voice_data: Dict, system: str, req: Dict) -> None:
    """后台线程：初稿 + 最多 2 轮改写循环。"""
    from gui import sse

    project = req["project"]
    novel_dir = config.NOVEL_DIR / project
    chapter_no = req["chapter_no"]
    target_score = req["target_score"]
    pass_line = req["pass_line"]
    max_attempts = 3  # 1 初稿 + 2 改写

    try:
        user = f"请写第{chapter_no}章。{req['task']}\n目标字数约{req['words']}字。"
        best_content = None
        best_cons = 0.0
        best_qc = 0

        for attempt in range(1, max_attempts + 1):
            with _WRITING_LOCK:
                _WRITING_TASKS[task_id]["status"] = "running" if attempt == 1 else "rewriting"
                _WRITING_TASKS[task_id]["attempt"] = attempt
                _WRITING_TASKS[task_id]["message"] = f"第{attempt}稿生成中"

            sse.broker.publish({
                "task_type": "writing", "task_id": task_id,
                "phase": "generating", "attempt": attempt,
                "chapter_no": chapter_no,
            })

            r = engine_adapter.llm_chat(user=user, system=system, task="writing",
                                        max_tokens=6000, temperature=0.8)
            content = r.get("text", "")

            # 打分
            with _WRITING_LOCK:
                _WRITING_TASKS[task_id]["status"] = "scoring"
            cons = engine_adapter.score_text(voice_data, content, label=f"第{chapter_no}章")
            qc = engine_adapter.chapter_check(content, None)
            cons_score = cons["score"]
            qc_score = qc.get("score", 0)
            cons_ok = cons_score >= target_score
            qc_ok = qc_score >= pass_line

            attempt_record = {
                "attempt": attempt, "consistency": cons_score, "quality": qc_score,
                "consistency_ok": cons_ok, "quality_ok": qc_ok,
                "issues": qc.get("issues", [])[:5], "char_count": len(content),
            }
            with _WRITING_LOCK:
                _WRITING_TASKS[task_id]["attempts"].append(attempt_record)
                _WRITING_TASKS[task_id]["score"] = cons_score
                _WRITING_TASKS[task_id]["quality_score"] = qc_score

            sse.broker.publish({
                "task_type": "writing", "task_id": task_id,
                "phase": "scored", "attempt": attempt,
                "consistency": cons_score, "quality": qc_score,
                "consistency_ok": cons_ok, "quality_ok": qc_ok,
            })

            if cons_ok and qc_ok:
                best_content = content
                best_cons = cons_score
                best_qc = qc_score
                break

            # MEDIUM：用加权分比较（一致性 60% + 质量 40%），避免高一致性低质量稿胜出
            combined = cons_score * 0.6 + qc_score * 0.4
            best_combined = best_cons * 0.6 + best_qc * 0.4
            if combined > best_combined or best_content is None:
                best_content = content
                best_cons = cons_score
                best_qc = qc_score

            # 构建改写 user prompt
            user = _build_rewrite_user(user, req, cons_score, target_score,
                                       cons.get("details", []), qc.get("issues", []),
                                       voice_data, content)

        # 落盘最佳稿
        chapter_path = engine_adapter.save_chapter(str(novel_dir), chapter_no, best_content or "")
        with _WRITING_LOCK:
            _WRITING_TASKS[task_id]["status"] = "done"
            _WRITING_TASKS[task_id]["chapter_path"] = str(chapter_path.relative_to(config.ROOT_DIR))
            _WRITING_TASKS[task_id]["message"] = (
                f"完成：一致性 {best_cons:.1f}/100，质量 {best_qc}/100")

        sse.broker.publish({
            "task_type": "writing", "task_id": task_id,
            "phase": "done", "chapter_no": chapter_no,
            "consistency": best_cons, "quality": best_qc,
            "chapter_path": str(chapter_path.relative_to(config.ROOT_DIR)),
        })

    except Exception as exc:  # noqa: BLE001
        with _WRITING_LOCK:
            _WRITING_TASKS[task_id]["status"] = "error"
            _WRITING_TASKS[task_id]["error"] = str(exc)
        sse.broker.publish({
            "task_type": "writing", "task_id": task_id,
            "phase": "error", "error": str(exc),
        })


def _build_rewrite_user(prev_user: str, req: Dict, score: float, target: int,
                        details: List[str], quality_issues: List[str],
                        voice_data: Dict, content: str) -> str:
    """构建改写指令：指出扣分点，要求重写。"""
    problems = []
    for d in details[:8]:
        if "偏短" not in d:
            problems.append(d)
    for issue in quality_issues[:5]:
        if isinstance(issue, dict):
            problems.append(f"[质量] {issue.get('detail', '')}")
        else:
            problems.append(f"[质量] {issue}")

    problem_text = "\n".join(f"- {p}" for p in problems) if problems else "- 整体一致性不足"
    return (
        f"上一稿一致性 {score:.1f}/100（目标 {target}），需要改写。\n"
        f"主要问题：\n{problem_text}\n\n"
        f"请在保持剧情连贯的前提下重写第{req['chapter_no']}章，"
        f"重点改善上述问题。目标字数约{req['words']}字。\n\n"
        f"上一稿全文：\n{content}"
    )


def _build_degrade_guide(req: Dict, prompt: str, chapter_path: Path, pass_line: int) -> str:
    """组装无模型降级指引 Markdown。"""
    return (
        f"# 内置智能接管写作任务（无外部模型模式）\n\n"
        f"## 任务\n"
        f"- 项目：{req['project']}\n"
        f"- 章节：第{req['chapter_no']}章\n"
        f"- 要点：{req['task']}\n"
        f"- 目标一致性分：{req['target_score']}/100\n"
        f"- 章节质量及格线：{pass_line}/100\n\n"
        f"## 写作要求（System Prompt）\n\n{prompt}\n\n"
        f"## 完成后\n"
        f"1. 将正文保存到：`{chapter_path}`\n"
        f"2. 或在 GUI「手动入库」贴回正文\n"
        f"3. 验收命令：`python novel.py 检查 {chapter_path} --voice <voice-card路径>`\n"
    )
