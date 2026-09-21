#!/usr/bin/env python3
"""
M2.3 风格一致性自检 — 生成章 vs voice-card 逐维打分
"""
import argparse
import json
import sys
from pathlib import Path

# 直陈式情绪词（出现即扣分）
DIRECT_EMOTION = ["很愤怒", "很生气", "感到难过", "非常开心", "很伤心", "感到害怕",
                  "很紧张", "很幸福", "很沮丧", "很兴奋", "很失落", "很委屈"]

# 视角标记
POV_MARKERS = ["他", "她", "她和他", "他心里", "她心里"]

def extract_keywords(desc: str, max_kws: int = 8) -> list:
    """从声线卡描述中提取可匹配的关键词。

    2026-09-05 修复（B2）：原先只收录 len<=10 的整段字符串——导致
    refusal_pattern/anger_pattern 这类长描述永远不会进入核心词集合。
    现对长描述改为抽取其中引号片段（「…」/''/""/“…”）作为关键词；
    短字符串（≤10 字）仍整段收录；无引号片段的长描述跳过。
    """
    kws = []
    if len(desc) >= 2 and len(desc) <= 10:
        kws.append(desc)
    else:
        # 长描述：抽取引号内的具体词语作为可匹配关键词
        for op, cl in [("「", "」"), ("『", "』"), ("“", "”"), ("‘", "’"), ('"', '"'), ("'", "'")]:
            start = 0
            while True:
                i = desc.find(op, start)
                if i < 0:
                    break
                j = desc.find(cl, i + len(op))
                if j < 0:
                    break
                frag = desc[i + len(op):j].strip()
                if 2 <= len(frag) <= 10:
                    kws.append(frag)
                start = j + len(cl)
    return kws[:max_kws]

def _vt_to_str(item) -> str:
    """verbal_tics 元素可能是字符串或 dict，统一转字符串。"""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        ctx = item.get("情境") or item.get("context") or item.get("场景") or ""
        rule = item.get("规则") or item.get("rule") or ""
        if ctx and rule:
            return f"{ctx}：{rule}"
        return ctx or rule or str(item)
    return str(item)

def check_voices(text, voices):
    """角色声线执行度"""
    present = []
    for v in voices:
        name = v.get("name", "")
        if name and (name in text or (len(name) >= 2 and name[:2] in text)):
            present.append(v)
    if not present:
        return 0.0, ["  本章无角色出场，无法检查声线"]
    per = 35 / len(present)
    total = 0
    details = []
    for v in present:
        ss = v.get("speech_signature") or {}
        name = v.get("name", "?")
        kws = []
        for t in ss.get("verbal_tics", []):
            kws.extend(extract_keywords(_vt_to_str(t)))
        for field in ("refusal_pattern", "anger_pattern"):
            val = ss.get(field)
            if isinstance(val, str):
                kws.extend(extract_keywords(val))
        kws = list(dict.fromkeys(kws))
        hit = sum(1 for k in kws if k and k in text)
        if not kws:
            score = round(per * 0.5, 1)
        elif hit == 0:
            score = 0.0
        elif hit >= len(kws) or (len(kws) >= 2 and hit >= len(kws) * 0.5):
            score = round(per, 1)
        elif hit == 1:
            score = round(per * 0.7, 1)
        else:
            score = round(per * 0.85, 1)
        total += score
        # 分子分母必须同精度：per 常为分数（如 35/13=2.6923），若分母按 :.0f
        # 显示成「3」而分子按 :.1f 显示成「2.7」，满分角色会被下游
        # qc._detail_is_meaningful_issue 误判为「低于满分」并记假 issue。
        details.append(f"  {name}: 命中 {hit}/{len(kws)} 核心词({kws[:4]}) → {score:.1f}/{per:.1f}")
    return min(total, 35), details

