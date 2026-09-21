#!/usr/bin/env python3
"""
章节质量自检 — 独立于 voice-card 的章节本身质量评分

检查维度（共 100 分）：
  1. 字数（8）— ≥1500 满分，向下线性衰减
  2. 对话占比（12）— 15-40% 满分，区间外连续衰减
  3. 章末钩子（12）— 有悬念/断句/情感冲击/反转
  4. 开头吸引力（8）— 前 200 字是否有冲突/悬念/场景
  5. 情绪密度（12）— 每 400 字≥1 处体感词（命中率连续计分）
  6. 直陈式情绪词（8）— 零出现满分，随次数连续扣减
  7. 段落节奏（8）— 短段(≤15字)占比 10-40% 满分，区间外连续
  8. 结构完整性（8）— 有开头/发展/收束
  9. AI 味检测（4）— 高频模板句式扣分
  10. 疲劳词检测（8）— "了"字密度/情绪标签词/连接词滥用（密度连续扣分）
  11. 让字专项（5）— "让"字过多 = AI味重灾区（密度连续计分）
  12. 情绪标签词（7）— 区分对话/旁白中的情绪标签词滥用

评分语义（2026-09-18）：硬边界档位改为分段线性连续打分（_ramp），
满分区与各维权重不变；消除「改 1 字跳 2–4 分」的悬崖效应（评估报告 P1-2）。
分数可带 1 位小数；判定线 PASS≥75 / WARN≥60 语义不变。

用法:
  python chapter_check.py <章节.txt> [--genre-pack genre-pack.json]
  → 输出 JSON: {"score": 85, "details": [...], "issues": [...], "verdict": "PASS"}
"""
import argparse
import json
import re
import sys
from pathlib import Path

from metrics import dialogue_char_count

# 直陈式情绪词（出现即扣分）
DIRECT_EMOTION = ["很愤怒", "很生气", "感到难过", "非常开心", "很伤心", "感到害怕",
                  "很紧张", "很幸福", "很沮丧", "很兴奋", "很失落", "很委屈",
                  "非常愤怒", "非常难过", "感到高兴", "感到幸福"]

# 体感词库
BODY_WORDS = ["心跳", "指尖", "耳根", "脊背", "手心", "喉结", "呼吸", "发烫", "发麻",
              "冰凉", "发白", "发红", "发酸", "发抖", "发紧", "发软", "发沉", "发热",
              "额头", "鼻尖", "嘴唇", "膝盖", "脚踝", "肩膀", "后背", "胸口", "小腹",
              "掌心", "指节", "手腕", "脚趾", "脖子", "下巴", "眉心", "太阳穴"]

# 钩子关键词（章末 300 字内出现 = 有钩子）
# 2026-09-21：追加英文章末钩模式（多语料）；中文词表保持不变，仅增加可命中项。
HOOK_KEYWORDS = [
    r"[。！？]\s*$",  # 以中文句末标点结束（弱钩子）
    r"[.!?]\s*$",  # 英文章末句号/问号/叹号（弱钩子）
    r"[…]{1,3}|\.\.\.",  # 省略号（悬念）
    r"忽然|突然|猛然|骤然",  # 突发事件
    r"\b(Suddenly|Abruptly|Without warning)\b",  # EN 突发
    r"门.*开了|电话.*响|手机.*响|有人.*敲",  # 中断/引入
    r"她不知道|他不知道|谁也没想到",  # 悬念
    r"\bdidn'?t know\b|\bhad no idea\b|\bnever expected\b",  # EN 悬念
    r"转身|回头|推门|拉开|站起",  # 动作钩子
    r"\bturned around\b|\bturned to leave\b|\bpushed open\b|\bstepped forward\b|\bstood up\b",
    r"明天|以后|从此|那天起",  # 时间钩子
    r"\btomorrow\b|\bfrom that day\b|\bnever again\b",
    r"可是|可那|但是|却只|却还|却在",  # 转折留白
    r"\bBut\b|\bHowever\b|\bYet\b",  # EN 转折
    r"如果|难道|究竟能|是否还",  # 设问/不确定
    r"\?$",  # 英文设问收尾
    r"\bif only\b|\bwhat if\b|\bcould it be\b",
]

# 评分阈值默认值（题材包未配置 quality_thresholds 时的回退线）
DEFAULT_PASS = 75
DEFAULT_WARN = 60

