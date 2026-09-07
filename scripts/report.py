#!/usr/bin/env python3
"""
M3 拆书报告渲染器 — 资产 JSON → 可交付的 Markdown 拆书报告

把 voice-card + structure-obs + commercial-obs 三份资产渲染成一份
结构完整、可直接交付（闲鱼/公众号/知识星球）的专业拆书报告。

用法:
  python report.py <voice-card.json> [--structure structure-obs.json] [--commercial commercial-obs.json] [--out report.md]
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
REPORTS_DIR = ROOT / "reports"

# 铁律二：报告字符数硬门槛（字符数口径）
MIN_REPORT_CHARS = 10000


# --------------------------------------------------------------------------
# 各资产 → 报告章节
# --------------------------------------------------------------------------

def _join(v, sep="、"):
    if isinstance(v, list):
        return sep.join(str(x) for x in v)
    return str(v or "")


def section_meta(meta: dict) -> str:
    return f"""**题材**：{meta.get('genre', '未知')}
**对标来源**：{meta.get('source_title', '未知')}
**采样范围**：第 {'-'.join(map(str, meta.get('sample_chapters', [])[:2]))} 章 等 {len(meta.get('sample_chapters', []))} 章（共 {meta.get('total_sample_words', 0)} 字）
**置信度**：{meta.get('confidence', 0):.0%}
"""


def section_voices(voices: list) -> str:
    if not voices:
        return "（本卡未提取到角色声线）\n"
    out = []
    for v in voices:
        ss = v.get("speech_signature") or {}
        name = v.get("name", "?")
        role = v.get("role", "")
        out.append(f"### {name}（{role}）\n")
        if ss.get("avg_utterance_length"):
            out.append(f"- **发言长度**：单次平均 {ss['avg_utterance_length']} 字\n")
        if ss.get("verbal_tics"):
            out.append(f"- **口头禅/语气习惯**：{_join(ss['verbal_tics'])}\n")
        if ss.get("refusal_pattern"):
            out.append(f"- **拒绝方式**：{ss['refusal_pattern']}\n")
        if ss.get("anger_pattern"):
            out.append(f"- **生气时**：{ss['anger_pattern']}\n")
        if ss.get("physical_habit"):
            out.append(f"- **说话小动作**：{_join(ss['physical_habit'])}\n")
        if ss.get("never_says"):
            out.append(f"- **绝不会说**：{_join(ss['never_says'])}\n")
        arc = v.get("arc") or {}
        if arc.get("arc_type"):
            out.append(f"- **成长弧光**：{arc['arc_type']}（{arc.get('start_state', '')} → {arc.get('end_state', '')}）\n")
        out.append("\n")
    return "".join(out)


def section_style(vc: dict) -> str:
    lines = []
    narr = vc.get("narration") or {}
    if narr.get("pov"):
        lines.append(f"- **视角**：{narr['pov']}")
    if narr.get("tense_feel"):
        lines.append(f"- **叙述距离**：{narr['tense_feel']}")
    sr = narr.get("sentence_rhythm") or {}
    if sr.get("burst_pattern"):
        lines.append(f"- **短句爆发场景**：{sr['burst_pattern']}")
    para = narr.get("paragraph") or {}
    if para.get("usage_of_single_line"):
        lines.append(f"- **单句成段用法**：{para['usage_of_single_line']}")
    eh = vc.get("emotion_handling") or {}
    if eh.get("mode"):
        lines.append(f"- **情绪写法模式**：{eh['mode']}")
    if eh.get("body_reaction_vocabulary"):
        lines.append(f"- **惯用身体反应**：{_join(eh['body_reaction_vocabulary'])}")
    for ex in eh.get("examples") or []:
        if ex.get("pattern"):
            lines.append(f"- **情绪呈现规律**：{ex['pattern']}")
        if ex.get("anti_pattern"):
            lines.append(f"- **反例（不要这样写）**：{ex['anti_pattern']}")
    img = vc.get("imagery") or {}
    if img.get("high_freq_metaphor_domains"):
        lines.append(f"- **比喻取材领域**：{_join(img['high_freq_metaphor_domains'])}")
    sp = img.get("sensory_preference") or {}
    if sp:
        order = sorted(sp.items(), key=lambda x: -x[1]) if any(isinstance(v, (int, float)) for v in sp.values()) else list(sp.items())
        lines.append("- **感官偏重**：" + "、".join(f"{k}({v})" for k, v in order[:3]))
    banned = vc.get("banned") or {}
    if banned.get("never_used_words"):
        lines.append(f"- **全文回避词**：{_join(banned['never_used_words'])}")
    return "\n".join(lines) + "\n" if lines else "（文风数据不完整）\n"


def section_structure(so: dict) -> str:
    if not so:
        return "（无结构观测）\n"
    lines = []
    ca = so.get("chapter_analyses")
    if isinstance(ca, list) and ca:
        roles = {}
        for c in ca:
            r = c.get("role") or c.get("章节功能") or "?"
            roles[r] = roles.get(r, 0) + 1
        total = sum(roles.values())
        dist = "、".join(f"{k}×{v}" for k, v in sorted(roles.items(), key=lambda x: -x[1]))
        lines.append(f"- **章节功能分布**（{total} 章）：{dist}")
        hooks = [c.get("hook") for c in ca if c.get("hook")]
        if hooks:
            lines.append("- **钩子骨架模板**：")
            for h in hooks[:4]:
                if isinstance(h, dict) and h.get("skeleton"):
                    lines.append(f"  - [{h.get('type', '?')}] {h['skeleton']}")
    agg = so.get("aggregate")
    if isinstance(agg, dict):
        if agg.get("hook_type_freq"):
            top = sorted(agg["hook_type_freq"].items(), key=lambda x: -x[1])[:5]
            lines.append(f"- **高频钩子**：{'、'.join(f'{k}×{v}' for k, v in top)}")
        if agg.get("foreshadow_avg_span"):
            lines.append(f"- **伏笔平均跨度**：{agg['foreshadow_avg_span']} 章（同时挂起 ≈{agg.get('foreshadow_concurrent_open', '?')} 条）")
        if agg.get("climax_cycle"):
            lines.append(f"- **爆发周期**：{agg['climax_cycle']}")
    return "\n".join(lines) + "\n"


def section_commercial(co: dict) -> str:
    if not co:
        return "（无商业观测）\n"
    lines = []
    pd = co.get("payoff_density")
    if isinstance(pd, dict):
        if pd.get("per_thousand_words"):
            pv = pd["per_thousand_words"]
            # 数字无单位时补说明
            if isinstance(pv, (int, float)):
                lines.append(f"- **爽点密度**：每千字约 {pv} 次")
            else:
                lines.append(f"- **爽点密度**：{pv}")
        pts = pd.get("payoff_types")
        if isinstance(pts, list):
            lines.append("- **爽点类型构成**：")
            for t in pts[:6]:
                if isinstance(t, dict) and t.get("type"):
                    bl = t.get("buildup_length")
                    bl_s = f"，铺垫约 {bl} 字" if bl not in (None, "", "?", "0") else ""
                    lines.append(f"  - {t['type']}（{t.get('ratio', '?')}）{bl_s}")
        if pd.get("dry_spell_tolerance"):
            lines.append(f"- **干旱期容忍度**：{pd['dry_spell_tolerance']}")
    oa = co.get("opening_analysis")
    if isinstance(oa, dict):
        c1 = oa.get("chapter_1")
        if isinstance(c1, dict):
            lines.append("- **开篇第 1 章拆解**：")
            if c1.get("first_300_words_task"):
                lines.append(f"  - 前 300 字任务：{c1['first_300_words_task']}")
            if c1.get("hook_position"):
                lines.append(f"  - 首个钩子位置：{c1['hook_position']}")
            if c1.get("protagonist_intro_method"):
                lines.append(f"  - 主角登场方式：{c1['protagonist_intro_method']}")
            if c1.get("golden_finger_reveal"):
                lines.append(f"  - 金手指/核心设定揭示：{c1['golden_finger_reveal']}")
        if oa.get("chapter_2_3_task"):
            lines.append(f"- **第 2-3 章留存任务**：{oa['chapter_2_3_task']}")
    pw = co.get("paywall")
    if isinstance(pw, dict):
        pos = pw.get("position_chapter", "?")
        # 清洗「第 第6章」这类重复前缀
        pos_s = str(pos).strip()
        pos_s = re.sub(r'^第\s*第', '第', pos_s)
        lines.append(f"- **付费卡点**：{pos_s}")
        if pw.get("cliffhanger_technique"):
            lines.append(f"  - 卡点手法：{pw['cliffhanger_technique']}")
        if pw.get("pre_paywall_buildup"):
            lines.append(f"  - 卡点前蓄力：{pw['pre_paywall_buildup']}")
    rr = co.get("retention_risk_points")
    if isinstance(rr, list) and rr:
        lines.append("- **流失高危点与规避**：")
        for r in rr[:4]:
            if isinstance(r, dict) and r.get("position"):
                lines.append(f"  - {r.get('position')}：{r.get('reason', '')} → 规避：{r.get('mitigation', '')}")
    return "\n".join(lines) + "\n"


def build_report(voice, structure, commercial, title_override=None) -> str:
    meta = voice.get("meta") or {}
    src = title_override or meta.get("source_title", "未知作品")
    genre = meta.get("genre", "未知题材")
    today = datetime.now().strftime("%Y-%m-%d")

    sections = []
    sections.append(f"""# 拆书报告：《{src}》

