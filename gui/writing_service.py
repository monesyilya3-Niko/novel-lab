"""M2 写作服务层：注入 / 写作(长任务) / 打分 / 组装 / 手动入库 / 项目列举。

分层边界：只经 ``engine_adapter`` 触碰 scripts/，不直接 import 任何脚本。
长任务并发上限 2（D6）；写入路径唯一为 NOVEL_DIR/<project>（D1）。
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from gui import config, engine_adapter, migrate
from gui.logging_setup import get_logger
from gui.services import ServiceError, assert_asset_kind

_log = get_logger("writing_service")

# ---------------------------------------------------------------------------
# 任务注册表（进程内，不落库）
# ---------------------------------------------------------------------------
_WRITING_TASKS: dict[str, dict[str, Any]] = {}
# RLock：generate() 提交路径在外层持锁后还会调 _active_writing_count()（同样拿锁），
# 非重入 Lock 会自死锁（与 quality_service._QUALITY_LOCK 同一事故口径）。
_WRITING_LOCK = threading.RLock()

_ACTIVE_STATUSES = frozenset({"pending", "running", "scoring", "rewriting"})
_MAX_CONCURRENT_WRITING = 2
_MAX_TERMINAL_TASKS = 50  # 终态任务最多保留 N 个


def _prune_terminal_tasks() -> None:
    """清理终态任务，防止注册表无限增长。"""
    with _WRITING_LOCK:
        terminal = {k: v for k, v in _WRITING_TASKS.items()
                    if v.get("status") not in _ACTIVE_STATUSES}
        if len(terminal) > _MAX_TERMINAL_TASKS:
            # 按创建时间删除最旧的（task_id 是 uuid4 hex，无时间成分，不能按它排序）。
            # 历史任务可能缺 created_at（旧版本注册表），缺省按 0（最旧）处理。
            to_remove = sorted(terminal.keys(),
                               key=lambda k: terminal[k].get("created_at", 0)
                               )[:len(terminal) - _MAX_TERMINAL_TASKS]
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


def _load_asset_json(ref: str) -> dict[str, Any]:
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
        raise ServiceError(f"资产文件损坏: {exc}", 500) from exc


def _load_asset_of_kind(ref: str, expected: str) -> dict[str, Any]:
    """加载资产引用并按**内容契约**校验 kind。

    文件名不保证与内容一致（蒸馏卡历史上落成 ``*-voice-card-distilled.json``），
    因此 distilled 当 voice、index 当 prose_card 等错配必须在此同步拒绝（400），
    而不是把错误资产塞进 prompt。识别逻辑统一在 ``services.assert_asset_kind``。
    """
    data = _load_asset_json(ref)
    assert_asset_kind(data, expected, ref)
    return data


def _asset_genre(data: dict) -> str | None:
    """提取资产的题材标识。

    书资产（voice/structure/commercial/craft/distilled）用 ``meta.genre``；
    题材包/文风卡的题材在 ``meta.id`` 里（``genre-<slug>``），``meta.genre``
    为空。未知返回 None（历史资产缺字段时不阻断，避免误伤）。
    """
    meta = data.get("meta", {}) or {}
    g = meta.get("genre")
    if g:
        return str(g)
    aid = meta.get("id", "")
    if isinstance(aid, str) and aid.startswith("genre-"):
        return aid[len("genre-"):]
    return None


def _require_genre_match(voice_data: dict, assets: dict[str, dict | None]) -> None:
    """铁律一：注入时按题材匹配，禁止跨题材污染。

    voice 题材已知、且某可选资产题材已知、两者不一致 → 400。
    任一侧题材未知时不阻断（历史资产缺字段，避免误伤正常注入）。
    tracking_state / context_intent 是写作现场状态，无题材语义，不参与校验；
    prose_card（文风卡）是风格参照物，允许跨题材选用（"通用文风卡"定位，
    tests/test_writing_service.py::test_real_prose_card_accepted 为证），
    调用方不要把 prose_card 传进来。
    """
    voice_genre = _asset_genre(voice_data)
    if not voice_genre:
        return
    for label, data in assets.items():
        if not data:
            continue
        g = _asset_genre(data)
        if g and g != voice_genre:
            raise ServiceError(
                f"题材不一致（铁律一：禁止跨题材污染）：voice 为 {voice_genre!r}，"
                f"{label} 为 {g!r}", 400)


def _atomic_write_json(fp: Path, data: dict) -> None:
    """原子写 JSON：先写临时文件再 os.replace，避免并发同目标 torn-write。

    assemble() 的 4 类资产卡可能被并发组装同一本书；直接 write_text 是截断写，
    并发写会产生损坏的 JSON（读方 500"资产文件损坏"）。与 services 报告写盘同口径。
    """
    # tmp 名必须唯一：并发写同一目标时固定 tmp 名会互相抢占（一方 replace 掉
    # 另一方的 tmp，导致 FileNotFoundError）。
    tmp = fp.with_name(f"{fp.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, fp)


# ---------------------------------------------------------------------------
# 同步能力
# ---------------------------------------------------------------------------

def list_projects() -> list[dict[str, Any]]:
    """枚举 NOVEL_DIR 下项目；始终追加只读项目 default（D1）。

    2026-09-18 修复：此前仅当 ``novel/`` 目录已存在时才返回 default，
    全新环境 GUI 写作台项目列表为空。契约要求 default **恒在**（只读）。
    """
    projects: list[dict[str, Any]] = []
    nd = config.NOVEL_DIR
    try:
        nd.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
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
    # CLI 只读 default 项目：无论 novel/ 是否为空都必须出现
    projects.append({"id": "default", "name": "default（CLI 只读）", "read_only": True})
    return projects


_PROJECT_ID_RE = re.compile(r"^[^\s/\\]+$")


def create_project(name: str) -> dict[str, Any]:
    """新建写作项目：在 ``config.NOVEL_DIR`` 下建目录并写 ``state.json``。

    安全规则：
    - name 为空 / 超长（>60）→ 400。
    - 目录 id 即 name 本身（首尾空白先去除）：禁止 ``/`` ``\\``、``.``/``..``，
      防止路径穿越出 NOVEL_DIR；``default`` 为 CLI 只读保留 id，禁止占用。
    - 同名目录已存在 → 409（不覆盖已有项目数据）。
    - ``state.json`` 经 ``_atomic_write_json`` 原子写入。
    """
    clean = (name or "").strip()
    if not clean:
        raise ServiceError("项目名不能为空", 400)
    if len(clean) > 60:
        raise ServiceError("项目名过长（最多 60 个字符）", 400)
    if clean in (".", "..") or not _PROJECT_ID_RE.match(clean):
        raise ServiceError("项目名不能包含 / 或 \\", 400)
    if clean == "default":
        raise ServiceError("default 为 CLI 只读保留项目，不能新建", 400)

    nd = config.NOVEL_DIR
    try:
        nd.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ServiceError(f"无法创建项目目录: {exc}", 500) from exc
    target = nd / clean
    # resolve 防御：即使上层校验有遗漏，解析后仍必须在 NOVEL_DIR 内。
    try:
        resolved = target.resolve()
        if resolved.parent != nd.resolve():
            raise ServiceError("非法项目名", 400)
    except OSError as exc:
        raise ServiceError(f"项目名非法: {exc}", 400) from exc
    if target.exists():
        raise ServiceError(f"项目已存在: {clean}", 409)
    try:
        target.mkdir()
    except OSError as exc:
        raise ServiceError(f"无法创建项目目录: {exc}", 500) from exc
    _atomic_write_json(target / "state.json",
                       {"name": clean, "created_at": time.time()})
    return {"id": clean, "name": clean, "read_only": False}


def inject(voice: str, structure: str | None = None, commercial: str | None = None,
           genre_pack: str | None = None, craft: str | None = None,
           distilled: str | None = None, prose_card: str | None = None,
           context_intent: str | None = None, tracking_state: str | None = None,
           save: bool = False) -> dict[str, Any]:
    """资产 → 写作 system prompt。

    每个资产参数只接受对应 kind 的内容：distilled 必须走 ``distilled`` 参数
    （不得塞进 voice/structure/commercial/craft），``prose_card`` 必须是文风卡本身
    而非题材索引；错配由 ``_load_asset_of_kind`` 同步拒绝为 400。
    """
    voice_data = _load_asset_of_kind(voice, "voice")
    structure_data = _load_asset_of_kind(structure, "structure") if structure else None
    commercial_data = _load_asset_of_kind(commercial, "commercial") if commercial else None
    genre_pack_data = _load_asset_json(genre_pack) if genre_pack else None
    craft_data = _load_asset_of_kind(craft, "craft") if craft else None
    distilled_data = _load_asset_of_kind(distilled, "distilled") if distilled else None
    prose_card_data = _load_asset_of_kind(prose_card, "prose_card") if prose_card else None
    # 铁律一：注入时按题材匹配，禁止跨题材污染（kind 校验只防错配，不防跨题材）。
    # prose_card 豁免：文风卡是风格参照，允许跨题材选用。
    _require_genre_match(voice_data, {
        "structure": structure_data, "commercial": commercial_data,
        "genre_pack": genre_pack_data, "craft": craft_data,
        "distilled": distilled_data,
    })
    prompt = engine_adapter.build_writing_prompt(
        voice_data,
        structure=structure_data,
        commercial=commercial_data,
        genre_pack=genre_pack_data,
        craft_card=craft_data,
        distilled=distilled_data,
        context_intent=context_intent,
        tracking_state=_load_asset_json(tracking_state) if tracking_state else None,
        genre_prose_card=prose_card_data,
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
        saved_path = migrate.rel_path(fp)

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


def score(voice: str, text: str | None = None, chapter_path: str | None = None,
          label: str = "", genre_pack: str | None = None) -> dict[str, Any]:
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
            raise ServiceError(f"读取章节失败: {exc}", 400) from exc

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


def assemble(name: str, genre: str, skip_craft: bool = False) -> dict[str, Any]:
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

    def _load_pass(fname: str) -> dict[str, Any] | None:
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

    written: list[str] = []

    # voice-card
    if pass2 and pass3:
        voices = engine_adapter.normalize_pass2(pass2)
        narration, dialogue, emotion, imagery, banned = engine_adapter.normalize_pass3(pass3)
        vc = engine_adapter.assemble_asset_voice_card(
            name, genre, {"title": name}, metrics, voices,
            narration, dialogue, emotion, imagery, banned)
        vc_fp = config.ASSETS_ROOT / f"{name}-voice-card.json"
        _atomic_write_json(vc_fp, vc)
        migrate.sync_asset(vc_fp)
        written.append(str(vc_fp.name))

    # structure-obs
    if pass1:
        so = engine_adapter.assemble_asset_obs("structure", name, genre, pass1)
        so_fp = config.ASSETS_ROOT / f"{name}-structure-obs.json"
        _atomic_write_json(so_fp, so)
        migrate.sync_asset(so_fp)
        written.append(str(so_fp.name))

    # commercial-obs
    if pass4:
        co = engine_adapter.assemble_asset_obs("commercial", name, genre, pass4)
        co_fp = config.ASSETS_ROOT / f"{name}-commercial-obs.json"
        _atomic_write_json(co_fp, co)
        migrate.sync_asset(co_fp)
        written.append(str(co_fp.name))

    # craft-card
    if pass5 and not skip_craft:
        cc = engine_adapter.assemble_asset_craft_card(name, genre, {"title": name}, metrics, pass5)
        cc_fp = config.ASSETS_ROOT / f"{name}-craft-card.json"
        _atomic_write_json(cc_fp, cc)
        migrate.sync_asset(cc_fp)
        written.append(str(cc_fp.name))

    return {"name": name, "genre": genre, "written": written}


def assemble_candidates() -> list[dict[str, Any]]:
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
             novel_name: str | None = None, prompt: str | None = None,
             genre_pack: str | None = None, words: int = 2400,
             target_score: int = 90, quality_target: int | None = None,
             save_prompt: bool = False) -> dict[str, Any]:
    """开始写作任务。无模型时同步返回降级指引；有模型时后台线程跑改写循环。"""
    project = _sanitize_project(project)
    if chapter_no < 1:
        raise ServiceError("chapter_no 必须 ≥ 1", 400)

    voice_data = _load_asset_of_kind(voice, "voice")
    novel_dir = config.NOVEL_DIR / project
    engine_adapter.ensure_novel_structure(str(novel_dir), novel_name or project)

    # 构建 system prompt
    gp_data = _load_asset_json(genre_pack) if genre_pack else None
    # 铁律一：注入时按题材匹配，禁止跨题材污染。
    _require_genre_match(voice_data, {"genre_pack": gp_data})
    if not prompt:
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
                "created_at": time.time(),
                "chapter_no": chapter_no, "target_score": target_score,
                "pass_line": pass_line, "prompt": system,
                "guide_markdown": guide,
                "guide_path": migrate.rel_path(guide_path),
                "chapter_path": migrate.rel_path(chapter_path),
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
            "created_at": time.time(),
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
    except RuntimeError as exc:
        # HIGH：start 失败必须释放并发槽位，否则永久占用
        with _WRITING_LOCK:
            _WRITING_TASKS[task_id]["status"] = "error"
            _WRITING_TASKS[task_id]["error"] = "线程启动失败"
        raise ServiceError("线程启动失败，请稍后重试", 500) from exc
    return {"task_id": task_id, "status": "running", "mode": "llm", "chapter_no": chapter_no}


def task_state(task_id: str) -> dict[str, Any]:
    """查询写作任务状态。"""
    import copy
    with _WRITING_LOCK:
        t = _WRITING_TASKS.get(task_id)
        if not t:
            raise ServiceError(f"任务不存在: {task_id}", 404)
        # MEDIUM：锁内 deepcopy，避免嵌套列表被并发修改
        return copy.deepcopy(t)


def import_chapter(project: str, chapter_no: int, content: str,
                   novel_name: str | None = None, voice: str | None = None,
                   genre_pack: str | None = None) -> dict[str, Any]:
    """手动入库：用户贴回会话内写好的正文 → 落盘 + 双维度打分。"""
    project = _sanitize_project(project)
    if chapter_no < 1:
        raise ServiceError("chapter_no 必须 ≥ 1", 400)
    if not content or not content.strip():
        raise ServiceError("content 不能为空", 400)

    novel_dir = config.NOVEL_DIR / project
    # 资产内容契约：voice 的加载与 kind 校验必须在 ensure_novel_structure/save_chapter
    # **之前**完成（与 score()/generate() 的顺序一致）。否则校验抛 400 时章节文件已落盘、
    # state.json 的 current_chapter/word_count_today 已被推进——修正后重试还会重复累加字数。
    voice_data = _load_asset_of_kind(voice, "voice") if voice else None

    engine_adapter.ensure_novel_structure(str(novel_dir), novel_name or project)
    chapter_path = engine_adapter.save_chapter(str(novel_dir), chapter_no, content)

    result: dict[str, Any] = {
        "chapter_path": migrate.rel_path(chapter_path),
        "chapter_no": chapter_no, "char_count": len(content),
    }

    if voice_data is not None:
        cons = engine_adapter.score_text(voice_data, content, label=f"第{chapter_no}章")
        qc = engine_adapter.chapter_check(content, None)
        pass_line, _ = engine_adapter.resolve_thresholds(
            _load_asset_json(genre_pack) if genre_pack else None)
        result["consistency_score"] = cons["score"]
        result["quality_score"] = qc.get("score", 0)
        result["quality_verdict"] = qc.get("verdict", "?")
        result["pass_line"] = pass_line

    # v2.0.2：码字统计（失败不阻断写作主流程）
    try:
        from gui import writing_extra
        writing_extra.record_words(project, writing_extra.count_words(content), chapters=1)
    except Exception:
        pass

    return result


def _run_generate(task_id: str, voice_data: dict, system: str, req: dict) -> None:
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
        # v2.0.2：码字统计（失败不阻断：统计表异常不得让已落盘的章节任务卡住）
        try:
            from gui import writing_extra
            writing_extra.record_words(project, writing_extra.count_words(best_content or ""), chapters=1)
        except Exception:
            pass
        with _WRITING_LOCK:
            _WRITING_TASKS[task_id]["status"] = "done"
            _WRITING_TASKS[task_id]["chapter_path"] = migrate.rel_path(chapter_path)
            _WRITING_TASKS[task_id]["message"] = (
                f"完成：一致性 {best_cons:.1f}/100，质量 {best_qc}/100")

        sse.broker.publish({
            "task_type": "writing", "task_id": task_id,
            "phase": "done", "chapter_no": chapter_no,
            "consistency": best_cons, "quality": best_qc,
            "chapter_path": migrate.rel_path(chapter_path),
        })

    except Exception as exc:  # noqa: BLE001
        with _WRITING_LOCK:
            _WRITING_TASKS[task_id]["status"] = "error"
            _WRITING_TASKS[task_id]["error"] = str(exc)
        sse.broker.publish({
            "task_type": "writing", "task_id": task_id,
            "phase": "error", "error": str(exc),
        })


def _build_rewrite_user(prev_user: str, req: dict, score: float, target: int,
                        details: list[str], quality_issues: list[str],
                        voice_data: dict, content: str) -> str:
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


def _build_degrade_guide(req: dict, prompt: str, chapter_path: Path, pass_line: int) -> str:
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
