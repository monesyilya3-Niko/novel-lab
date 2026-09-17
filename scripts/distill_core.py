# -*- coding: utf-8 -*-
"""蒸馏核心库（纯函数，无第三方依赖）。

本模块是「蒸馏层」的纯逻辑内核，负责把同一题材下多本拆书产出的四类资产
（voice-card / craft-card / structure-obs / commercial-obs）跨书聚合、对齐、
去重、冲突解决、盲区诊断与置信度评分。

设计约束（来自 docs/system_design.md）：
    * 仅使用 Python 标准库，import 白名单严格限定；
    * 原始资产文件永不改写，聚合结果通过 distill.py 另存为 distilled JSON；
    * id 约定稳定可复现，供下一期语义检索/RAG 直接引用；
    * 对齐缺失字段补 null，聚合时跳过 null 不报错，缺失 book 记入盲区。

聚合分层与置信度（§7）：
    * hard（3 本）= 基础置信 0.8；
    * soft（2 本）= 0.6；
    * personal（1 本）= 0.3（不进 rules，仅保留为个人风格）；
    * 每缺一本书扣 0.1、发生冲突再扣 0.1、下限 0.1；
    * confidence < 0.5 置 over_generalized=true。
"""

from __future__ import annotations

import copy
import json
import math
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field as dc_field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 四类资产维度，与资产文件名后缀一一对应。
DIMENSIONS: tuple[str, ...] = (
    "voice-card",
    "craft-card",
    "structure-obs",
    "commercial-obs",
)

# 置信度分层阈值（§7）。
CONFIDENCE_HARD: float = 0.8
CONFIDENCE_SOFT: float = 0.6
CONFIDENCE_PERSONAL: float = 0.3
CONFIDENCE_MIN: float = 0.1
MISSING_BOOK_PENALTY: float = 0.1
CONFLICT_PENALTY: float = 0.1
OVER_GENERALIZED_THRESHOLD: float = 0.5

# voice-card 聚合的 5 个 key（架构师拍板，provenance 不聚合，banned 取交集）。
VOICE_AGG_KEYS: tuple[str, ...] = (
    "narration",
    "dialogue",
    "emotion_handling",
    "imagery",
    "banned",
)

# commercial-obs 统一目标结构（§3.2），缺失补 null。
COMMERCIAL_FIELDS: tuple[str, ...] = (
    "payoff_density",
    "buildup_length",
    "payoff_types",
    "skeleton",
    "dry_spell_tolerance",
    "common_mistakes",
    "paywall",
)

# craft-card 的 10 个分析维度。
CRAFT_DIMENSIONS: tuple[str, ...] = (
    "foreshadowing",
    "information_release",
    "pov_control",
    "scene_transition",
    "tension_building",
    "dialogue_craft",
    "rhythm_control",
    "sensory_craft",
    "narrative_engine",
    "emotional_algorithm",
)

# structure-obs 顶层聚合字段。
STRUCTURE_FIELDS: tuple[str, ...] = (
    "hook_type_freq",
    "hook_min_interval",
    "climax_cycle",
    "foreshadow_avg_span",
    "foreshadow_max_span",
    "foreshadow_concurrent_open",
)

# ---------------------------------------------------------------------------
# 二期 · 技法归一化常量（与 CONFIDENCE_HARD 等并列，统一收敛在此处）
# ---------------------------------------------------------------------------

# 双条件合并判据（降误合并）：技法名 Jaccard 且 skeleton Jaccard 同时达标才合并。
TECHNIQUE_NAME_JACCARD: float = 0.5
TECHNIQUE_SKELETON_JACCARD: float = 0.3
# skeleton 缺失时退化为单条件（仅 name）合并，阈值提高避免误合并。
TECHNIQUE_NAME_ONLY_JACCARD: float = 0.7
# 字符 n-gram 的 n 值。
NGRAM_N: int = 2

# 归一化时移除的停用词（虚词/连接词，不影响技法语义）。
STOPWORDS: frozenset[str] = frozenset(
    {
        "的",
        "了",
        "与",
        "和",
        "及",
        "或",
        "之",
        "在",
        "是",
        "对",
        "把",
        "被",
        "而",
        "并",
        "等",
        "着",
        "过",
        "一个",
        "一种",
        "这种",
        "那种",
        "使用",
        "进行",
        "通过",
        "利用",
        "对于",
        "关于",
    }
)

# 项目根 synonyms.json 路径（可编辑同义词表，缺失/损坏回退空表）。
SYNONYMS_PATH: Path = Path(__file__).resolve().parent.parent / "synonyms.json"


@dataclass
class SourceValue:
    """单本来源的原始取值。

    Attributes:
        book: 来源书标识（如 ``chireng`` / ``qingning`` / ``sangshi``）。
        value: 归一化后的取值（可能为 None 表示该字段缺失）。
        raw: 未归一化的原始值，供盲区诊断与来源回显。
    """

    book: str
    value: Any = None
    raw: Any = None


@dataclass
class AggregatedRule:
    """一条聚合后的蒸馏规则。

    Attributes:
        id: 稳定规则 id，形如 ``<dimension>-<field-slug>-<4位序号>``。
        dimension: 所属维度（voice-card 等四类之一）。
        field: 字段名（或聚合 key，如 ``dialogue_ratio``）。
        kind: 分层（hard / soft / personal）。
        books_count: 实际贡献该值的书籍数量。
        value: 聚合结果（数值中位数 / 列表交集 / 字符串等）。
        sources: 来源明细列表（SourceValue）。
        confidence: 置信度评分（0.0~1.0）。
        conflict: 是否发生同 field 多值分歧。
        over_generalized: 是否过度泛化（confidence < 0.5）。
        blindspot_books: 缺失该字段的书籍列表。
    """

    id: str = ""
    dimension: str = ""
    field: str = ""
    kind: str = "soft"
    books_count: int = 0
    value: Any = None
    sources: List[SourceValue] = dc_field(default_factory=list)
    confidence: float = 0.0
    conflict: bool = False
    over_generalized: bool = False
    blindspot_books: List[str] = dc_field(default_factory=list)


@dataclass
class TechniqueCluster:
    """归一化聚类后的技法簇（二期任务 A）。

    Attributes:
        representative: 簇代表名（簇内频次最高的原文 name）。
        names: 簇内所有原始 name（去重，保持首次出现顺序）。
        skeletons: 簇内所有非空 skeleton（去重）。
        sources: 来源明细（book + raw name），可追溯。
        count: 簇内技法出现总频次（跨书累计）。
        books: 贡献该簇的书籍列表（去重）。
    """

    representative: str = ""
    names: List[str] = dc_field(default_factory=list)
    skeletons: List[str] = dc_field(default_factory=list)
    sources: List[SourceValue] = dc_field(default_factory=list)
    count: int = 0
    books: List[str] = dc_field(default_factory=list)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """把字段路径转为 id 安全的 slug（``/`` 与 ``.`` 转 ``-``）。"""
    return re.sub(r"[/.]+", "-", str(text)).strip("-")