# 对话占比满分区默认值（评估报告 P1-4：慢热抒情文体与 15%–40% 硬带冲突）
# 题材包 commercial.quality_thresholds.dialogue_optimal = {"min": x, "max": y} 可覆盖。
# campus-redemption 语料实测 voice-card dialogue_ratio：0.0737 / 0.1469 / 0.2562 / 0.3016
DEFAULT_DIALOGUE_BAND = (0.15, 0.40)

# 「了」字密度标定线（2026-09-17 按语料分位数重标定，取代旧绝对值 >5 / >8）
#
# 标定依据：
#   - 语料：corpus/*_chosen.txt，共 6 本
#     （autumn / chireng / duwo / qingning / sangshi / suyixinjian）
#   - 样本量：54 章（章粒度；密度口径 = 「了」字数 / 汉字数 × 1000）
#   - 分位数：p75 = 27.0、p90 = 31.2（参考：p05 = 13.3、p50 = 23.9）
#   - 标定日期：2026-09-17
#   - 动机：旧口径 >5 / >8 使语料 100% 的章扣满 3 分、0% 不扣分，该维度零区分度；
#     改分位数后 75% 的章不再扣分，仅 top 25% 略扣、top 10% 重扣。
#   - 阈值随语料扩充应重算：语料变更后需重新统计章粒度分位数并更新下面两个常量。
#   - 2026-09-18：p75→p90 之间改为连续扣分（0→3），消除「跨线跳档」刷分空间。
LE_DENSITY_PENALTY_LINE = 27.0  # <= 不扣分（语料 p75）；之上向 p90 线性过渡到扣 3
LE_DENSITY_HEAVY_LINE = 31.2    # >= 扣满 3 分（语料 p90）


def _ramp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    """分段线性插值：把 x∈[x0,x1] 映射到 y∈[y0,y1]，区间外夹紧到端点。

    用于把「悬崖式档位」改为连续打分：跨过旧阈值时分数平滑过渡，
    消除「改 1 个字跳 2–4 分」的边界效应（评估报告 P1-2）。
    """
    if x1 <= x0:
        return float(y1) if x >= x1 else float(y0)
    if x <= x0:
        return float(y0)
    if x >= x1:
        return float(y1)
    t = (x - x0) / (x1 - x0)
    return y0 + (y1 - y0) * t


def _score1(v: float) -> float:
    """分数统一保留 1 位小数，消除浮点噪声。"""
    return round(float(v) + 1e-12, 1)


def _fmt_score(v: float) -> str:
    """整数分显示为 int，否则 1 位小数（detail 文案用）。"""
    v = _score1(v)
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.1f}"

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
    """1. 字数检查（8 分）— 连续打分：≥1500 满分，向下线性衰减。

    2026-09-18：取代旧档位（1500→8 / 1200→6 / 1000→3 / <1000→0），
    消除「1499→1500 = +2 分」悬崖。锚点与旧档位端点一致。
    """
    cn = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    if cn >= 1500:
        score, label = 8.0, "✓"
    elif cn >= 1200:
        score = _ramp(cn, 1200, 1500, 6.0, 8.0)
        label = "略短"
    elif cn >= 1000:
        score = _ramp(cn, 1000, 1200, 3.0, 6.0)
        label = "偏短"
    else:
        score = _ramp(cn, 0, 1000, 0.0, 3.0)
        label = "严重不足"
    score = _score1(score)
    if label == "✓":
        return score, f"字数 {cn} ✓"
    return score, f"字数 {cn}（{label}）"


