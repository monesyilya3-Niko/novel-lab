#!/usr/bin/env python3
"""
设定一致性纯算法检测 — 世界观约束 + 角色属性 + 别名一致性（纯标准库）

三大检测：
  1. 世界观约束   — 读 entities.json 可选 world_rules 列表，用 regex 检测正文
                    是否违反约束（如「禁止出现枪械」）。
  2. 角色属性一致 — 读 characters[].attributes（如 {"年龄": 18}），检测正文
                    「唐雨 N 岁」中的 N 与属性值冲突。
  3. 别名一致性   — 复用 write.py 既有的别名混用检测逻辑：同一角色在正文中
                    只用别称而不用全名，提示称呼异常。

entities.json 约定（向后兼容，缺失字段静默跳过）：
  {
    "characters": [
      {"name": "唐雨", "aliases": ["小雨"], "attributes": {"年龄": 18}}
    ],
    "world_rules": ["校园题材，无超自然", "禁止出现枪械"]
  }

issue 统一结构：{"type", "severity", "chapter", "detail"}
severity 枚举：critical / high / medium / low

用法:
  python setting_check.py <novel_dir 或 章节目录> [--json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import chapter_loader

# 从 logic_check 复用实体加载（同目录导入，纯标准库）
try:
    from logic_check import load_entities, _load_texts
except ImportError:  # 直接以脚本方式运行时的兜底（独立可用）
    def load_entities(novel_dir):
        novel_dir = Path(novel_dir)
        candidates = [novel_dir / "settings" / "entities.json"]
        if novel_dir.is_dir() and novel_dir.name == "chapters":
            candidates.insert(0, novel_dir.parent / "settings" / "entities.json")
        for c in candidates:
            if c.exists():
                try:
                    data = json.loads(c.read_text(encoding="utf-8"))
                    return data if isinstance(data, dict) else {}
                except Exception:
                    return {}
        return {}

    def _load_texts(source):
        """兜底：委托 chapter_loader，与 logic_check 共用同一套发现规则。

        此处**不得**再实现一遍递归扫描——两套规则会漂移（这正是 2026-09-16 统一
        加载器的起因）。
        """
        return chapter_loader.load_chapter_texts(source)


# ---------------------------------------------------------------------------
# 1. 世界观约束检测
# ---------------------------------------------------------------------------

# world_rules 常见「禁止/不得/避免/无」类约束 → 从规则文本提取禁用词。
# 规则格式约定：「禁止出现枪械」→ 关键词「枪械」；「校园题材，无超自然」→
# 关键词「超自然」。检测正文是否出现关键词。
_PROHIBIT_RE = re.compile(r'(?:禁止|严禁|不得|不能|不要|避免|切勿)\s*(?:出现|提及|描写|使用)?\s*([\u4e00-\u9fff、，,]{1,12})')


def _extract_banned_keywords(rule: str) -> list:
    """从一条 world_rule 提取用于检测的禁用关键词列表。"""
    kws = []
    for m in _PROHIBIT_RE.finditer(rule):
        kws.append(m.group(1))
    # 兜底：若规则含「无 X」/「没有 X」，把 X 视为禁用词
    for m in re.finditer(r'(?:无|没有|不存在)\s*([\u4e00-\u9fff]{1,8})', rule):
        kws.append(m.group(1))
    # 去重 + 过滤停用字（避免「出现」「提及」这类被误当关键词）
    STOP = {"出现", "提及", "描写", "使用", "任何", "所有"}
    kws = [k for k in dict.fromkeys(kws) if k and k not in STOP]
    return kws


def _check_world_rules(texts: dict, world_rules: list) -> list:
    """检测正文是否违反世界规则约束。"""
    issues = []
    if not isinstance(world_rules, list):
        return issues
    banned_keywords = []
    for rule in world_rules:
        if not isinstance(rule, str):
            continue
        banned_keywords.extend(_extract_banned_keywords(rule))
    banned_keywords = [k for k in dict.fromkeys(banned_keywords) if k]
    if not banned_keywords:
        return issues

    for ch in sorted(texts.keys()):
        text = texts[ch]
        for kw in banned_keywords:
            if kw and kw in text:
                issues.append({
                    "type": "world_rule_violation",
                    "severity": "high",
                    "chapter": ch,
                    "detail": f"Ch{ch} 出现禁用词「{kw}」，违反世界设定约束",
                })
    return issues


# ---------------------------------------------------------------------------
# 2. 角色属性一致性检测
# ---------------------------------------------------------------------------

# 属性名 → 正文抽取正则（支持「N岁」「第N年」等）
_ATTR_PATTERNS = {
    "年龄": re.compile(r'([\u4e00-\u9fff]{2,4})\s*(\d{1,3})\s*岁'),
}


def _check_attributes(texts: dict, characters: list) -> list:
    """检测正文数值属性与 entities.json attributes 声明冲突。"""
    issues = []
    if not isinstance(characters, list):
        return issues

    # 构建 canonical_name -> {属性名: 期望值}
    attr_map = {}
    name_aliases = []  # [(canonical, [称呼])] 供正文定位
    for c in characters:
        if not isinstance(c, dict):
            continue
        name = c.get("name", "")
        if not name:
            continue
        attrs = c.get("attributes", {})
        if isinstance(attrs, dict) and attrs:
            attr_map[name] = attrs
        aliases = [a for a in (c.get("aliases", []) or []) if isinstance(a, str) and a]
        name_aliases.append((name, [name] + aliases))

    if not attr_map:
        return issues

    # 属性名 → 期望值 → 检测
    for ch in sorted(texts.keys()):
        text = texts[ch]
        for attr_name, pat in _ATTR_PATTERNS.items():
            for name, val in pat.findall(text):
                name = name.strip()
                if not name:
                    continue
                # 找到该名字对应的 canonical 实体
                canonical = None
                for cn, names in name_aliases:
                    if name == cn or name in names:
                        canonical = cn
                        break
                if canonical is None or canonical not in attr_map:
                    continue
                expected = attr_map[canonical].get(attr_name)
                if expected is None:
                    continue
                # 期望值可能是 int 或 str，统一转 int 比较
                try:
                    expected_int = int(expected)
                except (TypeError, ValueError):
                    continue
                actual_int = int(val)
                if actual_int != expected_int:
                    issues.append({
                        "type": "attribute_contradiction",
                        "severity": "high",
                        "chapter": ch,
                        "detail": f"角色「{canonical}」属性{attr_name}应为 {expected_int}，"
                                  f"Ch{ch} 正文写为 {actual_int}，设定不一致",
                    })
    return issues


# ---------------------------------------------------------------------------
# 3. 别名一致性检测（复用 write.py 逻辑）
# ---------------------------------------------------------------------------

def _check_alias_consistency(texts: dict, characters: list) -> list:
    """复用 write.py run_conflict_check 的别名混用检测逻辑。

    原文逻辑（write.py 检查2）：已知实体及其别名在正文中，
    若别名出现而全名未出现 → 提示「仅以别称出现」。
    这里升级为跨章统一检测：任一章节出现该情况即报 medium issue。
    """
    issues = []
    if not isinstance(characters, list):
        return issues
    known = {}
    for c in characters:
        if not isinstance(c, dict):
            continue
        name = c.get("name", "")
        if name:
            known[name] = [a for a in (c.get("aliases", []) or [])
                           if isinstance(a, str) and a]

    if not known:
        return issues

    for ch in sorted(texts.keys()):
        text = texts[ch]
        for name, aliases in known.items():
            hit = [a for a in aliases if a and a in text]
            if hit and name not in text:
                issues.append({
                    "type": "alias_consistency",
                    "severity": "medium",
                    "chapter": ch,
                    "detail": f"Ch{ch} 角色「{name}」仅以别称「{'、'.join(hit[:3])}」出现，"
                              f"未出现全名，称呼可能不统一",
                })
    return issues


# ---------------------------------------------------------------------------
# 检测覆盖率报告（2026-09-17 第二轮 Task B / 报告 P2-1）
# ---------------------------------------------------------------------------
# 缺 entities.json（或其中某字段）时对应检测静默跳过，输出仍是「0 问题」——
# 与「查过且没问题」无法区分。setting_coverage() 显式报告哪些项可评估。
# 纯加性：不参与任何评分、不改变 check_setting 的返回与判定。

# checks 的固定顺序（evaluable / skipped 均按此顺序输出）
SETTING_CHECK_ORDER = ("world_rules", "attributes", "alias")

# 各检测项缺失时的中文原因（多项缺失用「；」拼接）
_SETTING_SKIP_REASONS = {
    "world_rules": "缺少 entities.json 的 world_rules，世界观约束未检测",
    "attributes": "缺少 entities.json 的 characters[].attributes，角色属性一致性未检测",
    "alias": "缺少 entities.json 的 characters[].aliases，别名一致性未检测",
}

_NO_CHAPTERS_REASON = "无章节文本"


def setting_coverage(texts: dict, entities: dict = None) -> dict:
    """返回设定一致性各检测项的「是否可评估」信息。

    判定规则（与 check_setting 的实际执行分支一致）：
      - world_rules：需要 ``entities["world_rules"]`` 为非空列表；
      - attributes：需要至少一个 ``characters[].attributes`` 为非空 dict；
      - alias：需要至少一个 ``characters[].aliases`` 为非空列表；
      - texts 为空：chapters=0，三项全 False，skipped_reason="无章节文本"。

    Args:
        texts: {章号:int -> 文本:str}（空值条目与 check_setting 同口径忽略）。
        entities: entities.json 解析结果（可选）。

    Returns:
        dict: 与 ``logic_check.logic_coverage`` 同构
            {"entities_loaded": bool, "chapters": int,
             "checks": {"world_rules": bool, "attributes": bool, "alias": bool},
             "evaluable": [...], "skipped": [...], "skipped_reason": str}
            entities_loaded 口径：``characters`` 为非空列表即 True。
    """
    texts = {int(k): v for k, v in (texts or {}).items() if v}
    has_chapters = bool(texts)
    entities = entities if isinstance(entities, dict) else {}
    characters = entities.get("characters")
    characters = characters if isinstance(characters, list) else []
    entities_loaded = bool(characters)

    world_rules = entities.get("world_rules")
    checks = {
        "world_rules": has_chapters and isinstance(world_rules, list) and bool(world_rules),
        "attributes": has_chapters and any(
            isinstance(c, dict) and isinstance(c.get("attributes"), dict) and bool(c.get("attributes"))
            for c in characters),
        "alias": has_chapters and any(
            isinstance(c, dict) and isinstance(c.get("aliases"), list) and bool(c.get("aliases"))
            for c in characters),
    }
    evaluable = [k for k in SETTING_CHECK_ORDER if checks[k]]
    skipped = [k for k in SETTING_CHECK_ORDER if not checks[k]]
    if not has_chapters:
        skipped_reason = _NO_CHAPTERS_REASON
    else:
        skipped_reason = "；".join(_SETTING_SKIP_REASONS[k] for k in skipped)

    return {
        "entities_loaded": entities_loaded,
        "chapters": len(texts),
        "checks": checks,
        "evaluable": evaluable,
        "skipped": skipped,
        "skipped_reason": skipped_reason,
    }


def _format_coverage_warning(coverage: dict) -> str:
    """把覆盖率信息格式化为一行「⚠ 未评估: …（原因：…）」（skipped 为空返回 ""）。"""
    skipped = coverage.get("skipped") or []
    if not skipped:
        return ""
    return (f"⚠ 未评估: {'、'.join(skipped)}"
            f"（原因：{coverage.get('skipped_reason', '')}）")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def check_setting(texts: dict, entities: dict = None) -> list:
    """设定一致性检测，返回 issue 列表。

    Args:
        texts: {章号:int -> 文本:str}。
        entities: entities.json 解析结果（可选）。含可选 world_rules 列表、
                  characters[].attributes 属性表、characters[].aliases 别名表。
                  缺失字段静默跳过。

    Returns:
        list[dict]: issue 列表，每项 {"type", "severity", "chapter", "detail"}。
    """
    texts = {int(k): v for k, v in (texts or {}).items() if v}
    if not texts:
        return []

    entities = entities if isinstance(entities, dict) else {}
    world_rules = entities.get("world_rules", [])
    characters = entities.get("characters", [])

    issues = []
    issues.extend(_check_world_rules(texts, world_rules))
    issues.extend(_check_attributes(texts, characters))
    issues.extend(_check_alias_consistency(texts, characters))
    return issues


def main():
    ap = argparse.ArgumentParser(description="设定一致性纯算法检测")
    ap.add_argument("source", help="novel_dir 或章节目录或单章 txt")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    source = Path(args.source)
    try:
        texts = _load_texts(source)
    except (OSError, UnicodeError, chapter_loader.ChapterLoadError) as exc:
        # 章节加载失败（同章号冲突/读取失败）：与 logic_check.main 一致，输出错误并非零退出
        print(f"[X] {exc}", file=sys.stderr)
        sys.exit(1)
    if not texts:
        print("[X] 未找到章节文件", file=sys.stderr)
        sys.exit(1)
    entities = load_entities(source)
    issues = check_setting(texts, entities)
    coverage = setting_coverage(texts, entities)

    if args.json:
        print(json.dumps({"total_chapters": len(texts), "total_issues": len(issues),
                          "issues": issues, "coverage": coverage},
                         ensure_ascii=False, indent=2))
    else:
        print(f"设定一致性检测: {len(texts)} 章 / {len(issues)} 问题")
        print("=" * 50)
        for it in issues:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(it["severity"], "⚪")
            print(f"  {icon} [{it['severity']}] Ch{it['chapter']}: {it['detail']}")
        warning = _format_coverage_warning(coverage)
        if warning:
            print(warning)
    sys.exit(0 if not issues else 1)


if __name__ == "__main__":
    sys.exit(main())
