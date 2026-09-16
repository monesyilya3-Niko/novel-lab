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
        texts[int(m.group(1)) if m else 1] = source.read_text(encoding="utf-8")
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

# ---------------------------------------------------------------------------
# 中文数字支持（2026-09-16 新增）
# ---------------------------------------------------------------------------
# 旧实现只认阿拉伯数字，而中文小说里的年龄/天数/金额绝大多数写作汉字数字，
# 导致本项检测在中文长篇上「零覆盖」——报 0 问题并不代表一致，而是读不到数据。
# 现同时接受阿拉伯数字与汉字数字。

_CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def _cn_to_int(token: str):
    """把「十八」「二十三」「一百二十」等中文数字转为 int。

    Args:
        token: 阿拉伯数字串或中文数字串。

    Returns:
        int: 解析结果；无法解析时返回 None（调用方跳过）。
    """
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if any(ch not in _CN_DIGITS and ch not in _CN_UNITS for ch in token):
        return None
    total = section = number = 0
    for ch in token:
        if ch in _CN_DIGITS:
            number = _CN_DIGITS[ch]
        else:
            unit = _CN_UNITS[ch]
            section += (number or 1) * unit
            number = 0
    return total + section + number


# 实体名候选里出现这些字，几乎可以断定不是人名（而是「已经不是」「我那时候」这类片段）
# 含「第」：防止「温霜禾第二天」被切成实体名「温霜禾第」（序号类时间词归时间线检测）
_NAME_STOP_CHARS = set(
    "的了着过是不没有在就也都很又再被把给对从和与而但却因为所以之其于则若即使得"
    "个些来去上下里外中间时候我你他她它这那们第"
    "零〇一二两三四五六七八九十百千"
)


def _looks_like_name(name: str) -> bool:
    """粗筛实体名候选：2-4 字且不含功能字。"""
    if not name or not (2 <= len(name) <= 4):
        return False
    return not any(ch in _NAME_STOP_CHARS for ch in name)


# 同一实体 + 数值类别 的抽取模式：捕获 实体名 + 数值 + 单位
# （单位限定为年龄/年份/天数/金额/身高/手机号，避免把普通量词误判为矛盾）
# 实体名用非贪婪匹配，避免把紧随其后的汉字数字吞进名字里。
_NAME_CLS = r'[\u4e00-\u9fff]{2,4}?'
_NUM_CLS = r'(?:[0-9]+|[零〇一二两三四五六七八九十百千]+)'
_GAP_CLS = r'[\s，,、]{0,2}'

AGE_RE = re.compile(r'(' + _NAME_CLS + r')' + _GAP_CLS + r'(' + _NUM_CLS + r')\s*岁')
YEAR_RE = re.compile(r'(' + _NAME_CLS + r')' + _GAP_CLS + r'第?\s*(' + _NUM_CLS + r')\s*年')
DAY_RE = re.compile(r'(' + _NAME_CLS + r')' + _GAP_CLS + r'(' + _NUM_CLS + r')\s*天')
MONEY_RE = re.compile(r'(' + _NAME_CLS + r')' + _GAP_CLS + r'(' + _NUM_CLS + r')\s*[元块]')
HEIGHT_RE = re.compile(r'(' + _NAME_CLS + r')' + _GAP_CLS + r'(' + _NUM_CLS + r')\s*(?:cm|厘米)')
PHONE_RE = re.compile(r'(' + _NAME_CLS + r')' + _GAP_CLS + r'(?:电话|手机|号码|拨打|拨了)?\s*(\d{11})')

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
    """检测同一实体数值类别在不同章出现互斥取值。

    2026-09-16：同时接受阿拉伯数字与汉字数字；实体名候选经 `_looks_like_name`
    粗筛（剔除「已经不是」「我那时候」这类非人名片段），避免汉字数字放开后误报激增。
    """
    issues = []
    # entity_name -> {类别: {取值(int): 首次出现章号}}
    entity_values = {}
    for ch in sorted(texts.keys()):
        text = texts[ch]
        for cat, pat, label in _NUM_PATTERNS:
            for name, raw in pat.findall(text):
                name = name.strip()
                if not _looks_like_name(name):
                    continue
                val = _cn_to_int(raw.strip())
                if val is None:
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

# 对白（引号内）与比喻中的时间词不构成叙述时间锚点
_QUOTE_RE = re.compile(r'“[^”]*”|「[^」]*」|『[^』]*』|"[^"]*"')
_SIMILE_TIME_RE = re.compile(
    r'(?:好像|仿佛|如同|像是|似的|像)[^。！？\n]{0,6}?(?:昨天|今天|前天|明天)')

