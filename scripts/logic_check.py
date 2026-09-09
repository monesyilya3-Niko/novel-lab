#!/usr/bin/env python3
"""
逻辑合理性纯算法检测 — 跨章节硬矛盾检测（纯标准库，零第三方依赖）

检测四大类「硬矛盾」，全部用 regex 抽取 + 跨章 set 比较 + 单调性判断，
不依赖任何 LLM：

  1. 数字/年龄矛盾   — 同一实体年龄/年份/天数/金额/身高/手机号在不同章出现
                       互斥取值（例如 Ch1「唐雨 18 岁」、Ch3「唐雨 24 岁」）。
  2. 时间线矛盾       — 构建 ch→相对时间映射（昨天/今天/明天/第二天/次日/
                       第N天/N天后/N年前），检测相对时间单调性被破坏的章。
  3. 称呼矛盾         — 复用 entities.json 的 aliases，检测同一角色在相邻章节
                       被用不同称呼指代且无过渡标记。
  4. 状态矛盾         — 角色在场/位置/生死跨章冲突（例如 Ch3 死亡、Ch10 又出场
                       且无闪回标记）。

issue 统一结构：{"type", "severity", "chapter", "detail"}
severity 枚举：critical / high / medium / low

用法:
  python logic_check.py <novel_dir 或 章节目录> [--json]

entities.json 约定（novel_dir/settings/entities.json，可选）：
  {"characters": [{"name": "唐雨", "aliases": ["小雨"], "attributes": {"年龄": 18}}]}
缺失字段静默跳过。
"""
import argparse
import json
import re
import sys
from pathlib import Path

# 闪回/回忆/梦境标记——出现在这些语境里的状态不作为硬矛盾（宽容处理）
FLASHBACK_MARKERS = [
    "回忆", "回想", "想起", "记得", "当年", "从前", "曾经", "那时", "那时候",
    "梦里", "梦境", "梦到", "梦见", "闪回", "倒叙", "过去", "以前", "往昔",
    "去年", "前年", "几年前", "多年前", "很久以前", "记起", "浮现",
]


def load_entities(novel_dir: Path) -> dict:
    """从 novel_dir/settings/entities.json 加载实体表。

    文件不存在或解析失败时返回空 dict（调用方静默跳过，不抛异常）。
    兼容传入章节目录（novel_dir 可能是 chapters 目录，此时向上探测父级）。

    Args:
        novel_dir: novel-writing 项目目录（或其 chapters 子目录）。

    Returns:
        dict: entities 内容；缺失/解析失败返回 {}。
    """
    if novel_dir is None:
        return {}
    novel_dir = Path(novel_dir)
    # 兼容：传入的是 chapters 目录时，向上探测 settings
    candidates = []
    if novel_dir.is_dir() and novel_dir.name == "chapters":
        candidates.append(novel_dir.parent / "settings" / "entities.json")
    candidates.append(novel_dir / "settings" / "entities.json")
    for candidate in candidates:
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
    return {}


def _load_texts(source: Path) -> dict:
    """把章节目录/单章文件/novel_dir 归一为 {章号:int -> 文本:str}。"""
    texts = {}
    source = Path(source)
    if source.is_file():
        m = re.search(r'(\d+)', source.stem)
        texts[m.group(1) and int(m.group(1)) or 1] = source.read_text(encoding="utf-8")
        return texts
    if not source.is_dir():
        return {}
    # 支持 chapters 目录本身，或 novel_dir（此时定位 chapters 子目录）
    roots = [source]
    if (source / "chapters").is_dir():
        roots.append(source / "chapters")
    for root in roots:
        for f in sorted(root.rglob("*.txt")):
            m = re.search(r'(\d+)', f.stem)
            if m:
                texts[int(m.group(1))] = f.read_text(encoding="utf-8")
    return texts


def _chapter_number(issue_chapter) -> int:
    """issue.chapter 可能是 int 或 'ChN' 字符串，统一归一为 int。"""
    if isinstance(issue_chapter, int):
        return issue_chapter
    if isinstance(issue_chapter, str):
        m = re.search(r'(\d+)', issue_chapter)
        if m:
            return int(m.group(1))
    return 0


# ---------------------------------------------------------------------------
# 1. 数字/年龄矛盾
# ---------------------------------------------------------------------------

