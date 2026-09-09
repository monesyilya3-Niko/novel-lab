#!/usr/bin/env python3
"""
拆书流水线编排 — 采样 → 量化 → 四遍扫描 → 资产组装 → 校验 → 合规

一条命令跑完 M1 全部逻辑：
  1. 分层采样（sampler 逻辑，纯 CPU）
  2. 量化指标（metrics 逻辑，纯 CPU）
  3. 四遍扫描（Pass1-4，各自独立调用 LLM，任务路由选模型）
  4. 组装资产（voice-card + 结构观测 + 商业观测）
  5. Schema 校验（validate） + 合规扫描（compliance）

用法:
  python pipeline.py <book.txt> --genre campus-redemption
  python pipeline.py <book.txt> --genre campus-redemption --dry-run   # 不调 LLM，只走采样+量化
  python pipeline.py <book.txt> --genre campus-redemption --model-id ds   # 显式指定模型

输出:
  corpus/sampled/<name>/         采样分片（M1.1）
  corpus/metrics/<name>.json     量化指标（M1.2）
  assets/<name>-voice-card.json       声线卡（M1.3+1.4+1.5）
  assets/<name>-structure-obs.json    结构观测（单本，待≥3本聚合）
  assets/<name>-commercial-obs.json   商业观测（单本，待聚合）
"""
import argparse
import json
import re
import sys
from pathlib import Path

import sampler
import metrics as metrics_mod
import llm_client
import validate as validate_mod
import compliance as compliance_mod
import normalize as normalize_mod

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"
ASSETS_DIR = ROOT / "assets"
REPORTS_DIR = ROOT / "reports"

PASS_FILES = {
    "pass1_structure": "pass1_structure.md",
    "pass2_character": "pass2_character.md",
    "pass3_style": "pass3_style.md",
    "pass4_commercial": "pass4_commercial.md",
    "pass5_craft": "pass5_craft.md",
}


# --------------------------------------------------------------------------
# Prompt 文件解析：提取 SYSTEM / USER 模板
# --------------------------------------------------------------------------

def load_prompt(kind: str) -> tuple:
    """从 prompts/passX.md 提取 (system, user_template)。标题行即分隔标记。"""
    text = (PROMPTS_DIR / PASS_FILES[kind]).read_text(encoding="utf-8")
    # 标题形式：## SYSTEM（角色设定，原样粘贴） / ## USER（输入模板，按占位符替换）
    sys_m = re.search(r"^## SYSTEM.*?\n(.*?)(?=^## USER)", text, re.M | re.S)
    usr_m = re.search(r"^## USER.*?\n(.*?)(?=^## 版权|^## \S)", text, re.M | re.S)
    if not sys_m or not usr_m:
        raise RuntimeError(f"prompts/{PASS_FILES[kind]} 缺少 SYSTEM/USER 区块")
    return sys_m.group(1).strip(), usr_m.group(1).strip()


# --------------------------------------------------------------------------
# LLM 输出 → JSON（剥离 ```json 围栏 / 前后废话）
# --------------------------------------------------------------------------

def extract_json(raw: str) -> dict:
    raw = raw.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.S)
    if m:
        raw = m.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"输出中找不到 JSON: {raw[:200]}")
    return json.loads(raw[start:end + 1])


# --------------------------------------------------------------------------
# 四遍扫描
# --------------------------------------------------------------------------

