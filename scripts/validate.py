#!/usr/bin/env python3
"""
Schema 校验脚本 — 纯标准库，零依赖

校验 LLM 拆书输出是否符合六份 schema 的关键约束。
不符合的输出直接拒绝入库（exit code 1），WARN 级别仅提示（exit code 2）。

用法:
  python validate.py <asset.json> [--kind voice-card|genre-pack|trope-library|craft-card|structure-obs|commercial-obs]

--kind 缺省时按文件内容自动推断。
"""
import argparse
import json
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# 通用约束：enum / 范围 / 必填 / 类型
# --------------------------------------------------------------------------

ROLE_ENUM = {"主角", "女主", "反派", "导师", "配角", "工具人"}
ARC_ENUM = {"正向成长", "负向堕落", "平坦型", "先扬后抑", "先抑后扬"}
EMOTION_MODE_ENUM = {"直陈式", "体感式", "动作外化式", "环境投射式", "混合式"}
POV_ENUM = {"第一人称", "第三人称限知", "第三人称全知", "多视角轮换"}
HOOK_ENUM = {"悬念揭示", "危机降临", "身份反转", "实力展示", "情感冲击", "信息断点", "对手登场", "误会升级", "甜蜜瞬间", "暧昧拉扯"}
PAYOFF_ENUM = {"打脸", "升级", "收益兑现", "身份揭露", "他人认可", "情感回应", "反杀"}
CHAPTER_ROLE_ENUM = {"铺垫", "推进", "转折", "爆发", "缓冲", "过渡", "甜蜜", "拉扯", "告白"}
ABSTRACTION_ENUM = {"structural", "scenic", "verbal"}
LANG_SUBTYPE_ENUM = {"直白", "偶有潜台词", "大量潜台词"}

# 题材白名单：craft-card / voice-card 的 meta.genre 必须 ∈ 此集合。
# 后续扩展题材包时在此追加（铁律一）。
KNOWN_GENRES = {"campus-redemption"}

ERRORS = []   # 硬错误：拒绝入库
WARNS = []    # 警告：可入库但需复核


def reset():
    """清空错误/警告列表。每次独立校验前必须调用，防止跨资产累积。"""
    global ERRORS, WARNS
    ERRORS = []
    WARNS = []


def err(msg, path=""):
    ERRORS.append(f"  ✗ {path} {msg}")


def warn(msg, path=""):
    WARNS.append(f"  ⚠ {path} {msg}")


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_enum(v, allowed, path):
    if v not in allowed:
        err(f"值 '{v}' 不在允许集合 {sorted(allowed)}", path)


def check_bool(v, path):
    if not isinstance(v, bool):
        err(f"应为布尔值，实际 {type(v).__name__}", path)


def check_probability(v, path):
    if not is_num(v) or not (0 <= v <= 1):
        err(f"应为 0-1 之间的数字，实际 {v!r}", path)


def check_strength(v, path):
    if not is_num(v) or not (1 <= v <= 10):
        err(f"强度应为 1-10 整数，实际 {v!r}", path)


def check_obj(v, path):
    if not isinstance(v, dict):
        err(f"应为对象，实际 {type(v).__name__}", path)
        return False
    return True


def check_list(v, path, min_items=0):
    if not isinstance(v, list):
        err(f"应为数组，实际 {type(v).__name__}", path)
        return False
    if min_items and len(v) < min_items:
        err(f"数组至少 {min_items} 项，实际 {len(v)} 项", path)
    return True


def check_str(v, path, min_len=0, max_len=None):
    if not isinstance(v, str):
        err(f"应为字符串，实际 {type(v).__name__}", path)
        return False
    if min_len and len(v) < min_len:
        err(f"字符串过短（<{min_len}），实际 {len(v)}", path)
    if max_len and len(v) > max_len:
        warn(f"字符串过长（>{max_len}），可能夹带原文，需复核", path)
    return True


# --------------------------------------------------------------------------
# voice-card 校验
# --------------------------------------------------------------------------

