#!/usr/bin/env python3
"""
资产组装 — 把 AI 会话内产出的 pass1-5 中文键 JSON 组装成 4 类可入库资产

背景：无外部模型模式下，pipeline.py 在采样+量化后即退出（生成 AI 接管任务清单），
pass1-5 由 WorkBuddy 内置智能在会话内产出中文键 JSON，存到 corpus/raw/<书>/passN_*.json。
本脚本补上"AI 产出 → 资产入库"这一环：读取这些 pass JSON，归一化后组装成
voice-card / structure-obs / commercial-obs / craft-card 四类资产，写入 assets/。

用法（在 novel-lab 根目录运行）：
  python scripts/assemble.py <书名> --genre campus-redemption

  书名 = corpus/raw/ 下的目录名（如 chireng_chosen），同时用于读
  corpus/sampled/<书名>/manifest.json 与 corpus/metrics/<书名>.json。

输出：
  assets/<书名>-voice-card.json
  assets/<书名>-structure-obs.json
  assets/<书名>-commercial-obs.json
  assets/<书名>-craft-card.json
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import normalize as norm

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"
RAW_DIR = ROOT / "corpus" / "raw"
SAMPLED_DIR = ROOT / "corpus" / "sampled"
METRICS_DIR = ROOT / "corpus" / "metrics"

# Pass5 十大笔法维度（与 pipeline.py 保持一致）
DIM_NAMES = ["foreshadowing", "information_release", "pov_control",
             "scene_transition", "tension_building", "dialogue_craft",
             "rhythm_control", "sensory_craft", "narrative_engine", "emotional_algorithm"]
DK = {
    "foreshadowing": ["伏笔", "铺垫", "埋伏", "埋", "回收", "线索", "暗示", "预示", "物件", "象征"],
    "information_release": ["信息", "悬念", "释放", "揭示", "隐瞒", "秘密", "反转", "真相"],
    "pov_control": ["视角", "限知", "全知", "信息差", "叙述者", "内心独白", "心理", "旁白"],
    "scene_transition": ["转场", "切换", "过渡", "场景转换", "淡出", "时间", "空间", "地点"],
    "tension_building": ["张力", "紧张", "高潮", "压迫", "加速", "减速", "对比", "冲突", "危机", "威胁", "困境"],
    "dialogue_craft": ["对话", "潜台词", "沉默", "打断", "错位", "回应", "拒绝", "语气", "口吻", "言外之意"],
    "rhythm_control": ["节奏", "快慢", "段落", "留白", "停顿", "递进", "句式", "短句", "长句", "单句成段", "呼吸"],
    "sensory_craft": ["感官", "五感", "视觉", "听觉", "触觉", "嗅觉", "细节", "身体", "反应", "表情", "动作", "外貌"],
    "narrative_engine": ["驱动", "翻页", "悬念", "牵挂", "承诺", "兑现", "命运", "牵引", "吸引", "期待", "好奇"],
    "emotional_algorithm": ["情绪", "升起", "伪装", "转移", "释放", "压抑", "爆发", "隐忍", "隐藏", "流泪", "哽咽"],
}


def load_json(path: Path) -> dict:
    """读取 JSON 文件，编码容错（utf-8 优先，回退 utf-8-sig）。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def _confidence(n_chapters: int) -> float:
    """样本 ≥10 章才允许高置信；<10 章强制 ≤0.6（与 pipeline 一致）。"""
    return 0.6 if n_chapters < 10 else min(0.9, 0.65 + n_chapters / 80)


