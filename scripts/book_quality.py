#!/usr/bin/env python3
"""
全书内容质检 — 覆盖情节连贯性/文笔一致性/重复检测/凑字数检测

用法:
  python book_quality.py <章节目录或单章txt> [--voice voice-card.json] [--prev-chapters 目录]
  → 输出 JSON 质检报告

检测维度（共 6 大类）：
  1. 跨章重复（重复章节/重复段落/重复句子）
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

# --------------------------------------------------------------------------
# 1. 跨章重复检测
# --------------------------------------------------------------------------

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
    """检测跨章重复句子（>12字，跨≥3章）"""
    issues = []
    sent_chapters = defaultdict(set)
    for ch, text in texts.items():
        for sent in re.findall(r'[^。！？\n]{12,40}[。！？]', text):
            sent = sent.strip()
            if len(sent) >= 12:
                sent_chapters[sent].add(ch)
    for sent, chs in sent_chapters.items():
        if len(chs) >= 3:
            issues.append({
                "type": "duplicate_sentence",
                "severity": "medium",
                "chapters": sorted(chs),
                "detail": f"句子「{sent[:30]}…」在 {len(chs)} 章重复"
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
        expected_mode = voice_card.get('emotion_handling', {}).get('mode', '')
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
# 主函数
# --------------------------------------------------------------------------

def book_quality_check(chapter_dir: str, voice_card_path: str = None, prev_chapters_dir: str = None) -> dict:
    """全书内容质检。

    2026-09-05: 人名检测支持实体表——自动探测章节目录上两级/同级的
    settings/entities.json（write.py 入库结构为 novel_dir/settings/），
    也可由调用方通过 prev_chapters_dir 之外的方式扩展。
    """
    chapter_path = Path(chapter_dir)

    # 加载章节文本
    texts = {}
    if chapter_path.is_file():
        # 单章文件
        text = chapter_path.read_text(encoding='utf-8')
        texts[1] = text
    elif chapter_path.is_dir():
        # 章节目录（递归，兼容 chapters/arc-N/chapter-NNN.txt 的嵌套结构）
        for f in sorted(chapter_path.rglob('*.txt')):
            m = re.search(r'(\d+)', f.stem)
            if m:
                ch_num = int(m.group(1))
                texts[ch_num] = f.read_text(encoding='utf-8')

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
        "issues": all_issues[:50],  # 最多输出 50 条
    }


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
        print(f"全书内容质检")
        print(f"{'='*50}")
        print(f"章节: {result['total_chapters']} | 问题: {result['total_issues']} | 判定: {result['verdict']}")
        print()
        for sev in ['critical', 'high', 'medium', 'low']:
            count = result['severity'].get(sev, 0)
            if count:
                print(f"  {sev}: {count}")
        print()
        for issue in result['issues'][:15]:
            sev_icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '⚪'}.get(issue['severity'], '⚪')
            print(f"  {sev_icon} {issue['detail']}")
    
    sys.exit(0 if result['verdict'] == "PASS" else 1)


if __name__ == "__main__":
    main()
