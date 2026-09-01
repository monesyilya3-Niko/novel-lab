#!/usr/bin/env python3
"""
章节质量自检 — 独立于 voice-card 的章节本身质量评分

检查维度（共 100 分）：
  1. 字数（8）— ≥1500 满分，<1000 零分
  2. 对话占比（12）— 15-40% 满分，<5% 或 >60% 扣分
  3. 章末钩子（12）— 有悬念/断句/情感冲击/反转
  4. 开头吸引力（8）— 前 200 字是否有冲突/悬念/场景
  5. 情绪密度（12）— 每 400 字≥1 处体感词
  6. 直陈式情绪词（8）— 零出现满分
  7. 段落节奏（8）— 短段(≤15字)占比 10-40% 满分
  8. 结构完整性（8）— 有开头/发展/收束
  9. AI 味检测（4）— 高频模板句式扣分
  10. 疲劳词检测（8）— "了"字密度/情绪标签词/连接词滥用（借鉴 novel-deconstruct）
  11. 让字专项（5）— "让"字过多 = AI味重灾区
  12. 情绪标签词（7）— 区分对话/旁白中的情绪标签词滥用

用法:
  python chapter_check.py <章节.txt> [--genre-pack genre-pack.json]
  → 输出 JSON: {"score": 85, "details": [...], "issues": [...], "verdict": "PASS"}
"""
import argparse
import json
import re
import sys
from pathlib import Path

# 直陈式情绪词（出现即扣分）
DIRECT_EMOTION = ["很愤怒", "很生气", "感到难过", "非常开心", "很伤心", "感到害怕",
                  "很紧张", "很幸福", "很沮丧", "很兴奋", "很失落", "很委屈",
                  "非常愤怒", "非常难过", "感到高兴", "感到幸福"]

# 体感词库
BODY_WORDS = ["心跳", "指尖", "耳根", "脊背", "手心", "喉结", "呼吸", "发烫", "发麻",
              "冰凉", "发白", "发红", "发酸", "发抖", "发紧", "发软", "发沉", "发热",
              "额头", "鼻尖", "嘴唇", "膝盖", "脚踝", "肩膀", "后背", "胸口", "小腹",
              "掌心", "指节", "手腕", "脚趾", "脖子", "下巴", "眉心", "太阳穴"]

# 钩子关键词（章末 200 字内出现 = 有钩子）
HOOK_KEYWORDS = [
    r"[。！？]\s*$",  # 以句末标点结束（弱钩子）
    r"[…]{1,3}",  # 省略号（悬念）
    r"忽然|突然|猛然|骤然",  # 突发事件
    r"门.*开了|电话.*响|手机.*响|有人.*敲",  # 中断/引入
    r"她不知道|他不知道|谁也没想到",  # 悬念
    r"转身|回头|推门|拉开|站起",  # 动作钩子
    r"明天|以后|从此|那天起",  # 时间钩子
]

# AI 味模板句式
AI_TICS = [
    (r"她不知道，[^。]{5,30}(会|将|要)[^。]{3,20}", "作者预告旁白"),
    (r"那个画面浮现在脑海[:：]", "记忆闪回模板"),
    (r"像一道小小的伤口", "伤口比喻模板"),
    (r"镀了一层很薄的金色", "金色轮廓模板"),
    (r"不需要说很多话[。]", "沉默模板"),
    (r"在就够了[。]", "存在模板"),
    (r"她深吸一口气，[^。]{5,15}不知道", "深呼吸+不知道模板"),
]


def check_word_count(text: str) -> tuple:
    """1. 字数检查（10 分）"""
    cn = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    if cn >= 1500:
        return 10, f"字数 {cn} ✓"
    elif cn >= 1200:
        return 7, f"字数 {cn}（略短）"
    elif cn >= 1000:
        return 4, f"字数 {cn}（偏短）"
    else:
        return 0, f"字数 {cn}（严重不足）"


