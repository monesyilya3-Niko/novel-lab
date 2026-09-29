"""蒸馏注入渲染：把 distilled JSON 渲染为可注入 prompt 的文本段。

渲染规则（§3.4）：
    * 硬规则标『必守』；
    * 软规则标『建议』；
    * 冲突标『二选一/分歧』；
    * 盲区标『注意缺失』；
    * 空串表示不注入。

可读性（2026-09-29 用户反馈"注入像乱码"后改进）：
    * 字段路径映射为中文标签（如 narration.pov → 叙述人称）；
    * 占位零值（从未统计的数值字段写 0）整条跳过并在文末注明；
    * 分歧规则按书分段列出各书说法，不再堆成长串；
    * 值里内嵌的 JSON 字符串会被解析后用中文键名渲染；
    * 空串表示不注入。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


# 维度中文名，用于渲染标题。
DIMENSION_LABELS: dict[str, str] = {
    "voice-card": "声线风格",
    "craft-card": "写作技法",
    "structure-obs": "结构规律",
    "commercial-obs": "商业节奏",
}


# 字段路径 → 中文标签（基于 assets/*-distilled.json 实测字段清单整理）。
FIELD_LABELS: dict[str, str] = {
    # voice-card · 叙述
    "narration.pov": "叙述人称",
    "narration.tense_feel": "时态语感",
    "narration.chapter_opening_patterns": "开篇模式",
    "narration.sentence_rhythm.avg_length": "平均句长",
    "narration.sentence_rhythm.short_ratio": "短句占比",
    "narration.sentence_rhythm.long_ratio": "长句占比",
    "narration.sentence_rhythm.burst_pattern": "短句爆发模式",
    # voice-card · 对白
    "dialogue.dialogue_ratio": "对白占比",
    "dialogue.character_voices": "人物语言特征",
    "dialogue.subtext_level": "潜台词风格",
    # voice-card · 情绪
    "emotion_handling.mode": "情绪处理方式",
    "emotion_handling.body_reaction_vocabulary": "身体反应词库",
    "emotion_handling.examples": "情绪处理示例",
    # voice-card · 意象
    "imagery.high_freq_metaphor_domains": "高频隐喻域",
    "imagery.signature_devices": "标志性意象手法",
    "imagery.sensory_preference.visual": "视觉偏好",
    "imagery.sensory_preference.auditory": "听觉偏好",
    "imagery.sensory_preference.tactile": "触觉偏好",
    "imagery.sensory_preference.olfactory": "嗅觉偏好",
    "imagery.sensory_preference.gustatory": "味觉偏好",
    # voice-card · 禁用
    "banned.never_used_words": "禁用词",
    # craft-card
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
    # structure-obs
    "aggregate.climax_cycle": "高潮周期",
    "aggregate.foreshadow_avg_span": "伏笔平均跨度",
    "aggregate.foreshadow_max_span": "伏笔最大跨度",
    "aggregate.foreshadow_concurrent_open": "并发伏笔数",
    "aggregate.hook_min_interval": "钩子最小间隔",
    "aggregate.hook_type_freq": "钩子类型分布",
    # commercial-obs
    "skeleton": "商业骨架",
    "buildup_length": "铺垫长度",
    "payoff_density.per_thousand_words": "爽点密度（每千字）",
    "payoff_density.per_chapter": "爽点密度（每章）",
    "payoff_types": "爽点类型",
    "paywall": "付费卡点",
    "common_mistakes": "常见误区",
    "dry_spell_tolerance": "干情节容忍度",
}

# 未命中整路径时的分段回退映射。
_SEGMENT_LABELS: dict[str, str] = {
    "narration": "叙述",
    "dialogue": "对白",
    "emotion_handling": "情绪处理",
    "imagery": "意象",
    "banned": "禁用",
    "sentence_rhythm": "句式节奏",
    "sensory_preference": "感官偏好",
    "craft_analysis": "技法分析",
    "craft_summary": "技法总结",
    "aggregate": "聚合统计",
    "payoff_density": "爽点密度",
    "pov": "人称",
    "technique": "技法",
}

# 值里的 dict 键 → 中文（把 {"name": …,"speech_signature": …} 这类技术字段转可读）。
_KEY_LABELS: dict[str, str] = {
    "name": "名字",
    "role": "角色",
    "arc": "弧光",
    "speech_signature": "语言特征",
    "never_says": "绝不说",
    "refusal_pattern": "拒绝方式",
    "verbal_tics": "口头禅",
    "pattern": "模式",
    "anti_pattern": "忌用",
    "emotion": "情绪",
    "type": "类型",
    "ratio": "占比",
    "buildup_length": "铺垫长度",
    "example_structure": "示例结构",
    "frequency": "频次",
    "note": "说明",
    "anger_pattern": "愤怒模式",
    "physical_habit": "肢体习惯",
    "arc_type": "弧光类型",
    "avg_utterance_length": "平均话语长度",
    "cliffhanger_technique": "悬念手法",
    "position_chapter": "卡点章节",
    "pre_paywall_buildup": "卡点前铺垫",
    "climax_position": "高潮位置",
    "main_arc_intervals": "主线区间",
    "turning_chapters": "转折章节",
    "max_consecutive_chapters": "最大连续章数",
    "start": "开始",
    "end": "结束",
    "start_state": "初态",
    "end_state": "终态",
    "chapter_1": "第一章",
    "chapter_2_3_task": "第二三章任务",
}

# 占位零值字段：值为 0 即表示"从未统计"，渲染时整条跳过。
# 依据（2026-09-29 实测）：原始资产里四本书该字段全为 0，而同一资产的
# burst_pattern 文本内明确写着"平均29字""平均句长18.91字"——数值从未被算过。
# 注意：不在此表中的字段值为 0 时视为真实有效的 0，予以保留。
_ZERO_MEANS_MISSING = frozenset({
    "narration.sentence_rhythm.avg_length",
    "narration.sentence_rhythm.short_ratio",
    "narration.sentence_rhythm.long_ratio",
})

# 占比字段：0~1 的浮点渲染为百分比。
_RATIO_FIELDS = frozenset({
    "dialogue.dialogue_ratio",
    "narration.sentence_rhythm.short_ratio",
    "narration.sentence_rhythm.long_ratio",
})

# 字数单位字段（按路径末段匹配）。
_LEN_SUFFIXES = ("avg_length", "buildup_length")


def _field_label(field: str) -> str:
    """字段路径转中文标签；未知字段做分段回退美化。"""
    if field in FIELD_LABELS:
        return FIELD_LABELS[field]
    parts = []
    for seg in field.split("."):
        if seg in _SEGMENT_LABELS:
            parts.append(_SEGMENT_LABELS[seg])
        else:
            parts.append(seg.replace("_", ""))
    return "·".join(parts)


def _is_placeholder_zero(field: str, value: Any) -> bool:
    """是否为占位零值（从未统计写 0）。排除 bool（False == 0 的陷阱）。"""
    return (
        field in _ZERO_MEANS_MISSING
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value == 0
    )


def _fmt_number(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, float):
        return str(round(value, 2))
    return str(value)


def _parse_embedded(text: str) -> Any | None:
    """解析值字符串里内嵌的 JSON（整体或"；"连接的多段）。

    成功返回解析后的对象；解析不出返回 None（调用方保留原文）。
    """
    s = text.strip()
    if not s:
        return None
    if s[0] in "{[":
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
    if "；" in s:
        parts = [p.strip() for p in s.split("；") if p.strip()]
        parsed: list[Any] = []
        any_ok = False
        for p in parts:
            if p and p[0] in "{[":
                try:
                    parsed.append(json.loads(p))
                    any_ok = True
                    continue
                except json.JSONDecodeError:
                    pass
            parsed.append(p)
        if any_ok:
            return parsed
    return None


def _render_value(value: Any) -> str:
    """把规则值渲染为可读文本。"""
    if value is None:
        return "（缺失）"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, str):
        parsed = _parse_embedded(value)
        if parsed is not None:
            return _render_value(parsed)
        return value
    if isinstance(value, (list, tuple)):
        if not value:
            return "（空）"
        items = [_render_value(v) for v in value]
        # 纯标量用顿号，含结构项用分号分隔更清晰。
        sep = "、" if all(isinstance(v, (str, int, float)) for v in value) else "；"
        return sep.join(items)
    if isinstance(value, dict):
        parts = []
        for k, vv in value.items():
            if vv is None or vv == {} or vv == [] or vv == "":
                continue
            label = _KEY_LABELS.get(k, k)
            rendered = _render_value(vv)
            # ratio 类 0~1 浮点转百分比。
            if k == "ratio" and isinstance(vv, float) and 0 <= vv <= 1:
                rendered = f"{vv:.0%}"
            parts.append(f"{label}：{rendered}")
        return "；".join(parts) if parts else "（空）"
    return str(value)


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def render_distilled(distilled: dict | None) -> str:
    """把单个维度的 distilled dict 渲染为 prompt 文本段。

    Args:
        distilled: ``{meta, rules, blindspots, stats}`` 结构；None 或空规则返回空串。

    Returns:
        渲染后的文本；无内容时返回空串（调用方据此决定是否注入）。
    """
    if not distilled:
        return ""
    rules: list[dict] = distilled.get("rules") or []
    blindspots: list[dict] = distilled.get("blindspots") or []
    meta: dict[str, Any] = distilled.get("meta") or {}

    if not rules and not blindspots:
        return ""

    dimension = meta.get("dimension", "")
    label = DIMENSION_LABELS.get(dimension, dimension or "蒸馏")
    books_count = meta.get("books_count", 0)
    source_books = "、".join(meta.get("source_books") or []) or "未知"

    lines: list[str] = []
    lines.append(f"## 〇·五、蒸馏规则（{label} · 跨 {books_count} 本聚合）")
    lines.append(f"> 来源书籍：{source_books}。以下为多本对标作品聚合出的共性规则。")

    # 分组：hard 优先，soft 其次。
    hard = [r for r in rules if r.get("kind") == "hard"]
    soft = [r for r in rules if r.get("kind") == "soft"]
    skipped: list[str] = []

    if hard:
        lines.append("\n### 必守规则（三本一致 · 硬边界）")
        for r in hard:
            line = _render_rule_line(r, "必守")
            if line:
                lines.append(line)
            else:
                skipped.append(_field_label(r.get("field", "")))

    if soft:
        lines.append("\n### 建议规则（两本一致 · 高置信）")
        for r in soft:
            line = _render_rule_line(r, "建议")
            if line:
                lines.append(line)
            else:
                skipped.append(_field_label(r.get("field", "")))

    if skipped:
        lines.append(
            f"\n> 注：以下 {len(skipped)} 项数值从未被统计，已省略未注入："
            + "、".join(skipped)
        )

    if blindspots:
        lines.append("\n### 盲区提示（注意缺失）")
        seen: set = set()
        for b in blindspots:
            key = (b.get("book"), b.get("field"))
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- 《{b.get('book')}》缺「{_field_label(b.get('field', ''))}」：{b.get('note', '')}")

    return "\n".join(lines)


def _render_rule_line(rule: dict, kind_label: str) -> str:
    """渲染单条规则。占位零值返回空串（调用方跳过并记入省略注）。"""
    field = rule.get("field", "")
    value = rule.get("value")
    confidence = rule.get("confidence", 0.0)
    conflict = rule.get("conflict", False)
    over = rule.get("over_generalized", False)

    if _is_placeholder_zero(field, value):
        return ""

    label = _field_label(field)
    tag = "【二选一/分歧】" if conflict else f"【{kind_label}】"
    conf = f"（置信 {confidence:.2f}）"
    if over:
        conf += " ⚠过度泛化"

    if conflict:
        # 分歧：按书分段，避免多书文本堆成一串。
        out = [f"- {tag} {label}：各书说法不一{conf}"]
        for s in rule.get("sources") or []:
            book = s.get("book", "?")
            v = _render_value(s.get("value"))
            out.append(f"  · 《{book}》：{_truncate(v, 200)}")
        return "\n".join(out)

    if isinstance(value, bool):
        text = "是" if value else "否"
    elif (
        isinstance(value, (int, float))
        and field in _RATIO_FIELDS
        and 0 <= value <= 1
    ):
        text = f"{value:.0%}"
    elif (
        isinstance(value, (int, float))
        and field.split(".")[-1] in _LEN_SUFFIXES
    ):
        text = f"{_fmt_number(value)}字"
    else:
        text = _render_value(value)
    return f"- {tag} {label}：{text} {conf}"


def render_all_distilled(distilled_by_dim: dict[str, dict]) -> str:
    """渲染全部四个维度的蒸馏段，用分隔符拼接。"""
    sections: list[str] = []
    for dimension in ("voice-card", "craft-card", "structure-obs", "commercial-obs"):
        seg = render_distilled(distilled_by_dim.get(dimension))
        if seg:
            sections.append(seg)
    return "\n\n".join(sections)
