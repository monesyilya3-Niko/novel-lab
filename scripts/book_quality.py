#!/usr/bin/env python3
"""
全书内容质检 — 覆盖情节连贯性/文笔一致性/重复检测/凑字数检测

用法:
  python book_quality.py <章节目录或单章txt> [--voice voice-card.json] [--prev-chapters 目录]
  → 输出 JSON 质检报告

检测维度（共 6 大类）：
  1. 跨章/章内重复（重复章节/重复段落/跨章重复句子/章内重复句子）
  2. 情节连贯性（人物状态/时间线/逻辑矛盾）
  3. 文笔风格一致性（句式/比喻/情绪写法）
  4. 凑字数检测（废话/重复描写/无意义堆砌）
  5. 乱编检测（人名错误——读 settings/entities.json 实体表；数字矛盾）
  6. AI味检测（模板句/过度排比/作者旁白）

⚠️ 局限性说明（2026-09-05 标注）：情节连贯/凑字数/AI味检测基于固定模板
匹配，覆盖面有限，输出结果需人工复核，不能直接采信。
"""
import argparse
import json
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict

import chapter_loader

# --------------------------------------------------------------------------
# 1. 跨章重复检测
# --------------------------------------------------------------------------

# 章内重复句占比判定的最小样本量：句子总数低于此值时小分母比例不可靠，
# 一律按 low 报告并置 low_sample=True（见 check_intra_chapter_repeats）。
MIN_SAMPLE_SENTS_FOR_RATIO = 8

# 报告输出的问题条数上限（2026-09-17 终审 M-5）：超过时 `issues` 只给前
# MAX_REPORTED_ISSUES 条，返回值同时给出 `total_issues`（真实总数）、
# `issues_truncated`（是否被截断）与 `issues_limit`（本上限），消费方据此提示读者。
MAX_REPORTED_ISSUES = 50


