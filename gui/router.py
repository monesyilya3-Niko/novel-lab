"""REST 路由表 + 请求分发 + JSON 序列化 + 统一错误码。

响应统一包裹：``{"code": 0, "data": ..., "message": ""}``。
code 约定：0 成功；400 参数错误；403 路径越权（导入限定项目根内）；
404 资源不存在；409 状态冲突；413 请求体超限（>10MB）；500 内部错误。
"""
from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from gui import engine_adapter, services
from gui.services import ServiceError

# ---------------------------------------------------------------------------
# 响应工具
# ---------------------------------------------------------------------------

def ok(data: Any = None) -> dict[str, Any]:
    return {"code": 0, "data": data, "message": ""}


def err(code: int, message: str) -> dict[str, Any]:
    return {"code": code, "data": None, "message": message}


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


# ---------------------------------------------------------------------------
# 处理器
# ---------------------------------------------------------------------------

def _h_import(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    path = (body or {}).get("path", "")
    if not path:
        raise ServiceError("缺少 path 参数", 400)
    # M8：API 层限制导入路径在项目根内，防止任意文件读取（纵深防御）。
    from gui import config as _config
    resolved = Path(path).resolve()
    root = _config.ROOT_DIR.resolve()
    if not resolved.is_relative_to(root):
        raise ServiceError("导入路径必须在项目目录内", 403)
    batch_size = _safe_batch_size((body or {}).get("batch_size"))
    return ok(services.import_book(path, batch_size))


def _samples_dir() -> Path:
    """内置示例语料目录：与 gui/ 同级的 samples/（原创内容，随安装包发布）。

    注意：corpus/ 是 gitignore 的版权语料区，示例必须放在 samples/ 才能
    随 git archive 进入安装包，且不触发打包安全自检的 corpus 泄漏告警。
    """
    from gui import config as _config
    # GUI_DIR = <install>/gui → samples 在 <install>/samples
    d = Path(_config.GUI_DIR).resolve().parent / "samples"
    return d


def _h_list_samples(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    """GET /api/samples：列出内置示例语料（供新手一键导入试手）。"""
    d = _samples_dir()
    items = []
    if d.is_dir():
        for fp in sorted(d.glob("示例-*.txt")):
            try:
                size = fp.stat().st_size
                # 快速数章节数
                chapters = 0
                with fp.open("r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("第") and "章" in line[:12]:
                            chapters += 1
                            if chapters > 999:
                                break
            except OSError:
                continue
            # 从文件名提取题材名：示例-校园救赎.txt → 校园救赎
            genre = fp.stem.replace("示例-", "")
            items.append({
                "name": fp.name,
                "genre": genre,
                "size": size,
                "chapters": chapters,
            })
    return ok({"samples": items})


def _h_import_sample(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    """POST /api/samples/import：一键导入内置示例语料。

    body: {"name": "示例-校园救赎.txt"}。安全：name 必须严格匹配
    示例文件名白名单（示例-*.txt），不接受路径分隔符，防止目录遍历。
    """
    from gui import config as _config
    name = (body or {}).get("name", "")
    if not name or not isinstance(name, str):
        raise ServiceError("缺少 name 参数", 400)
    # 白名单校验：只允许 示例-<题材>.txt，且不含路径分隔符
    import re as _re
    if not _re.fullmatch(r"示例-[^/\\]+\.txt", name):
        raise ServiceError("非法示例文件名", 400)
    src = _samples_dir() / name
    # 解析后必须仍在 samples 目录内（纵深防御）
    try:
        resolved = src.resolve()
    except OSError as exc:
        raise ServiceError("示例文件不存在", 404) from exc
    if not resolved.is_relative_to(_samples_dir().resolve()) or not resolved.is_file():
        raise ServiceError("示例文件不存在", 404)
    # 复制到用户语料目录（防重名），再走标准导入流程
    _config.CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    dest = services.unique_corpus_path(name)
    shutil.copy2(resolved, dest)
    batch_size = _safe_batch_size((body or {}).get("batch_size"))
    try:
        return ok(services.import_book(str(dest), batch_size))
    except Exception:
        # P2-2：导入失败删掉已复制的副本，不在 corpus 留垃圾文件。
        try:
            dest.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _h_get_book(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    book_id = params["book_id"]
    return ok(services.get_book(book_id))


def _h_get_chapter(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    book_id = params["book_id"]
    idx = _safe_int(params.get("idx"), -1, "idx")
    if idx < 0:
        raise ServiceError("缺少或非法 idx", 400)
    return ok(services.get_chapter(book_id, idx))


def _h_split_batch(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    book_id = params["book_id"]
    idx = _safe_int(params.get("idx"), -1, "idx")
    if idx < 0:
        raise ServiceError("缺少或非法 idx", 400)
    batch_size = _safe_batch_size((body or {}).get("batch_size"))
    return ok(services.split_chapter_batches(book_id, idx, batch_size))


def _h_start(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    book_id = (body or {}).get("book_id", "")
    genre = (body or {}).get("genre", "unknown")
    model_id = (body or {}).get("model_id")
    batch_size = _safe_batch_size((body or {}).get("batch_size"))
    if not book_id:
        raise ServiceError("缺少 book_id", 400)
    return ok(services.start_analysis(book_id, genre, model_id, batch_size))


def _h_pause(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    book_id = (body or {}).get("book_id", "")
    if not book_id:
        raise ServiceError("缺少 book_id", 400)
    return ok(services.pause(book_id))


def _h_resume(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    book_id = (body or {}).get("book_id", "")
    if not book_id:
        raise ServiceError("缺少 book_id", 400)
    genre = (body or {}).get("genre")
    model_id = (body or {}).get("model_id")
    return ok(services.resume(book_id, genre, model_id))


def _h_retry_failed(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    book_id = (body or {}).get("book_id", "")
    if not book_id:
        raise ServiceError("缺少 book_id", 400)
    return ok(services.retry_failed(book_id))


def _h_status(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    book_id = params.get("book_id")
    return ok(services.get_status(book_id))


def _h_asset(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    book_id = params.get("book_id", "")
    if not book_id:
        raise ServiceError("缺少 book_id", 400)
    try:
        chapter_index = int(params.get("chapter", 0))
        batch_index = int(params.get("batch", 0))
    except (TypeError, ValueError) as exc:
        raise ServiceError("chapter/batch 必须为整数", 400) from exc
    pass_name = params.get("pass", "")
    if not pass_name:
        raise ServiceError("缺少 pass", 400)
    return ok(services.get_asset(book_id, chapter_index, batch_index, pass_name))


def _h_models(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    return ok({"models": engine_adapter.list_models(),
               "any_configured": engine_adapter.any_model_configured()})


# ---------------------------------------------------------------------------
# 阶段一新增端点
# ---------------------------------------------------------------------------

def _h_overview(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    return ok(services.get_overview())


def _h_list_assets(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    kind = params.get("kind") or None
    genre = params.get("genre") or None
    book_id = params.get("book_id") or None
    try:
        offset = int(params.get("offset", "0") or "0")
        limit = int(params.get("limit", "50") or "50")
    except ValueError as exc:
        raise ServiceError("offset/limit 必须为整数", 400) from exc
    return ok(services.list_assets(kind, genre, book_id, offset, limit))


def _h_stats(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    return ok(services.get_stats())


def _h_asset_detail(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    kind = params["kind"]
    asset_id = params["id"]
    return ok(services.get_asset_detail(kind, asset_id))


def _h_list_reports(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    return ok(services.list_reports())


def _h_get_report(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    report_id = params["id"]
    return ok(services.get_report(report_id))


def _h_book_results(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    book_id = params["book_id"]
    return ok(services.get_book_results(book_id))


def _h_book_scores(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    book_id = params["book_id"]
    return ok(services.get_book_scores(book_id))


def _h_full_analysis(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    book_id = (body or {}).get("book_id", "")
    genre = (body or {}).get("genre", "unknown")
    model_id = (body or {}).get("model_id")
    if not book_id:
        raise ServiceError("缺少 book_id", 400)
    return ok(services.run_full_analysis(book_id, genre, model_id))


def _h_genres(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    """P0-4：题材列表（前端下拉唯一来源，与后端校验同源）。"""
    from gui import engine_adapter
    return ok({"genres": engine_adapter.known_genres()})


# ---------------------------------------------------------------------------
# W15 阶段二：写作（M2）+ 质检（M3）端点
# ---------------------------------------------------------------------------

def _h_writing_projects(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import writing_service
    return ok(writing_service.list_projects())


def _h_writing_inject(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import writing_service
    b = body or {}
    return ok(writing_service.inject(
        voice=b.get("voice", ""), structure=b.get("structure"),
        commercial=b.get("commercial"), genre_pack=b.get("genre_pack"),
        craft=b.get("craft"), distilled=b.get("distilled"),
        prose_card=b.get("prose_card"), context_intent=b.get("context_intent"),
        tracking_state=b.get("tracking_state"), save=bool(b.get("save"))))


def _safe_int(value: Any, default: int, field: str) -> int:
    """安全 int 转换：非法值返回 400 而非 500。"""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ServiceError(f"{field} 必须为整数", 400) from exc


def _safe_batch_size(value: Any) -> int | None:
    """P2-B6：batch_size 非法值返回 400 而非透传导致 500。"""
    if value is None:
        return None
    bs = _safe_int(value, 0, "batch_size")
    if bs <= 0:
        raise ServiceError("batch_size 必须为正整数", 400)
    return bs


def _h_writing_generate(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import writing_service
    b = body or {}
    return ok(writing_service.generate(
        voice=b.get("voice", ""), project=b.get("project", ""),
        chapter_no=_safe_int(b.get("chapter_no"), 0, "chapter_no"), task=b.get("task", ""),
        novel_name=b.get("novel_name"), prompt=b.get("prompt"),
        genre_pack=b.get("genre_pack"), words=_safe_int(b.get("words"), 2400, "words"),
        target_score=_safe_int(b.get("target_score"), 90, "target_score"),
        quality_target=b.get("quality_target"),
        save_prompt=bool(b.get("save_prompt"))))


def _h_writing_task(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import writing_service
    return ok(writing_service.task_state(params["task_id"]))


def _h_writing_import_chapter(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import writing_service
    b = body or {}
    return ok(writing_service.import_chapter(
        project=b.get("project", ""), chapter_no=_safe_int(b.get("chapter_no"), 0, "chapter_no"),
        content=b.get("content", ""), novel_name=b.get("novel_name"),
        voice=b.get("voice"), genre_pack=b.get("genre_pack")))


def _h_writing_score(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import writing_service
    b = body or {}
    return ok(writing_service.score(
        voice=b.get("voice", ""), text=b.get("text"),
        chapter_path=b.get("chapter_path"), label=b.get("label", "")))


def _h_writing_assemble(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import writing_service
    b = body or {}
    return ok(writing_service.assemble(
        name=b.get("name", ""), genre=b.get("genre", ""),
        skip_craft=bool(b.get("skip_craft"))))


def _h_writing_assemble_candidates(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import writing_service
    return ok(writing_service.assemble_candidates())


def _h_quality_check(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import quality_service
    b = body or {}
    return ok(quality_service.check(
        target=b.get("target"), text=b.get("text"),
        voice=b.get("voice"), genre_pack=b.get("genre_pack")))


def _h_quality_book(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import quality_service
    b = body or {}
    return ok(quality_service.book(
        target=b.get("target"), text=b.get("text"), voice=b.get("voice")))


def _h_quality_qc(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import quality_service
    b = body or {}
    return ok(quality_service.qc(
        target=b.get("target"), text=b.get("text"), voice=b.get("voice"),
        genre_pack=b.get("genre_pack"), asset=b.get("asset"), book=b.get("book"),
        novel_dir=b.get("novel_dir"), llm_hook=bool(b.get("llm_hook"))))


def _h_quality_task(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import quality_service
    return ok(quality_service.qc_task_state(params["task_id"]))


def _h_quality_reports(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import quality_service
    return ok(quality_service.list_qc_reports())


# --- M5 系统与合规 handlers ---

def _h_system_status(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import system_service
    return ok(system_service.system_status())


def _h_compliance_scan(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import system_service
    b = body or {}
    return ok(system_service.compliance_scan(
        voice=b.get("voice"), book_path=b.get("book_path")))


def _h_model_info(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import system_service
    return ok(system_service.model_info())


def _h_get_settings(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import system_service
    return ok(system_service.get_settings())


def _h_update_settings(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import system_service
    return ok(system_service.update_settings(body or {}))


def _h_reset_settings(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import system_service
    return ok(system_service.reset_settings())


# --- 模型管理 handlers ---

def _h_list_models(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import model_service
    return ok(model_service.list_models())


def _h_get_model(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import model_service
    return ok(model_service.get_model(params["model_id"]))


def _h_add_model(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import model_service
    return ok(model_service.add_model(body or {}))


def _h_update_model(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import model_service
    return ok(model_service.update_model(params["model_id"], body or {}))


def _h_delete_model(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import model_service
    return ok(model_service.delete_model(params["model_id"]))


def _h_set_model_key(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import model_service
    b = body or {}
    return ok(model_service.set_api_key(params["model_id"], b.get("api_key", "")))


def _h_test_model(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import model_service
    return ok(model_service.test_model(params["model_id"]))


def _h_get_presets(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import model_service
    return ok(model_service.get_presets())


# --- 文风集成 handlers ---

def _h_analyze_style(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import style_service
    b = body or {}
    return ok(style_service.analyze_style(b.get("text", ""), b.get("name", "")))


def _h_save_style(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import style_service
    b = body or {}
    return ok(style_service.save_style(b.get("name", ""), b.get("style_card", {})))


def _h_list_styles(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import style_service
    return ok({"styles": style_service.list_styles()})


def _h_get_style(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import style_service
    return ok(style_service.get_style(params["name"]))


def _h_delete_style(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import style_service
    return ok(style_service.delete_style(params["name"]))


def _h_apply_style(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import style_service
    b = body or {}
    return ok(style_service.apply_style_prompt(b.get("style_name", ""), b.get("base_prompt", "")))


# --- 多平台适配 handlers ---

def _h_list_platforms(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import platform_service
    return ok({"platforms": platform_service.list_platforms()})


def _h_get_platform(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import platform_service
    return ok(platform_service.get_platform(params["platform_id"]))


def _h_check_compliance(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import platform_service
    b = body or {}
    return ok(platform_service.check_chapter_compliance(
        b.get("platform_id", ""), b.get("chapter_text", ""), b.get("chapter_title", "")))


def _h_format_chapter(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import platform_service
    b = body or {}
    return ok(platform_service.format_chapter(
        b.get("platform_id", ""), _safe_int(b.get("chapter_num"), 1, "chapter_num"),
        b.get("title", ""), b.get("content", "")))


def _h_export_book(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import platform_service
    b = body or {}
    return ok(platform_service.export_book_for_platform(
        b.get("platform_id", ""), b.get("book_dir", "")))


# --- M1 高级分析 handlers ---

def _h_distill_status(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import advanced_service
    return ok(advanced_service.distill_status(params["genre"]))


def _h_distill_run(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import advanced_service
    return ok(advanced_service.distill_genre(params["genre"]))


def _h_aggregate(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import advanced_service
    return ok(advanced_service.aggregate_genre(params["genre"]))


def _h_batch_status(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import advanced_service
    return ok(advanced_service.batch_status())


# --- M4 资产写入 handlers ---

def _h_asset_update(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import advanced_service
    b = body or {}
    return ok(advanced_service.update_asset(
        params["kind"], params["id"], b.get("content", {})))


def _h_asset_delete(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import advanced_service
    return ok(advanced_service.delete_asset(params["kind"], params["id"]))


def _h_asset_create(_params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import advanced_service
    b = body or {}
    return ok(advanced_service.create_asset(
        b.get("name", ""), b.get("kind", ""), b.get("content", {})))


# ---------------------------------------------------------------------------
# 管理员系统（/api/admin/*）：会话鉴权由 server 层完成，此处只做业务分发。
# 上下文经 query 注入：_admin_user / _admin_ip。
# ---------------------------------------------------------------------------

def _admin_ctx(params: dict[str, Any]) -> tuple[str, str]:
    return (str(params.get("_admin_user", "") or ""),
            str(params.get("_admin_ip", "") or "-"))


def _h_admin_me(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import admin
    user, _ = _admin_ctx(params)
    return ok({"loggedIn": True, "username": user,
               "mustChangePassword": admin.needs_password_change(user)})


def _h_admin_dashboard(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import admin
    return ok(admin.get_dashboard())


def _h_admin_books(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import state_store
    out = []
    for b in state_store.list_books_summary():
        book_id = b.get("book_id", "")
        try:
            detail = services.get_book(book_id)
            total = detail.get("totalChapters", 0)
        except Exception:  # noqa: BLE001
            total = 0
        out.append({
            "bookId": book_id,
            "title": b.get("title", ""),
            "status": b.get("status", "idle"),
            "totalChapters": total,
            "doneBatches": b.get("done", 0),
        })
    return ok(out)


def _h_admin_book_delete(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import admin
    user, ip = _admin_ctx(params)
    return ok(admin.delete_book(params["book_id"], user, ip))


def _h_admin_assets(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    kind = params.get("kind") or None
    genre = params.get("genre") or None
    return ok(services.list_assets(kind=kind, genre=genre))


def _h_admin_asset_delete(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import admin, advanced_service
    user, ip = _admin_ctx(params)
    result = advanced_service.delete_asset(params["kind"], params["asset_id"])
    admin.audit(user, ip, "admin.asset.delete",
                f"{params['kind']}:{params['asset_id']}")
    return ok(result)


def _h_admin_reports(_params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    return ok(services.list_reports())


def _h_admin_audit(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import admin
    try:
        limit = int(params.get("limit", 100))
    except (TypeError, ValueError):
        limit = 100
    return ok(admin.read_audit(limit,
                              action=str(params.get("action", "") or ""),
                              username=str(params.get("username", "") or ""),
                              since=params.get("since") or None,
                              until=params.get("until") or None))


def _h_admin_change_password(params: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    from gui import admin
    user, ip = _admin_ctx(params)
    b = body or {}
    admin.change_password(user, str(b.get("oldPassword", "")),
                          str(b.get("newPassword", "")), ip)
    return ok({"changed": True})


def _h_admin_sessions(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import admin
    current_sid = str(params.get("_admin_sid", "") or "")
    return ok(admin.list_sessions(current_sid))


def _h_admin_session_revoke(params: dict[str, Any], _body: dict[str, Any]) -> dict[str, Any]:
    from gui import admin
    user, ip = _admin_ctx(params)
    admin.revoke_session(params["sid"], user, ip)
    return ok({"revoked": True})


# ---------------------------------------------------------------------------
# 路由表
# ---------------------------------------------------------------------------

# (method, 正则, handler)。命名捕获组通过正则分组名传入 params。
ROUTES: list[tuple[str, re.Pattern, Callable[[dict, dict], dict]]] = [
    ("POST", re.compile(r"^/api/import$"), _h_import),
    ("GET", re.compile(r"^/api/samples$"), _h_list_samples),
    ("POST", re.compile(r"^/api/samples/import$"), _h_import_sample),
    ("GET", re.compile(r"^/api/book/(?P<book_id>[^/]+)$"), _h_get_book),
    ("GET", re.compile(r"^/api/book/(?P<book_id>[^/]+)/chapter/(?P<idx>\d+)$"), _h_get_chapter),
    ("POST", re.compile(r"^/api/book/(?P<book_id>[^/]+)/chapter/(?P<idx>\d+)/batch$"), _h_split_batch),
    ("POST", re.compile(r"^/api/analyze/start$"), _h_start),
    ("GET", re.compile(r"^/api/genres$"), _h_genres),
    ("POST", re.compile(r"^/api/analyze/pause$"), _h_pause),
    ("POST", re.compile(r"^/api/analyze/resume$"), _h_resume),
    ("POST", re.compile(r"^/api/analyze/retry-failed$"), _h_retry_failed),
    ("GET", re.compile(r"^/api/status$"), _h_status),
    ("GET", re.compile(r"^/api/asset$"), _h_asset),
    ("GET", re.compile(r"^/api/config/models$"), _h_models),
    # 阶段一新增端点（概览/资产/报告/拆书结果/一键分析）。
    ("GET", re.compile(r"^/api/overview$"), _h_overview),
    ("GET", re.compile(r"^/api/assets$"), _h_list_assets),
    ("GET", re.compile(r"^/api/stats$"), _h_stats),
    ("GET", re.compile(r"^/api/assets/(?P<kind>[^/]+)/(?P<id>[^/]+)$"), _h_asset_detail),
    ("GET", re.compile(r"^/api/reports$"), _h_list_reports),
    ("GET", re.compile(r"^/api/reports/(?P<id>[^/]+)$"), _h_get_report),
    ("GET", re.compile(r"^/api/book/(?P<book_id>[^/]+)/results$"), _h_book_results),
    ("GET", re.compile(r"^/api/book/(?P<book_id>[^/]+)/scores$"), _h_book_scores),
    ("POST", re.compile(r"^/api/analyze/full$"), _h_full_analysis),
    # W15 阶段二：写作（M2）
    ("GET", re.compile(r"^/api/writing/projects$"), _h_writing_projects),
    ("POST", re.compile(r"^/api/writing/inject$"), _h_writing_inject),
    ("POST", re.compile(r"^/api/writing/generate$"), _h_writing_generate),
    ("GET", re.compile(r"^/api/writing/tasks/(?P<task_id>[^/]+)$"), _h_writing_task),
    ("POST", re.compile(r"^/api/writing/chapters$"), _h_writing_import_chapter),
    ("POST", re.compile(r"^/api/writing/score$"), _h_writing_score),
    ("POST", re.compile(r"^/api/writing/assemble$"), _h_writing_assemble),
    ("GET", re.compile(r"^/api/writing/assemble-candidates$"), _h_writing_assemble_candidates),
    # W15 阶段二：质检（M3）
    ("POST", re.compile(r"^/api/quality/check$"), _h_quality_check),
    ("POST", re.compile(r"^/api/quality/book$"), _h_quality_book),
    ("POST", re.compile(r"^/api/quality/qc$"), _h_quality_qc),
    ("GET", re.compile(r"^/api/quality/tasks/(?P<task_id>[^/]+)$"), _h_quality_task),
    ("GET", re.compile(r"^/api/quality/reports$"), _h_quality_reports),
    # M5 系统与合规
    ("GET", re.compile(r"^/api/system/status$"), _h_system_status),
    ("POST", re.compile(r"^/api/system/compliance$"), _h_compliance_scan),
    ("GET", re.compile(r"^/api/system/models$"), _h_model_info),
    ("GET", re.compile(r"^/api/system/settings$"), _h_get_settings),
    ("PUT", re.compile(r"^/api/system/settings$"), _h_update_settings),
    ("POST", re.compile(r"^/api/system/settings/reset$"), _h_reset_settings),
    # M1 高级分析
    ("GET", re.compile(r"^/api/advanced/distill/(?P<genre>[^/]+)$"), _h_distill_status),
    ("POST", re.compile(r"^/api/advanced/distill/(?P<genre>[^/]+)$"), _h_distill_run),
    ("GET", re.compile(r"^/api/advanced/aggregate/(?P<genre>[^/]+)$"), _h_aggregate),
    ("GET", re.compile(r"^/api/advanced/batch-status$"), _h_batch_status),
    # M4 资产写入
    ("PUT", re.compile(r"^/api/assets/(?P<kind>[^/]+)/(?P<id>[^/]+)$"), _h_asset_update),
    ("DELETE", re.compile(r"^/api/assets/(?P<kind>[^/]+)/(?P<id>[^/]+)$"), _h_asset_delete),
    ("POST", re.compile(r"^/api/assets$"), _h_asset_create),
    # 模型管理
    ("GET", re.compile(r"^/api/models$"), _h_list_models),
    ("POST", re.compile(r"^/api/models$"), _h_add_model),
    ("GET", re.compile(r"^/api/models/presets$"), _h_get_presets),
    ("GET", re.compile(r"^/api/models/(?P<model_id>[^/]+)$"), _h_get_model),
    ("PUT", re.compile(r"^/api/models/(?P<model_id>[^/]+)$"), _h_update_model),
    ("DELETE", re.compile(r"^/api/models/(?P<model_id>[^/]+)$"), _h_delete_model),
    ("POST", re.compile(r"^/api/models/(?P<model_id>[^/]+)/key$"), _h_set_model_key),
    ("POST", re.compile(r"^/api/models/(?P<model_id>[^/]+)/test$"), _h_test_model),
    # 文风集成
    ("POST", re.compile(r"^/api/style/analyze$"), _h_analyze_style),
    ("POST", re.compile(r"^/api/style/save$"), _h_save_style),
    ("GET", re.compile(r"^/api/style/list$"), _h_list_styles),
    ("GET", re.compile(r"^/api/style/(?P<name>[^/]+)$"), _h_get_style),
    ("DELETE", re.compile(r"^/api/style/(?P<name>[^/]+)$"), _h_delete_style),
    ("POST", re.compile(r"^/api/style/apply$"), _h_apply_style),
    # 多平台适配
    ("GET", re.compile(r"^/api/platform/list$"), _h_list_platforms),
    ("GET", re.compile(r"^/api/platform/(?P<platform_id>[^/]+)$"), _h_get_platform),
    ("POST", re.compile(r"^/api/platform/check$"), _h_check_compliance),
    ("POST", re.compile(r"^/api/platform/format$"), _h_format_chapter),
    ("POST", re.compile(r"^/api/platform/export$"), _h_export_book),
    # 管理员系统（会话鉴权由 server 层 _check_auth 完成；login 由 server 直接处理）
    ("GET", re.compile(r"^/api/admin/me$"), _h_admin_me),
    ("GET", re.compile(r"^/api/admin/dashboard$"), _h_admin_dashboard),
    ("GET", re.compile(r"^/api/admin/books$"), _h_admin_books),
    ("DELETE", re.compile(r"^/api/admin/books/(?P<book_id>[^/]+)$"), _h_admin_book_delete),
    ("GET", re.compile(r"^/api/admin/assets$"), _h_admin_assets),
    ("DELETE", re.compile(r"^/api/admin/assets/(?P<kind>[^/]+)/(?P<asset_id>[^/]+)$"), _h_admin_asset_delete),
    ("GET", re.compile(r"^/api/admin/reports$"), _h_admin_reports),
    ("GET", re.compile(r"^/api/admin/audit$"), _h_admin_audit),
    ("POST", re.compile(r"^/api/admin/change-password$"), _h_admin_change_password),
    ("GET", re.compile(r"^/api/admin/sessions$"), _h_admin_sessions),
    ("DELETE", re.compile(r"^/api/admin/sessions/(?P<sid>[^/]+)$"), _h_admin_session_revoke),
]


def dispatch(method: str, path: str, body: dict[str, Any], query: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """路由分发。返回 (响应 payload, 或 None 表示非 API 路由)。

    对于 SSE 端点返回特殊标记 ``__sse__`` 让 server 层接管长连接。
    """
    # SSE 端点
    if method == "GET" and path == "/api/events":
        return None, "__sse__"

    for m, pattern, handler in ROUTES:
        if m != method:
            continue
        match = pattern.match(path)
        if match:
            params = match.groupdict()
            # MEDIUM：query 只补缺，不覆盖 path 捕获组
            for k, v in query.items():
                params.setdefault(k, v)
            return handler(params, body), None

    return None, None


_MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB


def read_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    """读取 JSON 请求体。L4：非法 Content-Length 返回 400；超大 body 返回 413。"""
    raw_len = handler.headers.get("Content-Length", "0") or "0"
    try:
        length = int(raw_len)
    except ValueError as exc:
        raise ServiceError("Content-Length 非法", 400) from exc
    if length < 0:
        raise ServiceError("Content-Length 非法", 400)
    if length == 0:
        return {}
    if length > _MAX_BODY_BYTES:
        raise ServiceError("请求体过大", 413)
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ServiceError("请求体不是合法 JSON", 400) from exc
    # P2-1 修复：JSON 数组/字符串等非对象会导致调用方 .get() 抛 AttributeError 转 500。
    if not isinstance(data, dict):
        raise ServiceError("请求体必须是 JSON 对象", 400)
    return data

_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB（长篇 txt 上传上限）


def _parse_content_disposition(value: str) -> tuple[str, str]:
    """解析 Content-Disposition，返回 (name, filename)。

    支持 filename="..."（含转义引号）与 RFC2231 filename*=utf-8''%XX 形式
    （中文文件名）。name 缺失时返回 ""。
    """
    from urllib.parse import unquote

    name = ""
    filename = ""
    # RFC2231 优先（含百分号编码的中文文件名）
    m = re.search(r"filename\*\s*=\s*([^;\s]+)", value, re.IGNORECASE)
    if m:
        raw_fn = m.group(1).strip().strip("\"'")
        if raw_fn.count("'") >= 2:
            _charset, _lang, raw_fn = raw_fn.split("'", 2)
        try:
            filename = unquote(raw_fn, encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            filename = raw_fn
    else:
        m = re.search(r'filename\s*=\s*"((?:[^"\\]|\\.)*)"', value)
        if m:
            filename = m.group(1).replace('\\"', '"').replace("\\\\", "\\")
    m = re.search(r'name\s*=\s*"((?:[^"\\]|\\.)*)"', value)
    if m:
        name = m.group(1)
    # 浏览器直发 raw UTF-8 中文文件名时（头按 latin-1 解码后为乱码），尝试恢复。
    if filename:
        try:
            filename = filename.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return name, filename


def parse_multipart_upload(raw: bytes, content_type: str) -> tuple[str, bytes, dict[str, str]]:
    """解析 multipart/form-data，返回 (文件名, 文件字节, 文本字段)。

    手工边界扫描实现（纯 bytes 操作），替代此前的 stdlib email 解析器：
    实测 email 包解析 100MB 级 body 时产生约 10 倍瞬时内存放大（服务 RSS
    峰值约 3.1GB）；此处改为切片提取，峰值约为 body 的 2 倍（raw + 文件切片）。
    只取第一个带文件名的 part 为上传文件；其余 form-data 文本 part 进 fields。
    """
    m = re.search(r"boundary=([^;]+)", content_type or "", re.IGNORECASE)
    if not m:
        raise ServiceError("Content-Type 缺少 boundary", 400)
    boundary = m.group(1).strip().strip("\"'")
    if not boundary or len(boundary) > 200:
        raise ServiceError("boundary 非法", 400)
    try:
        delim = b"--" + boundary.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ServiceError("boundary 非法", 400) from exc

    if not raw.startswith(delim):
        raise ServiceError("multipart 解析失败", 400)

    filename = ""
    file_bytes = b""
    fields: dict[str, str] = {}
    pos = len(delim)
    while True:
        if raw[pos:pos + 2] == b"--":
            break  # 结束分隔符 --boundary--
        if raw[pos:pos + 2] != b"\r\n":
            raise ServiceError("multipart 解析失败", 400)
        pos += 2

        hdr_end = raw.find(b"\r\n\r\n", pos)
        if hdr_end < 0:
            raise ServiceError("multipart 解析失败", 400)
        try:
            headers = raw[pos:hdr_end].decode("latin-1")
        except Exception as exc:  # noqa: BLE001
            raise ServiceError("multipart 解析失败", 400) from exc
        body_start = hdr_end + 4

        next_d = raw.find(b"\r\n" + delim, body_start)
        if next_d < 0:
            raise ServiceError("multipart 解析失败", 400)
        body = raw[body_start:next_d]
        pos = next_d + 2 + len(delim)  # 越过 \r\n--boundary，回到循环头部

        disp = ""
        part_ctype = ""
        for line in headers.split("\r\n"):
            low = line.lower()
            if low.startswith("content-disposition:"):
                disp = line.split(":", 1)[1]
            elif low.startswith("content-type:"):
                part_ctype = line.split(":", 1)[1].strip()
        pname, pfilename = _parse_content_disposition(disp)
        if pfilename and not filename:
            filename = pfilename
            file_bytes = body
        elif not pfilename and pname and "form-data" in disp.lower():
            charset = "utf-8"
            cm = re.search(r"charset=([^\s;]+)", part_ctype, re.IGNORECASE)
            if cm:
                charset = cm.group(1).strip().strip("\"'")
            try:
                fields[pname] = body.decode(charset, errors="replace")
            except LookupError:
                fields[pname] = body.decode("utf-8", errors="replace")
    if not filename:
        raise ServiceError("未找到上传文件（form 字段名应为 file）", 400)
    return filename, file_bytes, fields