def _flatten(value: Any) -> str:
    """把任意值转成可用于字符串匹配的归一化文本。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        parts = [_flatten(v) for v in value]
        return " | ".join(p for p in parts if p)
    if isinstance(value, dict):
        parts = [_flatten(v) for v in value.values()]
        return " | ".join(p for p in parts if p)
    return str(value)


def _to_number(value: Any) -> Optional[float]:
    """尽力把值转为数值；无法转换返回 None。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.search(r"-?\d+(?:\.\d+)?", value)
        if m:
            return float(m.group())
    return None


def _extract_word_count(buildup_length: Any) -> Optional[float]:
    """从 buildup_length 中抽取字数数值（int 原样，dict 取 ``words``）。"""
    if buildup_length is None:
        return None
    if isinstance(buildup_length, (int, float)):
        return float(buildup_length)
    if isinstance(buildup_length, dict):
        if "words" in buildup_length:
            return _to_number(buildup_length.get("words"))
        # 兜底：尝试 chapters/其他数值。
        for key in ("chapters", "chapters_count", "count"):
            if key in buildup_length:
                return _to_number(buildup_length.get(key))
    if isinstance(buildup_length, str):
        return _to_number(buildup_length)
    return None


def _dedup_payoff_types(items: Any) -> Any:
    """按 ``type`` 去重归一 payoff_types 条目，保留首次出现者的 ratio。

    payoff_types 可能在同一资产内重复出现同名 type（如 type 字段与 ratio
    字符串解析出的清单重叠，或 dict/list 嵌套里同名条目），跨书聚合时会产生
    「同名不同 ratio」的噪音条目。本函数按 type 名去重：

        * 非 list 输入（None / dict 残留等）原样返回；
        * 逐条提取 ``type`` 名（缺失则跳过），首次出现者保留其原始
          ``ratio``（含 None）；后续同名者丢弃；
        * 条目形如 ``{"type": ..., "ratio": ...}``；非 dict 条目若为字符串，
          按 ``type=字符串、ratio=None`` 归一后参与去重。

    保留「首次出现的 ratio」而非取 max/mean，是遵循架构师拍板的
    「保序、不引入二次计算」原则，避免对原始配比做主观加工。
    """
    if not isinstance(items, list):
        return items
    result: List[Any] = []
    seen: set = set()
    for item in items:
        if isinstance(item, dict):
            type_name = item.get("type")
            if type_name is None:
                # 无 type 字段的 dict 保留原样，避免误删结构。
                result.append(item)
                continue
            key = str(type_name)
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        elif isinstance(item, str):
            if item in seen:
                continue
            seen.add(item)
            result.append({"type": item, "ratio": None})
        else:
            # 其它非标量条目保留原样，不参与去重判断。
            result.append(item)
    return result


def _parse_payoff_ratio(value: Any) -> Optional[float]:
    """把单个 payoff ratio 解析为非负有限数值；不可解析返回 None。

    仅接受非 bool 的 int/float 且 ``>= 0`` 且有限（排除 NaN/Inf）。字符串、
    None、负数一律视为不可解析——真实资产里 sangshi 的 ratio 是「铺垫:爆发
    = 10:1」这类**另一种指标**，不是次数也不是占比，不能参与归一。
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _normalize_payoff_ratios(items: Any) -> Any:
    """在**单本书内部**把 payoff_types 的 ratio 归一为「占全书比」。

    真实四本书的 ratio 单位互不相同（次数 / 次数散落字符串 / 占比 0–1 /
    不可解析的比例式），直接跨书并集会得到「既非次数也非占比」的混合数
    （40+10+30+20+2.0+1.0=103）。本函数先逐书归一：

        share_i = ratio_i / sum(该书所有可解析的 ratio)

    规则：
        * 可解析 = 非 bool 的有限非负数值（见 :func:`_parse_payoff_ratio`）；
        * 不可解析项（None / 字符串 / 负数 / NaN / Inf）→ 该项 ratio 置
          ``None``，且**不参与**分母；
        * 分母为 0（全 0 / 空列表 / 全部不可解析）→ 全部置 ``None``，
          不做除法（不抛除零异常）；
        * 非 list 输入原样返回（与 :func:`_dedup_payoff_types` 一致）；
        * 其它键（如 suyixinjian 的 ``buildup_length``）原样保留；
        * 纯函数：不就地修改入参，返回新 list。
    """
    if not isinstance(items, list):
        return items

    parsed = [
        _parse_payoff_ratio(item.get("ratio")) if isinstance(item, dict) else None
        for item in items
    ]
    total = math.fsum(v for v in parsed if v is not None)

    normalized: List[Any] = []
    for item, value in zip(items, parsed):
        if not isinstance(item, dict):
            normalized.append(copy.deepcopy(item))
            continue
        entry = copy.deepcopy(item)
        entry["ratio"] = value / total if (value is not None and total > 0) else None
        normalized.append(entry)
    return normalized


def _parse_payoff_types(value: Any) -> Any:
    """解析 payoff_types 为 list；散落字符串用正则 ``类型:数字`` 解析，失败置 None。

    注意（Bug1 修复）：比例式字符串（如 ``铺垫:爆发 = 10:1``）含 ``=``，是
    「铺垫 vs 爆发」的配比描述，不是「类型:数字」清单，不应被正则误匹配成
    ``{"type": "爆发 = 10", "ratio": 1.0}``。因此字符串中若含 ``=`` 一律视为
    比例式，直接返回 None（由调用方降级处理）。

    所有返回 list 的路径统一经过 :func:`_dedup_payoff_types` 按 type 去重。
    """
    if value is None:
        return None
    if isinstance(value, list):
        return _dedup_payoff_types(copy.deepcopy(value))
    if isinstance(value, dict):
        # 某些 book 的 payoff_density 里内嵌 type/ratio，这里仅处理顶层 payoff_types。
        if "type" in value:
            return _parse_payoff_types(value["type"])
        return copy.deepcopy(value)
    if isinstance(value, str):
        # 含「=」的比例式（如 "铺垫:爆发 = 10:1 ..."）不按「类型:数字」解析。
        if "=" in value:
            return None
        # 形如 "情感回应:7，他人认可:2，反杀:1"
        parsed: List[Any] = []
        for m in re.finditer(r"([^:：，,;；\n=]+)[:：]\s*(\d+(?:\.\d+)?)", value):
            name = m.group(1).strip()
            ratio = float(m.group(2))
            if name:
                parsed.append({"type": name, "ratio": ratio})
        return _dedup_payoff_types(parsed) if parsed else None
    return None


def _median(values: List[float]) -> Optional[float]:
    """安全中位数；空列表返回 None。"""
    if not values:
        return None
    return statistics.median(values)


def _list_intersection(lists: List[List[Any]]) -> List[Any]:
    """多列表交集（保序，去重）；任一列表为空返回空。"""
    cleaned = [lst for lst in lists if lst is not None]
    if not cleaned:
        return []
    result: List[Any] = []
    for item in cleaned[0]:
        if all(item in lst for lst in cleaned[1:]) and item not in result:
            result.append(item)
    return result


def _list_union(lists: List[List[Any]]) -> List[Any]:
    """多列表并集（保序，去重）。"""
    result: List[Any] = []
    for lst in lists:
        if lst is None:
            continue
        for item in lst:
            if item not in result:
                result.append(item)
    return result


def _stringify_for_freq(value: Any) -> str:
    """把值转为适合频次聚合的字符串（保留语义，不提取数字）。

    str 原样；list 用「；」连接各元素（元素为 dict 时序列化）；dict 序列化
    key:value。用于自然语言字段的纯字符串匹配聚合。
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        parts = []
        for v in value:
            if isinstance(v, dict):
                parts.append(json.dumps(v, ensure_ascii=False, sort_keys=True))
            else:
                parts.append(str(v).strip())
        return "；".join(p for p in parts if p)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _freq_aggregate_strings_full(values: List[str]) -> tuple[str, bool]:
    """对自然语言字符串做纯字符串匹配 + 频次聚合，并返回是否发生分歧。

    返回 ``(聚合结果, has_divergence)``。``has_divergence=True`` 表示存在少数派
    表述被舍弃（众数占比 < 100%），调用方应据此标记 conflict（Bug2 修复）。

    策略：若存在完全一致的字符串，取出现频次最高者；若并列最高或无法去重，
    则将不同表述拼接保留来源（以 ``；`` 分隔）。只有当所有非空值完全一致时，
    ``has_divergence`` 才为 False。
    """
    non_empty = [v for v in values if v and v.strip()]
    if not non_empty:
        return "", False
    counter: Dict[str, int] = defaultdict(int)
    for v in non_empty:
        counter[v.strip()] += 1
    if len(counter) == 1:
        return non_empty[0].strip(), False
    # 存在多种表述 → 必然有分歧（即便众数占多数，少数派也不该被静默丢弃）。
    max_count = max(counter.values())
    top = [k for k, c in counter.items() if c == max_count]
    if len(top) == 1 and max_count >= 2:
        # 众数唯一且出现 >=2 次：取众数，但标记存在少数派分歧。
        return top[0], True
    # 无法去重：保留来源（按出现顺序去重后拼接），并标记分歧。
    seen: List[str] = []
    for v in non_empty:
        s = v.strip()
        if s not in seen:
            seen.append(s)
    return "；".join(seen), True


