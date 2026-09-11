"""模型管理服务层：自定义 API/模型的增删改查与测试。

分层边界：只经 ``engine_adapter`` 触碰 scripts/，不直接 import llm_client。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from gui import config, engine_adapter
from gui.services import ServiceError


def _get_llm_client():
    """延迟获取 llm_client 模块（经 engine_adapter 的 sys.path 注入）。"""
    import sys
    if str(config.SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(config.SCRIPTS_DIR))
    import llm_client
    return llm_client


def _validate_model_id(model_id: str) -> str:
    """校验模型 ID：非空、无路径分隔符。"""
    if not model_id or not model_id.strip():
        raise ServiceError("模型 ID 不能为空", 400)
    mid = model_id.strip()
    if any(ch in mid for ch in ("/", "\\", "..", "\x00", "\n", "\r", " ")):
        raise ServiceError(f"非法模型 ID: {model_id!r}", 400)
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", mid):
        raise ServiceError(f"模型 ID 只允许字母/数字/下划线/连字符: {model_id!r}", 400)
    return mid


def _validate_protocol(protocol: str) -> str:
    """校验协议类型。"""
    allowed = {"openai", "anthropic", "ollama"}
    if protocol not in allowed:
        raise ServiceError(f"协议必须为 {allowed} 之一，收到: {protocol!r}", 400)
    return protocol


def _validate_base_url(url: str) -> str:
    """校验 base_url。"""
    if not url or not url.strip():
        raise ServiceError("base_url 不能为空", 400)
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise ServiceError("base_url 必须以 http:// 或 https:// 开头", 400)
    return url.rstrip("/")


def list_models() -> Dict[str, Any]:
    """列出已配置模型（脱敏展示）。"""
    llm = _get_llm_client()
    cfg = llm.load_models()
    secrets = llm.load_secrets()

    models = []
    for mid, m in cfg.get("models", {}).items():
        has_key = bool(secrets.get(mid)) or bool(m.get("api_key_env"))
        models.append({
            "id": mid,
            "label": m.get("label", mid),
            "protocol": m.get("protocol", "openai"),
            "base_url": m.get("base_url", ""),
            "model_name": m.get("model_name", ""),
            "roles": m.get("roles", []),
            "has_key": has_key,
            "context_window": m.get("context_window"),
            "note": m.get("note", ""),
        })

    return {
        "models": models,
        "roles": cfg.get("roles", {}),
        "routes": cfg.get("routes", {}),
        "total": len(models),
    }


def get_model(model_id: str) -> Dict[str, Any]:
    """获取单个模型详情（脱敏）。"""
    mid = _validate_model_id(model_id)
    llm = _get_llm_client()
    cfg = llm.load_models()
    secrets = llm.load_secrets()

    m = cfg.get("models", {}).get(mid)
    if not m:
        raise ServiceError(f"模型不存在: {model_id}", 404)

    has_key = bool(secrets.get(mid)) or bool(m.get("api_key_env"))
    return {
        "id": mid,
        "label": m.get("label", mid),
        "protocol": m.get("protocol", "openai"),
        "base_url": m.get("base_url", ""),
        "model_name": m.get("model_name", ""),
        "roles": m.get("roles", []),
        "has_key": has_key,
        "api_key_env": m.get("api_key_env", ""),
        "context_window": m.get("context_window"),
        "json_mode": m.get("json_mode", False),
        "timeout": m.get("timeout", 180),
        "note": m.get("note", ""),
        "extra_headers": m.get("extra_headers", {}),
    }


def add_model(body: Dict[str, Any]) -> Dict[str, Any]:
    """添加新模型。"""
    if not body or not isinstance(body, dict):
        raise ServiceError("请求体必须为 JSON 对象", 400)

    mid = _validate_model_id(body.get("id", ""))
    protocol = _validate_protocol(body.get("protocol", "openai"))
    base_url = _validate_base_url(body.get("base_url", ""))
    model_name = body.get("model_name", "").strip()
    if not model_name:
        raise ServiceError("model_name 不能为空", 400)

    llm = _get_llm_client()
    cfg = llm.load_models()

    if mid in cfg.get("models", {}):
        raise ServiceError(f"模型已存在: {mid}", 409)

    model_entry: Dict[str, Any] = {
        "label": body.get("label", mid),
        "protocol": protocol,
        "base_url": base_url,
        "model_name": model_name,
        "roles": body.get("roles", []),
        "json_mode": bool(body.get("json_mode", False)),
        "timeout": int(body.get("timeout", 180)),
    }

    # 可选字段
    for opt in ("api_key_env", "context_window", "note", "anthropic_version"):
        if body.get(opt):
            model_entry[opt] = body[opt]
    if body.get("extra_headers") and isinstance(body["extra_headers"], dict):
        model_entry["extra_headers"] = body["extra_headers"]

    cfg.setdefault("models", {})[mid] = model_entry
    llm.save_models(cfg)

    # 如果提供了 API key，同时保存到 secrets
    api_key = body.get("api_key", "").strip()
    if api_key:
        secrets = llm.load_secrets()
        secrets[mid] = api_key
        llm.save_secrets(secrets)

    return get_model(mid)


def update_model(model_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """更新模型配置。"""
    mid = _validate_model_id(model_id)
    if not body or not isinstance(body, dict):
        raise ServiceError("请求体必须为 JSON 对象", 400)

    llm = _get_llm_client()
    cfg = llm.load_models()

    if mid not in cfg.get("models", {}):
        raise ServiceError(f"模型不存在: {model_id}", 404)

    m = cfg["models"][mid]

    # 可更新字段
    if "label" in body:
        m["label"] = str(body["label"]).strip()
    if "protocol" in body:
        m["protocol"] = _validate_protocol(body["protocol"])
    if "base_url" in body:
        m["base_url"] = _validate_base_url(body["base_url"])
    if "model_name" in body:
        name = str(body["model_name"]).strip()
        if not name:
            raise ServiceError("model_name 不能为空", 400)
        m["model_name"] = name
    if "roles" in body:
        m["roles"] = body["roles"] if isinstance(body["roles"], list) else []
    if "json_mode" in body:
        m["json_mode"] = bool(body["json_mode"])
    if "timeout" in body:
        m["timeout"] = int(body["timeout"])
    for opt in ("api_key_env", "context_window", "note", "anthropic_version"):
        if opt in body:
            if body[opt]:
                m[opt] = body[opt]
            else:
                m.pop(opt, None)
    if "extra_headers" in body:
        if body["extra_headers"] and isinstance(body["extra_headers"], dict):
            m["extra_headers"] = body["extra_headers"]
        else:
            m.pop("extra_headers", None)

    llm.save_models(cfg)

    # 更新 API key
    api_key = body.get("api_key", "").strip()
    if api_key:
        secrets = llm.load_secrets()
        secrets[mid] = api_key
        llm.save_secrets(secrets)

    return get_model(mid)


def delete_model(model_id: str) -> Dict[str, Any]:
    """删除模型。"""
    mid = _validate_model_id(model_id)
    llm = _get_llm_client()
    cfg = llm.load_models()

    if mid not in cfg.get("models", {}):
        raise ServiceError(f"模型不存在: {model_id}", 404)

    del cfg["models"][mid]
    # 清除角色绑定
    for role, bound_id in list(cfg.get("roles", {}).items()):
        if bound_id == mid:
            del cfg["roles"][role]
    llm.save_models(cfg)

    # 清除密钥
    secrets = llm.load_secrets()
    if mid in secrets:
        del secrets[mid]
        llm.save_secrets(secrets)

    return {"deleted": mid}


def set_api_key(model_id: str, api_key: str) -> Dict[str, Any]:
    """设置/更新 API Key。"""
    mid = _validate_model_id(model_id)
    if not api_key or not api_key.strip():
        raise ServiceError("api_key 不能为空", 400)

    llm = _get_llm_client()
    cfg = llm.load_models()
    if mid not in cfg.get("models", {}):
        raise ServiceError(f"模型不存在: {model_id}", 404)

    secrets = llm.load_secrets()
    secrets[mid] = api_key.strip()
    llm.save_secrets(secrets)

    return {"id": mid, "has_key": True}


def test_model(model_id: str) -> Dict[str, Any]:
    """测试模型连通性。"""
    mid = _validate_model_id(model_id)
    llm = _get_llm_client()

    try:
        result = llm.test_model(mid)
        return {"id": mid, "success": True, "result": result}
    except Exception as e:
        return {"id": mid, "success": False, "error": str(e)}


def get_presets() -> Dict[str, Any]:
    """获取内置服务商预设。"""
    import sys
    if str(config.SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(config.SCRIPTS_DIR))
    import model_config
    return {"presets": model_config.PRESETS}