def resolve_dialogue_band(genre_pack) -> tuple:
    """解析对话占比满分区，返回 (min, max)。

    读取顺序：
      1. ``commercial.quality_thresholds.dialogue_optimal``（与 resolve_thresholds 同路径）
      2. 顶层 ``quality_thresholds.dialogue_optimal``（题材包未写满 commercial 时的轻量挂载）
    回退：缺省 / 非法 → DEFAULT_DIALOGUE_BAND。静默回退，不抛异常。
    """
    if not isinstance(genre_pack, dict):
        return DEFAULT_DIALOGUE_BAND
    candidates = []
    commercial = genre_pack.get("commercial")
    if isinstance(commercial, dict):
        qt = commercial.get("quality_thresholds")
        if isinstance(qt, dict):
            candidates.append(qt)
    top_qt = genre_pack.get("quality_thresholds")
    if isinstance(top_qt, dict):
        candidates.append(top_qt)

    def _unit(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    for qt in candidates:
        opt = qt.get("dialogue_optimal")
        if not isinstance(opt, dict):
            continue
        mn, mx = opt.get("min"), opt.get("max")
        if not (_unit(mn) and _unit(mx)):
            continue
        if not (0.0 <= float(mn) < float(mx) <= 1.0):
            continue
        return (float(mn), float(mx))
    return DEFAULT_DIALOGUE_BAND


def check_dialogue_ratio(text: str, band=None) -> tuple:
    """2. 对话占比（12 分）— 满分区可按题材包配置，区间外连续衰减。

    分子统一走 metrics.dialogue_char_count（四类引号同一口径，2026-09-16 Task 3）；
    分母保持既有口径：汉字数。
    2026-09-18：连续打分 + 题材包可配满分区（P1-4）。默认带 (0.15, 0.40)。
    外侧锚点按带宽相对推导，默认带时与旧档位端点一致。
    """
    dialogue_chars = dialogue_char_count(text)
    total = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    if total == 0:
        return 0, "无文本"
    ratio = dialogue_chars / total

    lo, hi = band if band is not None else DEFAULT_DIALOGUE_BAND
    lo, hi = float(lo), float(hi)
    width = max(hi - lo, 1e-6)
    lo_mid = lo * (2.0 / 3.0)          # 默认 0.10
    lo_low = lo * (1.0 / 3.0)          # 默认 0.05
    hi_a = hi + width * 0.6            # 默认 0.55
    hi_b = hi + width * 0.8            # 默认 0.60
    hi_c = hi + width * 2.4            # 默认衰减终点附近

    if lo <= ratio <= hi:
        score, label = 12.0, "✓"
    elif lo_mid <= ratio < lo:
        score = _ramp(ratio, lo_mid, lo, 8.0, 12.0)
        label = "略低"
    elif hi < ratio <= hi_a:
        score = _ramp(ratio, hi, hi_a, 12.0, 8.0)
        label = "略高"
    elif lo_low <= ratio < lo_mid:
        score = _ramp(ratio, lo_low, lo_mid, 2.0, 8.0)
        label = "偏低"
    elif hi_a < ratio <= hi_b:
        score = _ramp(ratio, hi_a, hi_b, 8.0, 4.0)
        label = "偏高"
    elif ratio < lo_low:
        score = _ramp(ratio, 0.0, lo_low, 0.0, 2.0)
        label = "几乎无对话"
    else:
        # 对话过多：连续下降；子项不低于 2，避免短文本因「引号内标点 / 汉字分母」
        # 使 ratio>1 时被打成 0 分（旧档位该档固定 4 分，也从不为 0）
        score = _ramp(ratio, hi_b, max(hi_c, hi_b + 1e-6), 4.0, 2.0)
        label = "对话过多"
    score = _score1(score)
    if label == "✓":
        return score, f"对话占比 {ratio:.1%} ✓"
    return score, f"对话占比 {ratio:.1%}（{label}）"


def check_hook(text: str) -> tuple:
    """3. 章末钩子（12 分）

    2026-09-21 重标定：旧口径「每命中 +3、收束 +2、封顶 12」会使
    「3 类钩子 + 有效收束」永远停在 11 分——现实题材大量合格收束章
    被系统性压分（《暮冬念春》94/157 章卡在 11）。改为命中数主导：
      hits>=3 + 有效收束 → 12
      hits>=3 无收束 / hits==2 + 有效收束 → 9
      hits==2 + 极短收束（末行≤15字）→ 10
      hits==2 无收束 / hits==1 + 有效收束 → 6
      hits==1 无收束 → 3；无命中：收束 2 / 截断 0
    截断风险一律再扣 3。词表补充转折/设问类文学钩子。
    """
    tail = text[-300:] if len(text) > 300 else text
    hits = 0
    notes = []
    for pat in HOOK_KEYWORDS:
        if re.search(pat, tail):
            hits += 1
            notes.append(pat[:12])

    last_line = [l.strip() for l in text.split('\n') if l.strip()][-1] if text.strip() else ""
    closed = bool(last_line and re.search(r'[。！？…"\u201d]$', last_line))
    short_close = bool(closed and len(last_line) <= 15)
    truncated = bool(last_line and len(last_line) > 4 and not closed)
    if closed:
        notes.append("有效收束" + ("（短收）" if short_close else ""))
    if truncated:
        notes.append("截断风险")

    if hits >= 3 and closed:
        score = 12.0
    elif hits >= 3:
        score = 9.0
    elif hits == 2 and short_close:
        score = 10.0
    elif hits == 2 and closed:
        score = 9.0
    elif hits == 2:
        score = 6.0
    elif hits == 1 and closed:
        score = 6.0
    elif hits == 1:
        score = 3.0
    elif closed:
        score = 2.0
    else:
        score = 0.0

    if truncated:
        score = max(score - 3.0, 0.0)

    score = min(_score1(score), 12.0)
    state = f"closed={int(closed)} short={int(short_close)} trunc={int(truncated)}"
    return score, f"钩子 {score}/12: hits={hits}, {state}"


def check_opening(text: str) -> tuple:
    """4. 开头吸引力（8 分）

    2026-09-18：场景/冲突词表按现代校园·都市现实题材扩充。
    2026-09-21：开头窗口先 lstrip（去掉标题后空行），场景/动作词表
    再按现实题材实测缺口补齐（会议室/巷口/车厢/拆/递/签等）。
    """
    opening = text.lstrip()[:400] if len(text) > 400 else text.lstrip()
    act_window = opening[:120]
    dial_window = opening[:200]
    score = 0
    notes = []

    if re.search(
        r'(教室|走廊|操场|宿舍|食堂|图书馆|医院|车站|家里|旅馆|酒店|'
        r'咖啡馆|咖啡厅|办公室|会议室|公司|工厂|园区|邮局|法院|派出所|'
        r'河堤|河边|湖边|草坪|单元门|楼道|楼下|天台|出租屋|'
        r'杂货铺|奶茶店|早餐店|小区|校门|公交车|车厢|'
        r'巷|巷口|后街|教学楼|课桌|客厅|厨房|卧室|阳台|'
        r'火车|高铁|机场|商场|广场|马路|电梯|前台|柜台|实验室|工地)',
        opening,
    ):
        score += 2
        notes.append("场景建立")
    if re.search(
        r'(吵架|争执|矛盾|意外|突然|忽然|紧张|害怕|担心|不安|忐忑|'
        r'纠结|慌|震惊|愣住|失望|警惕|心虚|发抖|发白|窒息|压迫|'
        r'拒绝|被拘留|方案被|出事|失踪|跟踪|危险|关机|退回|失败|落空|不敢|绷紧|僵住)',
        opening,
    ):
        score += 2
        notes.append("冲突引入")
    if re.search(r'["\u201c\u2018\u2019].{2,20}["\u201c\u201d\u2018\u2019]', dial_window):
        score += 2
        notes.append("对话开场")
    if re.search(
        r'(走|跑|坐|站|推|拉|抓|拿|看|听|爬|靠|掏|翻|望|盯|赶|握|喘|醒|'
        r'拆|递|签|写|答|放|收|等|找|查|拨|吃|喝|笑|哭|擦|洗|叠|收起)',
        act_window,
    ):
        score += 2
        notes.append("动作开场")

    score = min(score, 8)
    return score, f"开头 {score}/8: {', '.join(notes)}"


def check_emotion_density(text: str) -> tuple:
    """5. 情绪密度（12 分）— 每 400 字≥1 处体感词；命中率连续计分。

    2026-09-18：ratio≥1 满分；0.7–1.0 / 0.4–0.7 / <0.4 线性插值，消除跳档。
    """
    cn = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    if cn == 0:
        return 0, "无文本"

    hits = 0
    for w in BODY_WORDS:
        hits += text.count(w)

    expected = max(1, cn // 400)
    ratio = hits / expected if expected > 0 else 0

    if ratio >= 1.0:
        score, label = 12.0, "✓"
    elif ratio >= 0.7:
        score = _ramp(ratio, 0.7, 1.0, 8.0, 12.0)
        label = "略少"
    elif ratio >= 0.4:
        score = _ramp(ratio, 0.4, 0.7, 4.0, 8.0)
        label = "偏少"
    else:
        score = _ramp(ratio, 0.0, 0.4, 0.0, 4.0)
        label = "严重不足"
    score = _score1(score)
    if label == "✓":
        return score, f"体感词 {hits} 处（期望≥{expected}）✓"
    return score, f"体感词 {hits} 处（期望≥{expected}，{label}）"


def check_direct_emotion(text: str) -> tuple:
    """6. 直陈式情绪词（8 分）— 零出现满分，随出现次数连续扣减。"""
    hits = sum(1 for w in DIRECT_EMOTION if w in text)
    if hits == 0:
        return 8, "直陈式情绪词 0 ✓"
    if hits <= 2:
        score = _score1(_ramp(hits, 0, 2, 8.0, 4.0))
        return score, f"直陈式情绪词 {hits} 个（扣 {_fmt_score(8 - score)} 分）"
    score = _score1(_ramp(hits, 2, 5, 4.0, 0.0))
    return score, f"直陈式情绪词 {hits} 个（严重扣分）"


def check_paragraph_rhythm(text: str) -> tuple:
    """7. 段落节奏（8 分）— 短段占比；2026-09-05 由 10 分降回 docstring 权重"""
    paras = [p.strip() for p in text.split('\n') if p.strip()]
    if not paras:
        return 0, "无段落"
    short = sum(1 for p in paras if len(p) <= 15)
    ratio = short / len(paras)

    if 0.10 <= ratio <= 0.40:
        score, label = 8.0, "✓"
    elif 0.05 <= ratio < 0.10:
        score = _ramp(ratio, 0.05, 0.10, 6.0, 8.0)
        label = "略少"
    elif 0.40 < ratio <= 0.55:
        score = _ramp(ratio, 0.40, 0.55, 8.0, 6.0)
        label = "略多"
    elif ratio > 0.55:
        score = _ramp(ratio, 0.55, 0.80, 6.0, 2.0)
        label = "过度精炼"
    else:
        score = _ramp(ratio, 0.0, 0.05, 4.0, 6.0)
        label = "段落过长"
    score = _score1(score)
    if label == "✓":
        return score, f"短段占比 {ratio:.1%} ✓"
    return score, f"短段占比 {ratio:.1%}（{label}）"


def check_structure(text: str) -> tuple:
    """8. 结构完整性（8 分）— 有开头/发展/收束；2026-09-05 由 10 分降回 docstring 权重"""
    paras = [p.strip() for p in text.split('\n') if p.strip()]
    if len(paras) < 3:
        return 0, "段落过少"
    score = 0
    notes = []

    # 开头（前 1/4 有场景/人物引入）
    opening = '\n'.join(paras[:max(1, len(paras)//4)])
    if len(opening) > 50:
        score += 2
        notes.append("有开头")

    # 发展（中段有变化/推进）
    mid = '\n'.join(paras[len(paras)//4:3*len(paras)//4])
    if len(mid) > 100:
        score += 4
        notes.append("有发展")

    # 收束（后 1/4 有明确结尾）
    ending = '\n'.join(paras[3*len(paras)//4:])
    if len(ending) > 30 and re.search(r'[。！？…"\u201d]', ending[-50:]):
        score += 2
        notes.append("有收束")

    return score, f"结构 {score}/8: {', '.join(notes)}"


def check_ai_tics(text: str) -> tuple:
    """9. AI 味检测（4 分）— 高频模板句式扣分（分值与显示标签 /4 对齐）"""
    score = 4
    notes = []
    for pat, label in AI_TICS:
        matches = re.findall(pat, text)
        if matches:
            score -= 1
            notes.append(f"{label}({len(matches)})")

    score = max(score, 0)
    return score, f"AI味 {score}/4: {', '.join(notes) if notes else '无 ✓'}"


def check_fatigue_words(text: str) -> tuple:
    """10. 疲劳词检测（8 分）— 借鉴 novel-deconstruct 的 6 类疲劳词

    「了」字密度档位 2026-09-17 由绝对值（>5 / >8）改为语料分位数标定
    （LE_DENSITY_PENALTY_LINE / LE_DENSITY_HEAVY_LINE）；情绪标签词与
    连接词两个子项的口径未变。
    """
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

    score = 8.0
    notes = []

    # 「了」字密度：p75 之下不扣；p75→p90 线性 0→3；≥p90 扣满 3（连续，无跳档）
    if le_density > LE_DENSITY_HEAVY_LINE:
        le_deduct = 3.0
        notes.append(f"了字密度 {le_density:.1f}/千字（过高）")
    elif le_density > LE_DENSITY_PENALTY_LINE:
        le_deduct = _ramp(
            le_density, LE_DENSITY_PENALTY_LINE, LE_DENSITY_HEAVY_LINE, 0.0, 3.0)
        notes.append(
            f"了字密度 {le_density:.1f}/千字（略高，扣 {_fmt_score(le_deduct)} 分）")
    else:
        le_deduct = 0.0
    score -= le_deduct

    if tag_count > cn / 200:
        score -= 2
        notes.append(f"情绪标签词 {tag_count} 处（过多）")

    if conn_count > 5:
        score -= 1
        notes.append(f"连接词 {conn_count} 处（过多）")

    score = _score1(max(score, 0.0))
    return score, f"疲劳词 {_fmt_score(score)}/8: {', '.join(notes) if notes else '无异常 ✓'}"


def check_rang_character(text: str) -> tuple:
    """11. "让"字专项（5 分）— 密度连续计分；过多 = AI味重灾区"""
    rang_count = text.count('让')
    cn = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    density = rang_count / (cn / 1000) if cn > 0 else 0

    if density <= 1:
        return 5, f"让字 {rang_count} 处 ✓"
    if density <= 2:
        score = _score1(_ramp(density, 1, 2, 5.0, 3.0))
        return score, f"让字 {rang_count} 处（略多）"
    score = _score1(_ramp(density, 2, 4, 3.0, 0.0))
    return score, f"让字 {rang_count} 处（过多，AI味重灾区）"


def check_emotion_tags(text: str) -> tuple:
    """12. 情绪标签词滥用（7 分）— 区分对话/旁白；次数连续计分"""
    narrator_tags = ['她感到', '他感到', '她觉得', '他觉得', '她意识到', '他意识到',
                     '她忽然感到', '他忽然感到', '她不禁感到', '她内心']
    tag_count = sum(text.count(w) for w in narrator_tags)

    if tag_count == 0:
        return 7, "旁白情绪标签 0 ✓"
    if tag_count <= 2:
        score = _score1(_ramp(tag_count, 0, 2, 7.0, 4.0))
        return score, f"旁白情绪标签 {tag_count} 处（略多）"
    score = _score1(_ramp(tag_count, 2, 5, 4.0, 0.0))
    return score, f"旁白情绪标签 {tag_count} 处（AI味重灾区）"


def resolve_thresholds(genre_pack):
    """解析评分阈值，返回 (pass, warn) 二元组。

    单一事实来源：题材包 commercial.quality_thresholds 可覆盖默认 75/60。
    回退规则（全部静默回退，不抛异常）：
      - genre_pack 为 None                 → (75, 60)
      - 无 quality_thresholds 键            → (75, 60)
      - pass / warn 非 int 或越界(0-100)   → (75, 60)
      - warn > pass                        → (75, 60)
    允许 pass == warn（此时无 WARN 档，>=pass 即 PASS，否则 FAIL）。

    Args:
        genre_pack: 题材包 dict（可选，来自 JSON 解析）。

    Returns:
        tuple[int, int]: (pass_line, warn_line)，保证在合法范围内。
    """
    if genre_pack is None:
        return DEFAULT_PASS, DEFAULT_WARN
    thresholds = genre_pack.get("commercial", {}).get("quality_thresholds") \
        if isinstance(genre_pack, dict) else None
    if not isinstance(thresholds, dict):
        return DEFAULT_PASS, DEFAULT_WARN

    pass_line = thresholds.get("pass")
    warn_line = thresholds.get("warn")

    def _valid(v):
        return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100

    if not (_valid(pass_line) and _valid(warn_line)):
        return DEFAULT_PASS, DEFAULT_WARN
    if warn_line > pass_line:
        return DEFAULT_PASS, DEFAULT_WARN
    return pass_line, warn_line


def chapter_check(text: str, genre_pack: dict = None) -> dict:
    """综合章节质量检查，返回评分报告。

    2026-09-05 修复（C1）：12 维分值回归文件头 docstring 权重，合计恰好 100
    （原函数内部满分 120，被 min(sum,100) 截断导致高分失真）。
    判定线调整: 默认 PASS≥75 / WARN≥60，可经题材包 quality_thresholds 适配。
    """
    checks = [
        check_word_count(text),       # 8分
        check_dialogue_ratio(text, resolve_dialogue_band(genre_pack)),  # 12分
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

    total = _score1(min(sum(float(s) for s, _ in checks), 100.0))
    details = [d for _, d in checks]
    issues = []
    for s, d in checks:
        if "偏短" in d and "严重" not in d:
            continue
        if "严重" in d or "不足" in d or "截断" in d:
            issues.append(d)

    # 判定（阈值来自 resolve_thresholds：题材包 quality_thresholds 可覆盖默认 75/60）
    pass_line, warn_line = resolve_thresholds(genre_pack)
    if total >= pass_line:
        verdict = "PASS"
    elif total >= warn_line:
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
        print(f"总分: {_fmt_score(result['score'])}/100 ({result['verdict']})")
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