def validate_voice_card(d):
    reset()
    if not check_obj(d, "voice-card"):
        return
    required = ["meta", "narration", "dialogue", "emotion_handling", "banned"]
    for k in required:
        if k not in d:
            err(f"缺少必填字段 '{k}'", "voice-card")

    meta = d.get("meta")
    if check_obj(meta, "meta"):
        for k in ("source_title", "genre", "extracted_at", "sample_chapters", "confidence"):
            if k not in meta:
                err(f"缺少必填字段 '{k}'", "meta")
        check_probability(meta.get("confidence"), "meta.confidence")
        check_str(meta.get("genre", ""), "meta.genre", min_len=2)
        if "human_reviewed" in meta:
            check_bool(meta["human_reviewed"], "meta.human_reviewed")
        sc = meta.get("sample_chapters")
        if check_list(sc, "meta.sample_chapters", min_items=3):
            for x in sc:
                if not is_num(x):
                    err("样本章节号应为数字", "meta.sample_chapters[]")

    narr = d.get("narration")
    if check_obj(narr, "narration"):
        check_enum(narr.get("pov"), POV_ENUM, "narration.pov")
        sr = narr.get("sentence_rhythm")
        if check_obj(sr, "narration.sentence_rhythm"):
            for f in ("avg_length", "short_ratio", "long_ratio"):
                if f in sr and not is_num(sr[f]):
                    err(f"应为数字，实际 {sr[f]!r}", f"narration.sentence_rhythm.{f}")
            if not isinstance(sr.get("burst_pattern", ""), str) or len(sr.get("burst_pattern", "")) < 4:
                warn("burst_pattern 缺失或过短——这是最能指导写作的字段", "narration.sentence_rhythm.burst_pattern")
        para = narr.get("paragraph")
        if check_obj(para, "narration.paragraph"):
            for f in ("avg_lines", "single_line_para_ratio"):
                if f in para and not is_num(para[f]):
                    err(f"应为数字", f"narration.paragraph.{f}")

    dlg = d.get("dialogue")
    if check_obj(dlg, "dialogue"):
        dr = dlg.get("dialogue_ratio")
        if dr is not None:
            check_probability(dr, "dialogue.dialogue_ratio")
        if "subtext_level" in dlg:
            check_enum(dlg["subtext_level"], LANG_SUBTYPE_ENUM, "dialogue.subtext_level")
        voices = dlg.get("character_voices")
        if check_list(voices, "dialogue.character_voices"):
            if len(voices) == 0:
                warn("character_voices 为空——至少应提取出主角声线", "dialogue.character_voices")
            for i, v in enumerate(voices):
                p = f"dialogue.character_voices[{i}]"
                if not check_obj(v, p):
                    continue
                if "name" not in v or not v.get("name"):
                    err("角色缺少 name", p)
                check_enum(v.get("role"), ROLE_ENUM, p + ".role")
                ss = v.get("speech_signature")
                if check_obj(ss, p + ".speech_signature"):
                    if "refusal_pattern" not in ss:
                        warn("缺 refusal_pattern（拒绝方式）——区分角色的最有效维度", p + ".speech_signature")
                    if "never_says" not in ss:
                        warn("缺 never_says 反向清单", p + ".speech_signature")
                    nv = ss.get("never_says")
                    # never_says 为空时降级为 WARN（新 pass2 格式可能不输出此字段）
                    if not nv:
                        warn("缺 never_says 反向清单——建议补充以防止角色串味", p + ".speech_signature")
                    elif isinstance(nv, list):
                        for w_ in nv:
                            if not isinstance(w_, str) or not w_.strip():
                                err("never_says 条目应为非空字符串", p + ".speech_signature.never_says[]")

    eh = d.get("emotion_handling")
    if check_obj(eh, "emotion_handling"):
        if "mode" not in eh:
            err("缺少 emotion_handling.mode——权重最高的字段", "emotion_handling")
        else:
            check_enum(eh["mode"], EMOTION_MODE_ENUM, "emotion_handling.mode")
        ex = eh.get("examples")
        if not ex:
            warn("emotion_handling.examples 为空——建议补充情绪写法示例", "emotion_handling")
        elif isinstance(ex, list):
            for i, e in enumerate(ex):
                p = f"emotion_handling.examples[{i}]"
                if not check_obj(e, p):
                    continue
                check_str(e.get("pattern", ""), p + ".pattern", min_len=4)
                if not e.get("anti_pattern"):
                    warn("缺 anti_pattern（反例）", p)

    b = d.get("banned")
    if check_obj(b, "banned"):
        nw = b.get("never_used_words")
        if not isinstance(nw, list):
            err("never_used_words 应为数组", "banned.never_used_words")
        elif nw:
            for w_ in nw:
                if not isinstance(w_, str) or not w_.strip():
                    err("never_used_words 条目应为非空字符串", "banned.never_used_words[]")
        else:
            # 直陈式/口语化文风可能确实没有回避词——这是特征不是缺陷，降级为警告
            mode = (d.get("emotion_handling") or {}).get("mode", "")
            if mode == "直陈式":
                warn("直陈式文风无回避词表——可能是文风特征，建议人工确认", "banned.never_used_words")
            else:
                warn("never_used_words 为空——建议补充反向清单", "banned.never_used_words")

    # --- imagery 校验（Phase 1.3 新增）---
    img = d.get("imagery")
    if check_obj(img, "imagery"):
        hfm = img.get("high_freq_metaphor_domains")
        if not isinstance(hfm, list) or len(hfm) == 0:
            warn("high_freq_metaphor_domains 为空——比喻取材领域是意象维度核心，应至少填2项", "imagery")
        elif len(hfm) < 2:
            warn(f"high_freq_metaphor_domains 仅{len(hfm)}项，建议至少2项", "imagery")
        else:
            # 检查是否被自然语言污染（非短词列表）
            for i, domain in enumerate(hfm):
                if not isinstance(domain, str):
                    err(f"比喻领域应为字符串，实际 {type(domain).__name__}", f"imagery.high_freq_metaphor_domains[{i}]")
                elif len(domain) > 10:
                    warn(f"比喻领域 '{domain[:15]}...' 过长（{len(domain)}字），应为简短标签（≤6字）", f"imagery.high_freq_metaphor_domains[{i}]")
        sp = img.get("sensory_preference")
        if isinstance(sp, dict) and sp:
            total = sum(v for v in sp.values() if isinstance(v, (int, float)))
            if abs(total - 1.0) > 0.15:
                warn(f"sensory_preference 各项和={total:.2f}，应接近1.0", "imagery.sensory_preference")
        elif sp == {} or sp is None:
            warn("sensory_preference 为空——五感偏好是文风指纹的重要维度", "imagery")
        sd = img.get("signature_devices")
        if not isinstance(sd, list) or len(sd) == 0:
            warn("signature_devices 为空——至少应填1个标志性修辞手法", "imagery")
    elif img is None:
        warn("缺少 imagery 字段——意象系统是文风分析的必要维度", "voice-card")

    prov = d.get("provenance")
    if check_obj(prov, "provenance"):
        if prov.get("contains_verbatim") is True:
            err("provenance.contains_verbatim 必须恒为 false", "provenance.contains_verbatim")
        elif "contains_verbatim" not in prov:
            warn("建议显式声明 provenance.contains_verbatim=false", "provenance")


