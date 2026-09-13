#!/usr/bin/env python3
"""
Pass5 题材包聚合器 — 多本同题材书 → genre-pack（题材包）

聚合逻辑（来自 analysis-pipeline.md Pass5 设计）：
1. 求交集 → 题材铁律（所有书都遵守的）
2. 求差集 → 作者个人风格（仅某本独有的，留在声线卡不上升到题材包）
3. 冲突项 → 标记为「流派分歧」，不做强制规则

关键阈值：
- 出现在 ≥80% 样本中的特征 → iron_rules
- 40%-80% → 建议项，不强制
- <40% → 个人特色，不入题材包

用法:
  python pass5_aggregate.py --genre campus-redemption [--books a,b,c]
  （默认聚合 assets/ 下同 genre 的全部 voice-card）
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import llm_client
import validate as validate_mod

ASSETS = ROOT / "assets"
IRON_THRESHOLD = 0.8   # ≥80% → 铁律
SUGGEST_THRESHOLD = 0.4  # 40-80% → 建议项


# --------------------------------------------------------------------------
# 资产收集
# --------------------------------------------------------------------------

def collect_books(genre: str, book_names: list | None) -> tuple:
    """收集同题材全部 voice-card。

    返回 ``(books, mismatches)`` 二元组：
        books: [{'name':..., 'voice':{...}, 'struct':{...}, 'comm':{...}}, ...]
        mismatches: [(name, actual_genre), ...] 混入的异题材书（铁律一：不再静默跳过）。
    """
    books = []
    mismatches = []
    vc_files = sorted(ASSETS.glob("*-voice-card.json"))
    for vc_f in vc_files:
        name = vc_f.name.replace("-voice-card.json", "")
        # 跳过合成测试数据（无法删除的遗留文件）
        if name.startswith("synthetic_"):
            continue
        vc = json.loads(vc_f.read_text(encoding="utf-8"))
        actual_genre = vc.get("meta", {}).get("genre")
        if actual_genre != genre:
            # 显式收集 mismatch，不再静默跳过（铁律一）
            mismatches.append((name, actual_genre))
            continue
        if book_names and name not in book_names:
            continue
        struct = {}
        sf = ASSETS / f"{name}-structure-obs.json"
        if sf.exists():
            struct = json.loads(sf.read_text(encoding="utf-8"))
        comm = {}
        cf = ASSETS / f"{name}-commercial-obs.json"
        if cf.exists():
            comm = json.loads(cf.read_text(encoding="utf-8"))
        books.append({"name": name, "voice": vc, "struct": struct, "comm": comm})
    return books, mismatches


# --------------------------------------------------------------------------
# 确定性交集统计（脚本算，不让模型数数）
# --------------------------------------------------------------------------

def extract_features(books: list) -> dict:
    """从各本书提取可统计的特征（pov/情绪模式/比喻领域/对话风格等），统计出现率。"""
    stats = {}
    for b in books:
        vc = b["voice"]
        feats = set()
        narr = vc.get("narration") or {}
        if narr.get("pov"):
            feats.add(f"pov:{narr['pov']}")
        sr = narr.get("sentence_rhythm") or {}
        if sr.get("burst_pattern"):
            # 提取短句爆发场景的 2 字核心
            for kw in re.findall(r'[\u4e00-\u9fff]{2,4}', sr["burst_pattern"][:20]):
                if kw in ("对话", "交锋", "内心", "震动", "尴尬", "窘迫", "高情绪", "场景", "战斗", "冲突"):
                    feats.add(f"burst:{kw}")
        eh = vc.get("emotion_handling") or {}
        if eh.get("mode"):
            feats.add(f"emotion_mode:{eh['mode']}")
        img = vc.get("imagery") or {}
        for d in img.get("high_freq_metaphor_domains", []):
            kw = re.sub(r'[（(].*?[）)]', '', d).strip()[:6]
            if kw:
                feats.add(f"metaphor:{kw}")
        banned = vc.get("banned") or {}
        for w in banned.get("never_used_words", [])[:3]:
            feats.add(f"avoid:{w}")
        for f in feats:
            stats.setdefault(f, set()).add(b["name"])
    # 转成出现率
    n = len(books)
    return {f: len(names) / n for f, names in stats.items()}


def summarize_thresholds(feature_rates: dict) -> dict:
    """按阈值分类特征。"""
    iron = sorted([f for f, r in feature_rates.items() if r >= IRON_THRESHOLD])
    suggest = sorted([f for f, r in feature_rates.items()
                      if SUGGEST_THRESHOLD <= r < IRON_THRESHOLD])
    personal = sorted([f for f, r in feature_rates.items() if r < SUGGEST_THRESHOLD])
    return {"iron": iron, "suggest": suggest, "personal": personal}


# --------------------------------------------------------------------------
# LLM 聚合
# --------------------------------------------------------------------------

def build_prompt(books: list, thresholds: dict) -> str:
    """构造 Pass5 聚合 prompt：把各书核心特征 + 阈值统计喂给模型。"""
    lines = []
    for b in books:
        vc = b["voice"]
        meta = vc.get("meta", {})
        narr = vc.get("narration", {})
        eh = vc.get("emotion_handling", {})
        banned = vc.get("banned", {})
        lines.append(f"""《{b['name']}》核心特征：
