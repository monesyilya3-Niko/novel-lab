"""去 AI 味检测与诊断服务（Deslop Diagnostic Service）。

纯 Python 标准库实现，严格遵循项目规范（零第三方依赖）。
针对中文网文核心痛点：
1. 假大空与玄虚修辞（Hollow Rhetoric）
2. 同义反复与冗余句式（Tautology）
3. 直陈式情绪宣泄而非具体描写（Direct Emotion Telling）
4. 口癖俗套转折词与模板动作（AI Tics & Connectors）
5. 被动句与「让」字泛滥（Passive & Rang Overuse）
6. 无由排比与连续同构句式（Parallel Structure）
"""

from __future__ import annotations

import re
from typing import Any

# 1. 假大空/玄虚修辞模板
HOLLOW_RHETORIC_PATTERNS = [
    (r"这一刻[，,]?(?:时间|空气|呼吸)?仿佛(?:凝固|停止|静止)了?", "时间凝固模板", "改为描写周围人物动作的戛然而止或具体的微观声响。"),
    (r"天地(?:之间|间)?仿佛只剩(?:下|下了)?", "天地只剩模板", "改为着眼于两人的目光交锋、距离感或周遭真实的背景环境。"),
    (r"命运的齿轮(?:在这一刻|开始|悄然)?转动", "命运齿轮滥用", "网文严重俗套烂梗，建议删除该句，直接推进现实事件。"),
    (r"仿佛跨越了(?:千山万水|几个世纪|漫长的岁月|时光)", "时空跨越虚辞", "虚化时空不如直接描写眼神变迁或身体记忆。"),
    (r"像一道小小的伤口", "伤口比喻模板", "典型 AI 伤感套路，建议具象化为实际的不甘或迟疑。"),
    (r"镀上了一层(?:淡淡的|很薄的)?(?:金|银|月)?光", "镀金镀光模板", "过于程式化的光影描写，可换成更日常的场景反光或略去。"),
    (r"不知为何[，,]?心底(?:忽然|猛然)?涌起一股", "无由情绪涌起", "情绪必须有前置视听刺激触发，勿凭空涌起。"),
    (r"眼底(?:闪过|掠过)(?:一丝|一抹)?(?:复杂的|冰冷的|凌厉的)?(?:神色|光芒|暗芒)?", "眼底复杂神色套路", "网文严重泛滥的套路眼部特写，改为动作、呼吸或微表情描写。"),
    (r"宛如(?:一[只头尊])?断了线的风筝", "断线风筝俗套", "换为实打实的重物坠落受击体感（如后背撞裂青砖、喉头腥甜）。"),
    (r"(?:不可置否|毋庸置疑|显而易见地?)", "说明文论调侵蚀", "小说叙事切忌议论文说教词汇，通过现场事实让读者自行得出结论。"),
]

# 2. 直陈式情绪词（直白喊出来而非演出）
DIRECT_EMOTION_PATTERNS = [
    (r"(?:十分|非常|极其|感到|显得|分外)(?:愤怒|生气|难过|伤心|绝望|悲痛|害怕|恐惧|兴奋|高兴)", "直陈式情绪词", "用生理反应（手抖、后槽牙咬紧、发冷）或即时动作演出情绪。"),
    (r"心中涌起(?:一股|一阵)?无法言说的(?:愤怒|绝望|悲伤|凄凉)", "无法言说情绪", "不要宣告'无法言说'，直接写出说不出来的具体情状。"),
    (r"(?:极度|无比|万分)(?:痛苦|震撼|狂喜|沮丧)", "极端副词堆砌", "削减副词修饰，强化名词与动词的力量感。"),
]

# 3. 同义反复与冗余修辞
TAUTOLOGY_PATTERNS = [
    (r"(?:十分|非常)愤怒[，,]?(?:心中|整个人)?(?:极其|分外)?(?:愤怒|生气)", "愤怒同义反复", "删除前后重复的一处。"),
    (r"寂静无声的(?:安静|死寂)", "寂静同义反复", "精简词语，避免'白色的白雪'式重复。"),
    (r"微微(?:勾起|露出一丝)?(?:淡淡的|微弱的)?笑意", "微小副词双重叠加", "保留'微勾嘴角'即可，避免过度的层层修饰。"),
    (r"深吸一口气[，,]?深呼吸", "深吸气重复", "动作单一化，一次即可。"),
]

# 4. 俗套口癖与转折
CLICHE_PATTERNS = [
    (r"就在这时[，,]?", "就在这时滥用", "非突发转折切勿频繁作为句首，直接叙述新动作。"),
    (r"(?:猛然间|突然之间|骤然间)[，,]?", "突然词频过高", "真正突兀的事发生时不需要大喊'突然'，直接抛出变化。"),
    (r"(?:不由得|忍不住|情不自禁地)", "不由得/忍不住口癖", "削减心理过渡词，直接写主角身体下意识的反应。"),
    (r"倒吸了一口(?:凉气|冷气)", "倒吸凉气俗套", "换为屏息、身形后仰或喉咙发紧等更生动的体感。"),
    (r"瞳孔(?:猛然|剧烈)?收缩", "瞳孔收缩俗套", "避免高频使用此模板，可用眼底暗沉、视线锁定等代替。"),
]

_SENT_SPLIT_RE = re.compile(r"[。！？\n\r]+|[…]{2,}")