# --------------------------------------------------------------------------
# genre-pack 校验
# --------------------------------------------------------------------------

def validate_genre_pack(d):
    reset()
    if not check_obj(d, "genre-pack"):
        return
    for k in ("meta", "structure", "commercial", "language_rules"):
        if k not in d:
            err(f"缺少必填字段 '{k}'", "genre-pack")

    meta = d.get("meta")
    if check_obj(meta, "meta"):
        for k in ("id", "name", "source_books"):
            if k not in meta:
                err(f"缺少必填字段 '{k}'", "meta")
        check_probability(meta.get("confidence"), "meta.confidence")
        sb = meta.get("source_books")
        if check_list(sb, "meta.source_books"):
            if len(sb) < 3:
                warn(f"题材包应由 ≥3 本聚合，当前 {len(sb)} 本", "meta.source_books")

    # --- structure 校验（遗留优化：接入 HOOK_ENUM / CHAPTER_ROLE_ENUM）---
    st = d.get("structure")
    if check_obj(st, "structure"):
        # chapter_roles[]：对象数组，每个元素含 role 字段。
        cr = st.get("chapter_roles")
        if check_list(cr, "structure.chapter_roles"):
            for i, role_obj in enumerate(cr):
                p = f"structure.chapter_roles[{i}]"
                if not check_obj(role_obj, p):
                    continue
                check_enum(role_obj.get("role"), CHAPTER_ROLE_ENUM, p + ".role")
        # hook_system：先查对象，再查 hook_types 列表，逐个校验 type。
        hs = st.get("hook_system")
        if check_obj(hs, "structure.hook_system"):
            ht = hs.get("hook_types")
            if check_list(ht, "structure.hook_system.hook_types"):
                for i, hook in enumerate(ht):
                    p = f"structure.hook_system.hook_types[{i}]"
                    if not check_obj(hook, p):
                        continue
                    check_enum(hook.get("type"), HOOK_ENUM, p + ".type")

    com = d.get("commercial")
    if check_obj(com, "commercial"):
        if "payoff_density" not in com:
            err("缺少 commercial.payoff_density", "commercial")
        pd = com.get("payoff_density")
        if check_obj(pd, "commercial.payoff_density"):
            pv = pd.get("per_thousand_words")
            if pv is not None and (not is_num(pv) or pv < 0):
                err("per_thousand_words 应为非负数字", "commercial.payoff_density.per_thousand_words")
            pts = pd.get("payoff_types")
            if check_list(pts, "commercial.payoff_density.payoff_types", min_items=1):
                for i, t in enumerate(pts):
                    p = f"commercial.payoff_density.payoff_types[{i}]"
                    if not check_obj(t, p):
                        continue
                    check_enum(t.get("type"), PAYOFF_ENUM, p + ".type")
                    bl = t.get("buildup_length")
                    if bl is None or not is_num(bl) or bl <= 0:
                        err("buildup_length 必须给具体数字（铺垫字数）", p + ".buildup_length")
                    if not t.get("skeleton"):
                        warn("缺 skeleton 执行骨架", p)
        oa = com.get("opening_analysis")
        if check_obj(oa, "commercial.opening_analysis"):
            c1 = oa.get("chapter_1")
            if check_obj(c1, "commercial.opening_analysis.chapter_1"):
                hp = c1.get("hook_position")
                if hp is not None and not is_num(hp):
                    err("hook_position 应为数字（第几字）", "commercial.opening_analysis.chapter_1.hook_position")
                if not c1.get("first_300_words_task"):
                    warn("缺 first_300_words_task", "commercial.opening_analysis.chapter_1")

    lr = d.get("language_rules")
    if check_obj(lr, "language_rules"):
        ir = lr.get("iron_rules")
        if check_list(ir, "language_rules.iron_rules", min_items=1):
            for i, r_ in enumerate(ir):
                p = f"language_rules.iron_rules[{i}]"
                if not check_obj(r_, p):
                    continue
                for k in ("rule", "bad_example", "good_example"):
                    if not r_.get(k):
                        err(f"缺少 '{k}'", p)