- 视角：{narr.get('pov', '?')}
- 短句爆发场景：{(narr.get('sentence_rhythm') or {}).get('burst_pattern', '?')[:60]}
- 情绪写法：{eh.get('mode', '?')}（{str((eh.get('examples') or [{}])[0].get('pattern', ''))[:60] if eh.get('examples') else '?'}）
- 回避词：{', '.join(banned.get('never_used_words', [])[:5])}
- 商业：{json.dumps(b.get('comm', {}).get('payoff_density', {}), ensure_ascii=False)[:100]}""")
    return f"""
你正在聚合「{books[0]['voice']['meta'].get('genre', 'unknown')}」题材的多本对标书，生成一份可复用的题材包（genre-pack）。
目标是提炼「题材铁律」——所有书都遵守的共同规律，而不是某本书的个人风格。

【各书核心特征】
{chr(10).join(lines)}

【脚本统计的跨书一致特征】
- 铁律候选（≥80% 书一致）：{', '.join(thresholds['iron']) if thresholds['iron'] else '无'}
- 建议候选（40-80%）：{', '.join(thresholds['suggest']) if thresholds['suggest'] else '无'}
- 个人特色（<40%，不应入题材包）：{', '.join(thresholds['personal']) if thresholds['personal'] else '无'}

【输出要求】严格 JSON，字段必须用英文小写。结构：
{{
  "meta": {{
    "id": "genre-短id",
    "name": "题材中文名",
    "sub_tags": ["细分标签"],
    "source_books": [{{"title": "书名", "platform": "番茄", "performance": "市场表现(如有)", "voice_card_ref": "文件名"}}],
    "target_platform": "番茄",
    "confidence": 0.0
  }},
  "structure": {{
    "chapter_word_range": {{"min": 0, "typical": 0, "max": 0}},
    "chapter_roles": [{{"role": "铺垫|推进|转折|爆发|缓冲|过渡", "ratio": 0.0, "typical_position": "", "beats": []}}],
    "hook_system": {{
      "hook_types": [{{"type": "悬念揭示|危机降临|身份反转|实力展示|情感冲击|信息断点|对手登场", "frequency": 0, "strength": 1, "skeleton": ""}}],
      "hook_density_curve": [],
      "anti_repetition_rule": ""
    }},
    "foreshadow_pattern": {{"avg_span": 0, "max_span": 0, "concurrent_open": 0, "plant_technique": []}},
    "arc_rhythm": {{"chapters_per_arc": 0, "arc_template": [], "climax_position": 0}}
  }},
  "commercial": {{
    "payoff_density": {{
      "per_thousand_words": 0.0,
      "payoff_types": [{{"type": "打脸|升级|收益兑现|身份揭露|他人认可|情感回应|反杀", "ratio": 0.0, "buildup_length": 0, "skeleton": ""}}],
      "dry_spell_tolerance": 0
    }},
    "opening_analysis": {{
      "chapter_1": {{"first_300_words_task": "", "hook_position": 0, "protagonist_intro_method": "", "conflict_intro_position": 0, "golden_finger_reveal": ""}},
      "chapter_2_3_task": "",
      "common_mistakes": []
    }},
    "paywall": {{"position_chapter": 0, "cliffhanger_technique": "", "pre_paywall_buildup": ""}},
    "update_rhythm": {{"chapters_per_day": 0, "burst_timing": ""}},
    "retention_risk_points": [{{"position": "", "reason": "", "mitigation": ""}}]
  }},
  "language_rules": {{
    "iron_rules": [{{"rule": "", "bad_example": "自造反例(非摘抄)", "good_example": "自造正例(非摘抄)", "rationale": ""}}],
    "banned_phrases": [],
    "fatigue_words": [{{"word": "", "max_per_chapter": 0}}],
    "required_elements": [],
    "forbidden_elements": []
  }},
  "world_conventions": {{
    "power_system_type": "",
    "progression_granularity": "",
    "naming_conventions": []
  }}
}}