def build_user_input(kind: str, slices: dict, metrics: dict) -> str:
    """按 Pass 从切片和指标组装 user 消息。"""
    if kind == "pass1_structure":
        parts = []
        for c in slices["pass1_structure"]["chapters"]:
            parts.append(f"## 第{c['index']}章 {c['title']}（{c['reason']}）\n{c['text']}\n【章末500字】\n{c['tail500']}")
        return "\n\n".join(parts)
    if kind == "pass2_character":
        parts = [f"[第{d['chapter']}章 {d['title']}] 前:{d['before']} | 对话:{d['line']} | 后:{d['after']}"
                 for d in slices["pass2_character"]["dialogues"]]
        return "\n".join(parts)
    if kind == "pass3_style":
        q = metrics
        quant = json.dumps({
            "avg_sentence_len": q["avg_sentence_len"],
            "dialogue_ratio": q["dialogue_ratio"],
            "char_ttr": q["char_ttr"],
            "top_bigrams": q["top_bigrams"][:10],
            "sensory": q["sensory"],
            "exclaim_ratio": q["exclaim_ratio"],
        }, ensure_ascii=False, indent=2)
        parts = [f"## 第{c['index']}章 {c['title']}\n{c['text']}" for c in slices["pass3_style"]["chapters"]]
        return f"【量化指标】\n{quant}\n\n【全文切片】\n" + "\n\n".join(parts)
    if kind == "pass4_commercial":
        parts = [f"## 第{c['index']}章 {c['title']}\n{c['text']}" for c in slices["pass4_commercial"]["chapters"]]
        return "\n\n".join(parts)
    if kind == "pass5_craft":
        # Pass5 需要：全文切片（开篇3+中段2+高潮1）+ 前四遍资产摘要
        # 复用 pass3_style 的切片（连续中段3章+高潮1章），额外加开篇章
        parts = []
        # 加开篇前3章（从 pass1 或 pass4 的切片中取）
        p1_chs = slices.get("pass1_structure", {}).get("chapters", [])
        for c in p1_chs[:3]:
            parts.append(f"## 第{c['index']}章 {c['title']}（开篇）\n{c['text']}")
        # 加中段+高潮（复用 pass3 切片）
        for c in slices.get("pass3_style", {}).get("chapters", []):
            parts.append(f"## 第{c['index']}章 {c['title']}\n{c['text']}")
        return "\n\n".join(parts)
    raise ValueError(f"未知 Pass: {kind}")


def run_pass(kind: str, slices: dict, metrics: dict, dry_run: bool,
             model_id: str | None) -> dict:
    system, template = load_prompt(kind)
    user = build_user_input(kind, slices, metrics)
    mid, model = llm_client.resolve_model(task=kind, model_id=model_id)
    print(f"  [Pass] {kind} → 模型 {mid} ({model['model_name']})  | user 约 {len(user)//1000}K 字")
    if dry_run:
        return {"_dry_run": True, "model": mid}

    # 首次调用 + 解析失败后的纠错重试（最多 3 轮）
    # Pass2/3/5 需要更多 token 输出（角色声线详细要求 + imagery + 8维笔法分析）
    max_tok = 16384 if kind in ("pass2_character", "pass3_style", "pass5_craft") else 8192
    for attempt in range(3):
        r = llm_client.chat(user=user, system=system, task=kind, model_id=model_id,
                            max_tokens=max_tok, temperature=0.3)
        print(f"      → tokens {r['prompt_tokens']}+{r['completion_tokens']}, 花费 ¥{r['cost']}, {r['elapsed']}s")
        try:
            out = extract_json(r["text"])
            # Pass2 质量门禁：角色数不足（<2）时重试——Pass2 是最不稳定的输出
            if kind == "pass2_character":
                n = len(normalize_mod.normalize_pass2(out))
                if n < 2 and attempt < 2:
                    print(f"      ⚠ 仅提取到 {n} 个角色，重试（要求全部出场角色）...")
                    system = system + "\n\n【重要】请输出对话切片中所有出场≥5次的角色（主角、女主、重要配角都要），不要只输出一个。"
                    continue
            out["_meta"] = {
                "model": r["model_id"],
                "tokens_in": r["prompt_tokens"],
                "tokens_out": r["completion_tokens"],
                "cost": r["cost"],
                "elapsed": r["elapsed"],
            }
            return out
        except (ValueError, json.JSONDecodeError) as e:
            # 存原始输出便于诊断，然后带纠错提示重试
            debug_dir = ROOT / "corpus" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / f"{kind}_attempt{attempt}.txt").write_text(r["text"], encoding="utf-8")
            print(f"      ⚠ JSON 解析失败（{str(e)[:60]}），原始输出已存 corpus/debug/{kind}_attempt{attempt}.txt")
            if attempt == 0:
                system = system + "\n\n【重要】你上一次的输出不是合法 JSON。请只输出一个合法的 JSON 对象，不要任何解释文字、不要 markdown 围栏、不要中文键名。"
    raise RuntimeError(f"{kind} 多次调用未产出合格输出")