# 句首「第N天」：句中用法（如「哭完以后，第二天仍要起床」）属惯用语，不作锚点
_DAY_ORDINAL_RE = re.compile(
    r'(?:^|[。！？…\n])\s*第\s*([0-9]{1,3}|[零〇一二两三四五六七八九十百千]{1,3})\s*天')
# 同一枚举窗口：两次锚点相距超过该字数，视为不同场景，互不约束
_SAME_SCENE_WINDOW = 1000


def _narration_only(text: str) -> str:
    """剥离引号内对白与比喻中的时间词，只保留叙述骨架。"""
    cleaned = _QUOTE_RE.sub('', text or '')
    return _SIMILE_TIME_RE.sub('', cleaned)


def _extract_day_ordinals(text: str) -> list:
    """抽取「句首第N天」锚点，返回 [(N, 位置)]，按出现顺序。"""
    out = []
    for m in _DAY_ORDINAL_RE.finditer(_narration_only(text)):
        n = _cn_to_int(m.group(1))
        if n:
            out.append((n, m.start()))
    return out


def _check_timeline_contradictions(texts: dict) -> list:
    """章内「第N天」日序单调性检测（2026-09-16 重写）。

    为什么重写：
        旧实现把「昨天/今天/明天」也当作时间锚点，并以**全书不回落的最高水位线**
        逐章比较（`prev_max = max(prev_max, ch_max)`）。结果是：只要书中任意一章
        出现「明天」，此后**任何不含前瞻时间词的章节都会被判「时间线倒退」**。
        在一本 157 章的长篇上实测产生 33 条误报（占 21% 章节），并直接把
        「逻辑合理」维度打到 0 分、连带 QC 判定 FAIL。
        根因是把**相对指代**（昨天/明天是相对于本章当下，不是书内绝对位置）
        当成了**绝对位置**；且不区分对白与比喻。

    现在只保留可证明的信号：
        同一场景窗口（`_SAME_SCENE_WINDOW` 字）内的「句首第N天」日序必须单调。
        例如「第三天…第二天…第三天…」出现在同一段叙述里，即为编号错误。
        句中「第二天」、对白里的时间词、比喻（「好像昨天才见过」）一律不计入。

    Returns:
        list[dict]: issue 列表，type 固定为 `timeline_contradiction`。
    """
    issues = []
    for ch in sorted(texts.keys()):
        seq = _extract_day_ordinals(texts[ch])
        prev_n = prev_pos = None
        for n, pos in seq:
            if n == 1:
                # 「第一天」显式开启一次新的计数，不与之前的日序比较
                prev_n = prev_pos = None
                continue
            if (prev_n is not None and n < prev_n
                    and (pos - prev_pos) <= _SAME_SCENE_WINDOW):
                issues.append({
                    "type": "timeline_contradiction",
                    "severity": "medium",
                    "chapter": ch,
                    "detail": f"同一段叙述内先写「第{prev_n}天」、后写「第{n}天」"
                              f"（相距 {pos - prev_pos} 字），日序疑似编号错误",
                })
            prev_n, prev_pos = n, pos
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
ALIVE_WORDS = ["出场", "出现", "走来", "说话", "开口", "站起", "坐下", "抬头"]
_DEATH_PROXIMITY = 50  # 死亡词须出现在角色名附近 N 字内才判定该角色死亡


def _name_near_death(name: str, text: str) -> bool:
    """检查角色名附近（±_DEATH_PROXIMITY 字）是否有死亡词。"""
    for m_start in range(len(text)):
        idx = text.find(name, m_start)
        if idx == -1:
            break
        window = text[max(0, idx - _DEATH_PROXIMITY): idx + len(name) + _DEATH_PROXIMITY]
        if any(d in window for d in DEATH_WORDS):
            return True
        m_start = idx + 1
    return False


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
            # HIGH：死亡判定改为角色名邻近窗口，不再整章一刀切
            is_death = _name_near_death(nm, text)
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
        llm_hook: Optional[Callable[[list[dict]], list[dict]]]，默认 None（纯算法）。
                  非 None 时对第一层检测结果做「LLM 因果合理性二次判定」：
                  入参为第一层完整 issue 列表，出参为过滤后 issue 列表。
                  若 llm_hook 抛异常，则捕获并回退返回纯算法结果（双保险）。

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

    # 第二层：LLM 因果合理性二次判定（仅当显式传入 callable 时启用）
    if llm_hook is not None:
        try:
            issues = llm_hook(issues)
        except Exception:
            # 防御兜底：即使传入的 hook 不健壮，也绝不让异常冒泡，回退纯算法结果
            pass
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