def check_dialogue_ratio(text: str) -> tuple:
    """2. 对话占比（15 分）"""
    # 统计引号内文本
    quotes = re.findall(r'["\u201c\u201d]([^"\u201c\u201d]{1,})["\u201c\u201d]', text)
    dialogue_chars = sum(len(q) for q in quotes)
    total = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    if total == 0:
        return 0, "无文本"
    ratio = dialogue_chars / total

    if 0.15 <= ratio <= 0.40:
        return 15, f"对话占比 {ratio:.1%} ✓"
    elif 0.10 <= ratio < 0.15:
        return 10, f"对话占比 {ratio:.1%}（略低）"
    elif 0.40 < ratio <= 0.55:
        return 10, f"对话占比 {ratio:.1%}（略高）"
    elif ratio < 0.05:
        return 3, f"对话占比 {ratio:.1%}（几乎无对话）"
    elif ratio > 0.60:
        return 5, f"对话占比 {ratio:.1%}（对话过多）"
    else:
        return 8, f"对话占比 {ratio:.1%}"


def check_hook(text: str) -> tuple:
    """3. 章末钩子（15 分）"""
    tail = text[-300:] if len(text) > 300 else text
    score = 0
    notes = []

    # 检查钩子关键词
    for pat in HOOK_KEYWORDS:
        if re.search(pat, tail):
            score += 3
            notes.append(pat[:15])
            if score >= 15:
                break

    # 检查章末是否有有效收束（非截断）
    last_line = [l.strip() for l in text.split('\n') if l.strip()][-1] if text.strip() else ""
    if last_line and re.search(r'[。！？…"\u201d]$', last_line):
        score = min(score + 2, 15)
        notes.append("有效收束")
    elif last_line and len(last_line) > 4:
        score = max(score - 3, 0)
        notes.append("截断风险")

    score = min(score, 15)
    return score, f"钩子 {score}/15: {', '.join(notes[:3])}"


def check_opening(text: str) -> tuple:
    """4. 开头吸引力（10 分）"""
    opening = text[:400] if len(text) > 400 else text
    score = 0
    notes = []

    # 场景建立（有具体地点/时间/动作）
    if re.search(r'(教室|走廊|操场|宿舍|食堂|图书馆|医院|车站|家里)', opening):
        score += 3
        notes.append("场景建立")
    # 冲突/悬念引入
    if re.search(r'(吵架|争执|矛盾|意外|突然|忽然|紧张|害怕|担心)', opening):
        score += 3
        notes.append("冲突引入")
    # 对话开场
    if re.search(r'["\u201c].{2,20}["\u201d]', opening[:200]):
        score += 2
        notes.append("对话开场")
    # 动作开场
    if re.search(r'(走|跑|坐|站|推|拉|抓|拿|看|听)', opening[:100]):
        score += 2
        notes.append("动作开场")

    score = min(score, 10)
    return score, f"开头 {score}/10: {', '.join(notes)}"