> 生成时间：{today} · 题材：{genre} · 由 novel-lab 拆书引擎自动产出
> 用途：学习对标作品的写作技法与商业结构。报告内容为抽象技法分析，不含原文摘录。

---

## 一、作品定位

{section_meta(meta)}
---

## 二、角色声线拆解

> 每个角色的「说话方式」「拒绝方式」「绝不会说」是写作时防串味的核心资产。

{section_voices((voice.get("dialogue") or {}).get("character_voices") or [])}
---

## 三、文风与情绪写法

{section_style(voice)}
---

## 四、结构规律

{section_structure(structure or {})}
---

## 五、商业洞察（留存与转化）

{section_commercial(commercial or {})}
---

## 六、给创作者的可执行清单

1. **视角**：严格按「文风」一节的视角设定写，不随意切换。
2. **角色开口即人**：每个角色按「声线拆解」说话，特别留意「绝不会说」清单——反向禁令约束力最强。
3. **情绪外化**：按「情绪写法模式」呈现情感，用身体反应代替情绪词（「后槽牙咬紧」而非「他很愤怒」）。
4. **钩子收尾**：每章末尾套用「钩子骨架模板」，同类钩子拉开间隔。
5. **节奏参考**：按「商业洞察」的爽点密度与干旱期容忍度控制章节节奏。
6. **卡点设计**：在「付费卡点」位置前蓄力，用「卡点手法」收尾。
7. **规避清单**：回避「全文回避词」，防止串味与 AI 味。