# --------------------------------------------------------------------------
# trope-library 校验
# --------------------------------------------------------------------------

def validate_trope_library(d):
    reset()
    if not check_obj(d, "trope-library"):
        return
    tropes = d.get("tropes")
    if not check_list(tropes, "tropes", min_items=1):
        return
    for i, t in enumerate(tropes):
        p = f"tropes[{i}]"
        if not check_obj(t, p):
            continue
        check_enum(t.get("abstraction_level"), ABSTRACTION_ENUM, p + ".abstraction_level")
        if t.get("abstraction_level") == "verbal":
            err("verbal 级别一律拒收（版权红线）", p + ".abstraction_level")
        if t.get("contains_verbatim") is True:
            err("contains_verbatim=true 一律拒收", p + ".contains_verbatim")
        sk = t.get("skeleton")
        if check_obj(sk, p + ".skeleton"):
            for k in ("setup", "escalation", "payoff", "aftermath"):
                if k not in sk:
                    warn(f"缺 skeleton.{k}", p)
        if t.get("abstraction_level") in ("structural", "scenic") and not t.get("parameters"):
            warn("缺少 parameters（可调参数）", p)
        eff = t.get("effectiveness")
        if check_obj(eff, p + ".effectiveness"):
            s = eff.get("payoff_strength")
            if s is not None:
                check_strength(s, p + ".effectiveness.payoff_strength")
        # === 新增：genre_scope 校验（铁律一）===
        gs = t.get("genre_scope")
        if gs is None:
            err("缺少 genre_scope 字段", p + ".genre_scope")   # 硬错误：题材作用域必须标注
        elif gs not in ("universal", *KNOWN_GENRES):
            err(f"genre_scope='{gs}' 非法，须 ∈ {{'universal', *sorted(KNOWN_GENRES)}}", p + ".genre_scope")