# --------------------------------------------------------------------------
# 资产组装
# --------------------------------------------------------------------------

def assemble_voice_card(name: str, genre: str, manifest: dict, pass2: dict,
                        pass3: dict, metrics: dict) -> dict:
    voices = pass2.get("character_voices", [])
    n_chapters = manifest["selected_count"]
    return {
        "meta": {
            "source_title": name,
            "genre": genre,
            "extracted_at": __import__("datetime").date.today().isoformat(),
            "sample_chapters": manifest["selected_indices"],
            "total_sample_words": metrics.get("total_chars", 0),
            # 样本 ≥10 章才允许高置信；<10 章强制 ≤0.6
            "confidence": 0.6 if n_chapters < 10 else min(0.9, 0.65 + n_chapters / 80),
            "human_reviewed": False,
        },
        "narration": pass3.get("narration", {}),
        "dialogue": {
            "dialogue_ratio": metrics.get("dialogue_ratio", 0),
            "tag_style": pass3.get("dialogue", {}).get("tag_style", ""),
            "subtext_level": pass3.get("dialogue", {}).get("subtext_level", "直白"),
            "character_voices": voices,
        },
        "emotion_handling": pass3.get("emotion_handling", {}),
        "imagery": pass3.get("imagery", {}),
        "banned": pass3.get("banned", {}),
        "provenance": {
            "contains_verbatim": False,
            "abstraction_note": "四遍扫描产物，经 compliance.py 扫描，连续12字匹配原文已拒收",
        },
    }


def assemble_obs(kind: str, name: str, genre: str, pass_out: dict) -> dict:
    """结构/商业观测：单本数据，标注待聚合（≥3本才生成题材包）。"""
    body = {k: v for k, v in pass_out.items() if not k.startswith("_")}
    return {
        "meta": {
            "source_title": name,
            "genre": genre,
            "scope": "single-book-observation",
            "awaiting_aggregation": True,
            "min_books_required": 3,
        },
        **body,
    }


