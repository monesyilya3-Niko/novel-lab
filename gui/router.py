"""REST 路由表 + 请求分发 + JSON 序列化 + 统一错误码。

响应统一包裹：``{"code": 0, "data": ..., "message": ""}``。
code 约定：0 成功；400 参数错误；404 资源不存在；409 状态冲突；500 内部错误。
"""
from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler
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
        return err(400, "offset/limit 必须为整数")
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


def read_body(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    """读取 JSON 请求体。"""
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ServiceError("请求体不是合法 JSON", 400)
