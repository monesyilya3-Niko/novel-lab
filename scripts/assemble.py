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
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

import normalize as norm
import compliance as comp
import validate as validate_mod

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


def _clean_verbatim(asset: dict, book_text: str) -> tuple:
    """用 clean_verbatim 的清洗规则清除资产中夹带的原文引用，返回 (清洗后资产, 清洗处数)。

    2026-09-01 集成：组装流程此前不包含清洗，导致 pass2 归一化重新带入原文台词
    （如 refusal_pattern 里的"例如'不弔了…'"），compliance 复扫 REJECT。
    """
    import clean_verbatim as cv
    ngram = comp.build_ngram_index(book_text)
    changed = 0

    def walk(node):
        nonlocal changed
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if isinstance(v, str):
                    cleaned, ch = cv.clean_string(v, ngram, k)
                    if ch:
                        node[k] = cleaned
                        changed += 1
                else:
                    walk(v)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, str):
                    cleaned, ch = cv.clean_string(v, ngram, "")
                    if ch:
                        node[i] = cleaned
                        changed += 1
                else:
                    walk(v)

    walk(asset)
    return asset, changed


def _sample_words(manifest: dict, metrics: dict) -> int:
    """采样字数：优先取 manifest.sample_words（pipeline 生成 manifest 时已算好）。

    2026-09-21 修复：此前一律填 `metrics.total_chars`（**全书**字数），但字段名与
    消费方（report.py 写「采样范围…共 N 字」、report_craft.py 取 words）都要求它是
    **采样**字数 —— 报告因此写着「采样 27 章共 32.8 万字」，自相矛盾。
    老 manifest 无该字段时退回旧行为，保持向后兼容。
    """
    v = manifest.get("sample_words")
    if isinstance(v, int) and v > 0:
        return v
    return metrics.get("total_chars", 0)


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
            "total_sample_words": _sample_words(manifest, metrics),
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
    # 2026-09-01 修复：structure-obs 的 chapter_analyses 若用 title 表达章节（如
    # "第1章 晨光与侧影"）而缺 chapter 字段，从 title 提取章节号补上，
    # 消除 validate 的"缺少 'chapter'"警告（qingning 曾报 22 条）。
    if kind == "structure" and isinstance(body.get("chapter_analyses"), list):
        for c in body["chapter_analyses"]:
            if isinstance(c, dict) and "chapter" not in c and c.get("title"):
                m = re.match(r"第\s*([0-9一二三四五六七八九十百千]+)\s*章", str(c["title"]))
                if m:
                    c["chapter"] = m.group(1)
    # 2026-09-21 修复：commercial-obs 的 common_mistakes 不来自 pass4 输出，
    # 每次重新组装都会静默丢失（sangshi 与 暮冬念春 各踩一次，均靠人工补回）。
    # 此处按同一口径兜底补齐，非新造观察：
    #   优先取 pass4 的 opening_analysis.common_mistakes；
    #   否则由本卡 retention_risk_points 汇总。
    if kind == "commercial" and not body.get("common_mistakes"):
        cm = None
        oa = body.get("opening_analysis")
        if isinstance(oa, dict) and oa.get("common_mistakes"):
            cm = list(oa["common_mistakes"])
        elif isinstance(body.get("retention_risk_points"), list) and body["retention_risk_points"]:
            parts = []
            for x in body["retention_risk_points"]:
                if isinstance(x, dict):
                    pos = x.get("position") or x.get("chapter") or x.get("range") or ""
                    reason = (x.get("reason") or x.get("risk") or x.get("description")
                              or x.get("detail") or "")
                    txt = f"{pos}：{reason}".strip("：") if pos else str(reason)
                    if txt:
                        parts.append(txt)
                elif x:
                    parts.append(str(x))
            cm = parts or None
        if cm:
            body["common_mistakes"] = cm
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
            "total_sample_words": _sample_words(manifest, metrics),
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


# 各类资产的来源 pass 文件（用于记录内容指纹）
SOURCE_PASSES = {
    "voice-card": ["pass2_character.json", "pass3_style.json"],
    "structure-obs": ["pass1_structure.json"],
    "commercial-obs": ["pass4_commercial.json"],
    "craft-card": ["pass5_craft.json"],
}