def check_duplicate_chapters(texts: dict) -> list:
    """检测整章内容重复（相似度 > 0.7）"""
    from difflib import SequenceMatcher
    issues = []
    chapters = sorted(texts.keys())
    for i in range(len(chapters)):
        for j in range(i+1, len(chapters)):
            a, b = chapters[i], chapters[j]
            ta, tb = texts[a], texts[b]
            # 取中段 500 字比较（避免开头结尾模板干扰）
            mid_a = ta[len(ta)//3:2*len(ta)//3][:500]
            mid_b = tb[len(tb)//3:2*len(tb)//3][:500]
            if len(mid_a) < 100 or len(mid_b) < 100:
                continue
            sim = SequenceMatcher(None, mid_a, mid_b).ratio()
            if sim > 0.7:
                issues.append({
                    "type": "duplicate_chapter",
                    "severity": "critical",
                    "chapters": [a, b],
                    "similarity": round(sim, 2),
                    "detail": f"Ch{a} 与 Ch{b} 中段相似度 {sim:.0%}，疑似重复章节"
                })
    return issues


def check_duplicate_paragraphs(texts: dict) -> list:
    """检测跨章重复段落（>30字完全相同）"""
    issues = []
    para_chapters = defaultdict(set)
    for ch, text in texts.items():
        for para in text.split('\n'):
            p = para.strip()
            if len(p) > 30:
                para_chapters[p].add(ch)
    for para, chs in para_chapters.items():
        if len(chs) >= 2:
            issues.append({
                "type": "duplicate_paragraph",
                "severity": "high",
                "chapters": sorted(chs),
                "detail": f"段落「{para[:40]}…」在 {len(chs)} 章重复"
            })
    return issues


def check_duplicate_sentences(texts: dict) -> list:
    """检测跨章重复句子（>12字，跨≥2章）

    2026-09-17（第二轮 Task A，报告 P0-2）：召回门槛由「≥3 章」下调为「≥2 章」——
    只在相邻两章重复的句子是读者最易察觉的形态，此前永远不报。严重度分档：
      - 2 章  → `low`（新增档，不参与 critical/high 判定规则）
      - ≥3 章 → `medium`（与调整前完全一致，不回退）
    另新增 `adjacent` 布尔字段：重复章号中是否存在相邻章（差值为 1）。
    句子切分正则与 12 字门槛保持不变。
    """
    issues = []
    sent_chapters = defaultdict(set)
    for ch, text in texts.items():
        for sent in re.findall(r'[^。！？\n]{12,40}[。！？]', text):
            sent = sent.strip()
            if len(sent) >= 12:
                sent_chapters[sent].add(ch)
    for sent, chs in sent_chapters.items():
        if len(chs) >= 2:
            chapters = sorted(chs)
            adjacent = any(b - a == 1 for a, b in zip(chapters, chapters[1:]))
            detail = f"句子「{sent[:30]}…」在 {len(chs)} 章重复"
            if adjacent:
                detail += "（相邻章）"
            issues.append({
                "type": "duplicate_sentence",
                "severity": "medium" if len(chs) >= 3 else "low",
                "chapters": chapters,
                "adjacent": adjacent,
                "detail": detail,
            })
    return issues


def check_intra_chapter_repeats(texts: dict) -> list:
    """检测章内重复句子（≥10 字的句子在同一章内出现 ≥2 次）

    2026-09-17（第二轮 Task A，报告 P0-2）：段落检测只认「>30 字整段完全相同」，
    识别不了「同一句碎片散布在多个段落中」的形态（项目曾发生 2000 字里 937 字重复的
    automerge 事故却被判 PASS）。本检查按**章内重复句占比**补上这一召回缺口。

    占比 `ratio = dups / 句子总数`（dups = 各重复句多出的出现次数之和）：
      - `ratio >= 0.25`          → `high`
      - `0.10 <= ratio < 0.25`   → `medium`
      - `ratio < 0.10`           → `low`

    **最小样本保护**：句子总数 < `MIN_SAMPLE_SENTS_FOR_RATIO` 时小分母占比不可靠
    （如「2 句里重复 1 句」= 50% 会被判 `high`，进而因 `high > 0` 使 `novel 质检`
    由 PASS 变 WARN，属新引入的误报），此时一律报 `low`，并在 issue 中以
    `low_sample=True` 标记；样本充足时为 `False`（该字段**始终给出**，便于消费方判断）。

    每章最多报 1 条（聚合）；无重复句或句子总数为 0 时跳过该章。
    """
    issues = []
    for ch in sorted(texts.keys()):
        sents = [s.strip() for s in re.split(r'(?<=[。！？…])', texts[ch])]
        sents = [s for s in sents if len(s) >= 10]
        if not sents:
            continue
        counter = Counter(sents)
        dups = sum(n - 1 for n in counter.values() if n > 1)
        if dups == 0:
            continue
        ratio = dups / len(sents)
        low_sample = len(sents) < MIN_SAMPLE_SENTS_FOR_RATIO
        if low_sample:
            # 小分母下比例不可靠，不按比例升级（避免新误报）
            severity = "low"
        elif ratio >= 0.25:
            severity = "high"
        elif ratio >= 0.10:
            severity = "medium"
        else:
            severity = "low"
        longest = max((s for s, n in counter.items() if n > 1), key=len)
        issues.append({
            "type": "intra_chapter_repeat",
            "severity": severity,
            "chapter": ch,
            "low_sample": low_sample,
            "detail": (f"Ch{ch} 章内重复句 {dups}/{len(sents)}（占比 {ratio:.0%}），"
                       f"最长重复句「{longest[:30]}…」"),
        })
    return issues


# --------------------------------------------------------------------------
# 2. 情节连贯性检测
# --------------------------------------------------------------------------

def check_plot_continuity(texts: dict) -> list:
    """检测情节连贯性问题"""
    issues = []
    chapters = sorted(texts.keys())
    
    # 检测时间线矛盾（"第二天"出现过多）
    for ch in chapters:
        text = texts[ch]
        next_day = len(re.findall(r'第二天|次日|隔天', text))
        if next_day >= 4:
            issues.append({
                "type": "timeline_contradiction",
                "severity": "medium",
                "chapter": ch,
                "detail": f"Ch{ch} 出现 {next_day} 次'第二天/次日/隔天'，时间线可能混乱"
            })
    
    # 检测人物状态矛盾（同一章内"紧张"和"放松"交替）
    tension_words = ["紧张", "害怕", "恐惧", "焦虑", "不安"]
    calm_words = ["放松", "平静", "安心", "淡定", "从容"]
    for ch in chapters:
        text = texts[ch]
        t_count = sum(text.count(w) for w in tension_words)
        c_count = sum(text.count(w) for w in calm_words)
        if t_count >= 3 and c_count >= 3:
            issues.append({
                "type": "mood_contradiction",
                "severity": "low",
                "chapter": ch,
                "detail": f"Ch{ch} 同时出现 {t_count} 处紧张词和 {c_count} 处平静词，情绪可能矛盾"
            })
    
    return issues


# --------------------------------------------------------------------------
# 3. 文笔风格一致性检测
# --------------------------------------------------------------------------

def check_style_consistency(texts: dict, voice_card: dict = None) -> list:
    """检测文笔风格一致性"""
    issues = []
    chapters = sorted(texts.keys())
    
    # 检测比喻密度波动（单章比喻密度 vs 全书平均）
    metaphor_patterns = [r'像', r'如同', r'仿佛', r'好像', r'宛如']
    densities = {}
    for ch in chapters:
        text = texts[ch]
        cn = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        if cn == 0:
            continue
        count = sum(len(re.findall(p, text)) for p in metaphor_patterns)
        densities[ch] = count / (cn / 1000)
    
    if densities:
        avg = sum(densities.values()) / len(densities)
        for ch, d in densities.items():
            if d > avg * 2.5:
                issues.append({
                    "type": "metaphor_density_spike",
                    "severity": "medium",
                    "chapter": ch,
                    "detail": f"Ch{ch} 比喻密度 {d:.1f}/千字（全书平均 {avg:.1f}），可能过度"
                })
    
    # 检测情绪写法模式漂移（如果提供了 voice-card）
    if voice_card:
        # 与 coverage 共用同一取值入口：_voice_card_mode 对非 str 的 mode 归一为 ""。
        # 若此处按真值直取（旧写法 .get('mode', '')），畸形卡片（如 mode=5）会一边被
        # coverage 判为「未评估」、一边产出 emotion_mode_drift —— 正是 Task B 要消除的
        # coverage/issue 自相矛盾（终审 M-1）。
        expected_mode = _voice_card_mode(voice_card)
        if expected_mode:
            direct_emotion = ["很愤怒", "很生气", "感到难过", "非常开心", "很伤心", "感到害怕"]
            for ch in chapters:
                text = texts[ch]
                direct_count = sum(text.count(w) for w in direct_emotion)
                if direct_count >= 3 and expected_mode != "直陈式":
                    issues.append({
                        "type": "emotion_mode_drift",
                        "severity": "medium",
                        "chapter": ch,
                        "detail": f"Ch{ch} 出现 {direct_count} 处直陈式情绪词（期望模式: {expected_mode}）"
                    })
    
    return issues


# --------------------------------------------------------------------------
# 4. 凑字数检测
# --------------------------------------------------------------------------

def check_word_padding(texts: dict) -> list:
    """检测凑字数行为"""
    issues = []
    chapters = sorted(texts.keys())
    
    # 检测无意义重复描写（同一段内相同句子出现≥2次）
    for ch in chapters:
        text = texts[ch]
        paras = text.split('\n')
        for i, para in enumerate(paras):
            p = para.strip()
            if len(p) > 20:
                # 检查同一段内重复
                if paras.count(para) >= 2:
                    issues.append({
                        "type": "paragraph_repeat",
                        "severity": "high",
                        "chapter": ch,
                        "detail": f"Ch{ch} 段落「{p[:30]}…」重复出现"
                    })
    
    # 检测废话段落（全是环境描写，无情节推进）
    env_patterns = [
        r'窗外的.{2,10}(下|落|飘|吹)',
        r'路灯.{2,10}照',
        r'月光.{2,10}(照|落|洒)',
        r'阳光.{2,10}(照|落|洒)',
    ]
    for ch in chapters:
        text = texts[ch]
        env_count = sum(len(re.findall(p, text)) for p in env_patterns)
        total_paras = len([p for p in text.split('\n') if p.strip()])
        if total_paras > 0 and env_count / total_paras > 0.4:
            issues.append({
                "type": "excessive_environment",
                "severity": "medium",
                "chapter": ch,
                "detail": f"Ch{ch} 环境描写占比 {env_count}/{total_paras} 段，可能缺乏情节推进"
            })
    
    return issues


# --------------------------------------------------------------------------
# 5. 乱编检测
# --------------------------------------------------------------------------

def check_fabrication(texts: dict, entities: dict = None) -> list:
    """检测乱编内容。

    2026-09-05 修复（C2）：人名检测改为实体表驱动——原硬编码「温霜禾/江春屿/
    周敏/林悦」是历史旧书角色，对任何新书无效且会误报（如新书角色"小周"被误判
    为旧角色"周敏"笔误）。现在：
      - entities 格式: {"characters": [{"name": "唐雨", "aliases": ["小雨"]}, ...]}
      - 无实体表 → 跳过人名检查并提示（宁可少报不误报）
    """
    issues = []
    chapters = sorted(texts.keys())

    # 检测人名错误（实体表驱动）
    if not entities or not entities.get("characters"):
        # 无实体表时不再做硬编码人名检查（旧版误报根源，已移除）
        pass
    else:
        known_names = set()
        alias_map = {}  # alias/变体 -> 正确名
        for c in entities.get("characters", []):
            name = c.get("name", "")
            if not name:
                continue
            known_names.add(name)
            for alias in (c.get("aliases", []) or []):
                if alias:
                    alias_map[alias] = name
        for ch in chapters:
            text = texts[ch]
            for wrong, correct in alias_map.items():
                # 别名出现但正确名全程未出现 → 可能是漏写或乱编
                if wrong in text and correct not in text:
                    issues.append({
                        "type": "name_error",
                        "severity": "medium",
                        "chapter": ch,
                        "detail": f"Ch{ch} 出现「{wrong}」但未出现实体表中的「{correct}」，请人工确认"
                    })

    # 检测数字矛盾（同一章内同一数字不同值）
    for ch in chapters:
        text = texts[ch]
        phone_nums = re.findall(r'(\d{11})', text)
        if len(set(phone_nums)) >= 2:
            issues.append({
                "type": "number_contradiction",
                "severity": "high",
                "chapter": ch,
                "detail": f"Ch{ch} 出现多个不同手机号 {set(phone_nums)}，可能矛盾"
            })

    return issues


# --------------------------------------------------------------------------
# 6. AI味检测
# --------------------------------------------------------------------------

def check_ai_flavor(texts: dict) -> list:
    """检测AI味内容"""
    issues = []
    
    ai_patterns = [
        (r'她不知道，[^。]{5,30}(会|将|要)', "作者预告旁白"),
        (r'那个画面浮现在脑海', "记忆闪回模板"),
        (r'像一道小小的伤口', "伤口比喻模板"),
        (r'镀了一层很薄的金色', "金色轮廓模板"),
        (r'不需要说很多话[。]', "沉默模板"),
        (r'在就够了[。]', "存在模板"),
        (r'她深吸一口气，[^。]{5,15}不知道', "深呼吸+不知道模板"),
        (r'那一刻，她忽然明白', "顿悟模板"),
    ]
    
    chapters = sorted(texts.keys())
    for ch in chapters:
        text = texts[ch]
        for pat, label in ai_patterns:
            matches = re.findall(pat, text)
            if matches:
                issues.append({
                    "type": "ai_flavor",
                    "severity": "medium",
                    "chapter": ch,
                    "detail": f"Ch{ch} 出现「{label}」×{len(matches)}，AI味痕迹"
                })
    
    return issues


# --------------------------------------------------------------------------
# 检测覆盖率（2026-09-17 第二轮 Task B / 报告 P2-1）
# --------------------------------------------------------------------------
# 「0 问题」与「没检查」在输出里必须可区分：缺 settings/entities.json 时人名
# 乱编检测静默跳过；单章输入时跨章重复检测与风格一致性根本不会执行。
# coverage 把这些前置条件显式报告给调用方。纯加性：不参与 severity 统计，
# 不影响 verdict 判定与任何既有返回键。

# checks 的固定顺序（skipped 按此顺序输出，便于消费方稳定解析）
BQ_CHECK_ORDER = (
    "duplicate_chapters",
    "duplicate_paragraphs",
    "duplicate_sentences",
    "intra_chapter_repeats",
    "plot_continuity",
    "word_padding",
    "fabrication_name",
    "ai_flavor",
    "style_consistency",
)

# 仅在 len(texts) >= 2 时才真正执行的检测项（跨章重复检测）
BQ_CROSS_CHAPTER_CHECKS = (
    "duplicate_chapters",
    "duplicate_paragraphs",
    "duplicate_sentences",
)


def _voice_card_mode(voice_card) -> str:
    """取 voice-card 的 ``emotion_handling.mode``（非 str / 缺失时返回 ""）。"""
    if not isinstance(voice_card, dict):
        return ""
    emotion = voice_card.get("emotion_handling")
    if not isinstance(emotion, dict):
        return ""
    mode = emotion.get("mode")
    return mode if isinstance(mode, str) else ""


def _book_quality_coverage(texts: dict, entities: dict = None,
                           voice_card: dict = None) -> dict:
    """返回 book_quality_check 各检测项「是否真正执行」的覆盖率信息。

    2026-09-17（第二轮 Task B fix round 1 / 审查 I1）：``style_consistency``
    **不能**与跨章重复检测同门控——``check_style_consistency`` 是无条件调用的，
    其情绪分支（``emotion_mode_drift``）逐章执行、单章即可产出问题。此前的门控
    导致「issues 里有 emotion_mode_drift，coverage.skipped 里却有
    style_consistency」的自相矛盾（与本任务目标方向相反）。修正后：
    ``style_consistency`` 可评估 ⇔ ``len(texts) >= 2`` 或 voice_card 提供了非空
    ``emotion_handling.mode``。

    2026-09-17（终审 M-1）：上面这条门控之所以成立，前提是**消费侧用同一口径取 mode**。
    ``check_style_consistency`` 已改为调用 ``_voice_card_mode()``，故 ``mode`` 为非 str
    时两侧一致地判为「无 mode」——不会出现「coverage 判未评估、issues 却产出
    emotion_mode_drift」的窄化矛盾。

    Args:
        texts: {章号:int -> 文本:str}。
        entities: 自动探测到的 entities.json 内容（可为 None）。
        voice_card: 加载到的 voice-card 内容（可为 None）。

    Returns:
        dict: {"entities_loaded": bool, "chapters": int,
               "checks": {9 项固定顺序}, "skipped": [...],
               "skipped_reason": str, "voice_card_loaded": bool}
    """
    has_multi_chapters = len(texts) >= 2
    entities_loaded = bool(isinstance(entities, dict) and entities.get("characters"))
    voice_card_loaded = bool(_voice_card_mode(voice_card))

    checks = {key: True for key in BQ_CHECK_ORDER}
    for key in BQ_CROSS_CHAPTER_CHECKS:
        checks[key] = has_multi_chapters
    checks["fabrication_name"] = entities_loaded
    checks["style_consistency"] = has_multi_chapters or voice_card_loaded

    skipped = [k for k in BQ_CHECK_ORDER if not checks[k]]
    reasons = []
    if not has_multi_chapters:
        reasons.append("仅 1 章，跨章检测未执行")
    if not checks["style_consistency"]:
        reasons.append("仅 1 章且无 voice_card，风格一致性未检测")
    if not entities_loaded:
        reasons.append("缺少 entities.json，人名乱编检测未执行")

    return {
        "entities_loaded": entities_loaded,
        "chapters": len(texts),
        "checks": checks,
        "skipped": skipped,
        "skipped_reason": "；".join(reasons),
        "voice_card_loaded": voice_card_loaded,
    }


# --------------------------------------------------------------------------
# 主函数
# --------------------------------------------------------------------------

def book_quality_check(chapter_dir: str, voice_card_path: str = None, prev_chapters_dir: str = None) -> dict:
    """全书内容质检。

    2026-09-05: 人名检测支持实体表——自动探测章节目录上两级/同级的
    settings/entities.json（write.py 入库结构为 novel_dir/settings/），
    也可由调用方通过 prev_chapters_dir 之外的方式扩展。

    2026-09-16: 章节加载统一委托 `chapter_loader.load_chapter_texts()`——备份/构建
    目录被排除，同章号冲突不再静默覆盖，而是返回
    `{"error": ..., "error_type": "chapter_load"}`（保持主函数错误 JSON 兼容）。
    """
    chapter_path = Path(chapter_dir)

    # 加载章节文本（统一委托 chapter_loader：排除备份/构建目录 + 同章号冲突显式报错）
    try:
        texts = chapter_loader.load_chapter_texts(chapter_path)
    except chapter_loader.ChapterLoadError as exc:
        return {"error": str(exc), "error_type": "chapter_load"}

    if not texts:
        return {"error": "未找到章节文件"}

    # 加载 voice-card（可选）
    voice_card = None
    if voice_card_path:
        voice_card = json.loads(Path(voice_card_path).read_text(encoding='utf-8'))

    # 自动探测实体表（可选）。章节传入路径可能是 novel_dir/chapters（目录）或
    # 单章文件，实体表约定位于 novel_dir/settings/entities.json：
    #   目录 → <dir>/settings/ 与 <dir.parent>/settings/ 都探测
    #   文件 → <file.parent>/settings/ 与 <file.parent.parent>/settings/
    entities = None
    bases = []
    if chapter_path.is_dir():
        bases = [chapter_path, chapter_path.parent]
    else:
        bases = [chapter_path.parent, chapter_path.parent.parent]
    for base in bases:
        candidate = base / "settings" / "entities.json"
        if candidate.exists():
            try:
                entities = json.loads(candidate.read_text(encoding='utf-8'))
            except Exception:
                entities = None
            break

    # 运行所有检查
    all_issues = []

    if len(texts) >= 2:
        all_issues.extend(check_duplicate_chapters(texts))
        all_issues.extend(check_duplicate_paragraphs(texts))
        all_issues.extend(check_duplicate_sentences(texts))

    for ch, text in texts.items():
        single = {ch: text}
        all_issues.extend(check_plot_continuity(single))
        all_issues.extend(check_word_padding(single))
        all_issues.extend(check_fabrication(single, entities))
        all_issues.extend(check_ai_flavor(single))
        # 章内重复句检测（单章也要检测，故放在逐章循环内）
        all_issues.extend(check_intra_chapter_repeats(single))

    all_issues.extend(check_style_consistency(texts, voice_card))
    
    # 统计
    severity_count = Counter(i['severity'] for i in all_issues)
    type_count = Counter(i['type'] for i in all_issues)
    
    # 判定
    critical = severity_count.get('critical', 0)
    high = severity_count.get('high', 0)
    
    if critical > 0:
        verdict = "FAIL"
    elif high >= 5:
        verdict = "FAIL"
    elif high > 0:
        verdict = "WARN"
    else:
        verdict = "PASS"
    
    return {
        "total_chapters": len(texts),
        "total_issues": len(all_issues),
        "severity": dict(severity_count),
        "types": dict(type_count),
        "verdict": verdict,
        "issues": all_issues[:MAX_REPORTED_ISSUES],  # 最多输出 MAX_REPORTED_ISSUES 条
        # 2026-09-17（终审 M-5）：问题数超过上限时 `issues` 被截断，但 `total_issues`
        # 是真实总数——只给总数不给标记会让读者以为列表就是全部。纯新增键，
        # 既有键与判定规则不变。
        "issues_truncated": len(all_issues) > MAX_REPORTED_ISSUES,
        "issues_limit": MAX_REPORTED_ISSUES,
        # 2026-09-17（第二轮 Task B / 报告 P2-1）：追加覆盖率，区分「0 问题」与
        # 「没检查」。纯新增键，既有键与判定规则不变。
        # fix round 1（审查 I1）：需传入 voice_card——style_consistency 的情绪分支
        # 单章即可产出问题，门控不能只看章数。
        "coverage": _book_quality_coverage(texts, entities, voice_card),
    }


def format_truncation_hint(total: int, rendered: int) -> str:
    """实际渲染条数少于总数时返回一行提示，否则返回空串。

    各处 CLI 渲染的问题行数不同（15 / 20 / 5 / 8），但「被砍短了就得说明」这条
    规则一致，因此统一到这里：只有当 ``rendered < total`` 时才提示，且提示里的
    条数取调用方传入的 ``rendered``——它与实际打印的行数同源，不会漂移；未砍短
    时返回空串，调用方据此做到「不提示就零新增输出」。
    """
    if rendered >= total:
        return ""
    return f"⚠ 共 {total} 条，仅显示前 {rendered} 条"


def main():
    ap = argparse.ArgumentParser(description="全书内容质检")
    ap.add_argument("chapter_dir", help="章节目录或单章txt文件路径")
    ap.add_argument("--voice", help="voice-card JSON（可选，用于风格一致性检查）")
    ap.add_argument("--json", action="store_true", help="输出JSON格式")
    args = ap.parse_args()
    
    result = book_quality_check(args.chapter_dir, args.voice)

    # 未找到章节文件时优雅退出（避免 KeyError）
    if "error" in result:
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"[X] {result['error']}")
        sys.exit(1)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("全书内容质检")
        print(f"{'='*50}")
        print(f"章节: {result['total_chapters']} | 问题: {result['total_issues']} | 判定: {result['verdict']}")
        print()
        for sev in ['critical', 'high', 'medium', 'low']:
            count = result['severity'].get(sev, 0)
            if count:
                print(f"  {sev}: {count}")
        print()
        # 本命令实际渲染的问题行数：切片与下方提示共用，避免两处各写一份字面量。
        cli_issue_rows = 15
        shown_issues = result['issues'][:cli_issue_rows]
        for issue in shown_issues:
            sev_icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '⚪'}.get(issue['severity'], '⚪')
            print(f"  {sev_icon} {issue['detail']}")
        # 2026-09-17（第二轮收口）：本命令只列 cli_issue_rows 条，JSON 里也最多
        # issues_limit 条——只要实际渲染条数少于总数就必须说明（不只是超过 50 条时），
        # 否则「31 个问题只列 15 条」会被误读。提示中的条数取实际渲染行数，不写字面量；
        # 未砍短时不新增任何输出。
        hint = format_truncation_hint(result['total_issues'], len(shown_issues))
        if hint:
            # 响应体也被截断时（issues_limit），额外说明 --json 的上限。
            limit_note = (f"（--json 输出最多 {result['issues_limit']} 条）"
                          if result.get("issues_truncated") else "")
            print(f"  {hint}{limit_note}")
    
    sys.exit(0 if result['verdict'] == "PASS" else 1)


if __name__ == "__main__":
    main()
