#!/usr/bin/env python3
"""
M2.3 风格一致性自检 — 生成章 vs voice-card 逐维打分
"""
import argparse
import json
import re
import sys
from pathlib import Path

# 直陈式情绪词（出现即扣分）
DIRECT_EMOTION = ["很愤怒", "很生气", "感到难过", "非常开心", "很伤心", "感到害怕",
                  "很紧张", "很幸福", "很沮丧", "很兴奋", "很失落", "很委屈"]

# 视角标记
POV_MARKERS = ["他", "她", "她和他", "他心里", "她心里"]

def extract_keywords(desc: str, max_kws: int = 8) -> list:
    """从声线卡描述中提取可匹配的关键词"""
    kws = []
    # 使用简单的字符串匹配，而不是正则表达式
    if len(desc) >= 2 and len(desc) <= 10:
        kws.append(desc)
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
        details.append(f"  {name}: 命中 {hit}/{len(kws)} 核心词({kws[:4]}) → {score:.1f}/{per:.0f}")
    return min(total, 35), details

def check_emotion(text, emotion):
    """情绪写法"""
    sensation_words = [
        "心跳", "呼吸", "手指", "手心", "掌心", "喉咙", "眼眶", "鼻尖", "耳根", "脖子",
        "后背", "肩膀", "膝盖", "脚趾", "指尖", "脉搏", "太阳穴", "胸口", "胃里", "肚子",
        "发紧", "发酸", "发麻", "发凉", "发烫", "发热", "发抖", "发软", "发硬", "发胀",
        "渗出", "冒出", "涌起", "收紧", "松开", "攥紧", "掐住", "捏住", "握住", "抱住",
        "凉凉的", "暖暖的", "热热的", "冰冰的", "辣辣的", "咸咸的", "甜甜的", "酸酸的",
        "沙沙的", "嗡嗡的", "咚咚的", "砰砰的", "啪啪的", "哗哗的", "淅淅的", "簌簌的"
    ]
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
    details = [f"  体感词命中 {hit_sensation} 个(+{sensation_score}), 直陈式情绪词 {hit_direct} 个(-{direct_penalty}) → {score:.1f}/20"]
    return score, details

def check_narration(text, narration):
    """叙述层"""
    score = 0
    details = []
    pov_markers = POV_MARKERS
    hit_pov = sum(1 for m in pov_markers if m in text)
    if hit_pov > 0:
        score += 5
        details.append("  视角第三人称 ✓(+5)")
    else:
        details.append("  视角第三人称 ✗(+0)")
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
    """禁忌词"""
    if not banned:
        return 20, ["  禁忌词表为空，跳过检查"]
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
    """意象"""
    if not imagery:
        return 3, ["  意象表为空，给基础分"]
    domains = [
        "天气", "季节", "光线", "声音", "气味", "味道", "触感",
        "植物", "动物", "水", "火", "风", "雪", "雨", "云",
        "道路", "建筑", "房间", "窗户", "门", "镜子", "照片",
        "音乐", "颜色", "数字", "时间", "记忆", "梦境"
    ]
    hit_domains = []
    for domain in domains:
        if domain in text:
            hit_domains.append(domain)
    if len(hit_domains) == 0:
        score = 3
    elif len(hit_domains) <= 2:
        score = 6
    else:
        score = 10
    return score, [f"  意象领域命中 {len(hit_domains)} 个 → {score}/10"]

def consistency_check(voice_card_path: str, chapter_path: str):
    """主函数：一致性打分。"""
    voice_card = json.loads(Path(voice_card_path).read_text(encoding="utf-8"))
    chapter_text = Path(chapter_path).read_text(encoding="utf-8")
    voices = voice_card.get("dialogue", {}).get("character_voices", [])
    emotion = voice_card.get("emotion", {})
    narration = voice_card.get("narration", {})
    banned = voice_card.get("banned_words", [])
    imagery = voice_card.get("imagery", {})
    voice_score, voice_details = check_voices(chapter_text, voices)
    emotion_score, emotion_details = check_emotion(chapter_text, emotion)
    narration_score, narration_details = check_narration(chapter_text, narration)
    banned_score, banned_details = check_banned(chapter_text, banned)
    imagery_score, imagery_details = check_imagery(chapter_text, imagery)
    total_score = voice_score + emotion_score + narration_score + banned_score + imagery_score
    print(f"=== 风格一致性自检 ===")
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="风格一致性自检")
    parser.add_argument("voice", help="voice-card JSON 文件路径")
    parser.add_argument("chapter", help="生成章文件路径")
    args = parser.parse_args()
    consistency_check(args.voice, args.chapter)


def score_text(voice_card: dict, text: str, label: str = ""):
    """供 novel.py 调用的接口：返回 (score, details, raw)"""
    # 提取voice-card中的各个维度
    voices = voice_card.get("dialogue", {}).get("character_voices", [])
    emotion = voice_card.get("emotion", {})
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
        "imagery": imagery_score
    }

    return total_score, details, raw