def check_emotion(text, emotion):
    """情绪写法。

    2026-09-05 修复（B1-情绪）：体感词表改为「资产词表 ∪ 内置兜底」——
    优先使用 voice-card.emotion_handling.body_reaction_vocabulary 的真实资产词，
    内置 58 词仅作兜底（保证无资产词时敏感性不回退）。
    """
    asset_words = []
    if isinstance(emotion, dict):
        asset_words = [w for w in (emotion.get("body_reaction_vocabulary") or [])
                       if isinstance(w, str) and len(w) >= 2]
    sensation_words = list(dict.fromkeys(asset_words + [
        "心跳", "呼吸", "手指", "手心", "掌心", "喉咙", "眼眶", "鼻尖", "耳根", "脖子",
        "后背", "肩膀", "膝盖", "脚趾", "指尖", "脉搏", "太阳穴", "胸口", "胃里", "肚子",
        "发紧", "发酸", "发麻", "发凉", "发烫", "发热", "发抖", "发软", "发硬", "发胀",
        "渗出", "冒出", "涌起", "收紧", "松开", "攥紧", "掐住", "捏住", "握住", "抱住",
        "凉凉的", "暖暖的", "热热的", "冰冰的", "辣辣的", "咸咸的", "甜甜的", "酸酸的",
        "沙沙的", "嗡嗡的", "咚咚的", "砰砰的", "啪啪的", "哗哗的", "淅淅的", "簌簌的"
    ]))
    direct_emotion_words = DIRECT_EMOTION
    hit_sensation = sum(1 for w in sensation_words if w in text)
    hit_direct = sum(1 for w in direct_emotion_words if w in text)
    if hit_sensation == 0:
        sensation_score = 0
    elif hit_sensation <= 3:
        sensation_score = 15
    else:
        sensation_score = 20
    direct_penalty = min(hit_direct * 2, 10)
    score = max(0, sensation_score - direct_penalty)
    src = f"（资产词 {len(asset_words)} + 兜底）" if asset_words else "（内置兜底）"
    details = [f"  体感词命中 {hit_sensation} 个{src}(+{sensation_score}), 直陈式情绪词 {hit_direct} 个(-{direct_penalty}) → {score:.1f}/20"]
    return score, details

def check_narration(text, narration):
    """叙述层。

    2026-09-05 修复（B1-叙述）：视角检查读资产 narration.pov——
    「第三人称」→ 检查「他/她」；「第一人称」→ 检查「我」；缺失 → 维持旧行为。
    该项由"恒真"变为"与资产声明一致才得分"。
    """
    score = 0
    details = []
    pov = ""
    if isinstance(narration, dict):
        pov = str(narration.get("pov") or "")
    if "第一人称" in pov:
        pov_markers = ["我", "我们"]
        pov_label = "第一人称"
    else:
        # 资产缺失或声明第三人称 → 检查第三人称标记
        pov_markers = POV_MARKERS
        pov_label = pov or "第三人称"
    hit_pov = sum(1 for m in pov_markers if m in text)
    if hit_pov > 0:
        score += 5
        details.append(f"  视角{pov_label} ✓(+5)")
    else:
        details.append(f"  视角{pov_label} ✗(+0)")
    lines = [l.strip() for l in text.split(chr(10)) if l.strip()]
    short_streak = 0
    max_streak = 0
    for line in lines:
        if len(line) <= 10:
            short_streak += 1
            max_streak = max(max_streak, short_streak)
        else:
            short_streak = 0
    if max_streak >= 3:
        score += 5
        details.append(f"  短句爆发 {max_streak} 连续 ✓(+5)")
    else:
        details.append(f"  短句爆发 {max_streak} 连续(+0)")
    single_sentence_paragraphs = 0
    for line in lines:
        if len(line) <= 20 and not any(p in line for p in ['。', '！', '？', '……']):
            single_sentence_paragraphs += 1
    if single_sentence_paragraphs >= 5:
        score += 5
        details.append(f"  单句成段 {single_sentence_paragraphs} 段 ✓(+5)")
    else:
        details.append(f"  单句成段 {single_sentence_paragraphs} 段(+0)")
    return score, details

