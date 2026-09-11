"""REST 路由表 + 请求分发 + JSON 序列化 + 统一错误码。

响应统一包裹：``{"code": 0, "data": ..., "message": ""}``。
code 约定：0 成功；400 参数错误；404 资源不存在；409 状态冲突；500 内部错误。
"""
from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from gui import engine_adapter, services
from gui.services import ServiceError


# ---------------------------------------------------------------------------
# 响应工具
# ---------------------------------------------------------------------------

def ok(data: Any = None) -> Dict[str, Any]:
    return {"code": 0, "data": data, "message": ""}


def err(code: int, message: str) -> Dict[str, Any]:
    return {"code": code, "data": None, "message": message}


def _json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


# ---------------------------------------------------------------------------
# 处理器
# ---------------------------------------------------------------------------

def _h_import(params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    path = (body or {}).get("path", "")
    if not path:
        raise ServiceError("缺少 path 参数", 400)
    # M8：API 层限制导入路径在项目根内，防止任意文件读取（纵深防御）。
    from gui import config as _config
    resolved = Path(path).resolve()
    root = _config.ROOT_DIR.resolve()
    if not resolved.is_relative_to(root):
        raise ServiceError("导入路径必须在项目目录内", 403)
    batch_size = (body or {}).get("batch_size")
    return ok(services.import_book(path, batch_size))


def _h_get_book(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    book_id = params["book_id"]
    return ok(services.get_book(book_id))


def _h_get_chapter(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    book_id = params["book_id"]
    idx = int(params["idx"])
    return ok(services.get_chapter(book_id, idx))


def _h_split_batch(params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    book_id = params["book_id"]
    idx = int(params["idx"])
    batch_size = (body or {}).get("batch_size")
    return ok(services.split_chapter_batches(book_id, idx, batch_size))


def _h_start(params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    book_id = (body or {}).get("book_id", "")
    genre = (body or {}).get("genre", "unknown")
    model_id = (body or {}).get("model_id")
    batch_size = (body or {}).get("batch_size")
    if not book_id:
        raise ServiceError("缺少 book_id", 400)
    return ok(services.start_analysis(book_id, genre, model_id, batch_size))


def _h_pause(params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    book_id = (body or {}).get("book_id", "")
    if not book_id:
        raise ServiceError("缺少 book_id", 400)
    return ok(services.pause(book_id))


def _h_resume(params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    book_id = (body or {}).get("book_id", "")
    if not book_id:
        raise ServiceError("缺少 book_id", 400)
    genre = (body or {}).get("genre")
    model_id = (body or {}).get("model_id")
    return ok(services.resume(book_id, genre, model_id))


def _h_retry_failed(params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    book_id = (body or {}).get("book_id", "")
    if not book_id:
        raise ServiceError("缺少 book_id", 400)
    return ok(services.retry_failed(book_id))


def _h_status(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    book_id = params.get("book_id")
    return ok(services.get_status(book_id))


def _h_asset(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    book_id = params.get("book_id", "")
    if not book_id:
        raise ServiceError("缺少 book_id", 400)
    try:
        chapter_index = int(params.get("chapter", 0))
        batch_index = int(params.get("batch", 0))
    except (TypeError, ValueError):
        raise ServiceError("chapter/batch 必须为整数", 400)
    pass_name = params.get("pass", "")
    if not pass_name:
        raise ServiceError("缺少 pass", 400)
    return ok(services.get_asset(book_id, chapter_index, batch_index, pass_name))


def _h_models(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    return ok({"models": engine_adapter.list_models(),
               "any_configured": engine_adapter.any_model_configured()})


# ---------------------------------------------------------------------------
# 阶段一新增端点
# ---------------------------------------------------------------------------

def _h_overview(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    return ok(services.get_overview())


def _h_list_assets(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    kind = params.get("kind") or None
    genre = params.get("genre") or None
    book_id = params.get("book_id") or None
    try:
        offset = int(params.get("offset", "0") or "0")
        limit = int(params.get("limit", "50") or "50")
    except ValueError:
        raise ServiceError("offset/limit 必须为整数", 400)
    return ok(services.list_assets(kind, genre, book_id, offset, limit))


def _h_stats(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    return ok(services.get_stats())


def _h_asset_detail(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    kind = params["kind"]
    asset_id = params["id"]
    return ok(services.get_asset_detail(kind, asset_id))


def _h_list_reports(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    return ok(services.list_reports())


def _h_get_report(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    report_id = params["id"]
    return ok(services.get_report(report_id))


def _h_book_results(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    book_id = params["book_id"]
    return ok(services.get_book_results(book_id))


def _h_book_scores(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    book_id = params["book_id"]
    return ok(services.get_book_scores(book_id))


def _h_full_analysis(params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    book_id = (body or {}).get("book_id", "")
    genre = (body or {}).get("genre", "unknown")
    model_id = (body or {}).get("model_id")
    if not book_id:
        raise ServiceError("缺少 book_id", 400)
    return ok(services.run_full_analysis(book_id, genre, model_id))


# ---------------------------------------------------------------------------
# W15 阶段二：写作（M2）+ 质检（M3）端点
# ---------------------------------------------------------------------------

def _h_writing_projects(_params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import writing_service
    return ok(writing_service.list_projects())


def _h_writing_inject(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
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
    except (TypeError, ValueError):
        raise ServiceError(f"{field} 必须为整数", 400)


def _h_writing_generate(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
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


def _h_writing_task(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import writing_service
    return ok(writing_service.task_state(params["task_id"]))


def _h_writing_import_chapter(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import writing_service
    b = body or {}
    return ok(writing_service.import_chapter(
        project=b.get("project", ""), chapter_no=_safe_int(b.get("chapter_no"), 0, "chapter_no"),
        content=b.get("content", ""), novel_name=b.get("novel_name"),
        voice=b.get("voice"), genre_pack=b.get("genre_pack")))


def _h_writing_score(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import writing_service
    b = body or {}
    return ok(writing_service.score(
        voice=b.get("voice", ""), text=b.get("text"),
        chapter_path=b.get("chapter_path"), label=b.get("label", "")))


def _h_writing_assemble(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import writing_service
    b = body or {}
    return ok(writing_service.assemble(
        name=b.get("name", ""), genre=b.get("genre", ""),
        skip_craft=bool(b.get("skip_craft"))))


def _h_writing_assemble_candidates(_params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import writing_service
    return ok(writing_service.assemble_candidates())


def _h_quality_check(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import quality_service
    b = body or {}
    return ok(quality_service.check(
        target=b.get("target"), text=b.get("text"),
        voice=b.get("voice"), genre_pack=b.get("genre_pack")))


def _h_quality_book(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import quality_service
    b = body or {}
    return ok(quality_service.book(
        target=b.get("target"), text=b.get("text"), voice=b.get("voice")))


def _h_quality_qc(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import quality_service
    b = body or {}
    return ok(quality_service.qc(
        target=b.get("target"), text=b.get("text"), voice=b.get("voice"),
        genre_pack=b.get("genre_pack"), asset=b.get("asset"), book=b.get("book"),
        novel_dir=b.get("novel_dir"), llm_hook=bool(b.get("llm_hook"))))


def _h_quality_task(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import quality_service
    return ok(quality_service.qc_task_state(params["task_id"]))


def _h_quality_reports(_params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import quality_service
    return ok(quality_service.list_qc_reports())


# --- M5 系统与合规 handlers ---

def _h_system_status(_params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import system_service
    return ok(system_service.system_status())


def _h_compliance_scan(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import system_service
    b = body or {}
    return ok(system_service.compliance_scan(
        voice=b.get("voice"), book_path=b.get("book_path")))


def _h_model_info(_params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import system_service
    return ok(system_service.model_info())


def _h_get_settings(_params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import system_service
    return ok(system_service.get_settings())


def _h_update_settings(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import system_service
    return ok(system_service.update_settings(body or {}))


def _h_reset_settings(_params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import system_service
    return ok(system_service.reset_settings())


# --- 模型管理 handlers ---

def _h_list_models(_params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import model_service
    return ok(model_service.list_models())


def _h_get_model(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import model_service
    return ok(model_service.get_model(params["model_id"]))


def _h_add_model(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import model_service
    return ok(model_service.add_model(body or {}))


def _h_update_model(params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import model_service
    return ok(model_service.update_model(params["model_id"], body or {}))


def _h_delete_model(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import model_service
    return ok(model_service.delete_model(params["model_id"]))


def _h_set_model_key(params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import model_service
    b = body or {}
    return ok(model_service.set_api_key(params["model_id"], b.get("api_key", "")))


def _h_test_model(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import model_service
    return ok(model_service.test_model(params["model_id"]))


def _h_get_presets(_params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import model_service
    return ok(model_service.get_presets())


# --- 文风集成 handlers ---

def _h_analyze_style(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import style_service
    b = body or {}
    return ok(style_service.analyze_style(b.get("text", ""), b.get("name", "")))


def _h_save_style(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import style_service
    b = body or {}
    return ok(style_service.save_style(b.get("name", ""), b.get("style_card", {})))


def _h_list_styles(_params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import style_service
    return ok({"styles": style_service.list_styles()})


def _h_get_style(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import style_service
    return ok(style_service.get_style(params["name"]))


def _h_delete_style(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import style_service
    return ok(style_service.delete_style(params["name"]))


def _h_apply_style(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import style_service
    b = body or {}
    return ok(style_service.apply_style_prompt(b.get("style_name", ""), b.get("base_prompt", "")))


# --- 多平台适配 handlers ---

def _h_list_platforms(_params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import platform_service
    return ok({"platforms": platform_service.list_platforms()})


def _h_get_platform(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import platform_service
    return ok(platform_service.get_platform(params["platform_id"]))


def _h_check_compliance(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import platform_service
    b = body or {}
    return ok(platform_service.check_chapter_compliance(
        b.get("platform_id", ""), b.get("chapter_text", ""), b.get("chapter_title", "")))


def _h_format_chapter(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import platform_service
    b = body or {}
    return ok(platform_service.format_chapter(
        b.get("platform_id", ""), int(b.get("chapter_num", 1)),
        b.get("title", ""), b.get("content", "")))


def _h_export_book(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import platform_service
    b = body or {}
    return ok(platform_service.export_book_for_platform(
        b.get("platform_id", ""), b.get("book_dir", "")))


# --- M1 高级分析 handlers ---

def _h_distill_status(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import advanced_service
    return ok(advanced_service.distill_status(params["genre"]))


def _h_distill_run(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import advanced_service
    return ok(advanced_service.distill_genre(params["genre"]))


def _h_aggregate(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import advanced_service
    return ok(advanced_service.aggregate_genre(params["genre"]))


def _h_batch_status(_params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import advanced_service
    return ok(advanced_service.batch_status())


# --- M4 资产写入 handlers ---

def _h_asset_update(params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import advanced_service
    b = body or {}
    return ok(advanced_service.update_asset(
        params["kind"], params["id"], b.get("content", {})))


def _h_asset_delete(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import advanced_service
    return ok(advanced_service.delete_asset(params["kind"], params["id"]))


def _h_asset_create(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import advanced_service
    b = body or {}
    return ok(advanced_service.create_asset(
        b.get("name", ""), b.get("kind", ""), b.get("content", {})))


# ---------------------------------------------------------------------------
# 路由表
# ---------------------------------------------------------------------------

# (method, 正则, handler)。命名捕获组通过正则分组名传入 params。
ROUTES: list[Tuple[str, re.Pattern, Callable[[Dict, Dict], Dict]]] = [
    ("POST", re.compile(r"^/api/import$"), _h_import),
    ("GET", re.compile(r"^/api/book/(?P<book_id>[^/]+)$"), _h_get_book),
    ("GET", re.compile(r"^/api/book/(?P<book_id>[^/]+)/chapter/(?P<idx>\d+)$"), _h_get_chapter),
    ("POST", re.compile(r"^/api/book/(?P<book_id>[^/]+)/chapter/(?P<idx>\d+)/batch$"), _h_split_batch),
    ("POST", re.compile(r"^/api/analyze/start$"), _h_start),
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
]


def dispatch(method: str, path: str, body: Dict[str, Any], query: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
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


def read_body(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    """读取 JSON 请求体。L4：非法 Content-Length 返回 400；超大 body 返回 413。"""
    raw_len = handler.headers.get("Content-Length", "0") or "0"
    try:
        length = int(raw_len)
    except ValueError:
        raise ServiceError("Content-Length 非法", 400)
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
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ServiceError("请求体不是合法 JSON", 400)
