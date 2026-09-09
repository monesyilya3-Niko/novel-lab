# -*- coding: utf-8 -*-
"""
novel-lab 拆书数据看板 · 数据快照生成器（纯标准库，零第三方依赖）

扫描 assets/ 与 reports/，把 4 本书 + 蒸馏层 + 题材包 + 桥段库汇总成
dashboard-data.js（全局变量 window.__NOVEL_LAB__），供 index.html 纯前端读取。

用法：在 novel-lab 根目录执行
    python dashboard/build_data.py

输出：dashboard/dashboard-data.js
"""
import json
import os
import re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
REPORTS = os.path.join(ROOT, "reports")

BOOKS = ["chireng_chosen", "qingning_chosen", "sangshi_chosen", "suyixinjian_chosen"]

BOOK_TITLES = {
    "chireng_chosen": "赤冷",
    "qingning_chosen": "清宁",
    "sangshi_chosen": "丧诗",
    "suyixinjian_chosen": "溯雨信笺",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe(v, default=None):
    return v if v is not None else default


def as_list(v):
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        return list(v.values())
    return [] if v is None else [v]


def as_str(v):
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def md_chars(path):
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return len(f.read())


def extract_voice_card(path):
    """声线卡 -> 看板可展示的精简结构"""
    d = load_json(path)
    meta = d.get("meta", {})
    out = {"confidence": safe(meta.get("confidence"), 0), "total_words": safe(meta.get("total_sample_words"), 0)}

    narration = d.get("narration", {})
    if isinstance(narration, dict):
        out["pov"] = as_str(narration.get("pov"))
        out["tense"] = as_str(narration.get("tense_feel"))
        out["rhythm"] = as_str(narration.get("sentence_rhythm"))
        out["pov_switch"] = as_str(narration.get("pov_switch_rule"))

    dialogue = d.get("dialogue", {})
    if isinstance(dialogue, dict):
        out["dialogue_ratio"] = safe(dialogue.get("dialogue_ratio"))
        out["tag_style"] = as_str(dialogue.get("tag_style"))
        out["subtext_level"] = safe(dialogue.get("subtext_level"))
        cvs = dialogue.get("character_voices")
        if isinstance(cvs, dict):
            out["characters"] = [{"name": k, "voice": as_str(v)[:120]} for k, v in cvs.items()]
        elif isinstance(cvs, list):
            out["characters"] = [as_str(v)[:120] for v in cvs]
        else:
            out["characters"] = []

    eh = d.get("emotion_handling", {})
    if isinstance(eh, dict):
        out["emotion_mode"] = as_str(eh.get("mode"))
        out["emotion_examples"] = as_list(eh.get("examples"))

    imagery = d.get("imagery", {})
    if isinstance(imagery, dict):
        out["metaphor_domains"] = as_list(imagery.get("high_freq_metaphor_domains"))
        out["sensory"] = as_str(imagery.get("sensory_preference"))
        out["signature_devices"] = as_list(imagery.get("signature_devices"))
    else:
        out["metaphor_domains"] = []
        out["sensory"] = ""
        out["signature_devices"] = []

    banned = d.get("banned", {})
    if isinstance(banned, dict):
        out["banned"] = {
            "never_used_words": as_list(banned.get("never_used_words")),
            "avoided_structures": as_list(banned.get("avoided_structures")),
            "genre_taboos": as_list(banned.get("genre_taboos")),
        }
    else:
        out["banned"] = {"never_used_words": [], "avoided_structures": [], "genre_taboos": []}

    return out


def extract_craft_card(path):
    """笔法卡 -> 10 维技法精简结构"""
    d = load_json(path)
    ca = d.get("craft_analysis", {})
    dims = []
    for dim_name, dim_val in ca.items():
        if not isinstance(dim_val, dict):
            continue
        techniques = dim_val.get("techniques", [])
        t_list = []
        for t in techniques:
            if isinstance(t, dict):
                da = t.get("deep_analysis", {})
                t_list.append({
                    "name": as_str(t.get("name")),
                    "desc": as_str(t.get("description"))[:160],
                    "effect": as_str(t.get("effect"))[:120],
                    "skeleton": as_str(t.get("skeleton")),
                    "anti": as_str(t.get("anti_pattern")),
                    "deep": {
                        k: as_str(da.get(k))[:140] for k in da if isinstance(da, dict)
                    } if isinstance(da, dict) else {},
                })
        dims.append({"dimension": dim_name, "count": len(t_list), "techniques": t_list})

    cs = d.get("craft_summary", {})
    summary = {}
    if isinstance(cs, dict):
        summary = {
            "top_3": as_list(cs.get("top_3_strengths")),
            "unique": as_list(cs.get("unique_techniques")),
            "reusable": as_list(cs.get("reusable_patterns")),
        }
    return {"dimensions": dims, "summary": summary}


def extract_structure_obs(path):
    """结构观测 -> 章节分析 + 聚合指标"""
    d = load_json(path)
    chapters = d.get("chapter_analyses", [])
    agg = d.get("aggregate", {})
    return {
        "chapter_count": len(chapters) if isinstance(chapters, list) else 0,
        "aggregate": agg if isinstance(agg, dict) else {},
        "chapters": [as_str(c)[:120] for c in as_list(chapters)][:30],
    }


def extract_commercial_obs(path):
    """商业观测 -> 付费密度/骨架/卡点/更新节奏/留存风险"""
    d = load_json(path)
    out = {}
    pd = d.get("payoff_density", {})
    if isinstance(pd, dict):
        out["payoff_per_k"] = safe(pd.get("per_thousand_words"))
        out["payoff_types"] = pd.get("payoff_types", [])
    out["skeleton"] = as_str(d.get("skeleton"))
    out["dry_spell"] = as_str(d.get("dry_spell_tolerance"))
    out["paywall"] = d.get("paywall") if isinstance(d.get("paywall"), dict) else {}
    out["update_rhythm"] = d.get("update_rhythm") if isinstance(d.get("update_rhythm"), dict) else {}
    out["retention_risks"] = d.get("retention_risk_points", [])
    out["common_mistakes"] = as_str(d.get("common_mistakes"))
    return out


def build_book(book):
    d = {}
    vc = os.path.join(ASSETS, f"{book}-voice-card.json")
    cc = os.path.join(ASSETS, f"{book}-craft-card.json")
    so = os.path.join(ASSETS, f"{book}-structure-obs.json")
    co = os.path.join(ASSETS, f"{book}-commercial-obs.json")
    report = os.path.join(REPORTS, f"{book}-拆书报告.md")
    craft_report = os.path.join(REPORTS, f"{book}-笔法分析.md")

    d["id"] = book
    d["title"] = BOOK_TITLES.get(book, book)
    d["has_voice"] = os.path.exists(vc)
    d["has_craft"] = os.path.exists(cc)
    d["has_structure"] = os.path.exists(so)
    d["has_commercial"] = os.path.exists(co)
    d["report_chars"] = md_chars(report)
    d["craft_report_chars"] = md_chars(craft_report)
    d["total_report_chars"] = d["report_chars"] + d["craft_report_chars"]

    if d["has_voice"]:
        d["voice"] = extract_voice_card(vc)
    if d["has_craft"]:
        d["craft"] = extract_craft_card(cc)
    if d["has_structure"]:
        d["structure"] = extract_structure_obs(so)
    if d["has_commercial"]:
        d["commercial"] = extract_commercial_obs(co)

    # 报告纯文本（渲染用）
    d["report_md"] = open(report, encoding="utf-8").read() if os.path.exists(report) else ""
    d["craft_report_md"] = open(craft_report, encoding="utf-8").read() if os.path.exists(craft_report) else ""
    return d


def build_genre_pack():
    gp = os.path.join(ASSETS, "campus-redemption-genre-pack.json")
    if not os.path.exists(gp):
        return None
    d = load_json(gp)
    return {
        "meta": d.get("meta", {}),
        "structure": d.get("structure", {}),
        "commercial": d.get("commercial", {}),
        "language_rules": d.get("language_rules", {}),
        "world_conventions": d.get("world_conventions", {}),
    }


def build_distilled():
    out = {}
    for kind in ["voice-card", "craft-card", "structure-obs", "commercial-obs"]:
        p = os.path.join(ASSETS, f"campus-redemption-{kind}-distilled.json")
        if os.path.exists(p):
            out[kind] = load_json(p)
    return out


def build_trope_library():
    p = os.path.join(ASSETS, "trope-library.json")
    if not os.path.exists(p):
        return None
    d = load_json(p)
    return d


def main():
    books = [build_book(b) for b in BOOKS]
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "books": books,
        "genre_pack": build_genre_pack(),
        "distilled": build_distilled(),
        "trope_library": build_trope_library(),
    }
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard-data.js")
    js = "window.__NOVEL_LAB__ = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(js)
    total_report = sum(b["total_report_chars"] for b in books)
    print(f"[ok] 生成 {out_path}")
    print(f"[ok] 书籍 {len(books)} 本，报告合计 {total_report} 字符")


if __name__ == "__main__":
    main()