---

*报告由拆书引擎自动生成，建议结合原书人工复核关键判断（尤其声线与商业数据）。*
""")
    return "\n".join(sections)


def main():
    ap = argparse.ArgumentParser(description="拆书报告渲染器：资产 → 可交付 Markdown 报告")
    ap.add_argument("voice", help="voice-card JSON 路径")
    ap.add_argument("--structure", help="structure-obs JSON（可选）")
    ap.add_argument("--commercial", help="commercial-obs JSON（可选）")
    ap.add_argument("--title", help="报告标题（默认用资产 source_title）")
    ap.add_argument("--out", help="输出路径，默认 reports/<名>-拆书报告.md")
    args = ap.parse_args()

    voice = json.loads(Path(args.voice).read_text(encoding="utf-8"))
    structure = json.loads(Path(args.structure).read_text(encoding="utf-8")) if args.structure else None
    commercial = json.loads(Path(args.commercial).read_text(encoding="utf-8")) if args.commercial else None

    report = build_report(voice, structure, commercial, args.title)

    name = Path(args.voice).stem.replace("-voice-card", "")
    out = Path(args.out) if args.out else REPORTS_DIR / f"{name}-拆书报告.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")

    print(f"✓ 拆书报告已生成: {out}")
    print(f"  报告长度: {len(report)} 字符")

    # 铁律二：拆书报告字符数硬门槛（拆书报告 + 笔法分析合计 ≥10000，此处单份校验）
    if len(report) < MIN_REPORT_CHARS:
        print(f"⚠ 拆书报告字数 {len(report)} < 硬门槛 {MIN_REPORT_CHARS}，请补充分析")
        sys.exit(1)


if __name__ == "__main__":
    main()
