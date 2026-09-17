#!/usr/bin/env python3
"""
模型配置管理 CLI — 零依赖

命令：
  list                    列出已配置模型
  presets                 查看内置服务商预设
  add                     交互式添加模型
  add --preset deepseek --id ds-chat
  key <model_id>          设置/更新 API Key
  test [model_id]         连通性测试（不带参数测全部）
  role <role> <model_id>  绑定角色（cheap / strong / default）
  route <task> <role>     调整任务路由
  routes                  查看当前路由表
  fallback <model_id> [<fb1> <fb2> ...]
                          设置/清空主模型失败时的备用模型（不带 fb 参数即清空）
  remove <model_id>       删除模型
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import secret_store  # noqa: E402  （独立模块，llm_client 内部为延迟 import，不能从它转出）
from llm_client import (  # noqa: E402
    load_models, save_models, load_secrets, save_secrets,
    test_model, DEFAULT_ROUTES, MODELS_FILE, SECRETS_FILE,
)

# 常见服务商预设。省去翻文档找 base_url 的功夫
PRESETS = {
    "deepseek": {
        "label": "DeepSeek 官方",
        "protocol": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "model_name": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "price_in_per_1m": 2.0,
        "price_out_per_1m": 8.0,
        "context_window": 65536,
        "note": "性价比高，中文强，长上下文便宜。拆书主力候选",
    },
    "siliconflow": {
        "label": "硅基流动",
        "protocol": "openai",
        "base_url": "https://api.siliconflow.cn/v1",
        "model_name": "Qwen/Qwen2.5-72B-Instruct",
        "api_key_env": "SILICONFLOW_API_KEY",
        "price_in_per_1m": 4.13,
        "price_out_per_1m": 4.13,
        "context_window": 32768,
        "note": "模型多，可切换不同尺寸；部分小模型免费",
    },
    "moonshot": {
        "label": "月之暗面 Kimi",
        "protocol": "openai",
        "base_url": "https://api.moonshot.cn/v1",
        "model_name": "moonshot-v1-128k",
        "api_key_env": "MOONSHOT_API_KEY",
        "price_in_per_1m": 60.0,
        "price_out_per_1m": 60.0,
        "context_window": 131072,
        "note": "超长上下文，拆整本书友好但偏贵",
    },
    "zhipu": {
        "label": "智谱 GLM",
        "protocol": "openai",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model_name": "glm-4-plus",
        "api_key_env": "ZHIPU_API_KEY",
        "price_in_per_1m": 50.0,
        "price_out_per_1m": 50.0,
        "context_window": 131072,
        "note": "中文理解稳",
    },
    "dashscope": {
        "label": "阿里百炼 通义千问",
        "protocol": "openai",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_name": "qwen-max",
        "api_key_env": "DASHSCOPE_API_KEY",
        "price_in_per_1m": 20.0,
        "price_out_per_1m": 60.0,
        "context_window": 32768,
        "note": "中文网文语感好",
    },
    "openai": {
        "label": "OpenAI 官方",
        "protocol": "openai",
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY",
        "price_in_per_1m": 18.0,
        "price_out_per_1m": 72.0,
        "context_window": 128000,
        "note": "",
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "protocol": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "model_name": "claude-sonnet-4-20250514",
        "api_key_env": "ANTHROPIC_API_KEY",
        "price_in_per_1m": 21.0,
        "price_out_per_1m": 105.0,
        "context_window": 200000,
        "note": "长文本定性判断强，适合 Pass3/4",
    },
    "ollama": {
        "label": "本地 Ollama",
        "protocol": "ollama",
        "base_url": "http://localhost:11434",
        "model_name": "qwen2.5:14b",
        "api_key_env": "",
        "price_in_per_1m": 0,
        "price_out_per_1m": 0,
        "context_window": 32768,
        "num_ctx": 32768,
        "note": "本地零成本，适合反复调 prompt 和 Pass1/2",
    },
    "lmstudio": {
        "label": "本地 LM Studio",
        "protocol": "openai",
        "base_url": "http://localhost:1234/v1",
        "model_name": "local-model",
        "api_key_env": "",
        "price_in_per_1m": 0,
        "price_out_per_1m": 0,
        "context_window": 32768,
        "note": "OpenAI 兼容接口，本地跑",
    },
    "vllm": {
        "label": "本地 vLLM",
        "protocol": "openai",
        "base_url": "http://localhost:8000/v1",
        "model_name": "Qwen/Qwen2.5-14B-Instruct",
        "api_key_env": "",
        "price_in_per_1m": 0,
        "price_out_per_1m": 0,
        "context_window": 32768,
        "note": "吞吐高，适合批量拆书",
    },
    "custom": {
        "label": "自定义 OpenAI 兼容接口",
        "protocol": "openai",
        "base_url": "",
        "model_name": "",
        "api_key_env": "",
        "price_in_per_1m": 0,
        "price_out_per_1m": 0,
        "context_window": 32768,
        "note": "中转站、自建代理、其他厂商都用这个",
    },
}

TASK_LABELS = {
    "pass1_structure": "拆书·结构层（抽取型）",
    "pass2_character": "拆书·人物层（抽取型）",
    "pass3_style": "拆书·文风层（判断型）",
    "pass4_commercial": "拆书·商业层（判断型）",
    "pass5_aggregate": "题材包聚合（判断型）",
    "writing": "章节生成",
    "consistency_check": "风格一致性自检",
}


def _mask(key: str) -> str:
    if not key:
        return "(未设置)"
    if len(key) <= 10:
        return key[:2] + "***"
    return f"{key[:6]}...{key[-4:]}"


def cmd_presets(_):
    print("\n内置服务商预设：\n")
    for pid, p in PRESETS.items():
        price = "免费/本地" if p["price_in_per_1m"] == 0 else f"¥{p['price_in_per_1m']}/{p['price_out_per_1m']} 每百万tok"
        print(f"  {pid:<14} {p['label']}")
        print(f"  {'':14} {p['base_url'] or '(需自填)'}")
        print(f"  {'':14} 默认模型 {p['model_name'] or '(需自填)'} · 上下文 {p['context_window']} · {price}")
        if p["note"]:
            print(f"  {'':14} → {p['note']}")
        print()
    print("用法: python model_config.py add --preset deepseek --id ds\n")


def cmd_list(_):
    cfg = load_models()
    models, secrets = cfg["models"], load_secrets()
    if not models:
        print("\n尚未配置任何模型。\n  python model_config.py presets   # 看预设")
        print("  python model_config.py add       # 添加\n")
        return
    print(f"\n已配置 {len(models)} 个模型：\n")
    roles_rev = {}
    for role, mid in cfg["roles"].items():
        roles_rev.setdefault(mid, []).append(role)
    for mid, m in models.items():
        tags = f"  [{', '.join(roles_rev[mid])}]" if mid in roles_rev else ""
        key_state = "本地无需" if m.get("protocol") == "ollama" or not m.get("api_key_env", "x") else _mask(secrets.get(mid, ""))
        env = m.get("api_key_env")
        if env:
            import os
            if os.environ.get(env):
                key_state = f"环境变量 {env} ✓"
        print(f"  {mid}{tags}")
        print(f"    协议 {m.get('protocol')} · 模型 {m.get('model_name')}")
        print(f"    {m.get('base_url')}")
        print(f"    密钥 {key_state} · 上下文 {m.get('context_window', '?')}")
        print()
    print("角色绑定：")
    for role in ("cheap", "strong", "default"):
        print(f"  {role:<8} → {cfg['roles'].get(role, '(未绑定)')}")
    print()


def cmd_routes(_):
    cfg = load_models()
    print("\n任务路由表：\n")
    for task, label in TASK_LABELS.items():
        role = cfg["routes"].get(task, "?")
        mid = cfg["roles"].get(role, "(角色未绑定)")
        print(f"  {label:<24} → {role:<8} → {mid}")
    print("\n调整: python model_config.py route pass3_style strong\n")


def cmd_add(args):
    cfg = load_models()
    preset_id = args.preset
    if not preset_id:
        print("\n可用预设:", ", ".join(PRESETS))
        preset_id = input("选择预设 (回车=custom): ").strip() or "custom"
    if preset_id not in PRESETS:
        print(f"[X] 未知预设 '{preset_id}'。可用: {', '.join(PRESETS)}")
        return 1

    p = dict(PRESETS[preset_id])
    label = p.pop("label")
    p.pop("note", None)
    print(f"\n配置 {label}")

    mid = args.id or input(f"模型标识 id (默认 {preset_id}): ").strip() or preset_id
    if mid in cfg["models"] and not args.force:
        print(f"[X] '{mid}' 已存在，用 --force 覆盖")
        return 1

    def _fill(field, cli_value, label):
        """CLI 参数 > 交互输入 > 预设默认"""
        if cli_value:
            p[field] = cli_value
            return
        current = p.get(field, "")
        if current and not args.interactive:
            return
        hint = f" (默认 {current})" if current else ""
        v = input(f"{label}{hint}: ").strip()
        if v:
            p[field] = v

    _fill("base_url", args.base_url, "接口地址 base_url")
    if not p["base_url"]:
        print("[X] base_url 不能为空")
        return 1

    _fill("model_name", args.model_name, "模型名 model_name")
    if not p["model_name"]:
        print("[X] model_name 不能为空")
        return 1

    cfg["models"][mid] = p
    if not cfg["roles"]:
        cfg["roles"] = {"default": mid, "cheap": mid, "strong": mid}
        print("\n[i] 首个模型，已自动绑定为 default / cheap / strong")
    save_models(cfg)
    print(f"\n[OK] 模型 '{mid}' 已添加 → {MODELS_FILE}")

    # 密钥
    if p.get("protocol") != "ollama" and p.get("api_key_env") != "":
        key = args.key
        if not key and not args.no_key:
            print("\n密钥可用两种方式（任选其一）：")
            print(f"  A. 环境变量 {p.get('api_key_env') or '(自定义)'}  — 更安全，推荐")
            print("  B. 存入本地加密密钥库              — Windows DPAPI 加密（.secrets.bin），已自动 gitignore")
            key = input("现在输入 API Key (直接回车跳过): ").strip()
        if key:
            s = load_secrets()
            s[mid] = key
            save_secrets(s)
            print(f"[OK] 密钥已存入 {SECRETS_FILE}（{secret_store.storage_mode()}）")

    print(f"\n下一步: python model_config.py test {mid}")
    return 0


def cmd_key(args):
    cfg = load_models()
    if args.model_id not in cfg["models"]:
        print(f"[X] 模型 '{args.model_id}' 不存在")
        return 1
    key = args.value or input(f"输入 {args.model_id} 的 API Key: ").strip()
    if not key:
        print("[X] 密钥为空，未修改")
        return 1
    s = load_secrets()
    s[args.model_id] = key
    save_secrets(s)
    print(f"[OK] 已更新 → {_mask(key)}")
    return 0


def cmd_test(args):
    cfg = load_models()
    targets = [args.model_id] if args.model_id else list(cfg["models"])
    if not targets:
        print("[X] 无已配置模型")
        return 1
    print()
    failed = 0
    for mid in targets:
        print(f"  测试 {mid} ... ", end="", flush=True)
        r = test_model(mid)
        if r["ok"]:
            print(f"OK  ({r['elapsed']}s, {r['tokens']} tok)  回复: {r['reply']}")
        else:
            failed += 1
            print("FAIL")
            print(f"      {r['error'][:300]}")
    print()
    return 1 if failed else 0


def cmd_role(args):
    cfg = load_models()
    if args.model_id not in cfg["models"]:
        print(f"[X] 模型 '{args.model_id}' 不存在")
        return 1
    cfg["roles"][args.role] = args.model_id
    save_models(cfg)
    print(f"[OK] 角色 {args.role} → {args.model_id}")
    return 0


def cmd_route(args):
    cfg = load_models()
    if args.task not in DEFAULT_ROUTES:
        print(f"[X] 未知任务。可用: {', '.join(DEFAULT_ROUTES)}")
        return 1
    cfg["routes"][args.task] = args.role
    save_models(cfg)
    print(f"[OK] {TASK_LABELS.get(args.task, args.task)} → 角色 {args.role}")
    return 0


def cmd_fallback(args):
    """设置 / 清空某模型的备用模型链（主模型失败时按顺序回退）。"""
    cfg = load_models()
    mid = args.model_id
    if mid not in cfg["models"]:
        print(f"[X] 模型 '{mid}' 不存在")
        return 1

    targets = list(args.fallback_models or [])
    missing = [t for t in targets if t not in cfg["models"]]
    if missing:
        print(f"[X] 备用模型不存在: {', '.join(missing)}（未写入）")
        return 1

    if targets:
        cfg["models"][mid]["fallback"] = targets
        save_models(cfg)
        print(f"[OK] {mid} 的备用模型 → {', '.join(targets)}")
    else:
        cfg["models"][mid].pop("fallback", None)
        save_models(cfg)
        print(f"[OK] 已清空 {mid} 的备用模型")
    return 0


def cmd_remove(args):
    cfg = load_models()
    if args.model_id not in cfg["models"]:
        print(f"[X] 模型 '{args.model_id}' 不存在")
        return 1
    del cfg["models"][args.model_id]
    cfg["roles"] = {r: m for r, m in cfg["roles"].items() if m != args.model_id}
    save_models(cfg)
    s = load_secrets()
    if args.model_id in s:
        del s[args.model_id]
        save_secrets(s)
    print(f"[OK] 已删除 '{args.model_id}'")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="model_config", description="拆书系统模型配置管理")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("list", help="列出已配置模型")
    sub.add_parser("presets", help="查看内置服务商预设")
    sub.add_parser("routes", help="查看任务路由表")

    a = sub.add_parser("add", help="添加模型")
    a.add_argument("--preset", help="预设 id")
    a.add_argument("--id", help="模型标识")
    a.add_argument("--base-url", dest="base_url")
    a.add_argument("--model-name", dest="model_name")
    a.add_argument("--key", help="API Key")
    a.add_argument("--no-key", action="store_true", help="跳过密钥录入")
    a.add_argument("--force", action="store_true", help="覆盖同名")
    a.add_argument("-i", "--interactive", action="store_true", help="逐项确认")

    k = sub.add_parser("key", help="设置 API Key")
    k.add_argument("model_id")
    k.add_argument("value", nargs="?")

    t = sub.add_parser("test", help="连通性测试")
    t.add_argument("model_id", nargs="?")

    r = sub.add_parser("role", help="绑定角色")
    r.add_argument("role", choices=["cheap", "strong", "default"])
    r.add_argument("model_id")

    rt = sub.add_parser("route", help="调整任务路由")
    rt.add_argument("task")
    rt.add_argument("role", choices=["cheap", "strong", "default"])

    rm = sub.add_parser("remove", help="删除模型")
    rm.add_argument("model_id")

    fb = sub.add_parser("fallback", help="设置/清空备用模型")
    fb.add_argument("model_id")
    fb.add_argument("fallback_models", nargs="*", help="备用模型 id（留空=清空）")

    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return 0
    return {
        "list": cmd_list, "presets": cmd_presets, "routes": cmd_routes,
        "add": cmd_add, "key": cmd_key, "test": cmd_test,
        "role": cmd_role, "route": cmd_route, "remove": cmd_remove,
        "fallback": cmd_fallback,
    }[args.cmd](args) or 0


if __name__ == "__main__":
    sys.exit(main())
