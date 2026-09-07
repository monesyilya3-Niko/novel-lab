#!/usr/bin/env python3
"""
M2.1 资产注入器 — voice-card / 结构观测 / 商业观测 → 写作 system prompt

把拆书产出的结构化 JSON 资产，转成写作引擎直接可用的 system prompt。
M2.2 章节生成时，这个 prompt 作为 system 消息喂给 LLM。

用法:
  python inject.py <voice-card.json> [--structure structure-obs.json] [--commercial commercial-obs.json] [--genre-pack genre-pack.json] [--out out.md]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
PROMPTS_DIR = ROOT / "prompts" / "generated"

# 蒸馏渲染器（同目录），供注入蒸馏规则段使用。
try:
    from distill_render import render_distilled
except ImportError:  # 兼容无蒸馏层时的最小运行。
    def render_distilled(distilled):
        return ""

# 二期 · 检索模块（同目录），供 context_intent 针对性注入使用。
try:
    from retrieve import build_index, render_retrieval, retrieve_for_intent as _retrieve
    from distill_core import collect_assets
except ImportError:  # 兼容无检索模块时的最小运行。
    def render_retrieval(hits):
        return ""

    def build_index(assets):
        return None

    def _retrieve(intent, index, top_k=5):
        return []

    def collect_assets(genre, book_names=None):
        return {}


def retrieve_for_intent(intent: str, distilled=None, genre: str | None = None, top_k: int = 5) -> list:
    """按意图字符串检索蒸馏资产片段（二期 · 检索桥接）。

    优先从原始资产（``collect_assets``，含技法名/骨架等丰富词汇）建索引检索；
    若无法确定 genre，则退化为从 ``distilled`` 结构建索引。

    Args:
        intent: 意图字符串（如 ``"悬疑反转钩子"``）。
        distilled: 蒸馏结果（可选），用于兜底确定 genre 或作为索引来源。
        genre: 题材 id（可选），优先据此采集原始资产建索引。
        top_k: 返回条数上限。

    Returns:
        HitEntry 列表（score 降序）。
    """
    if not intent:
        return []

    # 确定 genre：入参优先，其次 distilled.meta.genre。
    resolved_genre = genre
    if not resolved_genre and isinstance(distilled, dict):
        meta = distilled.get("meta") or {}
        resolved_genre = meta.get("genre")
        if not resolved_genre:
            # {dimension: distilled_dict} 结构，取第一个有 genre 的维度。
            for value in distilled.values():
                if isinstance(value, dict):
                    m = value.get("meta") or {}
                    if m.get("genre"):
                        resolved_genre = m["genre"]
                        break

    # 优先用原始资产建索引（词汇丰富，召回更准）。
    if resolved_genre:
        assets = collect_assets(resolved_genre)
        index = build_index(assets)
        if index is not None and index.docs:
            return _retrieve(intent, index, top_k=top_k)

    # 兜底：从 distilled 结构建索引。
    index = build_index(_normalize_distilled_assets(distilled))
    if index is None:
        return []
    return _retrieve(intent, index, top_k=top_k)


def _normalize_distilled_assets(distilled) -> dict:
    """把多种 distilled 结构归一化为 ``{dimension: asset_dict}``。

    兼容：``{dimension: distilled_dict}``、单个 ``distilled_dict``（含
    ``meta.dimension``）、以及 ``{book: asset_dict}``（裸资产，按 meta.dimension
    分组）。
    """
    if not isinstance(distilled, dict):
        return {}
    # 单维度 distilled_dict：含 meta.dimension。
    meta = distilled.get("meta") if isinstance(distilled, dict) else None
    if isinstance(meta, dict) and meta.get("dimension"):
        return {meta["dimension"]: distilled}
    # {dimension: distilled_dict} 或 {book: asset_dict}：按值内 meta.dimension 分组。
    result: dict = {}
    for key, value in distilled.items():
        if not isinstance(value, dict):
            continue
        inner_meta = value.get("meta") or {}
        dimension = inner_meta.get("dimension") or key
        result[dimension] = value
    return result


# --------------------------------------------------------------------------
# 各资产 → Markdown 段落
# --------------------------------------------------------------------------

def render_narration(n: dict) -> str:
    if not n:
        return "（无叙述层数据）"
    lines = [f"- 视角：{n.get('pov', '未知')}"]
    if n.get("pov_switch_rule"):
        lines.append(f"- 视角切换：{n['pov_switch_rule']}")
    if n.get("tense_feel"):
        lines.append(f"- 叙述距离：{n['tense_feel']}")
    sr = n.get("sentence_rhythm") or {}
    if sr.get("burst_pattern"):
        lines.append(f"- 短句爆发场景：{sr['burst_pattern']}")
    para = n.get("paragraph") or {}
    if para.get("usage_of_single_line"):
        lines.append(f"- 单句成段用法：{para['usage_of_single_line']}")
    return "\n".join(lines)


def _vt_to_str(item) -> str:
    """verbal_tics 元素可能是字符串或 dict（{情境,规则}），统一转字符串。"""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        ctx = item.get("情境") or item.get("context") or item.get("场景") or ""
        rule = item.get("规则") or item.get("rule") or ""
        if ctx and rule:
            return f"{ctx}：{rule}"
        return ctx or rule or str(item)
    return str(item)


def render_voices(voices: list) -> str:
    if not voices:
        return "（无声线数据）"
    parts = []
    for v in voices:
        ss = v.get("speech_signature") or {}
        name = v.get("name", "?")
        role = v.get("role", "")
        lines = [f"### {name}（{role}）"]
        if ss.get("avg_utterance_length"):
            lines.append(f"- 单次发言平均 {ss['avg_utterance_length']} 字")
        if ss.get("verbal_tics"):
            lines.append(f"- 口头禅/语气词：{'、'.join(_vt_to_str(t) for t in ss['verbal_tics'])}")
        if ss.get("refusal_pattern"):
            lines.append(f"- 拒绝方式：{ss['refusal_pattern']}")
        if ss.get("anger_pattern"):
            lines.append(f"- 生气时：{ss['anger_pattern']}")
        if ss.get("physical_habit"):
            lines.append(f"- 说话小动作：{'、'.join(ss['physical_habit'])}")
        if ss.get("never_says"):
            lines.append(f"- 【绝不会说】：{'、'.join(ss['never_says'])}")
        arc = v.get("arc") or {}
        if arc.get("arc_type"):
            lines.append(f"- 弧光：{arc['arc_type']}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def render_emotion(e: dict) -> str:
    if not e:
        return "（无情绪写法数据）"
    lines = [f"- 情绪写法模式：{e.get('mode', '未知')}"]
    if e.get("body_reaction_vocabulary"):
        lines.append(f"- 身体反应词库：{'、'.join(e['body_reaction_vocabulary'])}")
    for ex in e.get("examples") or []:
        if ex.get("pattern"):
            lines.append(f"- 情绪「{ex.get('emotion', '通用')}」写法：{ex['pattern']}")
        if ex.get("anti_pattern"):
            lines.append(f"  ✗ 反例（不要这样写）：{ex['anti_pattern']}")
    return "\n".join(lines)


def render_imagery(img: dict) -> str:
    if not img:
        return "（无意象数据）"
    lines = []
    if img.get("high_freq_metaphor_domains"):
        lines.append(f"- 比喻取材领域：{'、'.join(img['high_freq_metaphor_domains'])}")
    sp = img.get("sensory_preference") or {}
    if sp:
        order = sorted(sp.items(), key=lambda x: -x[1]) if any(isinstance(v, (int, float)) for v in sp.values()) else list(sp.items())
        lines.append("- 感官偏重：" + "、".join(f"{k}({v})" for k, v in order[:3]))
    return "\n".join(lines)


def render_banned(b: dict) -> str:
    if not b:
        return "（无禁忌数据）"
    lines = []
    if b.get("never_used_words"):
        lines.append(f"- 全文避免使用：{'、'.join(b['never_used_words'])}")
    if b.get("avoided_structures"):
        lines.append(f"- 回避句式：{'、'.join(b['avoided_structures'])}")
    return "\n".join(lines)


def render_structure_obs(so: dict) -> str:
    """结构观测：章节功能 / 钩子骨架 / 伏笔规律（如果存在）。"""
    if not so:
        return "（无结构观测）"
    parts = []
    ca = so.get("chapter_analyses")
    if isinstance(ca, list) and ca:
        # 章节功能分布
        roles = {}
        for c in ca:
            r = c.get("role") or c.get("章节功能") or "?"
            roles[r] = roles.get(r, 0) + 1
        if roles:
            parts.append("### 章节功能分布")
            parts.append("、".join(f"{k}×{v}" for k, v in sorted(roles.items(), key=lambda x: -x[1])))
        # 前 3 个钩子骨架
        hooks = [c.get("hook") for c in ca if c.get("hook")]
        if hooks:
            parts.append("### 钩子骨架（抽象模板）")
            for h in hooks[:3]:
                if isinstance(h, dict) and h.get("skeleton"):
                    parts.append(f"- [{h.get('type', '?')}] {h['skeleton']}")
    agg = so.get("aggregate")
    if isinstance(agg, dict):
        if agg.get("hook_type_freq"):
            parts.append("### 钩子频次")
            parts.append(json.dumps(agg["hook_type_freq"], ensure_ascii=False))
        if agg.get("foreshadow_avg_span"):
            parts.append(f"- 伏笔平均跨度：{agg['foreshadow_avg_span']} 章")
    return "\n\n".join(parts)


def render_genre_pack(gp: dict) -> str:
    """题材包（genre-pack）：题材级铁律/禁忌/结构/商业规则，注入写作 prompt。"""
    if not gp:
        return "（无题材包）"
    parts = []

    # 1. 语言铁律（最高优先级）
    lr = gp.get("language_rules") or {}
    iron = lr.get("iron_rules")
    if isinstance(iron, list) and iron:
        parts.append("### 题材铁律（违反即题材崩塌）")
        for r in iron:
            line = f"- {r.get('rule', '')}"
            if r.get("bad_example"):
                line += f"（✗ {r['bad_example']}）"
            if r.get("good_example"):
                line += f"（✓ {r['good_example']}）"
            parts.append(line)

    # 2. 语言规则：必须要素 / 禁止要素 / 疲劳词
    if lr.get("required_elements"):
        parts.append("### 每章必需要素")
        parts.append("、".join(f"□ {x}" for x in lr["required_elements"]))
    if lr.get("forbidden_elements"):
        parts.append("### 章节禁止要素")
        parts.append("、".join(f"✗ {x}" for x in lr["forbidden_elements"]))
    if lr.get("banned_phrases"):
        parts.append("### 题材禁忌词（全文禁用）")
        parts.append("、".join(lr["banned_phrases"]))
    fw = lr.get("fatigue_words")
    if isinstance(fw, list) and fw:
        parts.append("### 疲劳词限额（全章出现次数上限）")
        parts.append("、".join(f"{x.get('word','?')}≤{x.get('max_per_chapter','?')}次" for x in fw))

    # 3. 结构：章节角色分布 + 钩子 + 伏笔
    st = gp.get("structure") or {}
    roles = st.get("chapter_roles")
    if isinstance(roles, list) and roles:
        parts.append("### 章节结构模板（各段职责与占比）")
        for r in roles:
            beats = "、".join(r.get("beats") or [])
            parts.append(f"- {r.get('role','?')}（占比 {r.get('ratio','?')}，{r.get('typical_position','?')}）：{beats}")
    hs = st.get("hook_system") or {}
    hts = hs.get("hook_types")
    if isinstance(hts, list) and hts:
        parts.append("### 钩子系统（章末钩子按此选型）")
        for t in hts:
            parts.append(f"- {t.get('type','?')}（频率 {t.get('frequency','?')}）：{t.get('skeleton','')}")
        if hs.get("anti_repetition_rule"):
            parts.append(f"- 防重复：{hs['anti_repetition_rule']}")
    fp = st.get("foreshadow_pattern") or {}
    if fp:
        parts.append(f"- 伏笔节奏：平均 {fp.get('avg_span','?')} 章回收，同时开放 {fp.get('concurrent_open','?')} 条，埋法：{'、'.join(fp.get('plant_technique') or [])}")

    # 4. 商业：爽点类型 + 卡点 + 更新节奏
    co = gp.get("commercial") or {}
    pts = (co.get("payoff_density") or {}).get("payoff_types")
    if isinstance(pts, list) and pts:
        parts.append("### 爽点类型（按占比选型铺垫）")
        for t in pts[:5]:
            if isinstance(t, dict) and t.get("type"):
                parts.append(f"- {t['type']}（占比 {t.get('ratio','?')}，铺垫 {t.get('buildup_length','?')} 字）：{t.get('skeleton','')}")
    pw = co.get("paywall") or {}
    if pw:
        parts.append(f"- 付费卡点规划：第 {pw.get('position_chapter','?')} 章，卡点手法：{pw.get('cliffhanger_technique','')}")
    if co.get("update_rhythm"):
        parts.append(f"- 更新节奏：{json.dumps(co['update_rhythm'], ensure_ascii=False)}")

    # 5. 世界观惯例
    wc = gp.get("world_conventions") or {}
    if wc:
        parts.append("### 世界观惯例")
        if wc.get("power_system_type"):
            parts.append(f"- 力量体系：{wc['power_system_type']}")
        if wc.get("naming_conventions"):
            parts.append(f"- 命名惯例：{'、'.join(wc['naming_conventions'])}")

    return "\n\n".join(parts)


def render_craft_card(cc: dict) -> str:
    """写作技法卡（craft-card）：8 维技法 → 可执行写作指导。"""
    if not cc:
        return ""
    ca = cc.get("craft_analysis") or {}
    summary = cc.get("craft_summary") or {}
    parts = []

    # TOP3 最强技法
    top = summary.get("top_3_strengths") or []
    if top:
        parts.append("### 最强技法（写作时优先运用）")
        for t in top:
            parts.append(f"- {t}")

    # 各维度技法（只输出有内容的维度）
    dim_labels = {
        "foreshadowing": "伏笔技法",
        "information_release": "信息释放",
        "pov_control": "视角控制",
        "scene_transition": "场景转换",
        "tension_building": "张力构建",
        "dialogue_craft": "对话技法",
        "rhythm_control": "节奏控制",
        "sensory_craft": "感官运用",
        "narrative_engine": "叙事引擎",
        "emotional_algorithm": "情感算法",
    }
    for dim_key, dim_label in dim_labels.items():
        dim_data = ca.get(dim_key) or {}
        techs = dim_data.get("techniques") or []
        if not techs:
            continue
        parts.append(f"### {dim_label}")
        for t in techs[:3]:
            name = t.get("name", "")
            skeleton = t.get("skeleton", "")
            anti = t.get("anti_pattern", "")
            line = f"- {name}"
            if skeleton:
                line += f"：{skeleton[:80]}"
            if anti:
                line += f"（✗ 反例：{anti[:60]}）"
            parts.append(line)

    # 可复用模式
    reusable = summary.get("reusable_patterns") or []
    if reusable:
        parts.append("### 最值得复用的写作模式")
        for r in reusable:
            parts.append(f"- {r}")

    return "\n\n".join(parts) if parts else ""


def render_commercial_obs(co: dict) -> str:
    """商业观测：爽点密度 / 前3章拆解 / 卡点（如果存在）。"""
    if not co:
        return "（无商业观测）"
    parts = []
    pd = co.get("payoff_density")
    if isinstance(pd, dict):
        if pd.get("per_thousand_words"):
            parts.append(f"- 爽点密度：每千字 {pd['per_thousand_words']}")
        if pd.get("dry_spell_tolerance"):
            parts.append(f"- 连续无爽点容忍上限：{pd['dry_spell_tolerance']} 章")
        pts = pd.get("payoff_types")
        if isinstance(pts, list):
            parts.append("### 爽点类型")
            for t in pts[:5]:
                if isinstance(t, dict) and t.get("type"):
                    parts.append(f"- {t['type']}（占比 {t.get('ratio', '?')}）铺垫 {t.get('buildup_length', '?')} 字")
    oa = co.get("opening_analysis")
    if isinstance(oa, dict):
        c1 = oa.get("chapter_1")
        if isinstance(c1, dict):
            if c1.get("first_300_words_task"):
                parts.append(f"- 开篇300字任务：{c1['first_300_words_task']}")
            if c1.get("hook_position"):
                parts.append(f"- 首个钩子位置：第 {c1['hook_position']} 字")
    return "\n".join(parts)


# --------------------------------------------------------------------------

def build_prompt(voice: dict, structure: dict | None, commercial: dict | None, genre_pack: dict | None = None, craft_card: dict | None = None, distilled: dict | None = None, context_intent: str | None = None) -> str:
    meta = voice.get("meta") or {}
    source = meta.get("source_title", "未知")

    sections = []
    sections.append(f"""# 写作风格注入 · 来自《{source}》的拆书资产

