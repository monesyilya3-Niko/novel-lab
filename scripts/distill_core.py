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


def _parse_payoff_types(value: Any) -> Any:
    """解析 payoff_types 为 list；散落字符串用正则 ``类型:数字`` 解析，失败置 None。

    注意（Bug1 修复）：比例式字符串（如 ``铺垫:爆发 = 10:1``）含 ``=``，是
    「铺垫 vs 爆发」的配比描述，不是「类型:数字」清单，不应被正则误匹配成
    ``{"type": "爆发 = 10", "ratio": 1.0}``。因此字符串中若含 ``=`` 一律视为
    比例式，直接返回 None（由调用方降级处理）。
    """
    if value is None:
        return None
    if isinstance(value, list):
        return copy.deepcopy(value)
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
        return parsed if parsed else None
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
        return [{"type": str(t), "ratio": None} for t in type_val]

    # qingning：type 为字符串、ratio 为 "情感回应:7，他人认可:2，反杀:1"。
    if isinstance(ratio_val, str):
        parsed = _parse_payoff_types(ratio_val)
        if parsed:
            return parsed

    # type 为单个字符串。
    if isinstance(type_val, str) and type_val:
        return [{"type": type_val, "ratio": None}]

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
    """craft-card 聚合：十维 techniques 按 name 字符串频次聚合；summary 分字段。"""
    rules: List[AggregatedRule] = []

    for dim in CRAFT_DIMENSIONS:
        # 收集该维度所有书的所有 technique.name。
        names_by_book: Dict[str, List[str]] = {}
        for book in books:
            analysis = aligned.get(book, {}).get("craft_analysis") or {}
            dim_node = analysis.get(dim) or {}
            techniques = dim_node.get("techniques") or []
            names = [
                t.get("name", "").strip()
                for t in techniques
                if isinstance(t, dict) and t.get("name")
            ]
            names_by_book[book] = names

        # 聚合所有 name 出现频次。
        all_names: List[str] = []
        for book in books:
            all_names.extend(names_by_book.get(book, []))
        counter: Dict[str, int] = defaultdict(int)
        for n in all_names:
            if n:
                counter[n] += 1

        if not counter:
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

        # 频次 >=2 视为硬/软规则，=1 视为个人风格。
        for name, count in sorted(counter.items(), key=lambda kv: -kv[1]):
            source_books = [b for b in books if name in names_by_book.get(b, [])]
            rules.append(
                _aggregate_field(
                    dimension="craft-card",
                    field=f"craft_analysis.{dim}.technique",
                    book_vals={b: (name if b in source_books else None) for b in books},
                    books=books,
                    aggregator="string-freq",
                    explicit_value=name,
                    explicit_count=count,
                )
            )

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


def _aggregate_commercial(
    aligned: Dict[str, dict], books: List[str]
) -> List[AggregatedRule]:
    """commercial-obs 聚合：各字段按类型聚合。

    * payoff_density：归一化为 {per_chapter, per_thousand_words}，子字段取数值中位数；
    * buildup_length：数值中位数；
    * payoff_types：列表并集；
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