def check_banned(text, banned):
    """禁忌词。

    ⚠️ 产品决策留档（2026-09-02 用户确认，勿当 bug 修复）：
    禁忌不做拦截——真实禁忌数据在 voice-card.banned.never_used_words 与
    genre-pack.language_rules.banned_phrases，写作时靠 inject 注入的 prompt
    约束，不靠评分拦截。本函数读到的顶层 banned_words 为 null → 跳过给满分，
    属预期行为。
    """
    if not banned:
        return 20, ["  禁忌词表为空，跳过检查（决策留档：禁忌不拦截，2026-09-02 确认）"]
    hit_banned = []
    for word in banned:
        if word in text:
            hit_banned.append(word)
    if not hit_banned:
        return 20, ["  禁忌词命中 0 个 → 20/20"]
    else:
        penalty = min(len(hit_banned) * 5, 20)
        score = max(0, 20 - penalty)
        return score, [f"  禁忌词命中 {len(hit_banned)} 个({hit_banned[:3]}) → {score}/20"]

def check_imagery(text, imagery):
    """意象。

    2026-09-05 修复（B1-意象）：领域表改为「资产领域 ∪ 内置兜底」——
    优先使用 voice-card.imagery.high_freq_metaphor_domains 的真实取材领域，
    按资产命中数给分；内置 28 领域仅兜底。权重不变（0→3, 1-2→6, ≥3→10）。
    """
    asset_domains = []
    if isinstance(imagery, dict):
        asset_domains = [d for d in (imagery.get("high_freq_metaphor_domains") or [])
                         if isinstance(d, str) and len(d) >= 2]
    domains = list(dict.fromkeys(asset_domains + [
        "天气", "季节", "光线", "声音", "气味", "味道", "触感",
        "植物", "动物", "水", "火", "风", "雪", "雨", "云",
        "道路", "建筑", "房间", "窗户", "门", "镜子", "照片",
        "音乐", "颜色", "数字", "时间", "记忆", "梦境"
    ]))
    hit_domains = []
    for domain in domains:
        if domain in text:
            hit_domains.append(domain)
    asset_hits = sum(1 for d in asset_domains if d in text)
    if len(hit_domains) == 0:
        score = 3
    elif len(hit_domains) <= 2:
        score = 6
    else:
        score = 10
    src = f"，含资产领域 {asset_hits} 个" if asset_domains else ""
    return score, [f"  意象领域命中 {len(hit_domains)} 个{src} → {score}/10"]

def consistency_check(voice_card_path: str, chapter_path: str):
    """主函数：一致性打分。"""
    voice_card = json.loads(Path(voice_card_path).read_text(encoding="utf-8"))
    chapter_text = Path(chapter_path).read_text(encoding="utf-8")
    voices = voice_card.get("dialogue", {}).get("character_voices", [])
    emotion = voice_card.get("emotion_handling", {})
    narration = voice_card.get("narration", {})
    banned = voice_card.get("banned_words", [])
    imagery = voice_card.get("imagery", {})
    voice_score, voice_details = check_voices(chapter_text, voices)
    emotion_score, emotion_details = check_emotion(chapter_text, emotion)
    narration_score, narration_details = check_narration(chapter_text, narration)
    banned_score, banned_details = check_banned(chapter_text, banned)
    imagery_score, imagery_details = check_imagery(chapter_text, imagery)
    total_score = voice_score + emotion_score + narration_score + banned_score + imagery_score
    print("=== 风格一致性自检 ===")
    print(f"章: {Path(chapter_path).name} ({len(chapter_text)} 字)")
    print()
    print(f"[1] 角色声线 (35): {voice_score:.1f}")
    for d in voice_details:
        print(d)
    print(f"[2] 情绪写法 (20): {emotion_score:.1f}")
    for d in emotion_details:
        print(d)
    print(f"[3] 叙述层 (15): {narration_score:.1f}")
    for d in narration_details:
        print(d)
    print(f"[4] 禁忌 (20): {banned_score:.1f}")
    for d in banned_details:
        print(d)
    print(f"[5] 意象 (10): {imagery_score:.1f}")
    for d in imagery_details:
        print(d)
    print()
    print(f"=== 总分: {total_score:.1f}/100 ===")
    if total_score >= 75:
        print("✅ PASS（≥75，符合要求）")
    elif total_score >= 60:
        print("⚠️ WARN（60-75，建议人工润色）")
    else:
        print("❌ FAIL（<60，需要修改）")
    return {
        "score": total_score,
        "voice": voice_score,
        "emotion": emotion_score,
        "narration": narration_score,
        "banned": banned_score,
        "imagery": imagery_score
    }