def assemble_voice_card_v2(name: str, genre: str, manifest: dict,
                           voices: list, narration: dict, dialogue: dict,
                           emotion: dict, imagery: dict, banned: dict,
                           metrics: dict) -> dict:
    """组装 voice-card（v2：接收归一化后的结构，不依赖 pass 原始输出键名）。"""
    n_chapters = manifest["selected_count"]
    # 确保 voices 注入到 dialogue 的 character_voices 中
    if voices and not dialogue.get("character_voices"):
        dialogue["character_voices"] = voices
    return {
        "meta": {
            "source_title": name,
            "genre": genre,
            "extracted_at": __import__("datetime").date.today().isoformat(),
            "sample_chapters": manifest["selected_indices"],
            "total_sample_words": metrics.get("total_chars", 0),
            "confidence": 0.6 if n_chapters < 10 else min(0.9, 0.65 + n_chapters / 80),
            "human_reviewed": False,
        },
        "narration": narration,
        "dialogue": dialogue,
        "emotion_handling": emotion,
        "imagery": imagery,
        "banned": banned,
        "provenance": {
            "contains_verbatim": False,
            "abstraction_note": "四遍扫描产物，经 compliance.py 扫描，连续12字匹配原文已拒收",
        },
    }


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="拆书流水线（采样→量化→四遍扫描→资产→校验→合规）")
    ap.add_argument("book", help="整本小说 TXT")
    ap.add_argument("--genre", default="unknown", help="题材 id，如 campus-redemption")
    ap.add_argument("--model-id", help="显式指定模型，缺省按任务路由")
    ap.add_argument("--dry-run", action="store_true", help="只走采样+量化+Pass 准备，不调 LLM")
    args = ap.parse_args()

    src = Path(args.book)
    if not src.exists():
        sys.exit(f"文件不存在: {src}")
    name = src.stem
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 采样
    text = src.read_text(encoding="utf-8")
    chapters = sampler.split_chapters(text)
    if len(chapters) < 5:
        sys.exit(f"章节过少（{len(chapters)}），无法有效拆解")
    sel = sampler.select(chapters)
    slices = sampler.build_slices(chapters, sel)
    manifest = {
        "book": name,
        "total_chapters": len(chapters),
        "selected_count": len(sel),
        "selected_indices": [i + 1 for i in sorted(sel)],
    }
    sampled_dir = ROOT / "corpus" / "sampled" / name
    sampled_dir.mkdir(parents=True, exist_ok=True)
    (sampled_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (sampled_dir / "slices.json").write_text(json.dumps(slices, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[1/7] 采样: {len(chapters)} 章 → {len(sel)} 章（manifest.json / slices.json）")

    # 2. 量化（对整本跑，指标更稳）
    m = metrics_mod.compute(text)
    metrics_dir = ROOT / "corpus" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / f"{name}.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[2/7] 量化: {m['total_chars']} 字, 均句长 {m['avg_sentence_len']}, "
          f"对话占比 {m['dialogue_ratio']}, TTR {m['char_ttr']}")

    # 3. 五遍扫描（Pass1-4 + Pass5 笔法分析）
    # 2026-09-01 起：无外部模型模式——采样+量化完成后优雅停止，
    # 切片与 prompt 留给 WorkBuddy 内置智能在会话内手动完成 pass1-5。
    if not llm_client.any_model_configured():
        ai_dir = ROOT / "corpus" / "raw" / name
        ai_dir.mkdir(parents=True, exist_ok=True)
        guide = ai_dir / "AI接管任务.md"
        guide.write_text(
            "# WorkBuddy 内置智能接管任务（无外部模型模式）\n\n"
            f"书名: {name} | 题材: {args.genre}\n"
            f"采样: {len(sel)}/{len(chapters)} 章 | 量化指标: corpus/metrics/{name}.json\n\n"
            "## 接管步骤\n"
            "1. 依次读 prompts/pass1_structure.md ~ pass5_craft.md 的要求\n"
            "2. 读 corpus/sampled/{book}/ 下对应切片文本\n"
            "3. 按 prompt 要求在会话内产出分析 JSON，存为 corpus/raw/{book}/passN_*.json\n"
            "4. 产出齐 4 个 pass 后，运行资产组装与校验（normalize → validate → compliance）\n"
            "5. 参考既有资产格式: assets/*-voice-card.json\n\n"
            "本文件由 pipeline.py 自动生成。\n",
            encoding="utf-8")
        print("[3/7] 五遍扫描: 未配置外部模型 —— 已生成 AI 接管任务清单")
        print(f"      → {guide}")
        print("      采样切片与量化指标已就绪，pass1-5 由 WorkBuddy 会话内完成")
        print("      （恢复外部模型可运行: python scripts/model_config.py add）")
        return 0

    print("[3/7] 五遍扫描:")
    results = {}
    raw_dir = ROOT / "corpus" / "raw" / name  # 按书名隔离，避免多本书互相覆盖
    raw_dir.mkdir(parents=True, exist_ok=True)
    for kind in ("pass1_structure", "pass2_character", "pass3_style", "pass4_commercial"):
        results[kind] = run_pass(kind, slices, m, args.dry_run, args.model_id)
        if not args.dry_run:
            (raw_dir / f"{kind}.json").write_text(
                json.dumps(results[kind], ensure_ascii=False, indent=2), encoding="utf-8")

    # 输出完整性检查：关键字段缺失时警告（模型输出结构不稳定，需重跑对应 Pass）
    if not args.dry_run:
        checks = {
            "pass4_commercial": [
                ("opening_analysis", "商业层缺开篇分析（Pass4 重跑或人工补）"),
                ("dry_spell_tolerance", "商业层缺干旱期容忍度（Pass4 重跑或人工补）"),
                ("paywall", "商业层缺付费卡点（Pass4 重跑或人工补）"),
            ],
        }

        def deep_has(obj, key):
            """递归检查嵌套 dict 里是否存在某键。"""
            if isinstance(obj, dict):
                if key in obj:
                    return True
                return any(deep_has(v, key) for v in obj.values())
            if isinstance(obj, list):
                return any(deep_has(v, key) for v in obj)
            return False
        for kind, fields in checks.items():
            for field, msg in fields:
                if not deep_has(results[kind], field):
                    print(f"      ⚠ [{kind}] 缺 '{field}' → {msg}")

    # 4. 组装资产
    print("[4/7] 组装资产:")
    if not args.dry_run:
        # Pass2/3 输出是中文自由键，经归一化转成 schema 结构
        import normalize as norm
        p2 = results["pass2_character"]
        p3 = results["pass3_style"]
        voices = norm.normalize_pass2(p2)
        narration, dialogue, emotion, imagery, banned = norm.normalize_pass3(p3)
        dialogue["dialogue_ratio"] = m.get("dialogue_ratio", 0)
        voice = assemble_voice_card_v2(name, args.genre, manifest, voices,
                                       narration, dialogue, emotion, imagery, banned, m)
        struct_obs = assemble_obs("structure", name, args.genre, results["pass1_structure"])
        comm_obs = assemble_obs("commercial", name, args.genre, results["pass4_commercial"])
        vc_path = ASSETS_DIR / f"{name}-voice-card.json"
        so_path = ASSETS_DIR / f"{name}-structure-obs.json"
        co_path = ASSETS_DIR / f"{name}-commercial-obs.json"
        for p, obj in ((vc_path, voice), (so_path, struct_obs), (co_path, comm_obs)):
            p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"      {vc_path.name} ({len(json.dumps(voice, ensure_ascii=False))//1024}K)")
        print(f"      {so_path.name}")
        print(f"      {co_path.name}")

        # 5. Pass5 笔法分析 + craft-card 组装
        print("[5/7] Pass5 笔法分析:")
        # 构建资产摘要供 Pass5 参考
        asset_summary = json.dumps({
            "structure": {k: v for k, v in results["pass1_structure"].items() if not k.startswith("_")},
            "voices": [{"name": v.get("name"), "role": v.get("role")} for v in voices],
            "emotion_mode": emotion.get("mode", "未知"),
            "imagery_domains": imagery.get("high_freq_metaphor_domains", []),
            "commercial_payoff": results["pass4_commercial"].get("payoff_density", {}).get("payoff_types", []),
        }, ensure_ascii=False, indent=2)
        # 将资产摘要注入 pass5 的 user input
        pass5_user = build_user_input("pass5_craft", slices, m)
        pass5_user = f"【前四遍扫描摘要】\n{asset_summary}\n\n【采样章节全文】\n{pass5_user}"
        pass5_result = run_pass("pass5_craft", slices, m, args.dry_run, args.model_id)
        if not args.dry_run:
            (raw_dir / "pass5_craft.json").write_text(
                json.dumps(pass5_result, ensure_ascii=False, indent=2), encoding="utf-8")
            # 组装 craft-card：兼容 4 种 pass5 输出格式
            DIM_NAMES = ["foreshadowing", "information_release", "pov_control",
                         "scene_transition", "tension_building", "dialogue_craft",
                         "rhythm_control", "sensory_craft", "narrative_engine", "emotional_algorithm"]
            DK = {
                "foreshadowing": ["伏笔","铺垫","埋伏","埋","回收","线索","暗示","预示","物件","象征"],
                "information_release": ["信息","悬念","释放","揭示","隐瞒","秘密","反转","真相"],
                "pov_control": ["视角","限知","全知","信息差","叙述者","内心独白","心理","旁白"],
                "scene_transition": ["转场","切换","过渡","场景转换","淡出","时间","空间","地点"],
                "tension_building": ["张力","紧张","高潮","压迫","加速","减速","对比","冲突","危机","威胁","困境"],
                "dialogue_craft": ["对话","潜台词","沉默","打断","错位","回应","拒绝","语气","口吻","言外之意"],
                "rhythm_control": ["节奏","快慢","段落","留白","停顿","递进","句式","短句","长句","单句成段","呼吸"],
                "sensory_craft": ["感官","五感","视觉","听觉","触觉","嗅觉","细节","身体","反应","表情","动作","外貌"],
                "narrative_engine": ["驱动","翻页","悬念","牵挂","承诺","兑现","命运","牵引","吸引","期待","好奇"],
                "emotional_algorithm": ["情绪","升起","伪装","转移","释放","压抑","爆发","隐忍","伪装","隐藏","流泪","哽咽"],
            }

            craft_analysis = {}
            craft_summary = {"top_3_strengths":[],"unique_techniques":[],"reusable_patterns":[]}
            all_tech_names = []

            # 格式检测
            if "craft_analysis" in pass5_result:
                craft_analysis = pass5_result["craft_analysis"]
                craft_summary = pass5_result.get("craft_summary", craft_summary)
            elif any(d in pass5_result for d in DIM_NAMES):
                # 只取 pass5 实际输出了的维度（不创建空壳）
                craft_analysis = {}
                for d in DIM_NAMES:
                    val = pass5_result.get(d)
                    if val:
                        craft_analysis[d] = val
            elif "chapter_analysis" in pass5_result:
                craft_analysis = {d:{"techniques":[]} for d in DK}
                for ch in pass5_result["chapter_analysis"]:
                    for tech in ch.get("techniques",[]):
                        nt = tech.get("name") or tech.get("technique_name","")
                        sk = tech.get("abstract_skeleton",""); ef = tech.get("effect","")
                        dc = tech.get("example_in_text") or tech.get("execution") or tech.get("method","")
                        an = tech.get("counter_example") or tech.get("anti_example") or tech.get("counter_exa","")
                        o = {"name":nt,"description":dc[:200],"effect":ef[:200],"skeleton":sk[:200],"anti_pattern":an[:200]}
                        ft = f"{nt} {sk} {ef}".lower(); placed=False
                        for d,kws in DK.items():
                            if any(k in ft for k in kws): craft_analysis[d]["techniques"].append(o); placed=True; break
                        if not placed: craft_analysis["tension_building"]["techniques"].append(o)
                        all_tech_names.append(nt)
            elif "techniques" in pass5_result and isinstance(pass5_result["techniques"],list):
                craft_analysis = {d:{"techniques":[]} for d in DK}
                for tech in pass5_result["techniques"]:
                    if not isinstance(tech,dict): continue
                    nt = (tech.get("name") or tech.get("technique_name") or tech.get("scenario",""))[:50]
                    sk = tech.get("abstract_skeleton",""); ef = tech.get("effect","")
                    dc = tech.get("method") or tech.get("execution") or tech.get("scenario","")
                    an = tech.get("counter_example") or tech.get("anti_example","")
                    o = {"name":nt,"description":dc[:200],"effect":ef[:200],"skeleton":sk[:200],"anti_pattern":an[:200]}
                    ft = f"{nt} {sk} {ef} {dc}".lower(); placed=False
                    for d,kws in DK.items():
                        if any(k in ft for k in kws): craft_analysis[d]["techniques"].append(o); placed=True; break
                    if not placed: craft_analysis["tension_building"]["techniques"].append(o)
                    all_tech_names.append(nt)

            if all_tech_names:
                craft_summary["top_3_strengths"] = all_tech_names[:3]
                craft_summary["unique_techniques"] = all_tech_names[3:5] if len(all_tech_names)>3 else []
                craft_summary["reusable_patterns"] = all_tech_names[:3]

            # 规范化：list→{techniques:[...]}，字段名标准化，从abstract_pattern生成名称
            for dk in list(craft_analysis.keys()):
                v = craft_analysis[dk]
                if isinstance(v,list):
                    norm = []
                    for t in v:
                        if not isinstance(t,dict): continue
                        nm = t.get("name") or t.get("technique_name") or ""
                        if not nm:
                            ap = t.get("abstract_pattern") or t.get("skeleton") or ""
                            if ap: nm = ap[:25].rstrip("，。、")
                        norm.append({"name":nm,"description":t.get("description") or t.get("example_in_text") or t.get("abstract_pattern",""),"effect":t.get("effect",""),"skeleton":t.get("skeleton") or t.get("abstract_pattern",""),"anti_pattern":t.get("anti_pattern") or t.get("反例") or t.get("counter_example","")})
                    craft_analysis[dk] = {"techniques":norm}
                elif isinstance(v,dict) and "techniques" not in v:
                    craft_analysis[dk] = {"techniques":[v]}

            n_chapters = manifest["selected_count"]
            craft_card = {
                "meta": {
                    "source_title": name,
                    "genre": args.genre,
                    "extracted_at": __import__("datetime").date.today().isoformat(),
                    "sample_chapters": manifest["selected_indices"],
                    "total_sample_words": m.get("total_chars", 0),
                    "confidence": 0.6 if n_chapters < 10 else min(0.9, 0.65 + n_chapters / 80),
                    "pass5_version": "1.0",
                },
                "craft_analysis": craft_analysis,
                "craft_summary": craft_summary,
                "provenance": {
                    "contains_verbatim": False,
                    "abstraction_note": "Pass5 笔法分析产物，经 compliance.py 扫描",
                },
            }
            # 深度分析校验 + 补齐（deep_analyze 不生成内容，只校验结构）
            try:
                import deep_analyze
                depth_stats = deep_analyze.analyze_craft_card(craft_card)
                if depth_stats["incomplete"] > 0:
                    print(f"  ⚠ 深度分析缺段 {depth_stats['incomplete']}/{depth_stats['total']} 条技法，"
                          f"报告可能达不到 1 万字")
            except ImportError:
                print("  ⚠ deep_analyze 模块缺失，跳过深度分析校验")

            cc_path = ASSETS_DIR / f"{name}-craft-card.json"
            cc_path.write_text(json.dumps(craft_card, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"      {cc_path.name} ({len(json.dumps(craft_card, ensure_ascii=False))//1024}K)")

            # 生成笔法报告
            try:
                import report_craft as rc_mod
                report = rc_mod.render_craft_report(craft_card)
                report_path = REPORTS_DIR / f"{name}-笔法分析.md"
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(report, encoding="utf-8")
                print(f"      {report_path.name}（可交付报告）")

                # 铁律二：笔法分析单份字数提示（合计校验由 novel.py「分析」命令在
                # 拆书报告 + 笔法报告都生成后统一执行）
                report_len = len(report)
                if report_len < 10000:
                    print(f"  ⚠ 笔法分析单份 {report_len} 字符 < 10000，"
                          f"合计校验以 novel.py「分析」命令为准")
            except Exception as e:
                print(f"      ⚠ 笔法报告生成失败: {e}")

        # 6. 校验（voice-card 严格校验；craft-card 也校验；观测文件延后）
        print("[6/7] Schema 校验:")
        vc_errs = 0
        all_assets = [(vc_path, "voice-card"), (so_path, None), (co_path, None)]
        if not args.dry_run:
            cc_path = ASSETS_DIR / f"{name}-craft-card.json"
            if cc_path.exists():
                all_assets.append((cc_path, "craft-card"))
        for p, kind in all_assets:
            if kind and kind in validate_mod.DISPATCH:
                errs_before = list(validate_mod.ERRORS)
                validate_mod.DISPATCH[kind](json.loads(p.read_text(encoding="utf-8")))
                new_errs = validate_mod.ERRORS[len(errs_before):]
                if new_errs:
                    vc_errs += len(new_errs)
                    print(f"      ✗ {p.name}: {len(new_errs)} 条硬错误")
                else:
                    print(f"      ✓ {p.name}: schema 校验通过")
            else:
                print(f"      ✓ {p.name}: 观测文件（单本中间产物），schema 校验延后至聚合")
        if vc_errs:
            sys.exit("资产校验失败，请检查上面错误。")

        # 7. 合规（voice-card/craft-card 失败阻塞；obs 文件只警告）
        print("[7/7] 合规扫描:")
        critical_assets = [vc_path]
        cc_path = ASSETS_DIR / f"{name}-craft-card.json"
        if cc_path.exists():
            critical_assets.append(cc_path)
        obs_assets = [so_path, co_path]
        compliance_failed = False
        for p in critical_assets:
            code = run_compliance(p, src)
            if code == 1:
                compliance_failed = True
                print(f"      ✗ {p.name}: 合规 REJECT（关键资产，阻塞入库）")
        for p in obs_assets:
            code = run_compliance(p, src)
            if code == 1:
                print(f"      ⚠ {p.name}: 合规 REJECT（观测文件，不阻塞入库，建议人工修复）")
        if compliance_failed:
            sys.exit("关键资产合规扫描未通过，入库被阻塞。")
    else:
        print("      [dry-run] 跳过组装/校验/合规（未调用 LLM）")
        print("      → 真实运行需先配置模型 key：")
        print("        python scripts/model_config.py add --preset deepseek --id ds --key <你的key>")
        print("        python scripts/model_config.py test ds")
        print("\n完成。下一步: 人工校验资产（M1.6），或提供更多同题材书跑聚合。")
        return 0

    # 蒸馏 Hook：拆书资产入库后，若同题材已 ≥3 本则幂等重跑蒸馏层。
    _run_distill_hook(args.genre)

    print("\n完成。下一步: 人工校验资产（M1.6），或提供更多同题材书跑聚合。")


def _run_distill_hook(genre: str) -> None:
    """拆书完成后的蒸馏 Hook（幂等，<3 本静默跳过）。"""
    if not genre or genre == "unknown":
        return
    # 统计该题材下已拆书（voice-card 代表已完整入库的书籍数，平铺在 assets/）。
    voice_cards = []
    for vc in sorted(ASSETS_DIR.glob("*-voice-card.json")):
        try:
            meta = json.loads(vc.read_text(encoding="utf-8")).get("meta") or {}
        except (json.JSONDecodeError, OSError):
            continue
        if meta.get("genre") == genre:
            voice_cards.append(vc)
    if len(voice_cards) < 3:
        print(f"\n[蒸馏 Hook] 同题材《{genre}》仅 {len(voice_cards)} 本（<3），暂不蒸馏。")
        return
    try:
        import distill
    except ImportError:
        print("\n[蒸馏 Hook] 蒸馏模块缺失，跳过。")
        return
    print(f"\n[蒸馏 Hook] 同题材《{genre}》已达 {len(voice_cards)} 本，幂等重跑蒸馏…")
    try:
        distill.run_distill(genre)
        print("  ✓ 蒸馏完成，4 类 distilled JSON 已更新。")
    except Exception as exc:  # noqa: BLE001 — Hook 不阻塞主流程。
        print(f"  ✗ 蒸馏失败（不阻塞拆书主流程）: {exc}")


def run_compliance(asset_path: Path, book_path: Path) -> int:
    """合规扫描封装：返回退出码（0 通过 / 1 拒绝 / 2 警告）。"""
    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    book_text = book_path.read_text(encoding="utf-8")
    ngram = compliance_mod.build_ngram_index(book_text)
    errs, warns = compliance_mod.scan_asset(asset, ngram)
    print(f"      {asset_path.name}: 硬错误 {len(errs)} / 警告 {len(warns)}")
    for e in errs:
        print(f"        ✗ {e}")
    for w in warns:
        print(f"        ⚠ {w}")
    return 1 if errs else (2 if warns else 0)


if __name__ == "__main__":
    main()