你正在续写/创作一部与该对标作品同风格的小说。以下资产是从《{source}》拆解出的可执行写作规则。
**每条规则都要执行，反向禁令（✗/绝不）是硬边界，违反即失分。**
""")

    gp = render_genre_pack(genre_pack or {})
    if gp and gp != "（无题材包）":
        sections.append("## 〇、题材规则（genre-pack · 最高优先级）\n\n" + gp)

    # 蒸馏规则段：插在 genre-pack 段之后、叙述层之前（§0 注入点定位）。
    ds = render_distilled(distilled)
    if ds:
        sections.append(ds)

    # 二期 · 针对性注入段：context_intent 非空时，在蒸馏段后追加检索命中。
    # 未传 context_intent（默认 None）时完全跳过，保证与一期字节级一致。
    if context_intent:
        # genre 来源：入参 distilled.meta.genre 优先，其次 voice.meta.genre。
        resolved_genre = None
        if isinstance(distilled, dict):
            dm = distilled.get("meta") or {}
            resolved_genre = dm.get("genre")
            if not resolved_genre:
                for value in distilled.values():
                    if isinstance(value, dict):
                        m = value.get("meta") or {}
                        if m.get("genre"):
                            resolved_genre = m["genre"]
                            break
        if not resolved_genre:
            resolved_genre = meta.get("genre")
        hits = retrieve_for_intent(
            context_intent, distilled=distilled, genre=resolved_genre
        )
        if hits:
            sections.append(render_retrieval(hits))

    sections.append("## 一、叙述层（narration）\n\n" + render_narration(voice.get("narration") or {}))
    sections.append("## 二、角色声线（dialogue.character_voices）\n\n" + render_voices((voice.get("dialogue") or {}).get("character_voices") or []))
    sections.append("## 三、情绪写法（emotion_handling）\n\n" + render_emotion(voice.get("emotion_handling") or {}))
    sections.append("## 四、意象与感官（imagery）\n\n" + render_imagery(voice.get("imagery") or {}))

    so = render_structure_obs(structure or {})
    if so and so != "（无结构观测）":  # 空输入返回占位串，不能注入（2026-09-01 修复）
        sections.append("## 五、结构规律（structure-obs）\n\n" + so)
    co = render_commercial_obs(commercial or {})
    if co and co != "（无商业观测）":  # 同上
        sections.append("## 六、商业节奏（commercial-obs）\n\n" + co)

    cc = render_craft_card(craft_card or {})
    if cc:
        sections.append("## 七、写作技法（craft-card · 可执行的写作技巧）\n\n" + cc)

    sections.append("## 八、禁忌（banned）\n\n" + render_banned(voice.get("banned") or {}))
    sections.append("""