def check_emotion_density(text: str) -> tuple:
    """5. 情绪密度（15 分）— 每 400 字≥1 处体感词"""
    cn = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    if cn == 0:
        return 0, "无文本"

    hits = 0
    for w in BODY_WORDS:
        hits += text.count(w)

    expected = max(1, cn // 400)
    ratio = hits / expected if expected > 0 else 0

    if ratio >= 1.0:
        return 15, f"体感词 {hits} 处（期望≥{expected}）✓"
    elif ratio >= 0.7:
        return 10, f"体感词 {hits} 处（期望≥{expected}，略少）"
    elif ratio >= 0.4:
        return 5, f"体感词 {hits} 处（期望≥{expected}，偏少）"
    else:
        return 0, f"体感词 {hits} 处（期望≥{expected}，严重不足）"


def check_direct_emotion(text: str) -> tuple:
    """6. 直陈式情绪词（10 分）— 零出现满分"""
    hits = sum(1 for w in DIRECT_EMOTION if w in text)
    if hits == 0:
        return 10, "直陈式情绪词 0 ✓"
    elif hits <= 2:
        return 5, f"直陈式情绪词 {hits} 个（扣 5 分）"
    else:
        return 0, f"直陈式情绪词 {hits} 个（严重扣分）"


def check_paragraph_rhythm(text: str) -> tuple:
    """7. 段落节奏（10 分）— 短段占比"""
    paras = [p.strip() for p in text.split('\n') if p.strip()]
    if not paras:
        return 0, "无段落"
    short = sum(1 for p in paras if len(p) <= 15)
    ratio = short / len(paras)

    if 0.10 <= ratio <= 0.40:
        return 10, f"短段占比 {ratio:.1%} ✓"
    elif 0.05 <= ratio < 0.10:
        return 7, f"短段占比 {ratio:.1%}（略少）"
    elif 0.40 < ratio <= 0.55:
        return 7, f"短段占比 {ratio:.1%}（略多）"
    elif ratio > 0.55:
        return 3, f"短段占比 {ratio:.1%}（过度精炼）"
    else:
        return 5, f"短段占比 {ratio:.1%}（段落过长）"


def check_structure(text: str) -> tuple:
    """8. 结构完整性（10 分）— 有开头/发展/收束"""
    paras = [p.strip() for p in text.split('\n') if p.strip()]
    if len(paras) < 3:
        return 0, "段落过少"
    score = 0
    notes = []

    # 开头（前 1/4 有场景/人物引入）
    opening = '\n'.join(paras[:max(1, len(paras)//4)])
    if len(opening) > 50:
        score += 3
        notes.append("有开头")

    # 发展（中段有变化/推进）
    mid = '\n'.join(paras[len(paras)//4:3*len(paras)//4])
    if len(mid) > 100:
        score += 4
        notes.append("有发展")

    # 收束（后 1/4 有明确结尾）
    ending = '\n'.join(paras[3*len(paras)//4:])
    if len(ending) > 30 and re.search(r'[。！？…"\u201d]', ending[-50:]):
        score += 3
        notes.append("有收束")

    return score, f"结构 {score}/10: {', '.join(notes)}"


def check_ai_tics(text: str) -> tuple:
    """9. AI 味检测（5 分）— 高频模板句式扣分"""
    score = 5
    notes = []
    for pat, label in AI_TICS:
        matches = re.findall(pat, text)
        if matches:
            score -= 1
            notes.append(f"{label}({len(matches)})")

    score = max(score, 0)
    return score, f"AI味 {score}/4: {', '.join(notes) if notes else '无 ✓'}"


def check_fatigue_words(text: str) -> tuple:
    """10. 疲劳词检测（8 分）— 借鉴 novel-deconstruct 的 6 类疲劳词"""
    cn = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    if cn == 0:
        return 0, "无文本"

    # "了"字密度（deconstruct 核心指标）
    le_count = text.count('了')
    le_density = le_count / (cn / 1000) if cn > 0 else 0

    # 情绪标签词（对话/旁白中的情绪标签）
    emotion_tags = ['紧张', '害怕', '开心', '难过', '生气', '担心', '兴奋', '感动', '委屈']
    tag_count = sum(text.count(w) for w in emotion_tags)

    # 连接词滥用
    connectors = ['突然', '忽然', '忽然间', '就在这时', '正在这时']
    conn_count = sum(text.count(w) for w in connectors)

    # 感叹词
    exclamations = ['啊', '呀', '哇', '唉', '哎']
    excl_count = sum(text.count(w) for w in exclamations)

    score = 8
    notes = []

    if le_density > 8:
        score -= 3
        notes.append(f"了字密度 {le_density:.1f}/千字（过高）")
    elif le_density > 5:
        score -= 1
        notes.append(f"了字密度 {le_density:.1f}/千字（略高）")

    if tag_count > cn / 200:
        score -= 2
        notes.append(f"情绪标签词 {tag_count} 处（过多）")

    if conn_count > 5:
        score -= 1
        notes.append(f"连接词 {conn_count} 处（过多）")

    score = max(score, 0)
    return score, f"疲劳词 {score}/8: {', '.join(notes) if notes else '无异常 ✓'}"


def check_rang_character(text: str) -> tuple:
    """11. "让"字专项（5 分）— "让"字过多 = AI味重灾区"""
    rang_count = text.count('让')
    cn = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    density = rang_count / (cn / 1000) if cn > 0 else 0

    if density <= 1:
        return 5, f"让字 {rang_count} 处 ✓"
    elif density <= 2:
        return 3, f"让字 {rang_count} 处（略多）"
    else:
        return 0, f"让字 {rang_count} 处（过多，AI味重灾区）"


def check_emotion_tags(text: str) -> tuple:
    """12. 情绪标签词滥用（7 分）— 区分对话/旁白"""
    # 旁白中的情绪标签词（AI味重灾区）
    narrator_tags = ['她感到', '他感到', '她觉得', '他觉得', '她意识到', '他意识到',
                     '她忽然感到', '他忽然感到', '她不禁感到', '她内心']
    tag_count = sum(text.count(w) for w in narrator_tags)

    if tag_count == 0:
        return 7, "旁白情绪标签 0 ✓"
    elif tag_count <= 2:
        return 4, f"旁白情绪标签 {tag_count} 处（略多）"
    else:
        return 0, f"旁白情绪标签 {tag_count} 处（AI味重灾区）"


def chapter_check(text: str, genre_pack: dict = None) -> dict:
    """综合章节质量检查，返回评分报告。"""
    checks = [
        check_word_count(text),       # 8分
        check_dialogue_ratio(text),   # 12分
        check_hook(text),             # 12分
        check_opening(text),          # 8分
        check_emotion_density(text),  # 12分
        check_direct_emotion(text),   # 8分
        check_paragraph_rhythm(text), # 8分
        check_structure(text),        # 8分
        check_ai_tics(text),          # 4分
        check_fatigue_words(text),    # 8分
        check_rang_character(text),   # 5分
        check_emotion_tags(text),     # 7分
    ]

    total = min(sum(s for s, _ in checks), 100)  # 上限 100
    details = [d for _, d in checks]
    issues = []
    for s, d in checks:
        if s == 0 or ("偏短" in d and "严重" not in d):
            continue
        if "严重" in d or "不足" in d or "截断" in d:
            issues.append(d)

    # 判定
    if total >= 80:
        verdict = "PASS"
    elif total >= 65:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    return {
        "score": total,
        "max_score": 100,
        "verdict": verdict,
        "details": details,
        "issues": issues,
    }


def main():
    ap = argparse.ArgumentParser(description="章节质量自检（100 分制）")
    ap.add_argument("chapter", help="章节文件路径")
    ap.add_argument("--genre-pack", help="题材包 JSON（可选，用于附加检查）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = ap.parse_args()

    ch_path = Path(args.chapter)
    if not ch_path.exists():
        sys.exit(f"文件不存在: {ch_path}")

    text = ch_path.read_text(encoding="utf-8")
    gp = None
    if args.genre_pack:
        gp = json.loads(Path(args.genre_pack).read_text(encoding="utf-8"))

    result = chapter_check(text, gp)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"章节质量检查: {ch_path.name}")
        print(f"{'='*50}")
        print(f"总分: {result['score']}/100 ({result['verdict']})")
        print()
        for d in result['details']:
            print(f"  {d}")
        if result['issues']:
            print()
            print("需改进:")
            for i in result['issues']:
                print(f"  ⚠ {i}")

    sys.exit(0 if result['verdict'] == "PASS" else 1)


if __name__ == "__main__":
    main()
