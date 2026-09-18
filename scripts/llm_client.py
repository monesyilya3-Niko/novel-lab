#!/usr/bin/env python3
"""
统一 LLM 调用层 — 零依赖（仅标准库）

设计要点：
1. 密钥与配置分离存储，配置可进 git，密钥不可
2. 三种协议：openai 兼容（通吃绝大多数）/ anthropic / ollama
3. 按任务路由模型：拆书四遍各自可指定不同模型
4. 失败可回退到备用模型：候选链由 resolve_fallback_chain 给出
   （主模型配置的 fallback → default 角色 → 其余已配置模型），
   chat(allow_fallback=True) 逐个候选重试；不可重试的错误（401/403/余额不足）
   立即换候选。连通性测试 test_model 显式关闭回退，避免「备用通了」被误报成
   「主模型通了」。
"""
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
MODELS_FILE = CONFIG_DIR / "models.json"
SECRETS_FILE = CONFIG_DIR / ".secrets.json"

# 任务默认路由。抽取类任务用便宜模型，判断类任务用强模型
DEFAULT_ROUTES = {
    "pass1_structure": "cheap",
    "pass2_character": "cheap",
    "pass3_style": "strong",
    "pass4_commercial": "strong",
    "pass5_aggregate": "strong",
    "writing": "strong",
    "consistency_check": "cheap",
}


class LLMError(Exception):
    pass


# LLM 不可用时仍可本地完成的能力（评估报告 item 10：显式降级提示）
LLM_DEGRADED_FEATURES = (
    "拆书分析 pass1-5（LLM 扫描）",
    "写作台 generate / novel 写作（LLM 正文生成）",
    "qc --llm-hook 因果二次判定",
    "模型连通性测试与额度相关操作",
)
LLM_STILL_AVAILABLE = (
    "纯算法质检（novel 检查 / 质检 / qc 默认路径）",
    "资产校验、注入 prompt 组装、组装 CLI（无模型可用）",
    "章节加载 / 重复检测 / 设定与逻辑一致性纯算法检测",
)


def describe_llm_degradation(error) -> str:
    """把 LLM 失败原因翻译成「哪些能力不可用 / 哪些仍可用」的可读提示。"""
    err = str(error or "")
    low = err.lower()
    if "尚未配置" in err:
        reason = "尚未配置外部模型"
        hint = "运行: python scripts/model_config.py add"
    elif ("insufficient" in low or "余额" in err
          or "HTTP 403" in err or "HTTP 401" in err):
        reason = "模型额度/权限不足"
        hint = ("充值或更换可用模型；可配置备用链: "
                "python scripts/model_config.py fallback <主模型> <备用...>")
    elif "连接失败" in err or "timed out" in low or "timeout" in low:
        reason = "网络连接失败"
        hint = "检查网络/代理后重试；配置备用模型可提高可用性"
    else:
        reason = "模型调用失败"
        hint = "查看原始错误；必要时 python novel.py 模型 --test <id>"

    degraded = "\n".join(f"  - {x}" for x in LLM_DEGRADED_FEATURES)
    still = "\n".join(f"  - {x}" for x in LLM_STILL_AVAILABLE)
    return (
        f"[LLM 降级] {reason}：{err}\n"
        f"  处理建议: {hint}\n"
        f"  当前不可用（依赖外部模型）:\n{degraded}\n"
        f"  仍然可用（纯本地）:\n{still}"
    )


# --------------------------------------------------------------------------
# 配置读写
# --------------------------------------------------------------------------

def _ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def any_model_configured() -> bool:
    """是否配置了至少一个外部模型。无模型时 pipeline 走 WorkBuddy 内置智能模式。"""
    try:
        return bool(load_models().get("models"))
    except Exception:
        return False


