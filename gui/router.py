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


def _h_writing_generate(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import writing_service
    b = body or {}
    return ok(writing_service.generate(
        voice=b.get("voice", ""), project=b.get("project", ""),
        chapter_no=int(b.get("chapter_no", 0)), task=b.get("task", ""),
        novel_name=b.get("novel_name"), prompt=b.get("prompt"),
        genre_pack=b.get("genre_pack"), words=int(b.get("words", 2400)),
        target_score=int(b.get("target_score", 90)),
        quality_target=b.get("quality_target"),
        save_prompt=bool(b.get("save_prompt"))))


def _h_writing_task(params: Dict[str, Any], _body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import writing_service
    return ok(writing_service.task_state(params["task_id"]))


def _h_writing_import_chapter(_params: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    from gui import writing_service
    b = body or {}
    return ok(writing_service.import_chapter(
        project=b.get("project", ""), chapter_no=int(b.get("chapter_no", 0)),
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
            # 合并 query string 参数
            params.update(query)
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