# 同一实体 + 数值类别 的抽取模式：捕获 实体名 + 数值 + 单位
# （单位限定为年龄/年份/天数/金额/身高/手机号，避免把普通量词误判为矛盾）
AGE_RE = re.compile(r'([\u4e00-\u9fff]{2,4})\s*(\d{1,3})\s*岁')
YEAR_RE = re.compile(r'([\u4e00-\u9fff]{2,4})\s*第?\s*(\d{1,4})\s*年')
DAY_RE = re.compile(r'([\u4e00-\u9fff]{2,4})\s*(\d{1,3})\s*天')
MONEY_RE = re.compile(r'([\u4e00-\u9fff]{2,4})\s*(\d{1,6})\s*[元块]')
HEIGHT_RE = re.compile(r'([\u4e00-\u9fff]{2,4})\s*(\d{2,3})\s*(?:cm|厘米)')
PHONE_RE = re.compile(r'([\u4e00-\u9fff]{2,4})\s*(?:电话|手机|号码|拨打|拨了)?\s*(\d{11})')

# 每个数值类别对应的抽取器与标签
_NUM_PATTERNS = [
    ("age", AGE_RE, "岁"),
    ("year", YEAR_RE, "年"),
    ("day", DAY_RE, "天"),
    ("money", MONEY_RE, "元"),
    ("height", HEIGHT_RE, "厘米"),
    ("phone", PHONE_RE, "手机号"),
]

# 类别名 -> (cat, pat, label) 元组查表，供矛盾信息生成时取 label（避免 dict() 从 3 元组构建崩溃）
_NUM_PATTERN_MAP = {t[0]: t for t in _NUM_PATTERNS}


def _check_number_contradictions(texts: dict) -> list:
    """检测同一实体数值类别在不同章出现互斥取值。"""
    issues = []
    # entity_name -> {类别: {取值: 首次出现章号}}
    entity_values = {}
    for ch in sorted(texts.keys()):
        text = texts[ch]
        for cat, pat, label in _NUM_PATTERNS:
            for name, val in pat.findall(text):
                name = name.strip()
                val = val.strip()
                if not name or not val:
                    continue
                rec = entity_values.setdefault(name, {}).setdefault(cat, {})
                if val not in rec:
                    rec[val] = ch
    for name, cats in entity_values.items():
        for cat, vals in cats.items():
            label = _NUM_PATTERN_MAP[cat][2]
            if len(vals) >= 2:
                # 数值互斥：同一实体同一类别出现 ≥2 个不同取值
                sorted_vals = sorted(vals.items(), key=lambda kv: _chapter_number(kv[1]))
                first_val, first_ch = sorted_vals[0]
                for val, ch in sorted_vals[1:]:
                    issues.append({
                        "type": "number_contradiction",
                        "severity": "high",
                        "chapter": ch,
                        "detail": f"实体「{name}」的{label}在 Ch{first_ch} 为 {first_val}，"
                                  f"Ch{ch} 变为 {val}，疑似矛盾",
                    })
    return issues


# ---------------------------------------------------------------------------
# 2. 时间线矛盾
# ---------------------------------------------------------------------------

# 相对时间锚点：命中的章会建立/推进相对时间，检测单调性
# 每个模式映射到 (天数偏移, 是否跨章推进标记)
_TIME_PATTERNS = [
    (re.compile(r'(?:^|[^前昨明])昨天'), "昨天"),
    (re.compile(r'(?:^|[^昨明])今天'), "今天"),
    (re.compile(r'(?:^|[^昨今])明天'), "明天"),
    (re.compile(r'第二天|次日'), "第二天"),
    (re.compile(r'第\s*(\d{1,3})\s*天'), None),  # 第N天，动态处理
    (re.compile(r'(\d{1,3})\s*天后'), None),      # N天后
    (re.compile(r'(\d{1,3})\s*年前'), None),      # N年前
    (re.compile(r'(\d{1,3})\s*年(?:前|之前)'), None),
]