# --------------------------------------------------------------------------
# craft-card 校验
# --------------------------------------------------------------------------

def validate_craft_card(d):
    reset()
    if not check_obj(d, "craft-card"):
        return
    for k in ("meta", "craft_analysis", "craft_summary"):
        if k not in d:
            err(f"缺少必填字段 '{k}'", "craft-card")

    meta = d.get("meta")
    if check_obj(meta, "meta"):
        for k in ("source_title", "genre", "extracted_at", "sample_chapters", "confidence"):
            if k not in meta:
                err(f"缺少必填字段 '{k}'", "meta")
        check_probability(meta.get("confidence"), "meta.confidence")
        # === 新增：genre 枚举校验（铁律一）===
        genre = meta.get("genre", "")
        if not genre:
            err("meta.genre 为空，题材未标注", "meta.genre")   # 硬错误
        elif genre not in KNOWN_GENRES:
            warn(f"meta.genre='{genre}' 不在已知题材白名单 {sorted(KNOWN_GENRES)}，"
                 f"请确认题材包是否已登记", "meta.genre")        # 警告（不阻断拆书，但阻断聚合）

    analysis = d.get("craft_analysis")
    if check_obj(analysis, "craft_analysis"):
        required_dims = ["foreshadowing", "information_release", "pov_control",
                         "scene_transition", "tension_building", "dialogue_craft",
                         "rhythm_control", "sensory_craft", "narrative_engine", "emotional_algorithm"]
        # 检查维度覆盖（至少 3/8 维有内容）
        covered_dims = sum(1 for dim in required_dims if dim in analysis and isinstance(analysis[dim], dict) and analysis[dim].get("techniques"))
        if covered_dims < 3:
            warn(f"仅 {covered_dims}/8 维有技法——建议重跑 Pass5 提升覆盖度", "craft_analysis")

    summary = d.get("craft_summary")
    if check_obj(summary, "craft_summary"):
        for k in ("top_3_strengths", "unique_techniques", "reusable_patterns"):
            v = summary.get(k)
            if not isinstance(v, list) or len(v) == 0:
                warn(f"craft_summary.{k} 为空", "craft_summary")

    prov = d.get("provenance")
    if check_obj(prov, "provenance"):
        if prov.get("contains_verbatim") is True:
            err("provenance.contains_verbatim 必须恒为 false", "provenance.contains_verbatim")


# --------------------------------------------------------------------------
# structure-obs 校验（2026-09-01 新增：此前无校验器，auto_kind 误判为 voice-card 导致 REJECT）
# --------------------------------------------------------------------------

def validate_structure_obs(d):
    reset()
    if not check_obj(d, "structure-obs"):
        return
    meta = d.get("meta")
    if check_obj(meta, "meta"):
        for k in ("source_title", "genre", "scope"):
            if k not in meta:
                err(f"缺少必填字段 '{k}'", "meta")

    ca = d.get("chapter_analyses")
    if check_list(ca, "chapter_analyses", min_items=1):
        for i, c in enumerate(ca):
            p = f"chapter_analyses[{i}]"
            if not check_obj(c, p):
                continue
            if "role" not in c:
                err("缺少 'role'", p)
            # qingning 等书的元素无 chapter 键（以 title 表达），缺失只警告
            for k in ("chapter", "beats", "hook", "foreshadow"):
                if k not in c:
                    warn(f"缺少 '{k}'", p)

    agg = d.get("aggregate")
    if check_obj(agg, "aggregate"):
        for k in ("hook_type_freq", "hook_min_interval", "foreshadow_avg_span",
                  "foreshadow_max_span", "foreshadow_concurrent_open"):
            if k not in agg:
                err(f"缺少必填字段 '{k}'", "aggregate")
        # climax_cycle 跨书类型不稳定（dict/list/str 均出现过），缺失只警告
        if "climax_cycle" not in agg:
            warn("缺少 'climax_cycle'", "aggregate")