def _freq_aggregate_strings(values: List[str]) -> str:
    """对自然语言字符串做频次聚合（向后兼容，仅返回聚合结果字符串）。"""
    value, _ = _freq_aggregate_strings_full(values)
    return value


# ---------------------------------------------------------------------------
# 二期 · 技法归一化（任务 A）
# ---------------------------------------------------------------------------

def _normalize_technique(name: str) -> str:
    """把技法名规范化为可比较的紧凑字符串。

    流程：小写 → 去空格与标点（仅保留字母数字 + 中日韩字符）→ 按停用词表过滤
    停用词 → 返回剩余字符串（可能为空串，空串不参与相似度合并）。

    实现采用「先统一小写、再逐步剥离停用词」的策略，而非一次性正则删除停用词：
    因为停用词（如「的」「了」）单字穿插在中文长句中，直接 ``re.sub`` 删除单字
    停用词会误伤其他词内部的同形字（如「目的」中的「的」）。故此处先做
    ``lower()`` + 去空白/标点，得到紧凑字符串后，再按停用词从长到短依次用
    ``str.replace`` 剥离整词。

    Args:
        name: 原始技法名（如 ``"三段式 钩子"``）。

    Returns:
        规范化后的紧凑字符串；空串表示无实质内容。
    """
    if name is None:
        return ""
    text = str(name).lower()
    # 仅保留字母数字 + 中日韩字符（去空格、标点、引号等）。
    text = "".join(ch for ch in text if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    if not text:
        return ""
    # 按长度降序剥离停用词（长词优先，避免误伤短词部分）。
    for sw in sorted(STOPWORDS, key=len, reverse=True):
        text = text.replace(sw, "")
    return text


def _char_ngram_similarity(a: str, b: str, n: int = NGRAM_N) -> float:
    """计算两个规范化字符串的字符 n-gram Jaccard 相似度。

    对每个字符串生成字符 n-gram 多重集，返回 ``|A∩B| / |A∪B|``。

    Args:
        a: 规范化后的字符串。
        b: 规范化后的字符串。
        n: n-gram 的 n 值（默认 2）。

    Returns:
        相似度 ``0.0~1.0``；空集时返回 0.0。
    """
    if not a or not b:
        return 0.0

    def _ngrams(s: str) -> set:
        if n <= 0:
            return set()
        if len(s) < n:
            return {s}
        return {s[i : i + n] for i in range(len(s) - n + 1)}

    set_a = _ngrams(a)
    set_b = _ngrams(b)
    if not set_a or not set_b:
        return 0.0
    inter = set_a & set_b
    union = set_a | set_b
    if not union:
        return 0.0
    return len(inter) / len(union)


def _load_synonyms() -> Dict[str, Dict[str, List[str]]]:
    """读取项目根 ``synonyms.json`` 同义词表。

    格式：``{维度: {规范名: [别名...]}}``。文件缺失或 JSON 损坏时回退空表 ``{}``，
    不影响相似度主路径。

    Returns:
        同义词表 dict；无文件或损坏时为 ``{}``。
    """
    try:
        if not SYNONYMS_PATH.is_file():
            return {}
        with open(SYNONYMS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def _cluster_techniques(techniques: List[dict]) -> List[TechniqueCluster]:
    """把技法列表按「同义词 → 双条件相似度」归一化聚成簇。

    对每个技法（含 name + skeleton），与已有簇的代表比较：
        * 同义词命中：直接并入对应规范名簇（优先于相似度判据，不经过相似度计算）；
        * 双条件：``name_jaccard >= TECHNIQUE_NAME_JACCARD`` 且
          ``skeleton_jaccard >= TECHNIQUE_SKELETON_JACCARD`` → 并入该簇；
        * skeleton 缺失：退化为单条件，``name_jaccard >= TECHNIQUE_NAME_ONLY_JACCARD``
          才合并（提高阈值避免误合并）；
        * 均不满足 → 新建簇。

    单元素簇 / 无法语义去重者原样保留各自来源，不强行合并、不丢数据。

    阈值说明（P3-b 结论，保持现状不改）：当前 3 本书的 craft 技法语义本就
    各异，跨书实测 name 相似度仅 0.00–0.12、skeleton 相似度 0.01–0.10，均远
    低于双条件阈值（0.5/0.3）与单条件阈值（0.7）。因此「62 条进 personal、
    仅 3 条进 rules」的根因是**数据覆盖不足 + 同义词表未显式收录**，而非
    阈值过严：实际所有跨书合并均由 synonyms.json 驱动（n-gram 阈值驱动的
    合并数为 0）。在此前提下，降低阈值既不会增加 rules（相似度太低），又会
    引入误合并风险，故阈值保持不变；后续如新增题材/书目导致相似技法自然
    增多，再依据实测分布重新评估阈值。

    Args:
        techniques: 技法 dict 列表，每项至少含 ``name``，可选 ``skeleton``，
            还可带 ``book``（来源书）字段。

    Returns:
        TechniqueCluster 列表（按首次出现顺序）。
    """
    synonyms = _load_synonyms()
    clusters: List[TechniqueCluster] = []
    # 簇代表名 → 簇索引，供相似度比较时 O(1) 定位。
    rep_to_idx: Dict[str, int] = {}
    # 同义词表展开后的「任一名称（规范名 + 别名）→ 簇索引」映射。
    # 该映射在建簇/归并后立即登记，且【永不 pop】，保证同义词命中稳定可达。
    alias_to_idx: Dict[str, int] = {}

    # 预先展开同义词表：任一名称 → 规范名，供 O(1) 命中（而非每次遍历表）。
    name_to_canon: Dict[str, str] = {}
    for dimension_aliases in synonyms.values():
        if not isinstance(dimension_aliases, dict):
            continue
        for canon, aliases in dimension_aliases.items():
            if not isinstance(aliases, list):
                continue
            name_to_canon.setdefault(canon, canon)
            for alias in aliases:
                name_to_canon.setdefault(alias, canon)

    for t in techniques:
        if not isinstance(t, dict):
            continue
        name = (t.get("name") or "").strip()
        if not name:
            continue
        skeleton = (t.get("skeleton") or "").strip()
        book = t.get("book") or ""

        norm_name = _normalize_technique(name)

        target_idx: Optional[int] = None

        # 1) 同义词命中优先：任一名称（规范名/别名）命中即归并到对应簇。
        if name in alias_to_idx:
            target_idx = alias_to_idx[name]
        elif name in name_to_canon:
            canon = name_to_canon[name]
            if canon in alias_to_idx:
                target_idx = alias_to_idx[canon]

        # 2) 未命中同义词 → 相似度判据。
        if target_idx is None and norm_name:
            norm_skel = _normalize_technique(skeleton)
            for idx, cluster in enumerate(clusters):
                rep_norm = _normalize_technique(cluster.representative)
                if not rep_norm:
                    continue
                name_sim = _char_ngram_similarity(norm_name, rep_norm)
                if cluster.skeletons and norm_skel:
                    # 双条件：name 且 skeleton 都达标才合并。
                    skel_sim = 0.0
                    for sk in cluster.skeletons:
                        sim = _char_ngram_similarity(
                            norm_skel, _normalize_technique(sk)
                        )
                        skel_sim = max(skel_sim, sim)
                    if (
                        name_sim >= TECHNIQUE_NAME_JACCARD
                        and skel_sim >= TECHNIQUE_SKELETON_JACCARD
                    ):
                        target_idx = idx
                        break
                else:
                    # skeleton 缺失（任一缺失）→ 单条件 name，提高阈值。
                    if name_sim >= TECHNIQUE_NAME_ONLY_JACCARD:
                        target_idx = idx
                        break

        if target_idx is not None:
            cluster = clusters[target_idx]
            if name not in cluster.names:
                cluster.names.append(name)
            if skeleton and skeleton not in cluster.skeletons:
                cluster.skeletons.append(skeleton)
            cluster.sources.append(SourceValue(book=book, value=name, raw=t.get("raw")))
            cluster.count += 1
            if book and book not in cluster.books:
                cluster.books.append(book)
            # 登记该 name 到簇映射（含其同义词规范名/别名，保证后续命中稳定）。
            alias_to_idx[name] = target_idx
            canon = name_to_canon.get(name)
            if canon:
                alias_to_idx.setdefault(canon, target_idx)
                for alias, c2 in name_to_canon.items():
                    if c2 == canon:
                        alias_to_idx.setdefault(alias, target_idx)
            # 更新代表名：频次最高的原文名；频次并列时优先取同义词表规范名。
            cluster.representative = _most_frequent_name(
                cluster.names, cluster.sources, canon_map=name_to_canon
            )
            rep_to_idx[cluster.representative] = target_idx
            continue

        # 新建簇。
        new_idx = len(clusters)
        cluster = TechniqueCluster(
            representative=name,
            names=[name],
            skeletons=[skeleton] if skeleton else [],
            sources=[SourceValue(book=book, value=name, raw=t.get("raw"))],
            count=1,
            books=[book] if book else [],
        )
        clusters.append(cluster)
        rep_to_idx[name] = new_idx
        alias_to_idx[name] = new_idx
        # 若该 name 是同义词规范名/别名，把同组所有名称都登记到本簇。
        canon = name_to_canon.get(name)
        if canon:
            alias_to_idx.setdefault(canon, new_idx)
            for alias, c2 in name_to_canon.items():
                if c2 == canon:
                    alias_to_idx.setdefault(alias, new_idx)

    return clusters


def _most_frequent_name(
    names: List[str],
    sources: List[SourceValue],
    canon_map: Optional[Dict[str, str]] = None,
) -> str:
    """从簇内原始 name 中选出频次最高者作为代表名。

    选择优先级：
        1. 频次最高者；
        2. 频次并列时，优先取「同义词表规范名」（即 ``canon_map.get(name) == name``，
           表示该 name 本身是规范名），语义更居中；
        3. 仍并列，取首次出现者。

    ``canon_map`` 缺省为 None 时保持旧行为（频次优先、并列取先出现者），向后兼容。
    """
    counter: Dict[str, int] = defaultdict(int)
    for s in sources:
        if s.value:
            counter[str(s.value)] += 1
    if not counter:
        return names[0] if names else ""
    # 先选出最高频次。
    best_count = max(counter.get(name, 0) for name in names)
    # 频次并列的候选集合。
    tied = [name for name in names if counter.get(name, 0) == best_count]
    if len(tied) > 1 and canon_map:
        # 并列时优先取规范名（canon_map[name] == name 表示该 name 是规范名本身）。
        for name in tied:
            if canon_map.get(name) == name:
                return name
    return tied[0]


# ---------------------------------------------------------------------------
# 资产采集
# ---------------------------------------------------------------------------

def collect_assets(
    genre: str, book_names: Optional[List[str]] = None
) -> Dict[str, Dict[str, dict]]:
    """采集指定题材下各本书的四类资产。

    资产平铺在 ``assets/*-<dimension>.json``，通过每本 ``meta.genre`` 过滤出
    同题材书籍（架构约定：glob assets/*.json，不按子目录组织）。

    Args:
        genre: 题材 id（如 ``campus-redemption``）。
        book_names: 可选，限定书籍；None 表示自动发现全部同题材。

    Returns:
        形如 ``{dimension: {book: asset_dict}}`` 的分组结果。
    """
    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    result: Dict[str, Dict[str, dict]] = {d: {} for d in DIMENSIONS}
    if not assets_dir.is_dir():
        return result

    for dimension in DIMENSIONS:
        pattern = f"*-{dimension}.json"
        for path in sorted(assets_dir.glob(pattern)):
            book = path.name[: -len(f"-{dimension}.json")]
            if book_names is not None and book not in book_names:
                continue
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                # 损坏的资产文件跳过，交由盲区诊断体现为缺失。
                continue
            # 过滤题材：读取 meta.genre 与入参 genre 比对。
            meta = data.get("meta") or {}
            if meta.get("genre") != genre:
                continue
            result[dimension][book] = data
    return result


# ---------------------------------------------------------------------------
# 对齐
# ---------------------------------------------------------------------------

def align(dimension: str, assets: Dict[str, dict]) -> Dict[str, dict]:
    """把单维度各本书的资产对齐为统一字段结构。

    缺失字段补 None；commercial-obs 做归一化（buildup_length 抽字数、
    payoff_types 正则解析、common_mistakes 处理嵌套路径）；structure-obs 与
    voice-card、craft-card 保持原结构但保证关键字段存在。

    Returns:
        ``{book: aligned_dict}``，其中字段键集合统一。
    """
    if dimension == "commercial-obs":
        return _align_commercial(assets)
    if dimension == "voice-card":
        return _align_voice(assets)
    if dimension == "craft-card":
        return _align_craft(assets)
    if dimension == "structure-obs":
        return _align_structure(assets)
    return {book: copy.deepcopy(a) for book, a in assets.items()}


def _align_commercial(assets: Dict[str, dict]) -> Dict[str, dict]:
    """commercial-obs 字段归一化（§3.2）。"""
    aligned: Dict[str, dict] = {}
    for book, asset in assets.items():
        out: Dict[str, Any] = {}
        for field in COMMERCIAL_FIELDS:
            out[field] = _normalize_commercial_field(asset, field)
        aligned[book] = out
    return aligned


def _normalize_commercial_field(asset: dict, field: str) -> Any:
    """按字段归一化单本书的 commercial 值；缺失返回 None。

    真实数据中若干字段散落在 payoff_density 内（顶层缺失），此处统一归位：
        * buildup_length：顶层优先，缺失/为 None 时从 payoff_density.buildup_length 兜底，
          统一抽字数数值；
        * payoff_types：无独立顶层字段，从 payoff_density 内提取（list 原样，
          type/ratio 散落字符串正则解析）；
        * payoff_density：归一化为 {per_chapter, per_thousand_words} 两个数值子字段；
        * common_mistakes：顶层优先，缺失时嵌套 opening_analysis.chapter_1 兜底。
    """
    if field == "buildup_length":
        raw = asset.get("buildup_length")
        if raw is None:
            pd = asset.get("payoff_density") or {}
            raw = pd.get("buildup_length") if isinstance(pd, dict) else None
        return _extract_word_count(raw)

    if field == "payoff_types":
        return _extract_payoff_types_from_asset(asset)

    if field == "payoff_density":
        pd = asset.get("payoff_density")
        if not isinstance(pd, dict):
            return None
        return {
            "per_chapter": _to_number(pd.get("per_chapter")),
            "per_thousand_words": _to_number(pd.get("per_thousand_words")),
        }

    if field == "common_mistakes":
        raw = asset.get("common_mistakes")
        if raw is None:
            nested = (asset.get("opening_analysis") or {}).get("chapter_1") or {}
            raw = nested.get("common_mistakes")
        return copy.deepcopy(raw)

    return copy.deepcopy(asset.get(field))


def _extract_payoff_types_from_asset(asset: dict) -> Any:
    """从 payoff_density 内提取并解析 payoff_types。

    优先 ``payoff_density.payoff_types``（list）；否则尝试 ``payoff_density.type``
    与 ``payoff_density.ratio``（散落字符串正则解析）。解析失败返回 None（记盲区）。
    """
    pd = asset.get("payoff_density")
    if not isinstance(pd, dict):
        return None

    # 直接 list 形式（chireng）。
    if "payoff_types" in pd:
        return _parse_payoff_types(pd.get("payoff_types"))

    # type + ratio 散落形式（qingning / sangshi）。
    type_val = pd.get("type")
    ratio_val = pd.get("ratio")

    # sangshi：type 为 list（如 ["情感回应","身份揭露","他人认可"]），ratio 是
    # 「铺垫:爆发 = 10:1」比例式。此时应直接用 type 列表降级为无比例条目，
    # 不要先解析 ratio 比例式字符串（否则会误把「爆发 = 10」当成 type）。
    if isinstance(type_val, list) and type_val:
        return _dedup_payoff_types([{"type": str(t), "ratio": None} for t in type_val])

    # qingning：type 为字符串、ratio 为 "情感回应:7，他人认可:2，反杀:1"。
    if isinstance(ratio_val, str):
        parsed = _parse_payoff_types(ratio_val)
        if parsed:
            return parsed

    # type 为单个字符串。
    if isinstance(type_val, str) and type_val:
        return _dedup_payoff_types([{"type": type_val, "ratio": None}])

    return None


def _align_voice(assets: Dict[str, dict]) -> Dict[str, dict]:
    """voice-card 对齐：保证 5 个聚合 key 存在（缺失补 None）。"""
    aligned: Dict[str, dict] = {}
    for book, asset in assets.items():
        out: Dict[str, Any] = {}
        for key in VOICE_AGG_KEYS:
            out[key] = copy.deepcopy(asset.get(key))
        aligned[book] = out
    return aligned


def _align_craft(assets: Dict[str, dict]) -> Dict[str, dict]:
    """craft-card 对齐：保证 craft_analysis 十维存在。"""
    aligned: Dict[str, dict] = {}
    for book, asset in assets.items():
        analysis = asset.get("craft_analysis") or {}
        out_analysis: Dict[str, Any] = {}
        for dim in CRAFT_DIMENSIONS:
            out_analysis[dim] = copy.deepcopy(analysis.get(dim))
        summary = asset.get("craft_summary") or {}
        aligned[book] = {
            "craft_analysis": out_analysis,
            "craft_summary": copy.deepcopy(summary),
        }
    return aligned


def _align_structure(assets: Dict[str, dict]) -> Dict[str, dict]:
    """structure-obs 对齐：保证 aggregate 关键字段存在。"""
    aligned: Dict[str, dict] = {}
    for book, asset in assets.items():
        aggregate = asset.get("aggregate") or {}
        out_agg: Dict[str, Any] = {}
        for field in STRUCTURE_FIELDS:
            out_agg[field] = copy.deepcopy(aggregate.get(field))
        aligned[book] = {
            "aggregate": out_agg,
            "chapter_analyses": copy.deepcopy(asset.get("chapter_analyses")),
        }
    return aligned


# ---------------------------------------------------------------------------
# 聚合
# ---------------------------------------------------------------------------

def aggregate(dimension: str, aligned: Dict[str, dict]) -> List[AggregatedRule]:
    """把对齐后的单维度资产聚合为规则列表。

    Args:
        dimension: 维度名。
        aligned: ``{book: aligned_dict}``。

    Returns:
        AggregatedRule 列表（含 hard/soft/personal 分层）。
    """
    books = sorted(aligned.keys())
    if dimension == "voice-card":
        rules = _aggregate_voice(aligned, books)
    elif dimension == "craft-card":
        rules = _aggregate_craft(aligned, books)
    elif dimension == "structure-obs":
        rules = _aggregate_structure(aligned, books)
    elif dimension == "commercial-obs":
        rules = _aggregate_commercial(aligned, books)
    else:
        rules = []
    # 过滤掉所有书都缺失（books_count==0 且 value 为空）的无意义规则，
    # 以及聚合后无实质内容（空列表交集/空串）的规则。
    return [
        r
        for r in rules
        if not (r.books_count == 0 or _is_empty(r.value))
    ]


def _kind_for_count(count: int) -> str:
    """按贡献书数确定分层。"""
    if count >= 3:
        return "hard"
    if count == 2:
        return "soft"
    return "personal"


def _group_by_field(
    rules: List[AggregatedRule],
) -> Dict[str, List[AggregatedRule]]:
    """按 field 分组。"""
    groups: Dict[str, List[AggregatedRule]] = defaultdict(list)
    for r in rules:
        groups[r.field].append(r)
    return groups


def _aggregate_voice(
    aligned: Dict[str, dict], books: List[str]
) -> List[AggregatedRule]:
    """voice-card 聚合：5 个 key，banned 取交集，其余按子字段聚合。"""
    rules: List[AggregatedRule] = []

    for key in VOICE_AGG_KEYS:
        if key == "banned":
            rules.extend(_aggregate_banned(aligned, books))
            continue

        # 对 key 下的叶子字段聚合。先收集所有叶子字段。
        leaf_fields: Dict[str, Dict[str, Any]] = defaultdict(dict)
        for book in books:
            node = aligned.get(book, {}).get(key)
            if not isinstance(node, dict):
                continue
            for leaf, val in _iter_leaves(node):
                leaf_fields[leaf][book] = val

        for leaf, book_vals in leaf_fields.items():
            rules.append(
                _aggregate_field(
                    dimension="voice-card",
                    field=f"{key}.{leaf}",
                    book_vals=book_vals,
                    books=books,
                    aggregator="median",
                )
            )

    return rules


def _iter_leaves(node: Any, prefix: str = "") -> List[tuple[str, Any]]:
    """展开 dict 的叶子字段为 ``(dot_path, value)``。"""
    result: List[tuple[str, Any]] = []
    if isinstance(node, dict):
        for k, v in node.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                result.extend(_iter_leaves(v, path))
            else:
                result.append((path, v))
    else:
        result.append((prefix, node))
    return result


def _aggregate_banned(
    aligned: Dict[str, dict], books: List[str]
) -> List[AggregatedRule]:
    """banned 聚合：三个子 key 各取交集（架构师拍板）。

    交集为空（三本无共同禁用项）时，降级为并集并标记 conflict，保留全部分歧
    来源，避免「必守空清单」误导。
    """
    sub_keys = ("never_used_words", "avoided_structures", "genre_taboos")
    rules: List[AggregatedRule] = []
    for sub in sub_keys:
        lists: Dict[str, Any] = {}
        for book in books:
            banned = aligned.get(book, {}).get("banned") or {}
            lists[book] = banned.get(sub)
        intersection = _list_intersection(
            [lists[b] for b in books if lists.get(b) is not None]
        )
        if intersection:
            rule = _aggregate_field(
                dimension="voice-card",
                field=f"banned.{sub}",
                book_vals=lists,
                books=books,
                aggregator="intersection",
            )
        else:
            # 无共同禁用项：用并集保留分歧，标记 conflict。
            rule = _aggregate_field(
                dimension="voice-card",
                field=f"banned.{sub}",
                book_vals=lists,
                books=books,
                aggregator="list-union",
            )
            rule.conflict = True
        rules.append(rule)
    return rules


def _aggregate_craft(
    aligned: Dict[str, dict], books: List[str]
) -> List[AggregatedRule]:
    """craft-card 聚合：十维 techniques 按归一化簇计数；summary 分字段。

    二期（任务 A）：技法不再按 name 精确匹配计数，而是先经同义词表 + 双条件
    字符 n-gram 相似度聚成 TechniqueCluster，再以簇为单位计数。簇内跨书
    books_count 正确累计；单元素簇 / 无法语义去重者保留各自来源（personal）。
    """
    rules: List[AggregatedRule] = []

    for dim in CRAFT_DIMENSIONS:
        # 收集该维度所有书的所有 technique（含 name + skeleton + book）。
        techniques: List[dict] = []
        for book in books:
            analysis = aligned.get(book, {}).get("craft_analysis") or {}
            dim_node = analysis.get(dim) or {}
            tech_list = dim_node.get("techniques") or []
            for t in tech_list:
                if not isinstance(t, dict) or not t.get("name"):
                    continue
                techniques.append(
                    {
                        "name": str(t.get("name")).strip(),
                        "skeleton": (t.get("skeleton") or "").strip(),
                        "book": book,
                        "raw": t,
                    }
                )

        if not techniques:
            rules.append(
                _aggregate_field(
                    dimension="craft-card",
                    field=f"craft_analysis.{dim}",
                    book_vals={b: None for b in books},
                    books=books,
                    aggregator="median",
                )
            )
            continue

        # 归一化聚类（同义词优先，其次双条件相似度）。
        clusters = _cluster_techniques(techniques)

        # 以簇为单位计数：分层与 books_count 均基于「去重书数」（len(cluster.books)），
        # 而非簇内总频次（cluster.count），避免单本书贡献多条技法时被虚标为 hard。
        # 排序仍按簇内总频次，代表高频簇优先展示。
        for cluster in sorted(clusters, key=lambda c: -c.count):
            rule = _aggregate_field(
                dimension="craft-card",
                field=f"craft_analysis.{dim}.technique",
                book_vals={
                    b: (cluster.representative if b in cluster.books else None)
                    for b in books
                },
                books=books,
                aggregator="string-freq",
                explicit_value=cluster.representative,
                explicit_count=len(cluster.books),
            )
            # 溯源：把簇内所有来源（含被归并的别名技法）挂到 sources，保留可追溯。
            rule.sources = list(cluster.sources)
            rules.append(rule)

    # craft_summary 字段聚合。
    for field_name in ("top_3_strengths", "unique_techniques", "reusable_patterns"):
        vals: Dict[str, Any] = {}
        for book in books:
            summary = aligned.get(book, {}).get("craft_summary") or {}
            vals[book] = summary.get(field_name)
        rules.append(
            _aggregate_field(
                dimension="craft-card",
                field=f"craft_summary.{field_name}",
                book_vals=vals,
                books=books,
                aggregator="list-union",
            )
        )

    return rules


def _aggregate_structure(
    aligned: Dict[str, dict], books: List[str]
) -> List[AggregatedRule]:
    """structure-obs 聚合：aggregate 六个字段各自聚合。"""
    rules: List[AggregatedRule] = []
    for field_name in STRUCTURE_FIELDS:
        vals: Dict[str, Any] = {}
        for book in books:
            agg = aligned.get(book, {}).get("aggregate") or {}
            vals[book] = agg.get(field_name)
        rules.append(
            _aggregate_field(
                dimension="structure-obs",
                field=f"aggregate.{field_name}",
                book_vals=vals,
                books=books,
                aggregator="median",
            )
        )
    return rules


def _merge_payoff_type_shares(
    share_vals: Dict[str, Any], books: List[str]
) -> List[dict]:
    """跨书按 type 归并 payoff 份额：同一 type 取各书贡献份额的中位数。

    类型顺序按书籍顺序（``books``）保序去重；某本书对某 type 的份额为 None
    （不可解析）时不参与该 type 的中位数；无任何书贡献数值则该 type 记 None。
    """
    ratios: Dict[str, List[float]] = {}
    order: List[str] = []
    for book in books:
        items = share_vals.get(book)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("type") is None:
                continue
            name = str(item.get("type"))
            if name not in ratios:
                ratios[name] = []
                order.append(name)
            value = item.get("ratio")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                ratios[name].append(float(value))
    return [{"type": name, "ratio": _median(ratios[name])} for name in order]


def _aggregate_payoff_types(
    aligned: Dict[str, dict], books: List[str]
) -> AggregatedRule:
    """payoff_types 专项聚合：书内归一为占比 → 跨书按 type 取中位数。

    真实资产中 ratio 口径混杂（chireng/qingning 为次数、suyixinjian 为占比、
    sangshi 为不可解析的比例式），直接跨书并集会出现 40 / 103 这类「既非次数
    也非占比」的值，与 schema 声明的「在全书中的占比」语义不符。此处先逐书
    经 :func:`_normalize_payoff_ratios` 归一为份额，再按 type 取中位数。

    分层/冲突判定仍复用 ``list-union`` 分支（口径与既有行为一致）；``sources``
    保留各书**原始**（未归一）取值，保证溯源不丢信息。
    """
    raw_vals = {b: aligned.get(b, {}).get("payoff_types") for b in books}
    share_vals = {b: _normalize_payoff_ratios(v) for b, v in raw_vals.items()}

    rule = _aggregate_field(
        dimension="commercial-obs",
        field="payoff_types",
        book_vals=share_vals,
        books=books,
        aggregator="list-union",
    )
    rule.value = _merge_payoff_type_shares(share_vals, books)
    rule.sources = [
        SourceValue(book=b, value=raw_vals.get(b), raw=raw_vals.get(b)) for b in books
    ]
    return rule


def _aggregate_commercial(
    aligned: Dict[str, dict], books: List[str]
) -> List[AggregatedRule]:
    """commercial-obs 聚合：各字段按类型聚合。

    * payoff_density：归一化为 {per_chapter, per_thousand_words}，子字段取数值中位数；
    * buildup_length：数值中位数；
    * payoff_types：书内归一为占比后跨书按 type 取中位数（Task 3.3）；
    * skeleton / dry_spell_tolerance / common_mistakes / paywall：字符串频次聚合。
    """
    rules: List[AggregatedRule] = []

    # payoff_density 递归聚合两个数值子字段。
    pd_sub_fields = ("per_chapter", "per_thousand_words")
    for sub in pd_sub_fields:
        vals: Dict[str, Any] = {}
        for book in books:
            pd = aligned.get(book, {}).get("payoff_density")
            vals[book] = pd.get(sub) if isinstance(pd, dict) else None
        rules.append(
            _aggregate_field(
                dimension="commercial-obs",
                field=f"payoff_density.{sub}",
                book_vals=vals,
                books=books,
                aggregator="median",
            )
        )

    for field_name, aggregator in (
        ("buildup_length", "median"),
        ("payoff_types", "list-union"),
        ("skeleton", "string-freq-auto"),
        ("dry_spell_tolerance", "string-freq-auto"),
        ("common_mistakes", "string-freq-auto"),
        ("paywall", "string-freq-auto"),
    ):
        if field_name == "payoff_types":
            # Task 3.3：ratio 改为「书内占比 → 跨书按 type 中位数」，其余不变。
            rules.append(_aggregate_payoff_types(aligned, books))
            continue
        vals: Dict[str, Any] = {}
        for book in books:
            vals[book] = aligned.get(book, {}).get(field_name)
        rules.append(
            _aggregate_field(
                dimension="commercial-obs",
                field=field_name,
                book_vals=vals,
                books=books,
                aggregator=aggregator,
            )
        )

    return rules


def _is_empty(value: Any) -> bool:
    """判断值是否为空（None / 空串 / 空容器），视为缺失。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def _aggregate_field(
    dimension: str,
    field: str,
    book_vals: Dict[str, Any],
    books: List[str],
    aggregator: str,
    explicit_value: Any = None,
    explicit_count: Optional[int] = None,
) -> AggregatedRule:
    """聚合单个字段，产出 AggregatedRule。

    aggregator 取值：
        * ``median``：数值中位数；
        * ``intersection``：列表交集；
        * ``list-union``：列表并集；
        * ``string-freq``：字符串频次（配合 explicit_value/count）；
        * ``string-freq-auto``：自然语言字段自动频次聚合。
    """
    present = {b: v for b, v in book_vals.items() if not _is_empty(v)}
    missing_books = [b for b in books if b not in present]
    count = explicit_count if explicit_count is not None else len(present)

    kind = _kind_for_count(count)
    conflict = False

    if aggregator == "string-freq":
        value = explicit_value
        sources = [
            SourceValue(book=b, value=explicit_value if b in present else None, raw=book_vals.get(b))
            for b in books
        ]
    elif aggregator == "intersection":
        lists = [present.get(b) for b in books if b in present]
        value = _list_intersection(lists)
        sources = [
            SourceValue(book=b, value=present.get(b), raw=book_vals.get(b)) for b in books
        ]
    elif aggregator == "list-union":
        lists = [present.get(b) for b in books if b in present]
        value = _list_union(lists)
        # P3-a 收口：payoff_types 跨书并集后，不同书对同一 type 给不同 ratio
        # （如「情感回应」ratio=20 / 7.0 / None），_list_union 只按整项相等去重，
        # 不去重 type，会留下同名重复。这里复用 _dedup_payoff_types 按 type 去重、
        # 保留首个 ratio（保序、不二次计算）。
        if field == "payoff_types":
            value = _dedup_payoff_types(value)
        sources = [
            SourceValue(book=b, value=present.get(b), raw=book_vals.get(b)) for b in books
        ]
        # Bug3 修复：list-union 无交集（各书列表两两无共同元素）说明「三本各说
        # 各话」，是并集而非共识，不应标 hard。此时降级分层并标记 conflict。
        non_empty_lists = [lst for lst in lists if lst]
        if len(non_empty_lists) >= 2 and not _list_intersection(non_empty_lists):
            conflict = True
            if kind == "hard":
                kind = "soft"
    elif aggregator == "string-freq-auto":
        # 自然语言字段：str 直接频次聚合；list 逐项频次；dict 序列化后频次。
        strs = [_stringify_for_freq(present[b]) for b in books if b in present]
        value, conflict = _freq_aggregate_strings_full(strs)
        value = value or None
        sources = [
            SourceValue(book=b, value=present.get(b), raw=book_vals.get(b)) for b in books
        ]
    else:  # median
        # 仅对纯数值（int/float，排除 bool）做中位数；字符串/容器走字符串频次。
        numeric = [present[b] for b in books if b in present if isinstance(present[b], (int, float)) and not isinstance(present[b], bool)]
        if numeric:
            value = _median([float(n) for n in numeric])
            if value is not None and value == int(value):
                value = int(value)
        else:
            # 非纯数值（字符串/dict/list）：做字符串频次聚合，并捕获分歧。
            strs = [_stringify_for_freq(present[b]) for b in books if b in present]
            value, conflict = _freq_aggregate_strings_full(strs)
            value = value or None
        sources = [
            SourceValue(book=b, value=present.get(b), raw=book_vals.get(b)) for b in books
        ]

    rule = AggregatedRule(
        id="",
        dimension=dimension,
        field=field,
        kind=kind,
        books_count=count,
        value=value,
        sources=sources,
        conflict=conflict,
        blindspot_books=missing_books,
    )
    return rule


# ---------------------------------------------------------------------------
# 冲突解决
# ---------------------------------------------------------------------------

def resolve_conflict(rules: List[AggregatedRule]) -> List[AggregatedRule]:
    """解决同一 field 的多值分歧。

    同 field 出现多条 hard/soft 规则且值不同时，标记 conflict=True 并保留多条
    （不强行合并）。同时分配稳定 id。
    """
    groups = _group_by_field(rules)
    resolved: List[AggregatedRule] = []

    for field_name, group in groups.items():
        # 仅统计 hard/soft 层（personal 不参与冲突判定）。
        meaningful = [r for r in group if r.kind in ("hard", "soft")]
        distinct_values = {_flatten(r.value) for r in meaningful}
        has_conflict = len(distinct_values) > 1

        for idx, rule in enumerate(group, start=1):
            if rule.kind in ("hard", "soft") and has_conflict:
                rule.conflict = True
            rule.id = f"{rule.dimension}-{_slugify(field_name)}-{idx:04d}"
            resolved.append(rule)

    return resolved


# ---------------------------------------------------------------------------
# 盲区诊断
# ---------------------------------------------------------------------------

def detect_blindspots(
    dimension: str, raw_assets: Dict[str, dict], aligned: Dict[str, dict]
) -> List[dict]:
    """诊断类型级盲区。

    对每本书，找出对齐后值为 None 的字段，产出盲区条目
    ``{book, dimension, field, note}``。
    """
    blindspots: List[dict] = []
    for book in sorted(aligned.keys()):
        for field_name, value in aligned[book].items():
            if value is None:
                blindspots.append(
                    {
                        "book": book,
                        "dimension": dimension,
                        "field": field_name,
                        "note": f"字段 {field_name} 缺失或无法归一化",
                    }
                )
            elif isinstance(value, dict):
                for leaf, leaf_val in _iter_leaves(value):
                    if leaf_val is None:
                        blindspots.append(
                            {
                                "book": book,
                                "dimension": dimension,
                                "field": f"{field_name}.{leaf}",
                                "note": f"字段 {field_name}.{leaf} 缺失",
                            }
                        )
    return blindspots


# ---------------------------------------------------------------------------
# 置信度评分
# ---------------------------------------------------------------------------

def score_confidence(rule: AggregatedRule) -> float:
    """计算单条规则的置信度（§7）。

    hard=0.8 / soft=0.6 / personal=0.3；每缺一本书 -0.1、冲突再 -0.1、下限 0.1。
    """
    if rule.kind == "hard":
        base = CONFIDENCE_HARD
    elif rule.kind == "soft":
        base = CONFIDENCE_SOFT
    else:
        base = CONFIDENCE_PERSONAL

    score = base
    score -= len(rule.blindspot_books) * MISSING_BOOK_PENALTY
    if rule.conflict:
        score -= CONFLICT_PENALTY
    score = max(score, CONFIDENCE_MIN)
    return round(score, 2)


# ---------------------------------------------------------------------------
# 编排
# ---------------------------------------------------------------------------

def distill_genre(
    genre: str, book_names: Optional[List[str]] = None
) -> Dict[str, dict]:
    """编排蒸馏全流程，返回按维度分组的 distilled dict。

    Returns:
        ``{dimension: distilled_dict}``，distilled_dict 遵循 §3.1 schema。
    """
    assets = collect_assets(genre, book_names=book_names)
    result: Dict[str, dict] = {}

    for dimension in DIMENSIONS:
        dim_assets = assets.get(dimension, {})
        if not dim_assets:
            result[dimension] = _empty_distilled(genre, dimension)
            continue

        aligned = align(dimension, dim_assets)
        rules = aggregate(dimension, aligned)
        rules = resolve_conflict(rules)
        for rule in rules:
            rule.confidence = score_confidence(rule)
            if rule.confidence < OVER_GENERALIZED_THRESHOLD:
                rule.over_generalized = True

        blindspots = detect_blindspots(dimension, dim_assets, aligned)

        # 分离 personal 风格（不进 rules，保留为 personal_styles 统计）。
        personal_rules = [r for r in rules if r.kind == "personal"]
        core_rules = [r for r in rules if r.kind in ("hard", "soft")]

        result[dimension] = _build_distilled(
            genre=genre,
            dimension=dimension,
            rules=core_rules,
            personal_rules=personal_rules,
            blindspots=blindspots,
            source_books=sorted(dim_assets.keys()),
        )

    return result


def _empty_distilled(genre: str, dimension: str) -> dict:
    """构造空维度 distilled（无资产时）。"""
    return _build_distilled(
        genre=genre,
        dimension=dimension,
        rules=[],
        personal_rules=[],
        blindspots=[],
        source_books=[],
    )


def _build_evidence(rule: AggregatedRule) -> List[dict]:
    """从规则的来源明细构造 evidence 数组（可追溯证据）。

    保持自由结构（不新增 schema），每条证据包含：
    ``source_chapter``（来源章节，无则空串）、``quote``（引用片段，取来源 value 的
    字符串化，无则空串）、``confidence``（该条证据置信度）、``dimension``（所属维度）。

    证据置信度按贡献来源数分摊：单来源置信度 = 规则置信度 / 来源数，
    体现「多本书共同支撑同一规则」的证据强度。
    """
    sources = rule.sources
    if not sources:
        return []

    n = len(sources)
    per_source_conf = rule.confidence / n if n else 0.0
    evidence: List[dict] = []
    for s in sources:
        # 来源 value 字符串化作为「引用」；value 为 None 时留空。
        quote = ""
        if s.value is not None:
            if isinstance(s.value, (list, dict)):
                quote = json.dumps(s.value, ensure_ascii=False)
            else:
                quote = str(s.value)
        evidence.append(
            {
                "source_chapter": "",  # 蒸馏层无章节粒度，留空（可追溯来源书）。
                "source_book": s.book,
                "quote": quote,
                "confidence": round(per_source_conf, 4),
                "dimension": rule.dimension,
            }
        )
    return evidence


def _build_distilled(
    genre: str,
    dimension: str,
    rules: List[AggregatedRule],
    personal_rules: List[AggregatedRule],
    blindspots: List[dict],
    source_books: List[str],
) -> dict:
    """组装符合 §3.1 schema 的 distilled dict。"""
    serialized_rules: List[dict] = []
    for rule in rules:
        serialized_rules.append(
            {
                "id": rule.id,
                "dimension": rule.dimension,
                "field": rule.field,
                "kind": rule.kind,
                "books_count": rule.books_count,
                "value": rule.value,
                "sources": [
                    {"book": s.book, "value": s.value} for s in rule.sources
                ],
                "evidence": _build_evidence(rule),
                "confidence": rule.confidence,
                "conflict": rule.conflict,
                "over_generalized": rule.over_generalized,
                "blindspot_books": rule.blindspot_books,
            }
        )

    hard_count = sum(1 for r in rules if r.kind == "hard")
    soft_count = sum(1 for r in rules if r.kind == "soft")
    conflict_count = sum(1 for r in rules if r.conflict)

    return {
        "meta": {
            "id": f"{genre}-{dimension}-distilled",
            "schema_version": "1.0",
            "dimension": dimension,
            "genre": genre,
            "distilled_at": datetime.now().isoformat(timespec="seconds"),
            "source_books": source_books,
            "books_count": len(source_books),
        },
        "rules": serialized_rules,
        "blindspots": blindspots,
        "stats": {
            "total_rules": len(rules),
            "hard_rules": hard_count,
            "soft_rules": soft_count,
            "personal_styles": len(personal_rules),
            "conflicts": conflict_count,
            "blindspots": len(blindspots),
        },
    }
