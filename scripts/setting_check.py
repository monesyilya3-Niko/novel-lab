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
        texts = {}
        source = Path(source)
        if source.is_file():
            m = re.search(r'(\d+)', source.stem)
            texts[int(m.group(1)) if m else 1] = source.read_text(encoding="utf-8")
            return texts
        if not source.is_dir():
            return {}
        roots = [source]
        if (source / "chapters").is_dir():
            roots.append(source / "chapters")
        for root in roots:
            for f in sorted(root.rglob("*.txt")):
                m = re.search(r'(\d+)', f.stem)
                if m:
                    texts[int(m.group(1))] = f.read_text(encoding="utf-8")
        return texts


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
    texts = _load_texts(source)
    if not texts:
        print("[X] 未找到章节文件", file=sys.stderr)
        sys.exit(1)
    entities = load_entities(source)
    issues = check_setting(texts, entities)

    if args.json:
        print(json.dumps({"total_chapters": len(texts), "total_issues": len(issues),
                          "issues": issues}, ensure_ascii=False, indent=2))
    else:
        print(f"设定一致性检测: {len(texts)} 章 / {len(issues)} 问题")
        print("=" * 50)
        for it in issues:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(it["severity"], "⚪")
            print(f"  {icon} [{it['severity']}] Ch{it['chapter']}: {it['detail']}")
    sys.exit(0 if not issues else 1)


if __name__ == "__main__":
    main()