def analyze_deslop(text: str) -> dict[str, Any]:
    """对输入文本进行全维度去 AI 味深度诊断。"""
    if not isinstance(text, str):
        text = str(text or "")

    raw_len = len(text)
    cn_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    if cn_count == 0:
        return {
            "ai_score": 0.0,
            "verdict": "NATURAL",
            "verdict_cn": "未检测到有效中文文本",
            "stats": {"word_count": 0, "sentence_count": 0, "issues_count": 0, "rang_density": 0.0},
            "issues": [],
            "suggestions": [],
            "highlights": [],
        }

    # 切句
    raw_sents = [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip()]
    sentence_count = len(raw_sents)

    issues: list[dict[str, Any]] = []

    # 1. 扫描假大空修辞
    for pat, label, suggestion in HOLLOW_RHETORIC_PATTERNS:
        for m in re.finditer(pat, text):
            issues.append({
                "type": "hollow_rhetoric",
                "label": label,
                "snippet": m.group(0),
                "index": m.start(),
                "weight": 12,
                "suggestion": suggestion,
            })

    # 2. 直陈式情绪
    for pat, label, suggestion in DIRECT_EMOTION_PATTERNS:
        for m in re.finditer(pat, text):
            issues.append({
                "type": "direct_emotion",
                "label": label,
                "snippet": m.group(0),
                "index": m.start(),
                "weight": 8,
                "suggestion": suggestion,
            })

    # 3. 同义反复
    for pat, label, suggestion in TAUTOLOGY_PATTERNS:
        for m in re.finditer(pat, text):
            issues.append({
                "type": "tautology",
                "label": label,
                "snippet": m.group(0),
                "index": m.start(),
                "weight": 10,
                "suggestion": suggestion,
            })

    # 4. 俗套口癖
    for pat, label, suggestion in CLICHE_PATTERNS:
        for m in re.finditer(pat, text):
            issues.append({
                "type": "cliche",
                "label": label,
                "snippet": m.group(0),
                "index": m.start(),
                "weight": 5,
                "suggestion": suggestion,
            })

    # 5. 「让」字密度专项
    rang_count = text.count("让")
    rang_density = (rang_count / (cn_count / 1000.0)) if cn_count > 0 else 0.0
    if rang_density > 8.0:
        issues.append({
            "type": "rang_overuse",
            "label": "「让」字密度超标",
            "snippet": f"全篇共出现 {rang_count} 个「让」字（千字密度 {rang_density:.1f}）",
            "index": 0,
            "weight": 15,
            "suggestion": "过度使用'让…产生…'被动句型是翻译腔与 AI 味的重灾区。将其重构为主谓主动句。",
        })

    # 6. 无由排比与连续同构句式检查
    for i in range(len(raw_sents) - 2):
        s1, s2, s3 = raw_sents[i], raw_sents[i+1], raw_sents[i+2]
        # 判断三个句子的前 2-3 个字是否完全同构（如"他看见…他听见…他感到…"）
        if len(s1) >= 4 and len(s2) >= 4 and len(s3) >= 4:
            prefix1, prefix2, prefix3 = s1[:2], s2[:2], s3[:2]
            if prefix1 == prefix2 == prefix3 and ("他" in prefix1 or "她" in prefix1 or "像" in prefix1):
                issues.append({
                    "type": "parallelism",
                    "label": "机械连续同构句",
                    "snippet": f"{s1}；{s2}；{s3}",
                    "index": text.find(s1) if text.find(s1) >= 0 else 0,
                    "weight": 14,
                    "suggestion": "连续相同句式开头显得过于工整死板，打破对仗，融合为更有节奏的错落叙述。",
                })

    # 综合计分 (0-100，越低越健康纯正，100 极度油腻严重 AI 味)
    # 基础分 = 惩罚分归一化
    penalty_sum = sum(it["weight"] for it in issues)
    # 按字数缩放：千字惩罚加权
    scale_factor = 1000.0 / max(cn_count, 300)
    scaled_penalty = penalty_sum * scale_factor
    ai_score = min(100.0, max(0.0, round(scaled_penalty * 1.8, 1)))

    if ai_score < 18.0:
        verdict = "NATURAL"
        verdict_cn = "自然流畅（无明显 AI 味）"
    elif ai_score < 40.0:
        verdict = "MILD"
        verdict_cn = "轻度模式化（个别俗套句式）"
    elif ai_score < 65.0:
        verdict = "NOTICEABLE"
        verdict_cn = "AI 腔明显（存在高频模板与直陈宣泄）"
    else:
        verdict = "SEVERE"
        verdict_cn = "重度 AI 味（需深度重塑润色）"

    # 生成全局改写建议
    general_suggestions = []
    if any(it["type"] == "hollow_rhetoric" for it in issues):
        general_suggestions.append("警惕'这一刻仿佛凝固'等玄虚修辞，网文需要的是落地的动作与环境反馈。")
    if any(it["type"] == "direct_emotion" for it in issues):
        general_suggestions.append("秉持'Show, don't tell'原则，用呼吸急促、眼神闪烁等具体动作代替'十分难过'。")
    if rang_density > 6.0:
        general_suggestions.append("大量减少'让'字被动句，将视角转回角色的直接动作。")
    if any(it["type"] == "cliche" for it in issues):
        general_suggestions.append("清理'就在这时'、'突然'等俗套连接词，突兀感靠叙述节奏自发带出。")

    return {
        "ai_score": ai_score,
        "verdict": verdict,
        "verdict_cn": verdict_cn,
        "stats": {
            "word_count": cn_count,
            "sentence_count": sentence_count,
            "issues_count": len(issues),
            "rang_density": round(rang_density, 1),
        },
        "issues": issues[:30],  # 最多返回前 30 项
        "suggestions": general_suggestions,
    }