def _extract_relative_time(text: str) -> list:
    """从文本抽取相对时间信号，返回 [(offset, 标签)]，offset 为相对天数。

    offset 语义（越大越靠后）：
      昨天=-1, 今天=0, 明天=+1, 第二天=+1, 第N天=N-1, N天后=+N, N年前=-N*365
    无法确定的返回空列表。
    """
    signals = []
    for pat, label in _TIME_PATTERNS:
        if label == "昨天":
            if pat.search(text):
                signals.append((-1, "昨天"))
        elif label == "今天":
            if pat.search(text):
                signals.append((0, "今天"))
        elif label == "明天":
            if pat.search(text):
                signals.append((1, "明天"))
        elif label == "第二天":
            if pat.search(text):
                signals.append((1, "第二天"))
        elif label is None and "第" in pat.pattern:
            for m in pat.finditer(text):
                signals.append((int(m.group(1)) - 1, f"第{m.group(1)}天"))
        elif label is None and "天后" in pat.pattern:
            for m in pat.finditer(text):
                signals.append((int(m.group(1)), f"{m.group(1)}天后"))
        elif label is None and ("年前" in pat.pattern or "年(?:前|之前)" in pat.pattern):
            for m in pat.finditer(text):
                signals.append((-int(m.group(1)) * 365, f"{m.group(1)}年前"))
    return signals


def _check_timeline_contradictions(texts: dict) -> list:
    """检测相对时间单调性破坏。"""
    issues = []
    chapters = sorted(texts.keys())
    # 记录每章「最靠前」与「最靠后」的相对时间，用于相邻章单调性比较
    prev_max = None  # 前一章的相对时间上界
    prev_ch = None
    for ch in chapters:
        text = texts[ch]
        signals = _extract_relative_time(text)
        if not signals:
            continue
        # 本章相对时间范围
        ch_min = min(s[0] for s in signals)
        ch_max = max(s[0] for s in signals)
        # 与前一章比较：若本章上界 < 前一章上界，说明时间倒退（单调性破坏）
        if prev_max is not None and ch_max < prev_max:
            issues.append({
                "type": "timeline_contradiction",
                "severity": "high",
                "chapter": ch,
                "detail": f"Ch{prev_ch} 相对时间推进到 {prev_max}，Ch{ch} 却回溯到 {ch_max}，"
                          f"时间线疑似倒退",
            })
        # 更新前章上界（用本章上界作为后续比较基准，允许同一天多章）
        prev_max = max(prev_max, ch_max) if prev_max is not None else ch_max
        prev_ch = ch
    return issues


# ---------------------------------------------------------------------------
# 3. 称呼矛盾
# ---------------------------------------------------------------------------

def _check_appellation_contradictions(texts: dict, entities: dict) -> list:
    """复用 entities.json aliases，检测相邻章称呼切换无过渡。"""
    issues = []
    characters = (entities or {}).get("characters", []) if isinstance(entities, dict) else []
    if not characters:
        return issues

    # 构建 name + aliases 的全集（每个可指代该角色的称呼）
    name_aliases = []  # [(canonical_name, [称呼列表])]
    for c in characters:
        if not isinstance(c, dict):
            continue
        name = c.get("name", "")
        if not name:
            continue
        aliases = [a for a in (c.get("aliases", []) or []) if isinstance(a, str) and a]
        all_names = [name] + aliases
        name_aliases.append((name, all_names))

    chapters = sorted(texts.keys())
    # 记录每个角色上一章实际使用的称呼（首个出现者）
    prev_appellation = {}  # canonical_name -> 上一章称呼
    prev_ch = {}           # canonical_name -> 上一章章号
    for ch in chapters:
        text = texts[ch]
        for canonical, all_names in name_aliases:
            # 本章该角色实际出现的称呼（按文中首次出现顺序）
            present = []
            for nm in all_names:
                if nm and nm in text:
                    present.append((text.find(nm), nm))
            if not present:
                continue  # 本章该角色未出场
            present.sort()
            cur_app = present[0][1]
            if canonical in prev_appellation:
                prev_app = prev_appellation[canonical]
                # 相邻章称呼切换且无过渡（两个称呼都非全名）
                if prev_app != cur_app and ch - prev_ch[canonical] <= 1:
                    issues.append({
                        "type": "appellation_contradiction",
                        "severity": "medium",
                        "chapter": ch,
                        "detail": f"角色「{canonical}」Ch{prev_ch[canonical]} 用「{prev_app}」指代，"
                                  f"Ch{ch} 切换为「{cur_app}」且无过渡，称呼不一致",
                    })
            prev_appellation[canonical] = cur_app
            prev_ch[canonical] = ch
    return issues