# --------------------------------------------------------------------------
# commercial-obs 校验（2026-09-01 新增：正文字段跨书变体大，meta 严格+核心结构存在性）
# --------------------------------------------------------------------------

COMMERCIAL_OBS_VARIANT_FIELDS = ("skeleton", "dry_spell_tolerance", "update_rhythm",
                                 "retention_risk_points", "common_mistakes")


def validate_commercial_obs(d):
    reset()
    if not check_obj(d, "commercial-obs"):
        return
    meta = d.get("meta")
    if check_obj(meta, "meta"):
        for k in ("source_title", "genre", "scope"):
            if k not in meta:
                err(f"缺少必填字段 '{k}'", "meta")

    for k in ("payoff_density", "opening_analysis", "paywall"):
        if k not in d:
            err(f"缺少必填结构 '{k}'", "commercial-obs")
        else:
            check_obj(d.get(k), k)

    for k in COMMERCIAL_OBS_VARIANT_FIELDS:
        if k not in d:
            warn(f"缺少 '{k}'（可选变体字段）", "commercial-obs")


# --------------------------------------------------------------------------
# genre-prose-card 校验（阶段② 增量：轻量种子模板，与 genre-pack 彻底分离）
# --------------------------------------------------------------------------

def validate_genre_prose_card(d):
    """题材文风卡轻量校验（软约束种子，非 genre-pack 铁律）。

    校验点（轻量，**不套用** genre-pack 的量化硬校验）：
    * ``meta.kind == "genre-prose-card"``（硬校验，区分于 genre-pack/voice-card）
    * ``meta.id`` / ``meta.name`` / ``meta.confidence``(0-1) 存在且类型正确
    * ``meta.provenance`` 存在且 ``verified`` 为布尔（本阶段恒 false）
    * ``language_rules`` 存在（软规则，不要求 iron_rules）
    * ``prose.sections`` 存在且非空（原文兜底）
    """
    reset()
    if not check_obj(d, "genre-prose-card"):
        return

    meta = d.get("meta")
    if check_obj(meta, "meta"):
        kind = meta.get("kind")
        if kind != "genre-prose-card":
            err(f"meta.kind 应为 'genre-prose-card'，实际 {kind!r}", "meta.kind")
        for k in ("id", "name"):
            if k not in meta:
                err(f"缺少必填字段 '{k}'", "meta")
            else:
                check_str(meta.get(k, ""), f"meta.{k}", min_len=2)
        if "confidence" not in meta:
            err("缺少必填字段 'confidence'", "meta")
        else:
            check_probability(meta.get("confidence"), "meta.confidence")
        # upgrade_status 枚举（缺省视为 seed，不报错）。
        if "upgrade_status" in meta:
            check_enum(meta.get("upgrade_status"), ("seed", "upgraded"), "meta.upgrade_status")
        prov = meta.get("provenance")
        if prov is None:
            warn("建议显式声明 provenance 溯源（来源/许可证/是否验证）", "meta.provenance")
        elif check_obj(prov, "meta.provenance"):
            if "verified" in prov:
                check_bool(prov["verified"], "meta.provenance.verified")
                if prov.get("verified") is not False:
                    warn("genre-prose-card 来源自报、未经验证，provenance.verified 应恒为 false", "meta.provenance.verified")

    if "language_rules" not in d:
        err("缺少必填字段 'language_rules'", "genre-prose-card")
    else:
        lr = d.get("language_rules")
        if check_obj(lr, "language_rules"):
            fe = lr.get("forbidden_elements")
            if fe is not None and not isinstance(fe, list):
                err(f"forbidden_elements 应为数组，实际 {type(fe).__name__}", "language_rules.forbidden_elements")

    if "prose" not in d:
        err("缺少必填字段 'prose'", "genre-prose-card")
    else:
        prose = d.get("prose")
        if check_obj(prose, "prose"):
            sections = prose.get("sections")
            if not isinstance(sections, dict) or len(sections) == 0:
                err("prose.sections 应为非空对象（原文兜底）", "prose.sections")


