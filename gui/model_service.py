"""模型管理服务层：自定义 API/模型的增删改查与测试。

分层边界：只经 ``engine_adapter`` 触碰 scripts/，不直接 import llm_client。
（铁律：只有 gui/engine_adapter.py 可以 import scripts/）
"""
from __future__ import annotations

import os
import re
from typing import Any

from gui import engine_adapter
from gui.services import ServiceError


def _model_has_key(secrets: dict[str, Any], model_id: str, model: dict[str, Any]) -> bool:
    """模型是否有可用密钥：secret store 有值，或 api_key_env 指向的环境变量真实存在。

    注意：只看 ``api_key_env`` 名称不看环境变量是否设置会误报（P1-B2）。
    """
    if secrets.get(model_id):
        return True
    env_name = model.get("api_key_env")
    return bool(env_name and os.environ.get(env_name))


def _validate_model_id(model_id: str) -> str:
    """校验模型 ID：非空、无路径分隔符。"""
    if not isinstance(model_id, str) or not model_id.strip():
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
    if not isinstance(url, str) or not url.strip():
        raise ServiceError("base_url 不能为空", 400)
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise ServiceError("base_url 必须以 http:// 或 https:// 开头", 400)
    return url.rstrip("/")


def _validate_timeout(value):
    """校验超时秒数：1–3600 的整数（bool/非整数/越界一律 400）。"""
    if isinstance(value, bool):
        raise ServiceError("timeout 必须为 1–3600 的整数（秒）", 400)
    if isinstance(value, float):
        if not value.is_integer():
            raise ServiceError("timeout 必须为 1–3600 的整数（秒）", 400)
        value = int(value)
    if not isinstance(value, int) or not 1 <= value <= 3600:
        raise ServiceError("timeout 必须为 1–3600 的整数（秒）", 400)
    return value


def list_models() -> dict[str, Any]:
    """列出已配置模型（脱敏展示）。"""
    cfg = engine_adapter.models_load()
    secrets = engine_adapter.secrets_load()

    models = []
    for mid, m in cfg.get("models", {}).items():
        has_key = _model_has_key(secrets, mid, m)
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


def get_model(model_id: str) -> dict[str, Any]:
    """获取单个模型详情（脱敏）。"""
    mid = _validate_model_id(model_id)
    cfg = engine_adapter.models_load()
    secrets = engine_adapter.secrets_load()

    m = cfg.get("models", {}).get(mid)
    if not m:
        raise ServiceError(f"模型不存在: {model_id}", 404)

    has_key = _model_has_key(secrets, mid, m)
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


def add_model(body: dict[str, Any]) -> dict[str, Any]:
    """添加新模型。"""
    if not body or not isinstance(body, dict):
        raise ServiceError("请求体必须为 JSON 对象", 400)

    mid = _validate_model_id(body.get("id", ""))
    protocol = _validate_protocol(body.get("protocol", "openai"))
    base_url = _validate_base_url(body.get("base_url", ""))
    model_name = body.get("model_name", "")
    if not isinstance(model_name, str) or not model_name.strip():
        raise ServiceError("model_name 不能为空", 400)
    model_name = model_name.strip()

    cfg = engine_adapter.models_load()

    if mid in cfg.get("models", {}):
        raise ServiceError(f"模型已存在: {mid}", 409)

    model_entry: dict[str, Any] = {
        "label": body.get("label", mid),
        "protocol": protocol,
        "base_url": base_url,
        "model_name": model_name,
        "roles": body.get("roles", []),
        "json_mode": bool(body.get("json_mode", False)),
        "timeout": _validate_timeout(body.get("timeout", 180)),
    }

    # 可选字段
    for opt in ("api_key_env", "context_window", "note", "anthropic_version"):
        if body.get(opt):
            model_entry[opt] = body[opt]
    if body.get("extra_headers") and isinstance(body["extra_headers"], dict):
        model_entry["extra_headers"] = body["extra_headers"]

    cfg.setdefault("models", {})[mid] = model_entry
    engine_adapter.models_save(cfg)

    # 如果提供了 API key，同时保存到 secrets
    api_key = body.get("api_key", "").strip()
    if api_key:
        secrets = engine_adapter.secrets_load()
        secrets[mid] = api_key
        engine_adapter.secrets_save(secrets)

    return get_model(mid)


def update_model(model_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """更新模型配置。"""
    mid = _validate_model_id(model_id)
    if not body or not isinstance(body, dict):
        raise ServiceError("请求体必须为 JSON 对象", 400)

    cfg = engine_adapter.models_load()

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
        m["timeout"] = _validate_timeout(body["timeout"])
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

    engine_adapter.models_save(cfg)

    # 更新 API key
    api_key = body.get("api_key", "").strip()
    if api_key:
        secrets = engine_adapter.secrets_load()
        secrets[mid] = api_key
        engine_adapter.secrets_save(secrets)

    return get_model(mid)


def delete_model(model_id: str) -> dict[str, Any]:
    """删除模型。"""
    mid = _validate_model_id(model_id)
    cfg = engine_adapter.models_load()

    if mid not in cfg.get("models", {}):
        raise ServiceError(f"模型不存在: {model_id}", 404)

    del cfg["models"][mid]
    # 清除角色绑定
    for role, bound_id in list(cfg.get("roles", {}).items()):
        if bound_id == mid:
            del cfg["roles"][role]
    engine_adapter.models_save(cfg)

    # 清除密钥
    secrets = engine_adapter.secrets_load()
    if mid in secrets:
        del secrets[mid]
        engine_adapter.secrets_save(secrets)

    return {"deleted": mid}


def set_api_key(model_id: str, api_key: str) -> dict[str, Any]:
    """设置/更新 API Key。"""
    mid = _validate_model_id(model_id)
    if not api_key or not api_key.strip():
        raise ServiceError("api_key 不能为空", 400)

    cfg = engine_adapter.models_load()
    if mid not in cfg.get("models", {}):
        raise ServiceError(f"模型不存在: {model_id}", 404)

    secrets = engine_adapter.secrets_load()
    secrets[mid] = api_key.strip()
    engine_adapter.secrets_save(secrets)

    return {"id": mid, "has_key": True}


def test_model(model_id: str) -> dict[str, Any]:
    """测试模型连通性。"""
    mid = _validate_model_id(model_id)

    try:
        result = engine_adapter.model_test(mid)
        return {"id": mid, "success": True, "result": result}
    except Exception as e:
        return {"id": mid, "success": False, "error": str(e)}


def get_presets() -> dict[str, Any]:
    """获取内置服务商预设。"""
    return engine_adapter.model_presets()