# ---------------------------------------------------------------------------
# 4. 状态矛盾（在场/位置/生死）
# ---------------------------------------------------------------------------

DEATH_WORDS = ["死了", "去世", "牺牲", "遇难", "身亡", "丧生", "死亡", "咽气", "断气"]
ALIVE_WORDS = ["出场", "出现", "走来", "说话", "开口", "站起", "坐下", "抬头", "开口"]


def _check_state_contradictions(texts: dict, entities: dict) -> list:
    """检测角色生死/在场状态跨章冲突（无闪回标记）。"""
    issues = []
    characters = (entities or {}).get("characters", []) if isinstance(entities, dict) else []
    # 收集可检测的角色名（canonical + aliases）
    role_names = []
    for c in characters:
        if not isinstance(c, dict):
            continue
        name = c.get("name", "")
        if not name:
            continue
        for nm in [name] + [a for a in (c.get("aliases", []) or []) if isinstance(a, str) and a]:
            role_names.append((name, nm))

    chapters = sorted(texts.keys())
    death_ch = {}   # canonical_name -> 首次判定死亡章号
    for ch in chapters:
        text = texts[ch]
        for canonical, nm in role_names:
            if nm not in text:
                continue
            is_death = any(d in text for d in DEATH_WORDS)
            is_flashback = any(m in text for m in FLASHBACK_MARKERS)
            # 该角色死亡章记录
            if is_death and canonical not in death_ch:
                death_ch[canonical] = ch
            # 若此前已判定死亡，本章仍出场且无闪回标记 → 矛盾
            if canonical in death_ch and ch > death_ch[canonical] and not is_flashback:
                # 出场证据：有生命活动词（可选，无则退化为「名字仍出现」）
                alive_evidence = any(a in text for a in ALIVE_WORDS)
                if alive_evidence:
                    issues.append({
                        "type": "state_contradiction",
                        "severity": "critical",
                        "chapter": ch,
                        "detail": f"角色「{canonical}」Ch{death_ch[canonical]} 已判定死亡，"
                                  f"Ch{ch} 却再次出场（无闪回标记），生死状态矛盾",
                    })
    return issues


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def check_logic(texts: dict, entities: dict = None, llm_hook=None) -> list:
    """逻辑合理性检测，返回 issue 列表。

    Args:
        texts: {章号:int -> 文本:str}。章号建议用正整数。
        entities: entities.json 解析结果（可选）。含 characters[].aliases 供称呼/
                  状态检测复用。缺失时仅做数字/时间线两类检测。
        llm_hook: 占位参数，为将来 LLM 增强预留，当前不实现（架构师已定稿）。

    Returns:
        list[dict]: issue 列表，每项 {"type", "severity", "chapter", "detail"}。
    """
    texts = {int(k): v for k, v in (texts or {}).items() if v}
    if not texts:
        return []

    issues = []
    issues.extend(_check_number_contradictions(texts))
    issues.extend(_check_timeline_contradictions(texts))
    if entities:
        issues.extend(_check_appellation_contradictions(texts, entities))
        issues.extend(_check_state_contradictions(texts, entities))
    return issues


def main():
    ap = argparse.ArgumentParser(description="逻辑合理性纯算法检测")
    ap.add_argument("source", help="novel_dir 或章节目录或单章 txt")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    source = Path(args.source)
    texts = _load_texts(source)
    if not texts:
        print("[X] 未找到章节文件", file=sys.stderr)
        sys.exit(1)
    entities = load_entities(source)
    issues = check_logic(texts, entities)

    if args.json:
        print(json.dumps({"total_chapters": len(texts), "total_issues": len(issues),
                          "issues": issues}, ensure_ascii=False, indent=2))
    else:
        print(f"逻辑合理性检测: {len(texts)} 章 / {len(issues)} 问题")
        print("=" * 50)
        for it in issues:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(it["severity"], "⚪")
            print(f"  {icon} [{it['severity']}] Ch{it['chapter']}: {it['detail']}")
    sys.exit(0 if not issues else 1)


if __name__ == "__main__":
    main()
