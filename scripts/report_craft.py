#!/usr/bin/env python3
"""
笔法深度分析报告生成器 — craft-card → 可交付 Markdown 报告

把 Pass5 产出的 craft-card JSON 转成人类可读的深度分析报告。
报告可直接用于：闲鱼卖"XX作者写作技法拆解"、自我学习、写作教学。

用法:
  python report_craft.py <craft-card.json> [--out report.md]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"


def _technique_block(t: dict, idx: int) -> str:
    """单个技法 → Markdown 段落。兼容中文/英文字段名。"""
    lines = []
    name = t.get("name") or t.get("technique_name") or f"技法{idx}"
    lines.append(f"**{idx}. {name}**")
    desc = t.get("description") or t.get("example_in_text") or ""
    if desc:
        lines.append(f"- **手法**：{desc}")
    if t.get("effect"):
        lines.append(f"- **效果**：{t['effect']}")
    skeleton = t.get("skeleton") or t.get("abstract_pattern") or ""
    if skeleton:
        lines.append(f"- **可复用骨架**：`{skeleton}`")
    anti = t.get("anti_pattern") or t.get("反例") or t.get("counter_example") or ""
    if anti:
        lines.append(f"- **反例**（该作者不会这么写）：{anti}")
    return "\n".join(lines)


def _dimension_section(dim_key: str, dim_data, dim_label: str) -> str:
    """单个技法维度 → Markdown 章节。兼容 dict 和 list 两种格式。"""
    if not dim_data:
        return ""
    # 兼容：dim_data 可能是 list（直接技法数组）或 dict（{techniques: [...]}）
    if isinstance(dim_data, list):
        techniques = dim_data
    else:
        techniques = dim_data.get("techniques", [])
    lines = [f"### {dim_label}\n"]
    if techniques:
        for i, t in enumerate(techniques, 1):
            lines.append(_technique_block(t, i))
            lines.append("")
    # 维度特有字段（仅 dict 格式有）
    if isinstance(dim_data, list):
        return "\n".join(lines)
    for key, label in [
        ("buried_payoff_ratio", "伏笔回收率"),
        ("note", "备注"),
        ("suspense_maintenance", "悬念维持手法"),
        ("info_asymmetry", "信息差运用"),
        ("dominant_style", "主要风格"),
        ("peak_valley_pattern", "张力起伏模式"),
        ("subtext_ratio", "潜台词占比"),
        ("tempo_shift_triggers", "节奏切换触发条件"),
        ("dominant_sense", "最常用感官"),
        ("rare_sense_usage", "罕见感官用法"),
    ]:
        val = dim_data.get(key)
        if val is not None:
            if isinstance(val, float):
                lines.append(f"- **{label}**：{val:.0%}")
            else:
                lines.append(f"- **{label}**：{val}")
    return "\n".join(lines)


def render_craft_report(craft: dict) -> str:
    """craft-card JSON → 完整 Markdown 报告。"""
    meta = craft.get("meta", {})
    analysis = craft.get("craft_analysis", {})
    summary = craft.get("craft_summary", {})

    title = meta.get("source_title", "未知作品")
    author = meta.get("author", "未知")
    genre = meta.get("genre", "")
    platform = meta.get("platform", "")
    confidence = meta.get("confidence", 0)
    chapters = meta.get("sample_chapters", [])
    words = meta.get("total_sample_words", 0)

    lines = [
        f"# 《{title}》写作技法深度拆解报告",
        "",
        f"> **作者**：{author}",
        f"> **题材**：{genre} · **平台**：{platform}",
        f"> **分析样本**：{len(chapters)} 章（{words:,} 字）",
        f"> **置信度**：{confidence:.0%}",
        f"> **生成时间**：{meta.get('extracted_at', '未知')}",
        "",
        "---",
        "",
        "## 技法总览",
        "",
    ]

    # 总览
    if summary.get("top_3_strengths"):
        lines.append("### 最强技法 TOP 3")
        for i, s in enumerate(summary["top_3_strengths"], 1):
            lines.append(f"{i}. {s}")
        lines.append("")

    if summary.get("unique_techniques"):
        lines.append("### 该作者独有技法")
        for t in summary["unique_techniques"]:
            lines.append(f"- {t}")
        lines.append("")

    if summary.get("reusable_patterns"):
        lines.append("### 最值得学习复用的模式")
        for p in summary["reusable_patterns"]:
            lines.append(f"- {p}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # 8 维深度拆解
    DIMENSIONS = [
        ("foreshadowing", "伏笔技法"),
        ("information_release", "信息释放技法"),
        ("pov_control", "视角控制技法"),
        ("scene_transition", "场景转换技法"),
        ("tension_building", "张力构建技法"),
        ("dialogue_craft", "对话技法"),
        ("rhythm_control", "节奏控制技法"),
        ("sensory_craft", "感官运用技法"),
        ("narrative_engine", "叙事引擎"),
        ("emotional_algorithm", "情感算法"),
    ]

    lines.append("## 8 维技法深度拆解\n")
    for dim_key, dim_label in DIMENSIONS:
        section = _dimension_section(dim_key, analysis.get(dim_key, {}), dim_label)
        if section:
            lines.append(section)
            lines.append("---")
            lines.append("")

    # 免责声明
    lines.extend([
        "",
        "---",
        "",
        "> 本报告由 novel-lab 拆书引擎 Pass5 笔法分析模块自动生成。",
        "> 所有技法骨架均为抽象模式，不含原文引用，可安全用于写作参考。",
        "> 重要创作决策请结合原文精读和专业编辑意见。",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="craft-card → 可交付 Markdown 报告")
    parser.add_argument("craft_card", help="craft-card JSON 文件路径")
    parser.add_argument("--out", help="输出 Markdown 文件路径（默认 reports/<书名>-笔法分析.md）")
    args = parser.parse_args()

    craft_path = Path(args.craft_card)
    if not craft_path.exists():
        print(f"✗ 文件不存在: {craft_path}", file=sys.stderr)
        sys.exit(1)

    craft = json.loads(craft_path.read_text(encoding="utf-8"))
    report = render_craft_report(craft)

    if args.out:
        out_path = Path(args.out)
    else:
        title = craft.get("meta", {}).get("source_title", "unknown")
        out_path = REPORTS_DIR / f"{title}-笔法分析.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"✓ 报告已生成: {out_path}")


if __name__ == "__main__":
    main()