def load_models() -> dict:
    """读取模型配置。文件不存在或损坏时返回空骨架"""
    if not MODELS_FILE.exists():
        return {"version": 1, "models": {}, "roles": {}, "routes": dict(DEFAULT_ROUTES)}
    try:
        with open(MODELS_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            raise ValueError("models.json 顶层不是对象")
    except (json.JSONDecodeError, OSError, ValueError):
        return {"version": 1, "models": {}, "roles": {}, "routes": dict(DEFAULT_ROUTES)}
    cfg.setdefault("models", {})
    cfg.setdefault("roles", {})
    cfg.setdefault("routes", dict(DEFAULT_ROUTES))
    return cfg


def save_models(cfg: dict):
    _ensure_config_dir()
    with open(MODELS_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_secrets() -> dict:
    import secret_store
    return secret_store.load_secrets()


def save_secrets(secrets: dict):
    import secret_store
    secret_store.save_secrets(secrets)


def resolve_api_key(model_id: str, model: dict) -> str:
    """
    密钥解析优先级：
    1. 环境变量（model.api_key_env 指定的变量名）
    2. .secrets.json
    3. 空串（本地模型如 ollama 通常不需要）
    """
    env_name = model.get("api_key_env")
    if env_name:
        val = os.environ.get(env_name)
        if val:
            return val
    return load_secrets().get(model_id, "")


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def _post_json(url: str, payload: dict, headers: dict, timeout: int = 180) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:600]
        raise LLMError(f"HTTP {e.code}: {body}") from None
    except urllib.error.URLError as e:
        raise LLMError(f"连接失败: {e.reason}") from None


# --------------------------------------------------------------------------
# 协议适配
# --------------------------------------------------------------------------

def _call_openai_compatible(model: dict, api_key: str, system: str,
                            user: str, max_tokens: int, temperature: float) -> dict:
    base = model["base_url"].rstrip("/")
    url = base + "/chat/completions" if not base.endswith("/chat/completions") else base
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    payload = {
        "model": model["model_name"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if model.get("json_mode"):
        payload["response_format"] = {"type": "json_object"}
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    for k, v in (model.get("extra_headers") or {}).items():
        headers[k] = v

    raw = _post_json(url, payload, headers, model.get("timeout", 180))
    try:
        text = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise LLMError(f"响应格式异常: {json.dumps(raw, ensure_ascii=False)[:400]}")
    usage = raw.get("usage") or {}
    return {
        "text": text,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }


def _call_anthropic(model: dict, api_key: str, system: str,
                    user: str, max_tokens: int, temperature: float) -> dict:
    base = model["base_url"].rstrip("/")
    url = base + "/messages" if not base.endswith("/messages") else base
    payload = {
        "model": model["model_name"],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        payload["system"] = system
    headers = {
        "x-api-key": api_key,
        "anthropic-version": model.get("anthropic_version", "2023-06-01"),
    }
    for k, v in (model.get("extra_headers") or {}).items():
        headers[k] = v

    raw = _post_json(url, payload, headers, model.get("timeout", 180))
    try:
        text = "".join(b.get("text", "") for b in raw["content"])
    except (KeyError, TypeError):
        raise LLMError(f"响应格式异常: {json.dumps(raw, ensure_ascii=False)[:400]}")
    usage = raw.get("usage") or {}
    return {
        "text": text,
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
    }


def _call_ollama(model: dict, api_key: str, system: str,
                 user: str, max_tokens: int, temperature: float) -> dict:
    base = model["base_url"].rstrip("/")
    url = base + "/api/chat" if not base.endswith("/api/chat") else base
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    payload = {
        "model": model["model_name"],
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            # 拆书是长上下文刚需，默认拉高
            "num_ctx": model.get("num_ctx", 32768),
        },
    }
    raw = _post_json(url, payload, {}, model.get("timeout", 600))
    try:
        text = raw["message"]["content"]
    except KeyError:
        raise LLMError(f"响应格式异常: {json.dumps(raw, ensure_ascii=False)[:400]}")
    return {
        "text": text,
        "prompt_tokens": raw.get("prompt_eval_count", 0),
        "completion_tokens": raw.get("eval_count", 0),
    }


PROTOCOL_HANDLERS = {
    "openai": _call_openai_compatible,
    "anthropic": _call_anthropic,
    "ollama": _call_ollama,
}


# --------------------------------------------------------------------------
# 对外接口
# --------------------------------------------------------------------------

def resolve_model(task: Optional[str] = None, model_id: Optional[str] = None) -> tuple:
    """
    解析该用哪个模型。
    显式 model_id > 任务路由 > 角色默认 > 报错
    返回 (model_id, model_dict)
    """
    cfg = load_models()
    models = cfg["models"]
    if not models:
        raise LLMError("尚未配置任何模型。运行: python model_config.py add")

    if model_id:
        if model_id not in models:
            raise LLMError(f"模型 '{model_id}' 不存在。已配置: {', '.join(models)}")
        return model_id, models[model_id]

    if task:
        role = cfg["routes"].get(task)
        if role:
            mid = cfg["roles"].get(role)
            if mid and mid in models:
                return mid, models[mid]

    # 回退：找 default 角色，再回退第一个
    mid = cfg["roles"].get("default")
    if mid and mid in models:
        return mid, models[mid]
    first = next(iter(models))
    return first, models[first]


def resolve_fallback_chain(task: Optional[str] = None,
                           model_id: Optional[str] = None) -> list:
    """
    给出候选模型 id 列表，第 1 位是 resolve_model 得到的主模型。

    第 2 位起的优先级：
      1. 主模型配置里的 fallback（字符串或字符串列表）
      2. cfg["roles"]["default"] 指向的模型
      3. 其余已配置模型（按 cfg["models"] 的插入顺序）

    去重、排除主模型本身、只保留确实存在于 cfg["models"] 的 id。
    主模型解析失败（无模型 / id 不存在）时不再抛错，返回「其它已配置模型」。
    """
    cfg = load_models()
    models = cfg["models"]
    try:
        primary_id, primary = resolve_model(task, model_id)
    except LLMError:
        return list(models)

    chain = [primary_id]
    fallback = primary.get("fallback")
    if isinstance(fallback, str):
        fallback = [fallback]
    for cand in (fallback or []):
        if isinstance(cand, str) and cand in models and cand not in chain:
            chain.append(cand)

    default_id = cfg["roles"].get("default")
    if default_id in models and default_id not in chain:
        chain.append(default_id)

    for mid in models:
        if mid not in chain:
            chain.append(mid)
    return chain


# 不可重试的错误特征（小写匹配）：重试只是白等，直接换候选
_NON_RETRYABLE_MARKERS = ("http 401", "http 403", "insufficient")


def _is_retryable_error(exc: Exception) -> bool:
    """该异常是否值得重试。401/403/余额不足 → False，其余（含网络层）→ True。"""
    if not isinstance(exc, LLMError):
        return True
    msg = str(exc).lower()
    return not any(marker in msg for marker in _NON_RETRYABLE_MARKERS)


def _chat_one(mid: str, model: dict, user: str, system: str,
              max_tokens: int, temperature: float, retries: int,
              json_mode: Optional[bool], skip_unretryable: bool) -> dict:
    """对单个模型执行「重试 retries 次」逻辑。彻底失败则抛 LLMError。

    skip_unretryable=True（启用备用链路时）→ 401/403/余额不足立即放弃该候选，
    把重试机会留给下一个候选；False（单模型路径）→ 沿用改造前的重试语义。
    """
    protocol = model.get("protocol", "openai")
    handler = PROTOCOL_HANDLERS.get(protocol)
    if not handler:
        raise LLMError(f"未知协议 '{protocol}'，支持: {', '.join(PROTOCOL_HANDLERS)}")

    api_key = resolve_api_key(mid, model)
    if protocol != "ollama" and not api_key:
        raise LLMError(
            f"模型 '{mid}' 缺少 API Key。\n"
            f"  设置环境变量 {model.get('api_key_env', 'N/A')}，或运行:\n"
            f"  python model_config.py key {mid}"
        )

    # json_mode 按调用覆盖（写作任务关闭，拆书任务沿用模型配置）
    if json_mode is not None:
        model = dict(model)
        model["json_mode"] = json_mode

    last_err = None
    for attempt in range(retries + 1):
        try:
            t0 = time.time()
            result = handler(model, api_key, system, user, max_tokens, temperature)
            result["model_id"] = mid
            result["model_name"] = model["model_name"]
            result["elapsed"] = round(time.time() - t0, 2)
            result["cost"] = _estimate_cost(model, result)
            return result
        except LLMError as e:
            last_err = e
            if (skip_unretryable and not _is_retryable_error(e)) or attempt >= retries:
                break
            time.sleep(2 ** attempt)
        except Exception as e:
            # 网络层异常（RemoteDisconnected/URLError/超时）也要重试
            last_err = e
            if attempt >= retries:
                break
            time.sleep(2 ** attempt + 1)
    raise LLMError(f"模型 '{mid}' 调用失败（重试 {retries} 次）: {last_err}")


def chat(user: str, system: str = "", task: Optional[str] = None,
         model_id: Optional[str] = None, max_tokens: int = 8192,
         temperature: float = 0.7, retries: int = 2,
         json_mode: Optional[bool] = None,
         allow_fallback: bool = True) -> dict:
    """
    统一调用入口。

    task: 任务名（pass1_structure / pass3_style / writing ...），按路由表选模型
    model_id: 显式指定模型，优先级高于 task
    json_mode: None=沿用模型配置；True/False=强制开启/关闭。
       写作任务必须传 False——小说正文不是 JSON。
    allow_fallback: True（默认）时按 resolve_fallback_chain 依次尝试候选模型；
       False 时只对主模型重试 retries 次，行为与不启用备用模型时完全一致。
       连通性测试应传 False——否则会把「备用模型通了」误报成「主模型通了」。
    """
    if not allow_fallback:
        mid, model = resolve_model(task, model_id)
        return _chat_one(mid, model, user, system, max_tokens, temperature,
                         retries, json_mode, skip_unretryable=False)

    chain = resolve_fallback_chain(task, model_id)
    if not chain:
        raise LLMError("尚未配置任何模型。运行: python model_config.py add")

    models = load_models()["models"]
    failures = []
    for mid in chain:
        try:
            return _chat_one(mid, models[mid], user, system, max_tokens,
                             temperature, retries, json_mode, skip_unretryable=True)
        except LLMError as e:
            failures.append((mid, str(e)))

    if len(chain) == 1:
        raise LLMError(
            f"模型 '{chain[0]}' 调用失败（重试 {retries} 次）: {failures[0][1]}"
            f"（无可用备用模型）"
        )
    detail = "；".join(f"候选 {mid}: {reason}" for mid, reason in failures)
    raise LLMError(f"全部 {len(chain)} 个候选模型均失败：{detail}")


def _estimate_cost(model: dict, result: dict) -> float:
    """按配置的价格估算本次花费（元）。本地模型为 0"""
    pin = model.get("price_in_per_1m", 0)
    pout = model.get("price_out_per_1m", 0)
    return round(
        result["prompt_tokens"] / 1_000_000 * pin
        + result["completion_tokens"] / 1_000_000 * pout,
        4,
    )


def test_model(model_id: str) -> dict:
    """连通性测试。配完模型必须能一键验证，否则用户不知道配对没配对"""
    cfg = load_models()
    if model_id not in cfg["models"]:
        return {"ok": False, "error": f"模型 '{model_id}' 不存在"}
    try:
        r = chat(
            user="请只回复两个字：正常",
            system="你是一个测试助手，严格按要求回复。",
            model_id=model_id,
            max_tokens=32,
            temperature=0,
            retries=0,
            # 连通性测试必须只测这一个模型：否则备用模型通了会被误报成主模型通了
            allow_fallback=False,
        )
        return {
            "ok": True,
            "reply": r["text"].strip()[:50],
            "elapsed": r["elapsed"],
            "tokens": r["prompt_tokens"] + r["completion_tokens"],
        }
    except LLMError as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(json.dumps(test_model(sys.argv[1]), ensure_ascii=False, indent=2))
    else:
        print("用法: python llm_client.py <model_id>   # 连通性测试")