def main(argv=None) -> int:
    """CLI 入口：风格一致性自检。

    2026-09-21 新增退出码语义 —— 此前只打印诊断、进程恒返回 0，无法用于
    CI 或上层脚本判断。现按阈值给判定：达标返回 0，未达标返回 1。

    阈值默认 75，与 novel-lab 其余维度保持一致（chapter_check / qc 的 PASS 线），
    可用 --threshold 覆盖。
    """
    parser = argparse.ArgumentParser(description="风格一致性自检")
    parser.add_argument("voice", help="voice-card JSON 文件路径")
    parser.add_argument("chapter", help="生成章文件路径")
    parser.add_argument("--threshold", type=float, default=75.0,
                        help="PASS 阈值（默认 75，与 chapter_check / qc 一致）")
    args = parser.parse_args(argv)
    result = consistency_check(args.voice, args.chapter)  # 返回 dict：score/voice/emotion/…
    total = float(result["score"])
    ok = total >= args.threshold
    print()
    print(f"CLI 判定: {'PASS' if ok else 'FAIL'}"
          f"（阈值 {args.threshold:g}，总分 {total:.1f}）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())


def score_text(voice_card: dict, text: str, label: str = ""):
    """供 novel.py 调用的接口：返回 (score, details, raw)"""
    # 提取voice-card中的各个维度
    voices = voice_card.get("dialogue", {}).get("character_voices", [])
    emotion = voice_card.get("emotion_handling", {})
    narration = voice_card.get("narration", {})
    banned = voice_card.get("banned_words", [])
    imagery = voice_card.get("imagery", {})

    # 各维度打分
    voice_score, voice_details = check_voices(text, voices)
    emotion_score, emotion_details = check_emotion(text, emotion)
    narration_score, narration_details = check_narration(text, narration)
    banned_score, banned_details = check_banned(text, banned)
    imagery_score, imagery_details = check_imagery(text, imagery)

    total_score = voice_score + emotion_score + narration_score + banned_score + imagery_score

    details = []
    details.append(f"章: {label} ({len(text)} 字)")
    details.append(f"[1] 角色声线 (35): {voice_score:.1f}")
    details.extend(voice_details)
    details.append(f"[2] 情绪写法 (20): {emotion_score:.1f}")
    details.extend(emotion_details)
    details.append(f"[3] 叙述层 (15): {narration_score:.1f}")
    details.extend(narration_details)
    details.append(f"[4] 禁忌 (20): {banned_score:.1f}")
    details.extend(banned_details)
    details.append(f"[5] 意象 (10): {imagery_score:.1f}")
    details.extend(imagery_details)
    details.append(f"总分: {total_score:.1f}/100")

    raw = {
        "voice": voice_score,
        "emotion": emotion_score,
        "narration": narration_score,
        "banned": banned_score,
        "imagery": imagery_score,
        # 逐角色声线明细同时被 character_arc 维度消费，单独回传以便下游去重，
        # 避免同一条问题在 character_arc 与 craft 两个维度各记一次。
        "voice_details": list(voice_details)
    }

    return total_score, details, raw