def source_fingerprint(raw_dir: Path, kind: str) -> dict:
    """计算某类资产来源 pass 文件的内容指纹（sha256 前 16 位）。

    2026-09-21 新增：资产此前只记 `extracted_at`（日期），无法判断「这份资产是从
    哪一版 pass 产出组装的」。`asset_sync_check` 只能用 mtime 做启发式判断 ——
    内容未变但文件被重写就会误报（实测撞到过一次）。指纹是内容级的确定性判据。
    """
    out = {}
    for fname in SOURCE_PASSES.get(kind, []):
        p = raw_dir / fname
        if p.exists():
            out[fname] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return out


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
    # 2026-09-01 集成：组装后自动清洗原文引用（若原文 TXT 存在），
    # 避免 pass2 归一化重新带入原文台词导致 compliance REJECT。
    book_path = ROOT / "corpus" / f"{name}.txt"
    if book_path.exists():
        voice, cleaned = _clean_verbatim(voice, book_path.read_text(encoding="utf-8"))
        if cleaned:
            print(f"  ⚠ 已清洗 {cleaned} 处原文引用（corpus/{name}.txt）")
    # 2026-09-21 总工重构：四类资产**先组装到内存**，校验全通过后才落盘。
    # 此前是「组装一个写一个」，校验在写盘之后——一旦校验失败，磁盘上的旧资产
    # 已被覆盖，只能靠 git / 备份找回。数据安全优先于流程简洁。
    built = []  # [(kind, path, data)]

    built.append(("voice-card", ASSETS_DIR / f"{name}-voice-card.json", voice))

    # 2. structure-obs
    print("[2/4] 组装 structure-obs:")
    built.append(("structure-obs", ASSETS_DIR / f"{name}-structure-obs.json",
                  assemble_obs("structure", name, args.genre, pass1)))

    # 3. commercial-obs
    print("[3/4] 组装 commercial-obs:")
    built.append(("commercial-obs", ASSETS_DIR / f"{name}-commercial-obs.json",
                  assemble_obs("commercial", name, args.genre, pass4)))

    # 4. craft-card（pass5 可选）
    if args.skip_craft:
        print("[4/4] 跳过 craft-card（--skip-craft）")
    else:
        print("[4/4] 组装 craft-card:")
        pass5 = _read_pass(name, "pass5_craft.json")
        built.append(("craft-card", ASSETS_DIR / f"{name}-craft-card.json",
                      assemble_craft_card(name, args.genre, manifest, metrics, pass5)))

    # 4.5 注入来源指纹（2026-09-21）：让资产能自证「来自哪一版 pass 产出」
    raw_dir = RAW_DIR / name
    for kind, _path, data in built:
        meta = data.setdefault("meta", {})
        if isinstance(meta, dict):
            fp = source_fingerprint(raw_dir, kind)
            if fp:
                meta["source_fingerprint"] = fp

    # 5. 内存校验 → 通过才落盘（2026-09-21 总工重构）
    # 组装成功 ≠ 资产合规（commercial-obs 曾因缺字段被静默写盘）；
    # 且校验必须在**写盘之前**，否则失败时磁盘上的旧资产已被覆盖。
    print("\n[5/5] 校验（内存对象，尚未落盘）:")
    failed = []
    for kind, _path, data in built:
        try:
            errs, warns = validate_mod.validate_asset_data(kind, data)
        except Exception as exc:  # 校验器自身异常也算不通过，不静默放过
            failed.append(kind)
            print(f"  {kind:16} 校验器异常: {exc}")
            continue
        if errs:
            failed.append(kind)
            print(f"  {kind:16} REJECT（{len(errs)} 硬错误）")
            for e in errs[:3]:
                print(f"      · {e}")
        else:
            print(f"  {kind:16} PASS（{len(warns)} 警告）" if warns
                  else f"  {kind:16} PASS")

    if failed:
        print(f"\n✗ {len(failed)} 类资产未通过校验：{', '.join(failed)}")
        print("  **已阻止写盘** —— 磁盘上的旧资产保持原样，未被覆盖。")
        print("  请修正对应 pass 产出后重新组装。")
        return 1

    print("\n落盘:")
    for _kind, path, data in built:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ {path.name}")

    print("\n组装完成：四类资产全部通过 schema 校验并已落盘。")
    print("下一步（可选）：")
    print(f"  novel.py 合规 assets/{name}-voice-card.json corpus/<书>.txt")


if __name__ == "__main__":
    sys.exit(main())
