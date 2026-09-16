#!/usr/bin/env python3
"""
量化指标脚本 — 纯标准库（本机无 jieba，故用字符级 + 2-gram 近似）

输出 voice-card / genre-pack schema 所需的量化字段。
句长 / 段落数 / 对话占比 / 字符级 TTR / 高频 2-gram（近似词频）/ 五感词分布。

注意：没有 jieba 时，词频用 CJK 连续串的 2-gram 高频近似（中文词多为 2 字）。
这是合理近似，不是精确分词。要精确词频，后续可装 jieba 后替换 bigram_freq。

用法:
  python metrics.py <book.txt | corpus/> [--out metrics.json]
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

CJK_RE = re.compile(r'[\u4e00-\u9fff]+')
SENT_RE = re.compile(r'[。！？!?…;；\n]')
# 四类成对引号：开引号 → 对应闭引号。
# ASCII 双引号自身既是开也是闭，扫描时按「开/关」切换处理。
PAIR_CLOSE = {'"': '"', '“': '”', '「': '」', '『': '』', '‘': '’'}
# 开引号集合（ASCII " 单独处理，见 dialogue_char_count）
OPEN_QUOTES = '“「『‘'

# 五感词库（精简版，可扩展）
SENSORY = {
    "视觉": ["看", "望", "盯", "瞥", "眨", "映", "闪", "亮", "暗", "红", "白", "黑", "金", "银", "碧", "艳", "炫", "光"],
    "听觉": ["听", "闻", "响", "鸣", "呼", "啸", "低语", "笑", "哭", "嘶", "咆", "声"],
    "嗅觉": ["香", "臭", "腥", "芳", "味", "嗅", "熏"],
    "味觉": ["甜", "苦", "酸", "辣", "咸", "涩", "鲜"],
    "触觉": ["摸", "触", "抚", "冷", "热", "烫", "冰", "软", "硬", "滑", "刺", "疼", "暖"],
}


def sentences(text):
    return [s for s in SENT_RE.split(text) if s.strip()]


def paragraphs(text):
    return [p for p in re.split(r'\n\s*\n', text) if p.strip()]


def cjk_runs(text):
    return CJK_RE.findall(text)


def char_ttr(text):
    """字符级类型-记号比（近似词汇丰富度）。"""
    chars = [c for run in cjk_runs(text) for c in run]
    if not chars:
        return 0.0
    return round(len(set(chars)) / len(chars), 4)


def bigram_freq(text, top=30):
    """CJK 连续串的 2-gram 高频（近似词频）。"""
    grams = Counter()
    for run in cjk_runs(text):
        for i in range(len(run) - 1):
            grams[run[i:i + 2]] += 1
    return [{"gram": g, "count": c} for g, c in grams.most_common(top)]


def dialogue_char_count(text):
    """统计引号内字符数（近似对白字数），支持四类成对引号。

    支持：ASCII ``"..."``、中文双引号 ``“...”``、直角引号 ``「...」``、
    双直角引号 ``『...』``（并兼容 ``‘...’``）。

    扫描规则（单一配对状态，避免不同类型引号互相误闭合）：
      - ASCII ``"`` 在开/关之间切换；
      - 其他开引号仅在当前没有打开引号时打开（嵌套开引号忽略，不计入正文）；
      - 只有与当前打开引号配对的闭引号才结束对白；
      - 其他类型的闭引号按正文字符累计，但不结束当前对白；
      - 开闭引号本身不累计；文末仍未闭合时保留已累计数量（对不完整草稿容错）。

    Args:
        text: 正文字符串。

    Returns:
        int: 引号内字符总数（开闭引号本身不计）。
    """
    count = 0
    close_char = None  # 当前打开引号对应的闭引号；None 表示不在对白中
    for ch in text:
        if ch == '"':
            if close_char is None:
                close_char = '"'
            elif close_char == '"':
                close_char = None
            else:
                count += 1  # 其他引号对未闭合时的 ASCII 引号按正文计
        elif ch in OPEN_QUOTES:
            if close_char is None:
                close_char = PAIR_CLOSE[ch]
            # 已有打开引号时的嵌套开引号忽略（引号本身不累计）
        elif close_char is None:
            continue
        elif ch == close_char:
            close_char = None
        else:
            count += 1
    return count


def dialogue_ratio(text):
    """引号内字符数 / 总字符数（近似对话占比）。

    分子统一走 :func:`dialogue_char_count`（四类引号同一口径）；
    分母保持既有口径：去空白后的总字符数。
    """
    total_chars = len(re.sub(r'\s', '', text))
    count = dialogue_char_count(text)
    return round(count / total_chars, 4) if total_chars else 0.0


def sensory_counts(text):
    return {sense: sum(text.count(w) for w in words) for sense, words in SENSORY.items()}


# 短句/长句阈值（与 schema/voice-card.schema.json 的字段描述一致：
# short_ratio=≤15字短句占比，long_ratio=≥40字长句占比）
SHORT_SENT_MAX = 15
LONG_SENT_MIN = 40


def sentence_length_profile(sent_lens: list) -> dict:
    """由句长列表算出短句/长句占比。

    voice-card 的 sentence_rhythm.short_ratio / long_ratio 依赖这两个值，
    此前 metrics 只算 avg/max/min，导致该三字段恒为 0（数据断流）。
    """
    if not sent_lens:
        return {"short_ratio": 0.0, "long_ratio": 0.0}
    n = len(sent_lens)
    short_n = sum(1 for L in sent_lens if L <= SHORT_SENT_MAX)
    long_n = sum(1 for L in sent_lens if L >= LONG_SENT_MIN)
    return {
        "short_ratio": round(short_n / n, 4),
        "long_ratio": round(long_n / n, 4),
    }


def compute(text):
    sents = sentences(text)
    sent_lens = [len(re.sub(r'\s', '', s)) for s in sents]
    total_chars = len(re.sub(r'\s', '', text))
    profile = sentence_length_profile(sent_lens)
    return {
        "total_chars": total_chars,
        "sentence_count": len(sents),
        "avg_sentence_len": round(sum(sent_lens) / len(sent_lens), 2) if sent_lens else 0,
        "max_sentence_len": max(sent_lens) if sent_lens else 0,
        "min_sentence_len": min(sent_lens) if sent_lens else 0,
        **profile,
        "paragraph_count": len(paragraphs(text)),
        "dialogue_ratio": dialogue_ratio(text),
        "char_ttr": char_ttr(text),
        "top_bigrams": bigram_freq(text),
        "sensory": sensory_counts(text),
        "exclaim_ratio": round(text.count('！') / max(1, len(sents)), 4),
    }


def main():
    ap = argparse.ArgumentParser(description="量化指标（句长/对话占比/TTR/高频2-gram/五感词）")
    ap.add_argument("book", help="TXT 路径，或目录（遍历 .txt）")
    ap.add_argument("--out", help="输出 JSON 路径")
    args = ap.parse_args()

    p = Path(args.book)
    files = list(p.glob("*.txt")) if p.is_dir() else [p]
    all_metrics = {}
    for f in files:
        all_metrics[f.stem] = compute(f.read_text(encoding="utf-8"))

    out = args.out or (p.parent / f"{p.stem}_metrics.json" if not p.is_dir() else "metrics.json")
    Path(out).write_text(json.dumps(all_metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 指标已写入 {out}")
    for name, m in all_metrics.items():
        print(f"  {name}: {m['total_chars']}字, 均句长{m['avg_sentence_len']}, "
              f"对话占比{m['dialogue_ratio']}, TTR{m['char_ttr']}")


if __name__ == "__main__":
    main()