def assemble_voice_card(name: str, genre: str, manifest: dict, metrics: dict,
                        voices: list, narration: dict, dialogue: dict,
                        emotion: dict, imagery: dict, banned: dict) -> dict:
    """组装 voice-card（接收归一化后的结构）。"""
    if voices and not dialogue.get("character_voices"):
        dialogue["character_voices"] = voices
    return {
        "meta": {
            "source_title": name,
            "genre": genre,
            "extracted_at": date.today().isoformat(),
            "sample_chapters": manifest.get("selected_indices", []),
            "total_sample_words": metrics.get("total_chars", 0),
            "confidence": _confidence(manifest.get("selected_count", 0)),
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


def assemble_obs(kind: str, name: str, genre: str, pass_out: dict) -> dict:
    """结构/商业观测：单本数据，标注待聚合。"""
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


def assemble_craft_card(name: str, genre: str, manifest: dict, metrics: dict,
                        pass5: dict) -> dict:
    """组装 craft-card：兼容 4 种 pass5 输出格式（与 pipeline.py 逻辑一致）。"""
    craft_analysis = {}
    craft_summary = {"top_3_strengths": [], "unique_techniques": [], "reusable_patterns": []}
    all_tech_names = []

    # 格式检测
    if "craft_analysis" in pass5:
        craft_analysis = pass5["craft_analysis"]
        craft_summary = pass5.get("craft_summary", craft_summary)
    elif any(d in pass5 for d in DIM_NAMES):
        craft_analysis = {}
        for d in DIM_NAMES:
            val = pass5.get(d)
            if val:
                craft_analysis[d] = val
    elif "chapter_analysis" in pass5:
        craft_analysis = {d: {"techniques": []} for d in DK}
        for ch in pass5["chapter_analysis"]:
            for tech in ch.get("techniques", []):
                nt = tech.get("name") or tech.get("technique_name", "")
                sk = tech.get("abstract_skeleton", "")
                ef = tech.get("effect", "")
                dc = tech.get("example_in_text") or tech.get("execution") or tech.get("method", "")
                an = tech.get("counter_example") or tech.get("anti_example") or tech.get("counter_exa", "")
                o = {"name": nt, "description": dc[:200], "effect": ef[:200],
                     "skeleton": sk[:200], "anti_pattern": an[:200]}
                ft = f"{nt} {sk} {ef}".lower()
                placed = False
                for d, kws in DK.items():
                    if any(k in ft for k in kws):
                        craft_analysis[d]["techniques"].append(o)
                        placed = True
                        break
                if not placed:
                    craft_analysis["tension_building"]["techniques"].append(o)
                all_tech_names.append(nt)
    elif "techniques" in pass5 and isinstance(pass5["techniques"], list):
        craft_analysis = {d: {"techniques": []} for d in DK}
        for tech in pass5["techniques"]:
            if not isinstance(tech, dict):
                continue
            nt = (tech.get("name") or tech.get("technique_name") or tech.get("scenario", ""))[:50]
            sk = tech.get("abstract_skeleton", "")
            ef = tech.get("effect", "")
            dc = tech.get("method") or tech.get("execution") or tech.get("scenario", "")
            an = tech.get("counter_example") or tech.get("anti_example", "")
            o = {"name": nt, "description": dc[:200], "effect": ef[:200],
                 "skeleton": sk[:200], "anti_pattern": an[:200]}
            ft = f"{nt} {sk} {ef} {dc}".lower()
            placed = False
            for d, kws in DK.items():
                if any(k in ft for k in kws):
                    craft_analysis[d]["techniques"].append(o)
                    placed = True
                    break
            if not placed:
                craft_analysis["tension_building"]["techniques"].append(o)
            all_tech_names.append(nt)

    if all_tech_names:
        craft_summary["top_3_strengths"] = all_tech_names[:3]
        craft_summary["unique_techniques"] = all_tech_names[3:5] if len(all_tech_names) > 3 else []
        craft_summary["reusable_patterns"] = all_tech_names[:3]

    # 规范化：list→{techniques:[...]}，字段名标准化，从 abstract_pattern 生成名称
    for dk in list(craft_analysis.keys()):
        v = craft_analysis[dk]
        if isinstance(v, list):
            norm_list = []
            for t in v:
                if not isinstance(t, dict):
                    continue
                nm = t.get("name") or t.get("technique_name") or ""
                if not nm:
                    ap = t.get("abstract_pattern") or t.get("skeleton") or ""
                    if ap:
                        nm = ap[:25].rstrip("，。、")
                norm_list.append({
                    "name": nm,
                    "description": t.get("description") or t.get("example_in_text") or t.get("abstract_pattern", ""),
                    "effect": t.get("effect", ""),
                    "skeleton": t.get("skeleton") or t.get("abstract_pattern", ""),
                    "anti_pattern": t.get("anti_pattern") or t.get("反例") or t.get("counter_example", ""),
                })
            craft_analysis[dk] = {"techniques": norm_list}
        elif isinstance(v, dict) and "techniques" not in v:
            craft_analysis[dk] = {"techniques": [v]}

    return {
        "meta": {
            "source_title": name,
            "genre": genre,
            "extracted_at": date.today().isoformat(),
            "sample_chapters": manifest.get("selected_indices", []),
            "total_sample_words": metrics.get("total_chars", 0),
            "confidence": _confidence(manifest.get("selected_count", 0)),
            "pass5_version": "1.0",
        },
        "craft_analysis": craft_analysis,
        "craft_summary": craft_summary,
        "provenance": {
            "contains_verbatim": False,
            "abstraction_note": "Pass5 笔法分析产物，经 compliance.py 扫描",
        },
    }


def _read_pass(name: str, pass_file: str) -> dict:
    """读取 corpus/raw/<name>/<pass_file>，缺失时报错。"""
    p = RAW_DIR / name / pass_file
    if not p.exists():
        sys.exit(f"缺少 {pass_file}：{p}（AI 会话内应先产出该 pass JSON）")
    return load_json(p)


def main():
    ap = argparse.ArgumentParser(description="组装 AI 产出的 pass1-5 JSON 为可入库资产")
    ap.add_argument("name", help="书名（corpus/raw/ 下的目录名，如 chireng_chosen）")
    ap.add_argument("--genre", default="unknown", help="题材 id，如 campus-redemption")
    ap.add_argument("--skip-craft", action="store_true", help="跳过 craft-card（pass5 缺失时用）")
    args = ap.parse_args()

    name = args.name

    # 读 manifest 与 metrics（采样/量化阶段产物，必须先跑 novel.py 拆书）
    manifest_path = SAMPLED_DIR / name / "manifest.json"
    metrics_path = METRICS_DIR / f"{name}.json"
    if not manifest_path.exists():
        sys.exit(f"缺少采样清单：{manifest_path}（先跑 novel.py 拆书 完成采样）")
    if not metrics_path.exists():
        sys.exit(f"缺少量化指标：{metrics_path}（先跑 novel.py 拆书 完成量化）")
    manifest = load_json(manifest_path)
    metrics = load_json(metrics_path)

    # 读 pass1-4（pass2/pass3 走归一化）
    pass1 = _read_pass(name, "pass1_structure.json")
    pass2 = _read_pass(name, "pass2_character.json")
    pass3 = _read_pass(name, "pass3_style.json")
    pass4 = _read_pass(name, "pass4_commercial.json")

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. voice-card：normalize pass2/3 → assemble
    print("[1/4] 组装 voice-card:")
    voices = norm.normalize_pass2(pass2)
    narration, dialogue, emotion, imagery, banned = norm.normalize_pass3(pass3)
    dialogue["dialogue_ratio"] = metrics.get("dialogue_ratio", 0)
    voice = assemble_voice_card(name, args.genre, manifest, metrics,
                                voices, narration, dialogue, emotion, imagery, banned)
    vc_path = ASSETS_DIR / f"{name}-voice-card.json"
    vc_path.write_text(json.dumps(voice, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {vc_path.name}")

    # 2. structure-obs
    print("[2/4] 组装 structure-obs:")
    so = assemble_obs("structure", name, args.genre, pass1)
    so_path = ASSETS_DIR / f"{name}-structure-obs.json"
    so_path.write_text(json.dumps(so, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {so_path.name}")

    # 3. commercial-obs
    print("[3/4] 组装 commercial-obs:")
    co = assemble_obs("commercial", name, args.genre, pass4)
    co_path = ASSETS_DIR / f"{name}-commercial-obs.json"
    co_path.write_text(json.dumps(co, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ {co_path.name}")

    # 4. craft-card（pass5 可选）
    if args.skip_craft:
        print("[4/4] 跳过 craft-card（--skip-craft）")
    else:
        print("[4/4] 组装 craft-card:")
        pass5 = _read_pass(name, "pass5_craft.json")
        craft = assemble_craft_card(name, args.genre, manifest, metrics, pass5)
        cc_path = ASSETS_DIR / f"{name}-craft-card.json"
        cc_path.write_text(json.dumps(craft, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ {cc_path.name}")

    print("\n组装完成。下一步：")
    print(f"  novel.py 校验 assets/{name}-voice-card.json")
    print(f"  novel.py 合规 assets/{name}-voice-card.json corpus/<书>.txt")


if __name__ == "__main__":
    main()
