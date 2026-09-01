#!/usr/bin/env python3
"""
LLM 输出归一化 — 把中文自由键转成 schema 结构

问题：json_mode 下模型倾向用中文键名（如「情绪写法模式」），
而 schema 要求英文键（如 emotion_handling.mode）。
内容质量没问题，缺的只是结构映射。这里做一次稳妥的归一化。

用法（被 pipeline.py import，也可独立测试）：
  python normalize.py <raw_pass2.json> <raw_pass3.json> --out voice-card.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# 通用工具
# --------------------------------------------------------------------------

def first(d: dict, *keys):
    """按多个候选键取第一个非空值。支持嵌套：键的值若是 dict，递归取第一个非空叶子。"""
    for k in keys:
        if k in d and d[k] not in (None, "", [], {}):
            v = d[k]
            if isinstance(v, dict):
                # 嵌套 dict：取第一个非空字符串/列表叶子
                for leaf in v.values():
                    if leaf not in (None, "", [], {}):
                        return leaf
            return v
    return None


def as_list(v):
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        return [s.strip() for s in re.split(r'[，,;；/、]', v) if s.strip()]
    return []


def as_str(v):
    """字符串直接返回；列表取第一条；dict 取第一个非空叶子。"""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, list) and v:
        return as_str(v[0])
    if isinstance(v, dict):
        for leaf in v.values():
            s = as_str(leaf)
            if s:
                return s
    return ""


# 中文引号对（兼容弯引号/直角引号/英文引号/Unicode弯引号 \u201c\u201d\u2018\u2019）
_QUOTE_RE = re.compile(r'[\u300c\u300e\u201c\u2018"\']([^\u300d\u300f\u201d\u2019"\']{2,12})[\u300d\u300f\u201d\u2019"\']')

# 常见口头禅/语气词模式（无引号时从规则文本中补充提取）
_TIC_INLINE_RE = re.compile(
    r'(?:例如|比如|像|常用的?)[：:\s]*'
    r'[\u300c\u300e\u201c\u2018"\']*'
    r'([^\s\u3000，。\u300d\u300f\u201d\u2019"\'、]{1,8})'
)


def extract_quoted(desc: str, max_items: int = 8) -> list:
    """从描述文本中抽取引号内的短短语（口头禅/称呼的核心词）。

    例如「自称『老子』」→「老子」；「叫对方『唐小雨』」→「唐小雨」。
    兼容 Unicode 弯引号 \u2018\u2019（chireng 数据实际使用的引号）。
    过滤掉「自称/例如/说明」等元词。用于把 dict 形态的 verbal_tics
    （{情境, 规则}）转成纯字符串口头禅列表。
    """
    out = []
    for m in _QUOTE_RE.finditer(desc):
        kw = m.group(1).strip()
        if not kw or any(w in kw for w in ("自称", "例如", "说明", "表示", "频率", "常常", "的")):
            continue
        if kw not in out:
            out.append(kw)
    return out[:max_items]


def extract_tics_from_text(text: str, max_items: int = 6) -> list:
    """从规则描述文本中提取口头禅关键词（引号提取的增强版）。

    策略：
    1. 先提取引号内的短语（兼容所有引号类型）
    2. 提取"例如：X"模式中的X（chireng 数据里口头禅常跟在"例如"后面）
    3. 去重并限制数量
    """
    out = extract_quoted(text, max_items)
    if len(out) >= max_items:
        return out[:max_items]

    # 补充：从"例如：X"模式提取（chireng 的 dict 里口头禅常这样出现）
    for m in _TIC_INLINE_RE.finditer(text):
        kw = m.group(1).strip()
        if kw and len(kw) >= 2 and kw not in out:
            # 过滤非口头禅词（描述性词语）
            if not any(w in kw for w in ("反问", "设问", "祈使", "陈述", "句式", "语气", "口吻",
                                          "方式", "手法", "技巧", "策略", "拒绝", "表达")):
                out.append(kw)
                if len(out) >= max_items:
                    return out[:max_items]
    return out[:max_items]


def _tics_to_str_list(v) -> list:
    """verbal_tics 统一转纯字符串列表：
    - 已是字符串列表 → 原样（去重）
    - dict 列表（{情境,规则}）→ 用 extract_tics_from_text 从每条规则中提取口头禅
    - 单个 dict → 同上

    修复：之前只用 extract_quoted（仅匹配引号内），chireng 数据的口头禅
    常用 \\u2018\\u2019 弯引号或跟在"例如"后面无引号，导致提取为空。
    现在用 extract_tics_from_text（引号+模式双重提取）。
    """
    if isinstance(v, list):
        out = []
        for item in v:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                ctx = item.get("情境") or item.get("context") or item.get("场景") or ""
                rule = item.get("规则") or item.get("rule") or ""
                desc = f"{ctx}：{rule}" if ctx and rule else (ctx or rule or str(item))
                out.extend(extract_tics_from_text(desc))
        return list(dict.fromkeys(x for x in out if x))
    if isinstance(v, dict):
        ctx = v.get("情境") or v.get("context") or ""
        rule = v.get("规则") or v.get("rule") or ""
        desc = f"{ctx}：{rule}" if ctx and rule else str(v)
        return extract_tics_from_text(desc)
    return as_list(v)


# --------------------------------------------------------------------------
# Pass2：角色声线归一化
# 输入形如：{"唐雨": {"拒绝方式": "...", "绝不会说的话": [...], "说话特征": [...]}, ...}
# 输出：character_voices 数组
# --------------------------------------------------------------------------

PASS2_KEYS = {
    "refusal": ["拒绝方式", "怎么拒绝", "拒绝", "refusal_pattern", "rejection_style"],
    "never": ["绝不会说的话", "绝不说", "never_says"],
    "anger": ["生气时", "愤怒时", "生气", "anger_pattern"],
    "tics": ["说话特征", "口头禅", "语气词", "说话习惯", "verbal_tics"],
    "habit": ["小动作", "固定动作", "physical_habit"],
    "avg_len": ["平均字数", "单次发言平均字数", "avg_utterance_length"],
    "start": ["起始状态", "开始状态", "start_state"],
    "end": ["结束状态", "最终状态", "end_state"],
    "turning": ["转折章节", "质变章节", "turning_chapters"],
    "arc_type": ["弧光类型", "成长弧类型", "arc_type"],
    "key_rules": ["key_rules", "行为规则", "关键规则"],
}


# 常见角色名 → 角色类型（基于流行网文命名规律，可扩展）
ROLE_NAME_HINTS = [
    (("男主", "男一", "男主角", "he", "他"), "主角"),
    (("女主", "女一", "女主角", "she", "她"), "女主"),
    (("反派", "女二", "男二", "校霸", "恶毒", "白莲"), "反派" if False else "配角"),
]


def _role_for(name: str, spec: dict, position: int = 99) -> str:
    """判断角色身份：优先 spec 声明 → 名字关键词 → 位置兜底（第一个=主角，第二个=女主）。"""
    declared = as_str(spec.get("角色") or spec.get("role") or "")
    if declared:
        for r in ("主角", "女主", "男主", "反派", "导师", "配角"):
            if r in declared:
                return r
    if any(k in name for k in ("女主", "女主角", "女主一", "女主二号")):
        return "女主"
    if any(k in name for k in ("男主", "男主角")):
        return "主角"
    if any(k in name for k in ("反派", "恶毒", "女配", "男配")):
        return "反派" if "反派" in name else "配角"
    # 位置兜底：仅第一个角色安全（Pass2 通常把最重要角色排最前，多为男主）。
    # 不自动判女主——Pass2 顺序不可靠（可能女二排第二），宁可保守判配角待人工校验。
    if position == 0:
        return "主角"
    return "配角"


def _extract_signature(spec: dict) -> dict:
    """从角色 spec 中提取 speech_signature（兼容中文/英文键 + speech_style 格式）。

    兼容的键名：
    - refusal: 拒绝方式 / refusal_pattern / rejection_style
    - never: 绝不会说的话 / never_says
    - anger: 生气时 / anger_pattern
    - tics: 说话特征 / 口头禅 / verbal_tics
    - key_rules: key_rules / 行为规则（新 pass2 格式，合并到 refusal_pattern）
    """
    refusal = as_str(first(spec, *PASS2_KEYS["refusal"]) or "")
    # 如果 refusal 为空但有 key_rules，用 key_rules 的第一条作为拒绝方式补充
    key_rules = first(spec, *PASS2_KEYS["key_rules"])
    if not refusal and isinstance(key_rules, list) and key_rules:
        refusal = as_str(key_rules[0])

    tics_raw = first(spec, *PASS2_KEYS["tics"])
    tics = _tics_to_str_list(tics_raw)

    never = as_list(first(spec, *PASS2_KEYS["never"]))
    # 如果 never_says 为空但有 key_rules，从 key_rules 中提取"绝不会"模式作为补充
    if not never and isinstance(key_rules, list):
        for rule in key_rules:
            if isinstance(rule, str) and any(kw in rule for kw in ("绝不会", "从不", "不会", "never")):
                never.append(rule[:30])

    ss = {
        "refusal_pattern": refusal,
        "never_says": never,
        "anger_pattern": as_str(first(spec, *PASS2_KEYS["anger"]) or ""),
        "verbal_tics": tics,
        "physical_habit": as_list(first(spec, *PASS2_KEYS["habit"])),
    }
    av = first(spec, *PASS2_KEYS["avg_len"])
    if isinstance(av, (int, float)):
        ss["avg_utterance_length"] = int(av)
    return {k: v for k, v in ss.items() if v not in (None, "", [])}


def _extract_arc(spec: dict) -> dict:
    """从角色 spec 中提取成长弧光。"""
    arc = {
        "start_state": as_str(first(spec, *PASS2_KEYS["start"]) or ""),
        "end_state": as_str(first(spec, *PASS2_KEYS["end"]) or ""),
        "turning_chapters": as_list(first(spec, *PASS2_KEYS["turning"])),
        "arc_type": as_str(first(spec, *PASS2_KEYS["arc_type"]) or ""),
    }
    return {k: v for k, v in arc.items() if v not in (None, "", [])}


def normalize_pass2(pass2: dict) -> list:
    """把角色名为键的 dict 转成 character_voices 数组。"""
    voices = []
    # 兼容三种形态：
    # 1. {"唐雨": {...}, "边炀": {...}}          —— 角色名为键
    # 2. {"character_voices": [...]}             —— 已是数组
    # 3. {"name": "桑幼", "说话风格": [...], ...} —— 单角色扁平结构（模型偷懒只输出一个）
    raw = pass2.get("character_voices", pass2)
    # 形态 4：{"角色列表": [...], "角色声线分析": [{角色/name: ..., 拒绝方式: ...}]}
    voice_list = None
    for k in ("角色声线分析", "角色分析", "characters", "voices"):
        if k in pass2 and isinstance(pass2[k], list):
            voice_list = pass2[k]
            break
    if voice_list is not None:
        # 形态 4：角色声线分析数组（每项含 角色/name + 声线字段）
        for item in voice_list:
            if not isinstance(item, dict):
                continue
            # 兼容 speech_signature / speech_style / 直接字段
            spec = item.get("speech_signature") or item.get("speech_style") or item
            name = item.get("角色") or item.get("name") or item.get("角色名") or ""
            if not name:
                continue
            voices.append({
                "name": name,
                "role": item.get("role") or item.get("身份") or _role_for(name, spec, position=len(voices)),
                "speech_signature": _extract_signature(spec),
                "arc": item.get("arc", {}) or _extract_arc(spec),
            })
    elif isinstance(pass2, dict) and "name" in raw and isinstance(raw.get("name"), str):
        # 单角色扁平结构 → 包装成单个角色
        spec = {k: v for k, v in raw.items() if k not in ("name", "_meta")}
        voices.append({
            "name": raw["name"],
            "role": _role_for(raw["name"], spec, position=0),
            "speech_signature": _extract_signature(spec),
            "arc": _extract_arc(spec),
        })
    elif isinstance(raw, dict):
        for name, spec in raw.items():
            if not isinstance(spec, dict) or name.startswith("_"):
                continue
            voices.append({
                "name": name,
                "role": _role_for(name, spec, position=len(voices)),
                "speech_signature": _extract_signature(spec),
                "arc": _extract_arc(spec),
            })
    elif isinstance(raw, list):
        # 已是数组形态，但键名可能是中文 → 逐条映射
        for item in raw:
            if not isinstance(item, dict):
                continue
            spec = item.get("speech_signature", item)
            name = item.get("name") or item.get("角色名") or item.get("角色") or ""
            if not name:
                continue
            voices.append({
                "name": name,
                "role": item.get("role") or _role_for(name, spec, position=len(voices)),
                "speech_signature": _extract_signature(spec),
                "arc": item.get("arc", {}) or _extract_arc(spec),
            })
    # 排序：主角/女主靠前
    order = {"主角": 0, "女主": 1, "男主": 1}
    voices.sort(key=lambda v: order.get(v.get("role"), 9))
    return voices


# --------------------------------------------------------------------------
# Pass3：文风归一化
# 输入形如：{"情绪写法模式": "混合式", "句法节奏规律": "...", "banned 字段（负空间）": [...]}
# 输出：narration / dialogue / emotion_handling / imagery / banned
# --------------------------------------------------------------------------

POV_MAP = {
    "第一人称": "第一人称",
    "第三人称限知": "第三人称限知",
    "第三人称有限": "第三人称限知",
    "有限视角": "第三人称限知",
    "第三人称全知": "第三人称全知",
    "全知": "第三人称全知",
    "多视角": "多视角轮换",
}


def _find_key(node, *keywords, depth=0):
    """按键名关键词查找节点值，返回命中的**原始值**（不做叶子下钻）。

    与 fuzzy_find 的区别：命中的键即使值是 dict，也原样返回，
    交由调用方决定怎么处理（split_anti / as_str / 再下钻）。
    depth 上限 4 层，防止异常结构无限递归。
    """
    if depth > 4 or not isinstance(node, dict):
        return None
    for k, v in node.items():
        if any(kw in str(k) for kw in keywords):
            return v
    for v in node.values():
        r = _find_key(v, *keywords, depth=depth + 1)
        if r is not None:
            return r
    return None


def fuzzy_find(node, *keywords):
    """递归模糊查找：在嵌套 dict/list 里找键名包含任一关键词的第一个值。
    Pass3 输出键名不稳定（写法规律/负空间（banned字）等变体），精确匹配不可靠。
    返回：str/list 值优先；dict 值会继续递归找叶子（避免漏掉嵌套结构）。

    修复：键命中但值是「纯字符串叶子组成的 dict」时，原实现会因递归找不到
    同名子键而返回 None，导致数据丢失（典型如 sangshi 的
    anti_pattern={"rhythm": "...", "imagery": "..."}）。现在兜底用 as_str 取
    第一个非空叶子。仅在原逻辑返回 None 时生效，不会改变已有命中结果。
    """
    if isinstance(node, dict):
        for k, v in node.items():
            if any(kw in str(k) for kw in keywords):
                if isinstance(v, (str, list)):
                    return v
                # dict 值：递归找其中的 str/list 叶子
                r = fuzzy_find(v, *keywords)
                if r is not None:
                    return r
                # 兜底：dict 的子键都不含关键词时，取其第一个非空叶子
                s = as_str(v)
                if s:
                    return s
        for v in node.values():
            r = fuzzy_find(v, *keywords)
            if r is not None:
                return r
    elif isinstance(node, list):
        for v in node:
            r = fuzzy_find(v, *keywords)
            if r is not None:
                return r
    return None


# 「避免X，Y」→（正面写法 Y，反例 X）
_ANTI_CLAUSE_RE = re.compile(r'^(避免[^，,；;。]*)[\s，,；;。]*(.*)$')

# 比喻领域标签中的举例部分（括号内），schema 要求领域名，不带具体喻体
_DOMAIN_EXAMPLE_RE = re.compile(r'[（(]')


def split_anti(value: str) -> tuple:
    """把「避免X，必须Y」拆成 (正面写法 Y, 反例 X)。

    qingning/sangshi 的 anti_pattern 条目都是这个句式，正面写法和反面
    约束写在同一句里，拆开才能分别填进 examples.pattern / anti_pattern。
    拆不出「避免」时返回 (原句, "")。
    """
    text = (value or "").strip()
    m = _ANTI_CLAUSE_RE.match(text)
    if m:
        return (m.group(2).strip() or text), m.group(1).strip()
    return text, ""


def clean_domain_label(label: str, max_len: int = 12) -> str:
    """把比喻领域标签收敛成纯领域名。

    schema 要求：「比喻取材领域，如「刀兵」「野兽」「天象」。领域比具体喻体
    更可复用」。而模型常输出「日常生活物件/场景（如'手机'、'龙眼树'）」这种
    带举例的长标签。这里去掉括号举例并限长。
    """
    s = _DOMAIN_EXAMPLE_RE.split((label or "").strip())[0].strip()
    s = s.rstrip("、/，,；; ")
    if len(s) > max_len:
        s = s[:max_len].rstrip("、/，,；; ")
    return s


# burst_pattern 提取的关键词优先级：越靠前越贴近「短句爆发出现在什么场景」
BURST_KEY_GROUPS = (
    ("短句爆发", "burst", "爆发"),
    ("句式节奏", "节奏", "句法", "sentence_length", "length_distribution"),
    ("rhythm", "pacing"),
)


def _shorten_domains(domains) -> list:
    """把比喻领域标签截成 ≤6 字简短标签，去掉括号内例子。

    例如「日常生活物件/场景（如'手机'、'保证书'）」→「日常物件」。
    策略：去括号例子 → 斜杠取更具体的一段 → 去冗余后缀 → 保底截断 6 字。
    """
    result = []
    for d in as_list(domains):
        s = str(d)
        # 去掉括号内例子
        s = s.split("（")[0].split("(")[0].strip()
        # 斜杠：取「具体语义更强」的一段（优先后段，因后段常是限定词如"行为/反应"）
        if "/" in s:
            segs = [x.strip() for x in s.split("/") if x.strip()]
            # 后段若只是"场景/描写/行为/反应"这类泛化词，则取前段；否则取后段（更具体）
            generic_tail = {"场景", "描写", "行为", "反应", "意象", "细节"}
            if segs and segs[-1] in generic_tail and len(segs) >= 2:
                s = segs[-2]
            elif segs:
                s = segs[-1]
        s = s.strip()
        # "X与Y"并列结构：取前段（"身体动作与反应" → "身体动作"）
        if "与" in s:
            s = s.split("与")[0].strip()
        # 精简常见冗余前缀
        s = s.replace("日常生活", "日常").strip()
        # 保底：仍超 6 字则截断
        if len(s) > 6:
            s = s[:6]
        if s:
            result.append(s)
    # 去重保序
    seen = set()
    out = []
    for d in result:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def extract_burst_pattern(pass3: dict) -> str:
    """按优先级提取「短句爆发出现在什么场景」。

    三本书的 pass3 键名完全不同，此前只用中文关键词（节奏/短句/句法）查，
    导致英文键的两本提取为空：
      - chireng: sentence_rhythm_pattern.short_burst_scene   （英文键）
      - sangshi: rhythm_pattern.sentence_length_distribution （英文键）
      - qingning: patterns.句式节奏                          （中文键，原本就能命中）
    """
    for group in BURST_KEY_GROUPS:
        s = as_str(_find_key(pass3, *group))
        if s and len(s) >= 8:
            return s
    return ""


def _anti_text(anti, banned_words) -> str:
    """把反例节点（dict/str/list）压成一段文本，供 examples.anti_pattern 使用。"""
    if isinstance(anti, dict) and anti:
        parts = [f"{k}：{as_str(v)}" for k, v in anti.items() if as_str(v)]
        return "；".join(parts)
    s = as_str(anti)
    if s:
        return s
    if isinstance(banned_words, list) and banned_words:
        words = [as_str(w) for w in banned_words if as_str(w)]
        if words:
            return "避免使用：" + "、".join(words[:8])
    return ""


def extract_emotion_examples(pass3: dict, mode: str) -> list:
    """从 pass3 提取「情绪→写法」映射 examples。

    兼容三本书的四种结构（此前只有 chireng/qingning/sangshi 全落空）：
      - sangshi : sentiment_pattern.switching_rules = [{scene, mode, example_pattern}]
                  → 一条规则一个 example
      - chireng : emotion_mode_analysis.switching_pattern = str
                  → 单条通用 example，anti 取自 banned_elements
      - qingning: anti_pattern = {名: "避免X，必须Y"} → 拆成正反两条填进 examples
      - 兜底    : banned 词表合成一条通用反例
    """
    rules = _find_key(pass3, "switching_rules", "switching_pattern",
                      "切换规律", "混合规律", "模式特征")
    anti = _find_key(pass3, "anti_pattern", "反例")
    banned_words = _find_key(pass3, "banned", "负空间", "禁忌", "禁用")
    generic = _find_key(pass3, "情绪写法模式", "sentiment_pattern", "情绪")
    generic_str = as_str(generic)
    # sentiment_pattern 是 dict 时 as_str 只取到 "混合式"，太短没用
    if generic_str and len(generic_str) < 20:
        generic_str = ""

    examples = []
    if isinstance(rules, list) and rules:
        anti_txt = _anti_text(anti, banned_words)
        for item in rules:
            if not isinstance(item, dict):
                continue
            scene = as_str(item.get("scene") or item.get("场景") or "通用")
            sub_mode = as_str(item.get("mode") or item.get("模式") or "")
            pat = as_str(item.get("example_pattern") or item.get("规律") or "")
            examples.append({
                "emotion": scene,
                "pattern": f"[{sub_mode}] {pat}" if sub_mode and pat else (pat or f"见 {mode}"),
                "anti_pattern": anti_txt,
            })
    elif as_str(rules):
        examples.append({
            "emotion": "通用",
            "pattern": as_str(rules),
            "anti_pattern": _anti_text(anti, banned_words),
        })
    elif isinstance(anti, dict) and anti:
        # 命名反例：每条拆成正反两半
        for name, val in anti.items():
            pos, neg = split_anti(as_str(val))
            if pos or neg:
                examples.append({"emotion": name, "pattern": pos, "anti_pattern": neg})

    # 通用规律（scene→mode 的整体描述）补到最前，作为总纲
    if generic_str and generic_str not in [e.get("pattern") for e in examples]:
        examples.insert(0, {
            "emotion": "通用",
            "pattern": generic_str,
            # 2026-09-01 修复：通用总纲也带上反例（取自 anti/banned），
            # 否则触发 validate 的"缺 anti_pattern"警告（qingning 曾因此 WARN）。
            "anti_pattern": _anti_text(anti, banned_words),
        })

    # 仍为空：用 banned 词表兜底一条
    if not examples:
        txt = _anti_text(anti, banned_words)
        if txt:
            examples.append({"emotion": "通用", "pattern": f"见 {mode}", "anti_pattern": txt})
    return examples[:8]


def normalize_pass3(pass3: dict) -> tuple:
    pov_raw = as_str(fuzzy_find(pass3, "视角", "pov") or "")
    pov = next((v for k, v in POV_MAP.items() if k in pov_raw), "第三人称限知")

    # 2026-09-01 修复：改用 extract_burst_pattern() 而非旧的中文关键词 fuzzy_find，
    # 否则英文键结构（chireng 的 sentence_rhythm_pattern / sangshi 的 rhythm_pattern）提取为空。
    burst = extract_burst_pattern(pass3)

    # tense_feel：从多个可能位置提取叙述距离感
    tense_feel = as_str(
        fuzzy_find(pass3, "叙述距离", "叙述者介入", "tense_feel")
        or ""
    )
    # 如果 fuzzy_find 找不到，从嵌套结构中推导
    if not tense_feel:
        # chireng 格式: emotion_mode_analysis 里可能有叙述距离描述
        emo_analysis = pass3.get("emotion_mode_analysis") or {}
        for v in emo_analysis.values():
            if isinstance(v, str) and ("叙述" in v or "视角" in v or "距离" in v or "贴近" in v):
                tense_feel = v[:80]
                break
    if not tense_feel:
        # qingning/sangshi 格式: 从 patterns/rhythm_pattern 推导
        for key in ["patterns", "rhythm_pattern", "sentiment_pattern"]:
            node = pass3.get(key) or {}
            if isinstance(node, dict):
                for v in node.values():
                    if isinstance(v, str) and ("叙述" in v or "视角" in v or "贴近" in v or "限知" in v):
                        tense_feel = v[:80]
                        break
            if tense_feel:
                break
    # 兜底：从 pov 推导，或截取已提取内容的前半段
    if not tense_feel or len(tense_feel) > 60:
        # 如果提取到的是节奏描述而非叙述距离，截取前半段
        if tense_feel and ("句长" in tense_feel or "波动" in tense_feel):
            # 从节奏描述推导叙述距离
            if "限知" in pov or "主角" in tense_feel:
                tense_feel = "贴身跟随主角感官，叙述者几乎不介入"
            else:
                tense_feel = "叙述距离适中，兼顾主角内心与外部观察"
        elif not tense_feel:
            if "限知" in pov:
                tense_feel = "贴身跟随主角，几乎无叙述者介入"
            elif "全知" in pov:
                tense_feel = "全知视角，叙述者可自由切换"
            else:
                tense_feel = "贴身跟随主角感官和思维"

    # chapter_opening_patterns：从 pass3 中提取章节开头模式
    opening_patterns = []
    opening_raw = fuzzy_find(pass3, "开头", "开篇", "opening", "章节起始") or ""
    if isinstance(opening_raw, str) and len(opening_raw) > 5:
        # 解析出模式列表
        for pat in ["直入对话", "场景白描", "承接上章悬念", "时间跳跃", "内心独白", "旁白点题",
                     "动作开场", "对话开场", "环境描写", "回忆切入"]:
            if pat in opening_raw:
                opening_patterns.append({"pattern": pat, "frequency": 1, "example_structure": ""})
    if not opening_patterns:
        # 从 burst_pattern 和 pov 推导默认模式
        if "限知" in pov:
            opening_patterns = [
                {"pattern": "场景白描", "frequency": 3, "example_structure": "[环境状态]+[人物动作]"},
                {"pattern": "内心独白", "frequency": 2, "example_structure": "[心理活动]+[场景引入]"},
            ]
        else:
            opening_patterns = [
                {"pattern": "承接上章悬念", "frequency": 2, "example_structure": "[上章钩子]+[新场景]"},
            ]

    narration = {
        "pov": pov,
        "pov_switch_rule": "",
        "tense_feel": tense_feel,
        "sentence_rhythm": {
            "avg_length": 0,
            "short_ratio": 0,
            "long_ratio": 0,
            "burst_pattern": as_str(burst),
        },
        "paragraph": {},
        "chapter_opening_patterns": opening_patterns,
    }

    dialogue = {
        "dialogue_ratio": 0,  # pipeline 会用 metrics 覆盖
        "tag_style": as_str(fuzzy_find(pass3, "对话标记", "对话标签", "对话模式", "tag_style") or ""),
        "subtext_level": "直白",
        "character_voices": [],
    }

    mode_raw = as_str(fuzzy_find(pass3, "情绪写法", "情绪", "emotion") or "")
    # 情绪写法可能是嵌套 dict（{"模式": "直陈式", "规律": "..."}），优先取「模式」字段
    mode_node = None
    for k, v in pass3.items():
        if "情绪" in k and isinstance(v, dict):
            mode_node = v
            break
    if mode_node:
        m = as_str(mode_node.get("模式") or mode_node.get("mode") or "")
        if m:
            mode_raw = m
    mode = next((m for m in ("直陈式", "体感式", "动作外化式", "环境投射式", "混合式") if m in mode_raw), "混合式")

    # 体感词：优先取显式词表；次选从「感官重心.具体化方式」「人物互动公式」「句法节奏」嵌套文本中
    # 提取引号内短语（如「手指都捏白了」「耷拉着脑袋」「心跳如鼓」）
    # 注意：模型可能用中文弯引号 ‘ ’（U+2018/2019）或直角引号 「」
    QUOTED = re.compile(r'[「『“‘\']([^」』”’\']{2,8})[」』”’\']')
    # 非体感词的干扰项（角色口头禅/对话内容，不属于身体反应词库）
    NON_BODY = ("老子", "唐小雨", "把头露出来", "我没，我没", "声若蚊鸣的", "懂？", "行不行")
    # 体感词：递归收集所有引号内短语（模型可能用嵌套结构）
    body_vocab = as_list(first(pass3, "高频动作外化词汇", "身体反应", "body_reaction_vocabulary"))
    if not body_vocab:
        def collect_quoted(node):
            out = []
            if isinstance(node, dict):
                for v in node.values():
                    out.extend(collect_quoted(v))
            elif isinstance(node, list):
                for v in node:
                    out.extend(collect_quoted(v))
            elif isinstance(node, str):
                out.extend(QUOTED.findall(node))
            return out
        body_vocab = collect_quoted(pass3)
        # 去重 + 过滤无实义/非体感词
        body_vocab = [w for w in dict.fromkeys(body_vocab)
                      if len(w) >= 2 and not any(x in w for x in NON_BODY)]
    emotion_handling = {
        "mode": mode,
        "body_reaction_vocabulary": body_vocab[:20],
        "examples": [],
    }
    # 2026-09-01 修复：改用 extract_emotion_examples() 而非旧的 fuzzy_find 单键提取，
    # 否则三本书的「情绪→写法」examples 全部落空（函数已兼容四种 pass3 结构但从未接线）。
    emotion_handling["examples"] = extract_emotion_examples(pass3, mode)

    # 意象系统：多种路径查找（pass3 输出结构不稳定）
    # 1. 顶层 imagery_system / imagery
    # 2. patterns.意象系统（qingning 格式）
    # 3. fuzzy_find 递归查找
    img_raw = pass3.get("imagery_system") or pass3.get("imagery") or {}
    if not isinstance(img_raw, dict) or not img_raw:
        # 从 patterns 子对象取
        patterns = pass3.get("patterns", {})
        if isinstance(patterns, dict):
            img_raw = patterns.get("意象系统") or patterns.get("imagery_system") or {}
    if not isinstance(img_raw, dict):
        img_raw = {}

    # high_freq_metaphor_domains
    domains = img_raw.get("high_freq_metaphor_domains") or as_list(fuzzy_find(pass3, "比喻", "意象", "metaphor"))
    # 2026-09-01 修复：把带例子的长标签（如"日常生活物件/场景（如'手机'…）"）截成 ≤6 字简短标签，
    # 否则触发 validate 的"比喻领域过长"警告（sangshi 曾报 28 字/19 字）。
    domains = _shorten_domains(domains)

    # sensory_preference：兼容中文键（视觉/听觉/触觉/嗅觉/味觉）和英文键
    sensory_raw = img_raw.get("sensory_preference") or {}
    sensory = {}
    if isinstance(sensory_raw, dict):
        SENSE_MAP = {"视觉": "visual", "听觉": "auditory", "触觉": "tactile", "嗅觉": "olfactory", "味觉": "gustatory"}
        for k, v in sensory_raw.items():
            if isinstance(v, (int, float)):
                en_key = SENSE_MAP.get(k, k)
                sensory[en_key] = round(float(v), 3)
        # 归一化到和=1.0
        total = sum(sensory.values())
        if total > 0 and abs(total - 1.0) > 0.05:
            sensory = {k: round(v / total, 3) for k, v in sensory.items()}

    # signature_devices：可能是字符串或列表
    devices_raw = img_raw.get("signature_devices") or []
    if isinstance(devices_raw, str):
        devices = [devices_raw] if devices_raw else []
    elif isinstance(devices_raw, list):
        devices = [str(d) for d in devices_raw if d]
    else:
        devices = []

    imagery = {
        "high_freq_metaphor_domains": as_list(domains),
        "sensory_preference": sensory,
        "signature_devices": devices,
    }

    # 负空间/禁忌词：可能是 {"banned": [...]} 或 ["..."] 或嵌套 dict
    never = fuzzy_find(pass3, "负空间", "banned", "禁忌", "回避", "禁用")
    if isinstance(never, dict):
        never = never.get("banned") or next((v for v in never.values() if isinstance(v, list)), [])
    banned = {
        "never_used_words": as_list(never),
        "avoided_structures": [],
        "genre_taboos": [],
    }

    return narration, dialogue, emotion_handling, imagery, banned


# --------------------------------------------------------------------------
# 指标回填：把 metrics.py 的量化值写进 voice-card 结构
# --------------------------------------------------------------------------

def apply_metrics(narration: dict, dialogue: dict, metrics: dict) -> tuple:
    """把量化指标回填到 narration / dialogue 的对应字段。

    修复前的问题：pipeline 只覆盖 dialogue.dialogue_ratio，
    narration.sentence_rhythm 的 avg_length/short_ratio/long_ratio 一直是
    normalize 里的硬编码 0（metrics 明明算得出 avg_sentence_len）。
    burst_pattern 是 LLM 分析的定性结论，不参与覆盖。

    Args:
        narration: normalize_pass3 产出的 narration 结构
        dialogue: normalize_pass3 产出的 dialogue 结构
        metrics: metrics.compute() 的完整输出

    Returns:
        (narration, dialogue) —— 原地修改后返回
    """
    sr = narration.setdefault("sentence_rhythm", {})
    # 仅当 metrics 给出有效值时覆盖（0 值不覆盖，避免把 '' 冲掉）
    for src_key, dst_key in (("avg_sentence_len", "avg_length"),
                             ("short_ratio", "short_ratio"),
                             ("long_ratio", "long_ratio")):
        v = metrics.get(src_key)
        if isinstance(v, (int, float)) and v:
            sr[dst_key] = v
    d_ratio = metrics.get("dialogue_ratio")
    if isinstance(d_ratio, (int, float)):
        dialogue["dialogue_ratio"] = d_ratio
    return narration, dialogue


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="LLM 输出归一化（中文键 → schema 结构）")
    ap.add_argument("pass2", help="pass2 原始输出 JSON")
    ap.add_argument("pass3", help="pass3 原始输出 JSON")
    args = ap.parse_args()

    p2 = json.loads(Path(args.pass2).read_text(encoding="utf-8"))
    p3 = json.loads(Path(args.pass3).read_text(encoding="utf-8"))
    voices = normalize_pass2(p2)
    narration, dialogue, emotion, imagery, banned = normalize_pass3(p3)
    print(json.dumps({
        "character_voices": voices,
        "narration": narration,
        "dialogue": dialogue,
        "emotion_handling": emotion,
        "imagery": imagery,
        "banned": banned,
    }, ensure_ascii=False, indent=2)[:1200])


if __name__ == "__main__":
    main()