# --------------------------------------------------------------------------

DISPATCH = {
    "voice-card": validate_voice_card,
    "genre-pack": validate_genre_pack,
    "trope-library": validate_trope_library,
    "craft-card": validate_craft_card,
    "structure-obs": validate_structure_obs,
    "commercial-obs": validate_commercial_obs,
    "genre-prose-card": validate_genre_prose_card,
}

AUTO_HINTS = {
    # craft-card 必须排在 voice-card 之前判定吗？不必——其 hint 键（craft_analysis/craft_summary）
    # 与 voice-card 的 hint 键互斥，但必须存在条目，否则落到兜底 voice-card 造成误判（历史 bug 2026-09-01）
    "craft-card": ["craft_analysis", "craft_summary"],
    "voice-card": ["character_voices", "emotion_handling"],
    "genre-pack": ["payoff_density", "opening_analysis", "iron_rules"],
    "trope-library": ["tropes", "abstraction_level"],
    # 2026-09-01 新增：此前缺条目导致 structure-obs/commercial-obs 兜底误判为 voice-card（15 硬错误 REJECT）
    "structure-obs": ["chapter_analyses", "aggregate"],
    "commercial-obs": ["payoff_density", "paywall"],
    # 阶段②：genre-prose-card 靠显式 meta.kind 判定（auto_kind 里优先检查，见下）
    "genre-prose-card": ["prose"],
}

# genre-pack 的 hint 键全部嵌套在 commercial/language_rules 里，需查子结构
GENRE_PACK_NESTED = ("commercial", "language_rules", "structure", "world_conventions")


def auto_kind(d: dict) -> str:
    # 阶段②：genre-prose-card 是显式 meta.kind 字段，须优先判断，
    # 否则会落到兜底 voice-card 造成误判（历史 bug 同款）。
    if (d.get("meta") or {}).get("kind") == "genre-prose-card":
        return "genre-prose-card"
    keys = set(d.keys())
    for kind, hints in AUTO_HINTS.items():
        if kind == "genre-pack":
            # 顶层有全部 4 个子结构键 → 判定为题材包（嵌套键不参与顶层判断）
            if all(h in keys for h in GENRE_PACK_NESTED):
                return kind
            continue
        if any(h in d for h in hints) or all(h in keys for h in hints):
            return kind
    return "voice-card"


def main():
    ap = argparse.ArgumentParser(description="校验拆书输出是否符合 schema")
    ap.add_argument("asset", help="待校验的 JSON 资产文件")
    ap.add_argument("--kind", choices=list(DISPATCH), help="资产类型，缺省自动推断")
    args = ap.parse_args()

    path = Path(args.asset)
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"JSON 解析失败: {e}")
        sys.exit(1)

    kind = args.kind or auto_kind(d)
    DISPATCH[kind](d)

    # 阶段② · 题材隔离校验：断言 meta.id 与文件名一致（防串味，共享知识约定 9）。
    # 仅对 genre-prose-card 生效；文件名约定 assets/genre-prose-card-<id>.json。
    if kind == "genre-prose-card":
        meta = d.get("meta") or {}
        card_id = meta.get("id", "")
        expected_stem = f"genre-prose-card-{card_id}"
        if card_id and path.stem != expected_stem:
            err(f"题材隔离失败：文件名 '{path.stem}' 与 meta.id '{card_id}' 不一致"
                f"（应为 '{expected_stem}'）", "meta.id")

    print(f"校验类型: {kind}  | 文件: {path.name}")
    print(f"硬错误 {len(ERRORS)} 条，警告 {len(WARNS)} 条")
    for e in ERRORS:
        print(e)
    for w in WARNS:
        print(w)

    if ERRORS:
        print("结论: REJECT（不符合 schema，禁止入库）")
        sys.exit(1)
    if WARNS:
        print("结论: WARN（可入库，建议人工复核）")
        sys.exit(2)
    print("结论: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
