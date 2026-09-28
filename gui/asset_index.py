"""全局资产索引服务：SQLite 查询为主 + 目录扫描为迁移/回退源。

设计要点（见 DESIGN_gui_persistence §1.2 / §4.2）：
- ``ASSET_KINDS`` 白名单常量在此文件顶部，作为**单一来源**，``migrate``/``services`` 引用。
- 查询方法（``list_assets``/``get_asset_detail``/``get_overview``/``count_by_kind``）优先走
  SQLite 聚合（``gui.db``），SQLite 为空（尚未迁移）时回退到目录扫描（阶段一行为），
  保证「迁移前旧测试/旧前端仍可用，迁移后以 SQLite 为权威」。
- 短 TTL 只读缓存仅提速，权威数据源始终是 SQLite；缓存可 ``invalidate()`` 重建。
- 返回前端的 ``path`` 一律 ``relative_to(ROOT_DIR)`` 相对化，不暴露绝对路径。
- ``kind`` 白名单校验防路径穿越。

kind 白名单（单一来源）：
    voice | structure | commercial | craft | genre_pack | prose_card | trope
    | distilled | prose_card_index

其中 ``distilled``（跨书题材蒸馏卡）与 ``prose_card_index``（题材文风卡寻址索引）
都是**独立 kind**：前者不再冒充对应的基础卡（voice/structure/commercial/craft），
后者不再与 ``trope`` 混用；二者均无单书归属（``book_id`` 为 None）。

除 9 类资产卡外，``list_assets``/``get_overview`` 为兼容阶段一前端，仍将
「报告（report）」与「书（book）」作为虚拟 kind 暴露（内部分别来自 reports/books 表）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from gui import config, db, migrate
from gui.logging_setup import get_logger

_log = get_logger("asset_index")

# kind 白名单（资产卡，单一来源）。任何新 kind 需在此显式登记，防路径穿越与越权读取。
ASSET_KINDS = ("voice", "structure", "commercial", "craft", "genre_pack", "prose_card", "trope",
               "distilled", "prose_card_index")

# 兼容阶段一的「虚拟 kind」：报告与书（内部映射到 reports/books 表，不落入 assets.kind）。
VIRTUAL_KINDS = ("report", "book")

# list_assets/get_asset_detail 可接受的全部 kind（资产卡 + 虚拟 kind）。
_ALL_KINDS = ASSET_KINDS + VIRTUAL_KINDS

# assets 目录文件名后缀 → kind 映射（顺序即匹配优先级，扫描回退源用）。
# 长后缀必须排在短后缀之前：四个 ``-*-distilled`` 若排在其基础后缀之后，
# ``-voice-card`` 会先命中把蒸馏卡误判为 voice；``genre-prose-card-index``
# 同理会被通用的 ``genre-prose-card-`` 吞掉。
_SUFFIX_KIND = (
    ("-voice-card-distilled", "distilled"),
    ("-structure-obs-distilled", "distilled"),
    ("-commercial-obs-distilled", "distilled"),
    ("-craft-card-distilled", "distilled"),
    ("genre-prose-card-index", "prose_card_index"),
    ("-voice-card", "voice"),
    ("-structure-obs", "structure"),
    ("-commercial-obs", "commercial"),
    ("-craft-card", "craft"),
    ("-genre-pack", "genre_pack"),
    ("genre-prose-card-", "prose_card"),
)

# 报告文件名后缀 → 报告类型（用于拆书报告 / 笔法分析区分）。
_REPORT_SUFFIX = (
    ("-拆书报告.md", "book"),
    ("-笔法分析.md", "craft"),
)


def _default_ttl() -> int:
    """缓存 TTL（秒），默认 5 秒，可用环境变量覆盖（测试便利）。"""
    import os
    raw = os.environ.get("NOVEL_LAB_GUI_INDEX_TTL", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return 5


# ---------------------------------------------------------------------------
# 资产可读摘要（2026-09-29 用户反馈"资产库有很多内容不对"）
#
# 详情页此前只返回原始 JSON，前端被迫 JSON.stringify —— 用户看到的是英文
# 键名和技术结构。现增加 describe_asset() 生成面向用户的中文 markdown 摘要：
# 基本信息 / 用途 / 关键内容 / 禁止项 / 适用位置。
# 原始 JSON 保留在详情 content 字段，前端收进"高级"折叠区。
# 纯标准库；不 import scripts（规约：仅 gui/engine_adapter.py 可 import scripts）。
# ---------------------------------------------------------------------------

_KIND_LABELS: dict[str, str] = {
    "voice": "声线卡",
    "structure": "结构观测卡",
    "commercial": "商业观测卡",
    "craft": "技法卡",
    "genre_pack": "题材包",
    "prose_card": "题材文风卡",
    "trope": "桥段库",
    "distilled": "蒸馏卡",
    "prose_card_index": "文风卡索引",
}

_KIND_PURPOSE: dict[str, str] = {
    "voice": "记录一本书的叙述声线与语言风格：人称、句式节奏、对白特征、情绪处理、意象偏好与禁用词，供写作时注入同款文风。",
    "structure": "记录一本书的章节结构规律：钩子间隔、高潮周期、伏笔跨度，供大纲规划与结构质检参考。",
    "commercial": "记录一本书的商业节奏：爽点密度与类型、付费卡点、铺垫长度，供把控节奏与卡点参考。",
    "craft": "记录一本书的写作技法：伏笔、节奏、转场、对白、感官描写等技法与可复用模式，供写作学习与注入。",
    "genre_pack": "多本书聚合的题材级资产：结构规律、商业规律、质检阈值、语言规则与世界观约定，同题材新书自动匹配注入。",
    "prose_card": "题材级语言风格卡：该题材整体的行文风格与语言规则，供题材级文风注入。",
    "trope": "桥段模式库：跨书、跨题材的通用桥段，供构思情节、找灵感时检索调用。",
    "distilled": "多本书聚合出的共性规则：必守（硬边界）、建议（高置信）与分歧，直接拼入写作 prompt，无需手动选择。",
    "prose_card_index": "题材文风卡的寻址索引：按题材快速定位对应的文风卡，系统内部使用。",
}

_KIND_USAGE: dict[str, str] = {
    "voice": "写作页 → 声线卡选择后注入，控制生成章节的人称、句式与语言风格。",
    "structure": "写作页 → 大纲/结构规划时参考；质检页 → 结构维度对照。",
    "commercial": "写作页 → 把控爽点节奏与卡点位置；质检页 → 商业维度对照。",
    "craft": "写作页 → 注入技法参考；拆书学习时浏览。",
    "genre_pack": "同题材新书 → 自动匹配注入；题材包管理 → 查看聚合口径。",
    "prose_card": "写作页 → 题材级文风注入（prose 模式）。",
    "trope": "写作页 → 情节构思时检索桥段；灵感枯竭时浏览找思路。",
    "distilled": "写作时自动注入（拼入 prompt），无需手动操作。",
    "prose_card_index": "系统内部寻址用，一般无需手动查看。",
}

# 各 kind 摘要优先展示的字段（点路径， 中文名）；不存在的字段自动跳过。
_KIND_HIGHLIGHTS: dict[str, list[tuple[str, str]]] = {
    "voice": [
        ("narration.pov", "叙述人称"),
        ("dialogue.dialogue_ratio", "对白占比"),
        ("narration.sentence_rhythm.burst_pattern", "短句爆发模式"),
        ("emotion_handling.mode", "情绪处理方式"),
        ("imagery.signature_devices", "标志性意象手法"),
    ],
    "craft": [
        ("craft_summary.top_3_strengths", "三大优势"),
        ("craft_summary.unique_techniques", "独门技法"),
        ("craft_summary.reusable_patterns", "可复用模式"),
        ("craft_analysis.foreshadowing.technique", "伏笔技法"),
        ("craft_analysis.rhythm_control.technique", "节奏控制技法"),
    ],
    "structure": [
        ("aggregate.climax_cycle", "高潮周期"),
        ("aggregate.hook_min_interval", "钩子最小间隔"),
        ("aggregate.foreshadow_avg_span", "伏笔平均跨度"),
        ("aggregate.hook_type_freq", "钩子类型分布"),
    ],
    "commercial": [
        ("skeleton", "商业骨架"),
        ("payoff_density.per_thousand_words", "爽点密度（每千字）"),
        ("payoff_types", "爽点类型"),
        ("paywall", "付费卡点"),
        ("buildup_length", "铺垫长度"),
        ("common_mistakes", "常见误区"),
    ],
    "genre_pack": [
        ("meta.name", "题材名"),
        ("meta.sub_tags", "子标签"),
        ("meta.target_platform", "目标平台"),
    ],
    "prose_card": [
        ("meta.name", "题材名"),
        ("meta.sub_tags", "子标签"),
        ("meta.target_platform", "目标平台"),
    ],
}

# 蒸馏卡维度中文名（与 scripts/distill_render.py.DIMENSION_LABELS 一致）。
_DISTILLED_DIM_LABELS: dict[str, str] = {
    "voice-card": "声线风格",
    "craft-card": "写作技法",
    "structure-obs": "结构规律",
    "commercial-obs": "商业节奏",
}

# 蒸馏卡规则字段中文标签：镜像 scripts/distill_render.py.FIELD_LABELS
# （规约禁止 import scripts；tests/test_asset_index.py 有同步测试防漂移）。
_DISTILLED_FIELD_LABELS: dict[str, str] = {
    "narration.pov": "叙述人称",
    "narration.tense_feel": "时态语感",
    "narration.chapter_opening_patterns": "开篇模式",
    "narration.sentence_rhythm.avg_length": "平均句长",
    "narration.sentence_rhythm.short_ratio": "短句占比",
    "narration.sentence_rhythm.long_ratio": "长句占比",
    "narration.sentence_rhythm.burst_pattern": "短句爆发模式",
    "dialogue.dialogue_ratio": "对白占比",
    "dialogue.character_voices": "人物语言特征",
    "dialogue.subtext_level": "潜台词风格",
    "emotion_handling.mode": "情绪处理方式",
    "emotion_handling.body_reaction_vocabulary": "身体反应词库",
    "emotion_handling.examples": "情绪处理示例",
    "imagery.high_freq_metaphor_domains": "高频隐喻域",
    "imagery.signature_devices": "标志性意象手法",
    "imagery.sensory_preference.visual": "视觉偏好",
    "imagery.sensory_preference.auditory": "听觉偏好",
    "imagery.sensory_preference.tactile": "触觉偏好",
    "imagery.sensory_preference.olfactory": "嗅觉偏好",
    "imagery.sensory_preference.gustatory": "味觉偏好",
    "banned.never_used_words": "禁用词",
    "craft_analysis.foreshadowing.technique": "伏笔技法",
    "craft_analysis.narrative_engine.technique": "叙事引擎技法",
    "craft_analysis.pov_control.technique": "视角控制技法",
    "craft_analysis.rhythm_control.technique": "节奏控制技法",
    "craft_analysis.scene_transition.technique": "转场技法",
    "craft_analysis.dialogue_craft.technique": "对白技法",
    "craft_analysis.sensory_craft.technique": "感官描写技法",
    "craft_summary.top_3_strengths": "三大优势",
    "craft_summary.unique_techniques": "独门技法",
    "craft_summary.reusable_patterns": "可复用模式",
    "aggregate.climax_cycle": "高潮周期",
    "aggregate.foreshadow_avg_span": "伏笔平均跨度",
    "aggregate.foreshadow_max_span": "伏笔最大跨度",
    "aggregate.foreshadow_concurrent_open": "并发伏笔数",
    "aggregate.hook_min_interval": "钩子最小间隔",
    "aggregate.hook_type_freq": "钩子类型分布",
    "skeleton": "商业骨架",
    "buildup_length": "铺垫长度",
    "payoff_density.per_thousand_words": "爽点密度（每千字）",
    "payoff_types": "爽点类型",
    "paywall": "付费卡点",
    "common_mistakes": "常见误区",
    "dry_spell_tolerance": "干情节容忍度",
}

# 占比字段：0~1 浮点在摘要里渲染为百分比（如对白占比 0.26 → 26%）。
_RATIO_PATHS = frozenset({
    "dialogue.dialogue_ratio",
})

# 占位零值字段镜像（与 scripts/distill_render.py._ZERO_MEANS_MISSING 一致；
# tests/test_asset_index.py 有同步测试）。摘要与注入必须一致：这些 0 不展示。
_ZERO_MEANS_MISSING = frozenset({
    "narration.sentence_rhythm.avg_length",
    "narration.sentence_rhythm.short_ratio",
    "narration.sentence_rhythm.long_ratio",
})

_GENRE_PACK_SECTIONS: tuple[tuple[str, str], ...] = (
    ("structure", "结构规律"),
    ("commercial", "商业规律"),
    ("quality_thresholds", "质检阈值"),
    ("language_rules", "语言规则"),
    ("world_conventions", "世界观约定"),
)


def _fmt_num(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, float):
        return str(round(value, 2))
    return str(value)


def _lookup_path(data: Any, path: str) -> Any:
    """按 'a.b.c' 点路径取值；缺失返回 None。"""
    cur = data
    for seg in path.split("."):
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return None
    return cur


def _try_parse_json(text: str) -> Any | None:
    """解析值字符串里内嵌的 JSON（整体或"；"连接的多段）；解析不出返回 None。"""
    s = text.strip()
    if not s:
        return None
    # 先处理"；"连接的多段（整体以 { 开头也可能是多段，不能先整体解析）。
    if "；" in s:
        parts = [q.strip() for q in s.split("；") if q.strip()]
        out: list[Any] = []
        ok = False
        for q in parts:
            if q[:1] in "{[":
                try:
                    out.append(json.loads(q))
                    ok = True
                    continue
                except json.JSONDecodeError:
                    pass
            out.append(q)
        return out if ok else None
    if s[0] in "{[":
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None
    return None


# 值内 dict 键的中文映射（最小集；蒸馏摘要里常见）。
_VALUE_KEY_LABELS: dict[str, str] = {
    "example_structure": "示例结构",
    "frequency": "频次",
    "pattern": "模式",
}


def _short_value(value: Any, limit: int = 100) -> str:
    """值压缩为一句话摘要；复杂结构只取可读名，不展开技术细节。"""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        return _fmt_num(value)
    if isinstance(value, str):
        parsed = _try_parse_json(value)
        if parsed is not None:
            return _short_value(parsed, limit)
        s = " ".join(value.split())
        return s if len(s) <= limit else s[:limit] + "…"
    if isinstance(value, (list, tuple)):
        if not value:
            return "（空）"
        names: list[str] = []
        for item in value[:5]:
            if isinstance(item, dict):
                names.append(str(
                    item.get("name") or item.get("title") or item.get("type")
                    or item.get("technique") or item.get("pattern") or "…"))
            elif isinstance(item, str):
                s = " ".join(item.split())
                names.append(s if len(s) <= 40 else s[:40] + "…")
            elif isinstance(item, (int, float)):
                names.append(_fmt_num(item))
            else:
                names.append(str(item))
        tail = f"（共 {len(value)} 项）" if len(value) > 5 else ""
        return "、".join(names) + tail
    if isinstance(value, dict):
        parts = []
        for k, vv in value.items():
            if vv is None or vv == {} or vv == [] or vv == "":
                continue
            label = _VALUE_KEY_LABELS.get(k, k)
            parts.append(f"{label}：{_short_value(vv, 40)}")
            if len(parts) >= 3:
                break
        return "；".join(parts) if parts else "（空）"
    return str(value)


def _source_names(meta: dict[str, Any]) -> list[str]:
    """来源书籍名：兼容 str 列表与 {'title': …} 字典列表。"""
    names: list[str] = []
    books = meta.get("source_books")
    if isinstance(books, list):
        for b in books:
            if isinstance(b, dict) and b.get("title"):
                names.append(str(b["title"]))
            elif isinstance(b, str):
                names.append(b)
    return names


def _is_placeholder_zero(field: str, value: Any) -> bool:
    return (
        field in _ZERO_MEANS_MISSING
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value == 0
    )


def _describe_distilled(data: dict[str, Any], meta: dict[str, Any]) -> list[str]:
    rules = data.get("rules")
    if not isinstance(rules, list):
        rules = []
    # 占位零值与注入保持一致：整条跳过，文末注明（不展示为有效规则）。
    skipped = [r for r in rules if isinstance(r, dict)
               and _is_placeholder_zero(r.get("field", ""), r.get("value"))]
    rules = [r for r in rules if r not in skipped]
    hard = [r for r in rules if isinstance(r, dict) and r.get("kind") == "hard"]
    soft = [r for r in rules if isinstance(r, dict) and r.get("kind") == "soft"]
    out = [f"共 {len(rules)} 条规则：必守 {len(hard)} 条，建议 {len(soft)} 条"]
    if skipped:
        out.append(f"（另有 {len(skipped)} 项数值从未被统计，已省略）")
    dim = meta.get("dimension") or ""
    out.append(f"覆盖维度：{_DISTILLED_DIM_LABELS.get(dim, dim or '—')}")
    for r in hard[:6]:
        field = r.get("field", "")
        label = _DISTILLED_FIELD_LABELS.get(field, field)
        rv = r.get("value")
        if (field in _RATIO_PATHS and isinstance(rv, (int, float))
                and 0 <= rv <= 1):
            val = f"{rv:.0%}"
        else:
            val = _short_value(rv, 80)
        out.append(f"必守 · {label}：{val}" if val else f"必守 · {label}")
    if len(hard) > 6:
        out.append(f"（另有 {len(hard) - 6} 条必守，见原始数据）")
    return out


def _describe_tropes(data: dict[str, Any]) -> list[str]:
    tropes = data.get("tropes")
    if not isinstance(tropes, list) or not tropes:
        return []
    out: list[str] = []
    names = [t.get("name") for t in tropes
             if isinstance(t, dict) and t.get("name")]
    if names:
        shown = "、".join(str(n) for n in names[:8])
        tail = f"（共 {len(names)} 个）" if len(names) > 8 else ""
        out.append(f"收录桥段{tail}：{shown}")
    scopes = sorted({str(t.get("genre_scope")) for t in tropes
                     if isinstance(t, dict) and t.get("genre_scope")})
    if scopes:
        out.append(f"适用范围：{'、'.join(scopes)}")
    return out


def _describe_prose_index(data: dict[str, Any]) -> list[str]:
    cards = data.get("cards")
    if isinstance(cards, dict) and cards:
        keys = list(cards.keys())
        shown = "、".join(str(k) for k in keys[:8])
        tail = f"（共 {len(keys)} 张）" if len(keys) > 8 else ""
        return [f"索引文风卡{tail}：{shown}"]
    return []


def _describe_genre_pack(data: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for path, label in _KIND_HIGHLIGHTS.get("genre_pack", []):
        value = _lookup_path(data, path)
        if value is None or value == [] or value == {} or value == "":
            continue
        out.append(f"{label}：{_short_value(value)}")
    present = [label for key, label in _GENRE_PACK_SECTIONS if key in data]
    if present:
        out.append(f"包含板块：{'、'.join(present)}")
    return out


def _describe_key_content(kind: str, data: dict[str, Any]) -> list[str]:
    if kind == "distilled":
        return _describe_distilled(data, data.get("meta") or {})
    if kind == "trope":
        return _describe_tropes(data)
    if kind == "genre_pack":
        return _describe_genre_pack(data)
    if kind == "prose_card_index":
        return _describe_prose_index(data)
    out: list[str] = []
    for path, label in _KIND_HIGHLIGHTS.get(kind, []):
        value = _lookup_path(data, path)
        if value is None or value == [] or value == {} or value == "":
            continue
        if path in _RATIO_PATHS and isinstance(value, (int, float)) and 0 <= value <= 1:
            out.append(f"{label}：{value:.0%}")
        else:
            out.append(f"{label}：{_short_value(value)}")
    if not out:
        # 兜底：未知结构只列顶层键，不伪造解读。
        for key, value in data.items():
            if key == "meta" or len(out) >= 5:
                break
            s = _short_value(value)
            if s:
                out.append(f"{key}：{s}")
    return out


def _describe_banned(data: dict[str, Any]) -> list[str]:
    never = _lookup_path(data, "banned.never_used_words")
    if isinstance(never, list) and never:
        shown = "、".join(str(w) for w in never[:10])
        tail = f"（共 {len(never)} 个）" if len(never) > 10 else ""
        return [f"禁用词{tail}：{shown}"]
    if isinstance(never, str) and never.strip():
        return [f"禁用词：{_short_value(never)}"]
    return []


def describe_asset(kind: str, name: str, data: Any) -> str:
    """生成资产的中文可读摘要（markdown）。

    栏目：基本信息 / 用途 / 关键内容 / 禁止项 / 适用位置。
    不存在的字段自动跳过，不伪造；data 异常时降级为通用摘要。
    """
    if not isinstance(data, dict):
        data = {}
    meta = data.get("meta")
    if not isinstance(meta, dict):
        meta = {}

    kind_label = _KIND_LABELS.get(kind, kind)
    lines: list[str] = [f"# {name}", ""]

    # 基本信息。
    info: list[str] = [f"类型：{kind_label}"]
    if meta.get("source_title"):
        info.append(f"来源书籍：{meta['source_title']}")
    else:
        names = _source_names(meta)
        if names:
            info.append(f"来源书籍：{'、'.join(names[:6])}")
    if meta.get("genre"):
        info.append(f"题材：{meta['genre']}")
    sub_tags = meta.get("sub_tags")
    if isinstance(sub_tags, list) and sub_tags:
        info.append(f"子标签：{'、'.join(str(t) for t in sub_tags[:6])}")
    if meta.get("id"):
        info.append(f"资产 ID：{meta['id']}")
    lines.append("## 基本信息")
    lines.extend(f"- {x}" for x in info)
    lines.append("")

    # 用途。
    lines.append("## 用途")
    lines.append(_KIND_PURPOSE.get(kind, "通用写作资产。"))
    lines.append("")

    # 关键内容。
    lines.append("## 关键内容")
    body = _describe_key_content(kind, data)
    if body:
        lines.extend(f"- {x}" for x in body)
    else:
        lines.append("- 暂无可展示的关键内容（见原始数据）。")
    lines.append("")

    # 禁止项。
    banned = _describe_banned(data)
    if banned:
        lines.append("## 禁止项")
        lines.extend(f"- {x}" for x in banned)
        lines.append("")

    # 适用位置。
    lines.append("## 适用位置")
    lines.append(_KIND_USAGE.get(kind, "资产库浏览。"))
    return "\n".join(lines)


class AssetIndex:
    """资产索引：SQLite 查询为主 + 目录扫描回退 + 短 TTL 只读缓存。

    SQLite 为权威（``gui.db``），``scan()`` 目录扫描仅作为「尚未迁移/测试隔离」时的
    回退源与 ``migrate`` 的同步参照。查询方法优先 SQL，SQL 为空则回退 scan。
    """

    def __init__(self, ttl_seconds: int | None = None) -> None:
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else _default_ttl()
        self._cache: dict[str, Any] = {}
        self._cache_ts: float = 0.0

    # ------------------------------------------------------------------
    # SQLite 就绪判断
    # ------------------------------------------------------------------

    def _db_ready(self) -> bool:
        """判断 SQLite 是否已有索引数据（assets/books/reports 任一非空）。"""
        try:
            conn = db.get_conn()
            n = conn.execute(
                "SELECT (SELECT COUNT(*) FROM assets) + "
                "(SELECT COUNT(*) FROM books) + "
                "(SELECT COUNT(*) FROM reports) AS n"
            ).fetchone()
            return bool(n and n["n"] and int(n["n"]) > 0)
        except Exception:  # noqa: BLE001 — 库未初始化/损坏时回退扫描。
            return False

    # ------------------------------------------------------------------
    # 目录扫描（回退源，阶段一行为）
    # ------------------------------------------------------------------

    def scan(self, force: bool = False) -> dict[str, Any]:
        """全量目录扫描，返回结构化索引 dict（含 items / counts）。

        保留作为 SQLite 为空时的回退源；生产迁移后一般不再调用。
        """
        now = time.time()
        if not force and self._cache and (now - self._cache_ts) < self.ttl_seconds:
            return self._cache

        items: list[dict[str, Any]] = []
        items.extend(self._scan_assets())
        items.extend(self._scan_reports())
        items.extend(self._scan_corpus())

        counts: dict[str, int] = {}
        for it in items:
            counts[it["kind"]] = counts.get(it["kind"], 0) + 1

        result = {
            "items": items,
            "counts": counts,
            "model_configured": self._model_configured(),
        }
        self._cache = result
        self._cache_ts = now
        return result

    def invalidate(self) -> None:
        """写操作后主动失效缓存。"""
        self._cache = {}
        self._cache_ts = 0.0

    def _scan_assets(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        root = config.ASSETS_ROOT
        if not root.is_dir():
            return out
        for fp in sorted(root.glob("*.json")):
            kind = self._classify_asset_name(fp.name)
            if kind is None:
                continue
            out.append(self._make_item(kind, fp, root))
        return out

    def _scan_reports(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        root = config.REPORTS_DIR
        if not root.is_dir():
            return out
        for fp in sorted(root.glob("*.md")):
            item = self._make_item("report", fp, root)
            item["report_kind"] = "book"
            item["book_id"] = fp.stem
            for suffix, rk in _REPORT_SUFFIX:
                if fp.name.endswith(suffix):
                    item["report_kind"] = rk
                    item["book_id"] = fp.name[: -len(suffix)]
                    break
            out.append(item)
        return out

    def _scan_corpus(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        root = config.CORPUS_DIR
        if not root.is_dir():
            return out
        for fp in sorted(root.glob("*.txt")):
            if fp.is_file():
                out.append(self._make_item("book", fp, root))
        return out

    def _model_configured(self) -> bool:
        fp = config.CONFIG_DIR / "models.json"
        if not fp.is_file():
            return False
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        models = data.get("models", {})
        return isinstance(models, dict) and len(models) > 0

    @staticmethod
    def _classify_asset_name(name: str) -> str | None:
        """按文件名后缀归类 asset 文件（扫描回退源）；无法归类返回 None。"""
        for suffix, kind in _SUFFIX_KIND:
            if suffix in name:
                return kind
        return None

    def _make_item(self, kind: str, fp: Path, root: Path) -> dict[str, Any]:
        try:
            rel = str(fp.relative_to(config.ROOT_DIR))
        except ValueError:
            rel = f"{root.name}/{fp.name}"
        st = fp.stat()
        return {
            "kind": kind,
            "id": self._item_id(kind, fp),
            "name": fp.stem,
            "path": rel,
            "size": st.st_size,
            "mtime": st.st_mtime,
            "book_id": self._book_id_from_name(kind, fp.stem),
        }

    @staticmethod
    def _item_id(kind: str, fp: Path) -> str:
        return f"{kind}:{fp.stem}"

    @staticmethod
    def _book_id_from_name(kind: str, stem: str) -> str | None:
        if kind == "report":
            return stem
        # 跨书蒸馏卡（题材级聚合）与题材文风卡索引（寻址表）：均无单书归属。
        if kind in ("distilled", "prose_card_index"):
            return None
        for suffix in ("-voice-card", "-structure-obs", "-commercial-obs", "-craft-card", "-genre-pack"):
            if suffix in stem:
                return stem.split(suffix)[0]
        if "genre-prose-card-" in stem:
            return None
        return None

    # ------------------------------------------------------------------
    # 查询（SQLite 为主 + 扫描回退）
    # ------------------------------------------------------------------

    def list_assets(self, kind: str | None = None, genre: str | None = None,
                    book_id: str | None = None, offset: int = 0, limit: int = 50) -> dict[str, Any]:
        """资产清单分页。kind/genre/book_id 可选，缺省返回全部。

        兼容旧签名 ``list_assets(kind, offset, limit)``（阶段一测试/调用方）：当第 2、3
        个位置参数均为 int（而非 genre/book_id 字符串）时，视为旧式调用并平移
        ``offset``/``limit``。

        Returns:
            {"total": int, "items": [AssetItem, ...]}
        """
        # 旧签名兼容：list_assets(kind, offset, limit) —— genre/book_id 位置被 int 占据。
        if isinstance(genre, int) and isinstance(book_id, int):
            offset, limit = genre, book_id
            genre, book_id = None, None

        if kind is not None and kind not in _ALL_KINDS:
            raise ValueError(f"未知资产类型: {kind}")
        offset = max(0, int(offset))
        limit = max(1, min(int(limit), 500))

        if self._db_ready():
            return self._list_from_db(kind, genre, book_id, offset, limit)
        return self._list_from_scan(kind, genre, book_id, offset, limit)

    def _list_from_db(self, kind: str | None, genre: str | None,
                      book_id: str | None, offset: int, limit: int) -> dict[str, Any]:
        """SQLite 查询：资产卡走 assets 表，report/book 走对应表，None 合并三类。"""
        if kind is None:
            kinds = list(ASSET_KINDS) + ["report", "book"]
        else:
            kinds = [kind]

        all_items: list[dict[str, Any]] = []
        for k in kinds:
            all_items.extend(self._query_kind(k, genre, book_id))
        # 稳定排序（name）。
        all_items.sort(key=lambda it: it.get("name", ""))
        total = len(all_items)
        return {"total": total, "items": all_items[offset:offset + limit]}

    def _query_kind(self, kind: str, genre: str | None, book_id: str | None) -> list[dict[str, Any]]:
        """按单个 kind 查询（assets 卡 / report / book）。"""
        if kind == "report":
            rows = db.list_reports(book_id)
            return [self._report_row_to_item(r) for r in rows]
        if kind == "book":
            rows = db.get_books(book_id=book_id, genre=genre)
            return [self._book_row_to_item(r) for r in rows]
        # 资产卡。
        rows = db.list_asset_rows(kind=kind, genre=genre, book_id=book_id, offset=0, limit=100000)
        return [self._asset_row_to_item(r) for r in rows]

    @staticmethod
    def _asset_row_to_item(row: dict[str, Any]) -> dict[str, Any]:
        name = row.get("name") or ""
        path = row.get("path")
        stem = Path(path).stem if path else name
        # 2026-09-23（总工排查）修复：DB 里的 size/mtime 是**上一次索引时的快照**，
        # 文件此后被改写就失真——实测 65 个资产中 24 个 size 不符（最严重
        # 暮冬念春-structure-obs：DB 28593 vs 磁盘 74875，差 2.6 倍），GUI 资产库
        # 因此显示错误体积。AGENTS.md §7 要求「所有数字以实测磁盘为准」，
        # 故以实时 stat 为准，仅在文件不可读（已删除/无权限）时退回 DB 缓存值。
        size = row.get("size")
        mtime = row.get("mtime")
        if path:
            try:
                st = migrate.resolve_rel_path(path).stat()
                size, mtime = st.st_size, st.st_mtime
            except OSError:
                pass
        return {
            "kind": row.get("kind"),
            "id": f"{row.get('kind')}:{stem}",
            "name": name,
            "path": path,
            "size": size,
            "mtime": mtime,
            "book_id": row.get("book_id"),
            "genre": row.get("genre"),
        }

    @staticmethod
    def _report_row_to_item(row: dict[str, Any]) -> dict[str, Any]:
        path = row.get("path", "")
        stem = Path(path).stem if path else row.get("title", "")
        return {
            "kind": "report",
            "id": f"report:{stem}",
            "name": stem,
            "path": path,
            "size": None,
            "mtime": None,
            "book_id": row.get("book_id"),
            "report_kind": row.get("type", "book"),
        }

    @staticmethod
    def _book_row_to_item(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "kind": "book",
            "id": f"book:{row.get('book_id')}",
            "name": row.get("book_id"),
            "path": row.get("source_path"),
            "size": None,
            "mtime": None,
            "book_id": row.get("book_id"),
        }

    def _list_from_scan(self, kind: str | None, genre: str | None,
                        book_id: str | None, offset: int, limit: int) -> dict[str, Any]:
        """扫描回退：阶段一行为（无 genre/book_id 过滤，报告/书也纳入）。"""
        data = self.scan()
        items = data["items"]
        if kind is not None:
            items = [it for it in items if it["kind"] == kind]
        total = len(items)
        return {"total": total, "items": items[offset:offset + limit]}

    def count_by_kind(self) -> dict[str, int]:
        """按 kind 计数（SQLite GROUP BY，空则回退扫描计数）。"""
        if self._db_ready():
            counts = db.count_by_kind()
            # 合并 report/book 计数（兼容阶段一 overview）。
            counts["report"] = len(db.list_reports())
            counts["book"] = len(db.get_books())
            return counts
        return dict(self.scan()["counts"])

    def get_asset_detail(self, kind: str, asset_id: str) -> dict[str, Any]:
        """资产详情：按 kind + id 定位并读取 JSON/文本内容。

        安全：kind 白名单 + id 校验（防路径穿越）。报告返回 markdown 原文。
        """
        if kind not in _ALL_KINDS:
            raise ValueError(f"未知资产类型: {kind}")
        name = self._resolve_name(kind, asset_id)
        if name is None:
            raise KeyError(f"资产不存在: {kind}:{asset_id}")

        # 优先 SQLite 定位 path（book_id 校验 + 相对 path 读取原文件）。
        if self._db_ready():
            detail = self._detail_from_db(kind, name, asset_id)
            if detail is not None:
                return detail

        # 回退：直接按目录读取（阶段一行为）。
        return self._detail_from_scan(kind, name, asset_id)

    def _detail_from_db(self, kind: str, name: str, asset_id: str) -> dict[str, Any] | None:
        if kind == "report":
            rows = db.list_reports()
            for r in rows:
                if Path(r.get("path", "")).stem == name:
                    fp = migrate.resolve_rel_path(r["path"])
                    if fp.is_file():
                        return {"kind": "report", "id": asset_id, "name": name,
                                "markdown": fp.read_text(encoding="utf-8")}
            return None
        if kind == "book":
            return None  # 书正文按需读 corpus，走 scan 回退。
        # 资产卡：按 asset_key = kind:name 定位 path。
        row = db.get_asset_by_key(f"{kind}:{name}")
        if row is None:
            return None
        fp = migrate.resolve_rel_path(row["path"])
        if not fp.is_file():
            return None
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning(f"资产详情加载失败，content 置空 {fp.name}: {exc}")
            data = {}
        return {"kind": kind, "id": asset_id, "name": name, "content": data,
                "summary": describe_asset(kind, name, data)}

    def _detail_from_scan(self, kind: str, name: str, asset_id: str) -> dict[str, Any]:
        if kind == "report":
            fp = config.REPORTS_DIR / f"{name}.md"
            if not fp.is_file():
                raise KeyError(f"报告不存在: {name}")
            return {"kind": "report", "id": asset_id, "name": name,
                    "markdown": fp.read_text(encoding="utf-8")}
        if kind == "book":
            fp = config.CORPUS_DIR / f"{name}.txt"
            if not fp.is_file():
                raise KeyError(f"语料不存在: {name}")
            # 只读前 2000 字符做预览：文本模式 read(n) 按字符计数，与
            # read_text()[:2000] 输出一致，但内存占用恒定（不随文件大小增长）。
            try:
                with fp.open("r", encoding="utf-8") as fh:
                    preview = fh.read(2000)
            except (OSError, UnicodeDecodeError):
                preview = ""
            return {"kind": "book", "id": asset_id, "name": name,
                    "size": fp.stat().st_size,
                    "preview": preview}
        fp = config.ASSETS_ROOT / f"{name}.json"
        if not fp.is_file():
            raise KeyError(f"资产不存在: {name}")
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            _log.warning(f"资产详情加载失败，content 置空 {fp.name}: {exc}")
            data = {}
        return {"kind": kind, "id": asset_id, "name": name, "content": data,
                "summary": describe_asset(kind, name, data)}

    def get_overview(self) -> dict[str, Any]:
        """首页概览聚合（SQL 聚合为主，空则回退扫描计数）。

        total_assets 只统计 ASSET_KINDS（真资产卡）；report/book 是虚拟 kind，
        已由 total_reports/total_books 单独展示，计入 total_assets 会虚报。
        """
        def _asset_total(counts: dict[str, int]) -> int:
            return sum(counts.get(k, 0) for k in ASSET_KINDS)

        if self._db_ready():
            counts = db.count_by_kind()
            assets_by_kind = self.count_by_kind()
            return {
                "total_books": len(db.get_books()),
                "total_genre_packs": counts.get("genre_pack", 0),
                "total_reports": len(db.list_reports()),
                "total_assets": _asset_total(assets_by_kind),
                "assets_by_kind": assets_by_kind,
                "model_configured": self._model_configured(),
                "recent_activity": [],
            }
        data = self.scan()
        counts = data["counts"]
        return {
            "total_books": counts.get("book", 0),
            "total_genre_packs": counts.get("genre_pack", 0),
            "total_reports": counts.get("report", 0),
            "total_assets": _asset_total(counts),
            "assets_by_kind": counts,
            "model_configured": data["model_configured"],
            "recent_activity": [],
        }

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    def _resolve_name(self, kind: str, asset_id: str) -> str | None:
        raw = str(asset_id)
        prefix = f"{kind}:"
        if not raw.startswith(prefix):
            return None
        name = raw[len(prefix):]
        if not name or any(ch in name for ch in ("/", "\\", "..")):
            return None
        if any(ch in name for ch in ("\x00", "\n", "\r")):
            return None
        return name


# 进程内单例（服务层与路由层共用）。
index = AssetIndex()