## 九、写作执行清单（硬性要求，逐条自查）

1. **视角固定**：严格遵守「叙述层」的视角设定，不随意切换。
2. **角色开口即人（最重要）**：每个出场角色必须使用声线卡里的【口头禅/昵称/称呼方式】至少 2 种。
   例如声线卡写了「自称老子」就必须让角色说「老子」；写了「叫对方唐小雨」就必须出现这个昵称；
   写了「拒绝方式先反问」就必须在拒绝场景用反问句。做不到宁可不写该场景。
3. **情绪外化**：每章至少 3 处「体感式」生理反应描写（心跳/指尖/耳根/脊背/手心等身体词），
   禁止直陈式偷懒（如「他很愤怒」「她很难过」这类直接情绪词）。
4. **比喻取材**：比喻必须从「意象」一节给出的取材领域里选（如动物、日常物件），
   禁止凭空发明与资产无关的宏大比喻（刀剑/星辰/宫殿类）。
5. **钩子收尾**：每章末尾按「钩子骨架」造一个钩子（悬念/打断/反转），不写流水账结尾。
6. **检查禁忌**：成稿前自查「禁忌」清单，命中的词/句式一律替换。
7. **对话占比**：网文强节奏，对话应占正文 25% 以上，避免大段叙述。
8. **技法运用**：如有「写作技法」一节，优先运用最强技法（TOP3），每个维度至少用 1 个技法。
9. **自查评分**：写完后对照「二、角色声线」逐角色核对——每个出场角色的声线特征词是否真的用上了。
""")

    return "\n\n---\n\n".join(sections)


def main():
    ap = argparse.ArgumentParser(description="资产注入器：voice-card → 写作 system prompt")
    ap.add_argument("voice", help="voice-card JSON 路径")
    ap.add_argument("--structure", help="structure-obs JSON（可选）")
    ap.add_argument("--commercial", help="commercial-obs JSON（可选）")
    ap.add_argument("--genre-pack", help="题材包 JSON（可选，注入题材级规则）")
    ap.add_argument("--craft-card", help="craft-card JSON（可选，注入写作技法）")
    ap.add_argument("--distilled", help="蒸馏规则 JSON（可选，注入跨书聚合规则）")
    ap.add_argument("--out", help="输出路径，默认 prompts/generated/<名>-writing-prompt.md")
    args = ap.parse_args()

    voice = json.loads(Path(args.voice).read_text(encoding="utf-8"))
    structure = json.loads(Path(args.structure).read_text(encoding="utf-8")) if args.structure else None
    commercial = json.loads(Path(args.commercial).read_text(encoding="utf-8")) if args.commercial else None
    genre_pack = json.loads(Path(args.genre_pack).read_text(encoding="utf-8")) if args.genre_pack else None
    craft_card = json.loads(Path(args.craft_card).read_text(encoding="utf-8")) if args.craft_card else None
    distilled = json.loads(Path(args.distilled).read_text(encoding="utf-8")) if args.distilled else None

    prompt = build_prompt(voice, structure, commercial, genre_pack, craft_card, distilled)

    name = Path(args.voice).stem.replace("-voice-card", "")
    out = Path(args.out) if args.out else PROMPTS_DIR / f"{name}-writing-prompt.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(prompt, encoding="utf-8")

    print(f"✓ 注入完成: {out}")
    print(f"  prompt 长度: {len(prompt)} 字符")
    print(f"  genre-pack: {'已注入' if genre_pack else '未注入'}")
    print(f"  craft-card: {'已注入' if craft_card else '未注入'}")
    print(f"  distilled: {'已注入' if distilled else '未注入'}")
    print(f"  （直接作为 system 消息喂给写作 LLM）")


if __name__ == "__main__":
    main()