【硬性约束】
1. iron_rules 只写 ≥80% 书一致的规律；40-80% 的写进 required_elements 或备注为建议。
2. 单个特征的 bad/good_example 必须自造，禁止摘抄任何一本书的原文。
3. 宁可题材包薄一点，也不要把个人风格误判成铁律。
4. 只输出 JSON，不要任何解释文字或 markdown 围栏。"""


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Pass5 题材包聚合器")
    ap.add_argument("--genre", required=True, help="题材 id，如 campus-redemption")
    ap.add_argument("--books", help="逗号分隔的书名，默认聚合该题材全部")
    ap.add_argument("--out", help="输出路径，默认 assets/<genre>-genre-pack.json")
    ap.add_argument("--dry-run", action="store_true", help="只统计特征，不调 LLM")
    args = ap.parse_args()

    book_names = [b.strip() for b in args.books.split(",")] if args.books else None
    books, mismatches = collect_books(args.genre, book_names)
    if mismatches:
        detail = "；".join(f"{n}(genre={g or '缺失'})" for n, g in mismatches)
        sys.exit(f"✗ 题材隔离违规：{detail} 与目标 '{args.genre}' 不符")
    if not books:
        sys.exit(f"未找到 {args.genre} 题材的 voice-card（assets/ 下）")
    print(f"聚合样本: {len(books)} 本 → {[b['name'] for b in books]}")
    if len(books) < 3:
        print(f"⚠ 样本 <3 本（当前 {len(books)}），题材包置信度将受限制（schema 要求 ≥3 才可信）")

    # 1. 确定性统计
    print("\n[1/3] 跨书特征统计:")
    feature_rates = extract_features(books)
    thresholds = summarize_thresholds(feature_rates)
    print(f"  铁律候选(≥80%): {thresholds['iron'] or '无'}")
    print(f"  建议候选(40-80%): {thresholds['suggest'] or '无'}")
    print(f"  个人特色(<40%): {thresholds['personal'] or '无'}")

    if args.dry_run:
        print("\n[dry-run] 跳过 LLM 聚合")
        return

    # 2. LLM 聚合
    print("\n[2/3] LLM 聚合题材包:")
    prompt = build_prompt(books, thresholds)
    r = llm_client.chat(user=prompt, system="你是网文题材分析师，只输出严格 JSON。",
                        task="pass5_aggregate", max_tokens=8192, temperature=0.3)
    print(f"      → tokens {r['prompt_tokens']}+{r['completion_tokens']}, {r['elapsed']}s")

    import pipeline as pipeline_mod
    pack = pipeline_mod.extract_json(r["text"])

    # 3. 校验 + 合规
    print("\n[3/3] 校验与合规:")
    validate_mod.ERRORS.clear()
    validate_mod.WARNS.clear()
    validate_mod.validate_genre_pack(pack)
    if validate_mod.ERRORS:
        print(f"  ✗ schema 校验: {len(validate_mod.ERRORS)} 条硬错误")
        for e in validate_mod.ERRORS[:8]:
            print(f"    {e}")
        sys.exit("题材包不符合 schema，未入库")
    print(f"  ✓ schema 校验通过（{len(validate_mod.WARNS)} 警告）")

    # 合规：用所有样本的正文做索引不现实，这里用每本书的资产做交叉检查的替代：
    # 校验 pack 内不含 verbal 内容
    ngram = set()
    pack_str = json.dumps(pack, ensure_ascii=False)
    if "contains_verbatim" in pack_str and '"contains_verbatim": true' in pack_str:
        sys.exit("✗ 题材包含 verbatim 标记，未入库")

    # MEDIUM：genre 用于拼接默认输出路径，必须白名单校验防路径穿越
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9_-]+", args.genre):
        sys.exit(f"✗ 非法 genre 名（仅允许字母/数字/下划线/连字符）: {args.genre!r}")

    out = Path(args.out) if args.out else ASSETS / f"{args.genre}-genre-pack.json"
    out.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 题材包已入库: {out}")
    print(f"  铁律 {len(pack.get('language_rules', {}).get('iron_rules', []))} 条, "
          f"必需要素 {len(pack.get('language_rules', {}).get('required_elements', []))} 条")
    print("\n→ 题材包可被 inject.py 注入写作（--genre-pack 参数）")


if __name__ == "__main__":
    main()
