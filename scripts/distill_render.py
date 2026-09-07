# -*- coding: utf-8 -*-
"""蒸馏注入渲染：把 distilled JSON 渲染为可注入 prompt 的文本段。

渲染规则（§3.4）：
    * 硬规则标『必守』；
    * 软规则标『建议』；
    * 冲突标『二选一/分歧』；
    * 盲区标『注意缺失』；
    * 空串表示不注入。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


# 维度中文名，用于渲染标题。
DIMENSION_LABELS: Dict[str, str] = {
    "voice-card": "声线风格",
    "craft-card": "写作技法",
    "structure-obs": "结构规律",
    "commercial-obs": "商业节奏",
}


def _render_value(value: Any) -> str:
    """把规则值渲染为可读文本。"""
    if value is None:
        return "（缺失）"
    if isinstance(value, (list, tuple)):
        if not value:
            return "（空）"
        items = []
        for v in value:
            if isinstance(v, dict):
                parts = []
                for k, vv in v.items():
                    if vv is not None:
                        parts.append(f"{k}:{vv}")
                items.append("{" + ", ".join(parts) + "}")
            else:
                items.append(str(v))
        return "、".join(items)
    if isinstance(value, dict):
        return ", ".join(f"{k}:{vv}" for k, vv in value.items() if vv is not None)
    return str(value)


def render_distilled(distilled: Optional[dict]) -> str:
    """把单个维度的 distilled dict 渲染为 prompt 文本段。

    Args:
        distilled: ``{meta, rules, blindspots, stats}`` 结构；None 或空规则返回空串。

    Returns:
        渲染后的文本；无内容时返回空串（调用方据此决定是否注入）。
    """
    if not distilled:
        return ""
    rules: List[dict] = distilled.get("rules") or []
    blindspots: List[dict] = distilled.get("blindspots") or []
    meta: Dict[str, Any] = distilled.get("meta") or {}

    if not rules and not blindspots:
        return ""

    dimension = meta.get("dimension", "")
    label = DIMENSION_LABELS.get(dimension, dimension or "蒸馏")
    books_count = meta.get("books_count", 0)
    source_books = "、".join(meta.get("source_books") or []) or "未知"

    lines: List[str] = []
    lines.append(f"## 〇·五、蒸馏规则（{label} · 跨 {books_count} 本聚合）")
    lines.append(f"> 来源书籍：{source_books}。以下为多本对标作品聚合出的共性规则。")

    # 分组：hard 优先，soft 其次。
    hard = [r for r in rules if r.get("kind") == "hard"]
    soft = [r for r in rules if r.get("kind") == "soft"]

    if hard:
        lines.append("\n### 必守规则（三本一致 · 硬边界）")
        for r in hard:
            lines.append(_render_rule_line(r, "必守"))

    if soft:
        lines.append("\n### 建议规则（两本一致 · 高置信）")
        for r in soft:
            lines.append(_render_rule_line(r, "建议"))

    if blindspots:
        lines.append("\n### 盲区提示（注意缺失）")
        seen: set = set()
        for b in blindspots:
            key = (b.get("book"), b.get("field"))
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- 《{b.get('book')}》缺「{b.get('field')}」：{b.get('note', '')}")

    return "\n".join(lines)


def _render_rule_line(rule: dict, kind_label: str) -> str:
    """渲染单条规则为一行。"""
    field = rule.get("field", "")
    value = rule.get("value")
    confidence = rule.get("confidence", 0.0)
    conflict = rule.get("conflict", False)
    over = rule.get("over_generalized", False)

    tag = "【二选一/分歧】" if conflict else f"【{kind_label}】"
    conf = f"（置信 {confidence:.2f}）"
    if over:
        conf += " ⚠过度泛化"

    text = _render_value(value)
    return f"- {tag} {field}: {text} {conf}"


def render_all_distilled(distilled_by_dim: Dict[str, dict]) -> str:
    """渲染全部四个维度的蒸馏段，用分隔符拼接。"""
    sections: List[str] = []
    for dimension in ("voice-card", "craft-card", "structure-obs", "commercial-obs"):
        seg = render_distilled(distilled_by_dim.get(dimension))
        if seg:
            sections.append(seg)
    return "\n\n".join(sections)
