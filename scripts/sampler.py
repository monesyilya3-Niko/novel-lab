#!/usr/bin/env python3
"""
分层采样脚本 — 纯标准库，零依赖

解决「整本书塞不进上下文」的根本问题：
把整本 TXT 切成章节，按策略采样 ~25-35 章，输出带标记的分片，
供四遍扫描各自取用不同切片。

用法:
  python sampler.py <corpus/book.txt> [--out corpus/sampled/<name>]
"""
import argparse
import json
import re
from pathlib import Path

# 章节标题识别：第X章 / 第X回 / 第X节 / 第X卷 / Chapter N
CHAPTER_RE = re.compile(
    r'^\s*(第[一二三四五六七八九十百千零0-9]+[章回节卷]|Chapter\s*\d+|CHAPTER\s*\d+)\b'
)
VOLUME_RE = re.compile(r'第[一二三四五六七八九十百千零0-9]+卷')
# 仅用中文引号对，避免 ASCII 直引号在正文里误匹配/贪婪跨越
QUOTE_PAIRS = [('「', '」'), ('『', '』'), ('“', '”'), ('‘', '’')]
# 句子边界（用于定位对话上下文）
SENT_RE = re.compile(r'[。！？!?…;；\n]')


def split_chapters(text):
    """把整本文本切成 (标题, 正文) 列表，过滤空章。"""
    chapters = []
    cur_title, cur_body = "（无标题开头）", []
    for ln in text.splitlines():
        if CHAPTER_RE.match(ln):
            if cur_body or cur_title != "（无标题开头）":
                chapters.append((cur_title.strip(), "\n".join(cur_body).strip()))
            cur_title, cur_body = ln.strip(), []
        else:
            cur_body.append(ln)
    if cur_body:
        chapters.append((cur_title.strip(), "\n".join(cur_body).strip()))
    return [(t, b) for t, b in chapters if b.strip()]


def detect_volumes(chapters):
    """按『第X卷』切分卷边界，返回 [(start, end), ...] 索引对。"""
    bounds, start = [], 0
    for i, (title, _) in enumerate(chapters):
        if VOLUME_RE.search(title):
            if start != i:
                bounds.append((start, i - 1))
            start = i
    bounds.append((start, len(chapters) - 1))
    return bounds


def select(chapters):
    """核心采样策略：开篇全取 + 中段三处连续5章 + 卷末 + 全书末章。"""
    n = len(chapters)
    sel = {}
    # 开篇段 1-10 章全取（商业价值最高）
    for i in range(0, min(10, n)):
        sel[i] = "开篇段(1-10章全取)"
    # 中段 25%/50%/75% 各连续 5 章（必须连续，否则看不出节奏）
    for p in (0.25, 0.5, 0.75):
        c = int(n * p)
        for i in range(max(0, c - 2), min(n - 1, c + 2) + 1):
            sel.setdefault(i, f"中段({int(p * 100)}%位置连续5章)")
    # 每卷末 2 章（与日常章成对对比）
    for (s, e) in detect_volumes(chapters):
        for i in range(max(s, e - 1), e + 1):
            sel.setdefault(i, "卷末高潮段(末2章)")
    # 全书末 2 章（收尾）
    for i in range(max(0, n - 2), n):
        sel.setdefault(i, "全书末章(收尾)")
    return sel


def last_n_chars(text, n=500):
    return text[-n:]


def split_sentences(text):
    return [s for s in re.split(r'[。！？!?…;；\n]', text) if s.strip()]


def extract_dialogue(chapters, indices):
    """抽取选中章里的对话行 + 前后各一句（数据量降到约 20%）。

    先按引号对定位对话片段，再反查其所在句子（避免句内句号把引号劈成两半）。
    """
    out = []
    for i in indices:
        title, body = chapters[i]
        # 句子边界（带字符偏移），用于定位上下文
        boundaries = [m.start() for m in SENT_RE.finditer(body)] + [len(body)]

        def sent_at(k):
            if k < 0 or k >= len(boundaries) - 1:
                return ""
            return body[boundaries[k]:boundaries[k + 1]].strip()

        for op, cl in QUOTE_PAIRS:
            pat = re.escape(op) + r'(?:[^' + re.escape(cl) + r']*)' + re.escape(cl)
            for m in re.finditer(pat, body):
                start = m.start()
                si = 0
                for k in range(len(boundaries) - 1):
                    if boundaries[k] <= start < boundaries[k + 1]:
                        si = k
                        break
                out.append({
                    "chapter": i + 1,
                    "title": title,
                    "before": sent_at(si - 1),
                    "line": sent_at(si),
                    "after": sent_at(si + 1),
                })
    return out


def build_slices(chapters, sel):
    indices = sorted(sel)
    n = len(chapters)
    mid_center = int(n * 0.5)
    style_idx = list(range(max(0, mid_center - 1), min(n - 1, mid_center + 1) + 1))[:3]
    climax_idx = [n - 1]
    opening_idx = list(range(0, min(10, n)))

    vol_ends = []
    for (s, e) in detect_volumes(chapters):
        vol_ends.extend([max(s, e - 1), e])
    commercial_idx = sorted(set(opening_idx + vol_ends + [n - 2, n - 1]))
    commercial_idx = [i for i in commercial_idx if 0 <= i < n]

    slices = {
        "pass1_structure": {
            "note": "结构层：采样章全本 + 章末500字原文（供 LLM 写章节摘要+结构）",
            "chapters": [{
                "index": i + 1, "title": chapters[i][0],
                "text": chapters[i][1],
                "tail500": last_n_chars(chapters[i][1]),
                "reason": sel[i],
            } for i in indices],
        },
        "pass2_character": {
            "note": "人物层：对话行 + 前后各一句（数据量降到约20%）",
            "dialogues": extract_dialogue(chapters, indices),
        },
        "pass3_style": {
            "note": "文风层：中段连续3章全文 + 1章高潮全文",
            "chapters": [{"index": i + 1, "title": chapters[i][0], "text": chapters[i][1]}
                         for i in sorted(set(style_idx + climax_idx))],
        },
        "pass4_commercial": {
            "note": "商业层：前10章全文 + 卷末 + 全书末章",
            "chapters": [{"index": i + 1, "title": chapters[i][0], "text": chapters[i][1]}
                         for i in commercial_idx],
        },
    }
    return slices


def main():
    ap = argparse.ArgumentParser(description="分层采样：整本 TXT → 带标记分片")
    ap.add_argument("book", help="整本小说 TXT 路径")
    ap.add_argument("--out", help="输出目录，默认 corpus/sampled/<书名>")
    args = ap.parse_args()

    src = Path(args.book)
    text = src.read_text(encoding="utf-8")
    chapters = split_chapters(text)
    sel = select(chapters)
    slices = build_slices(chapters, sel)
    indices = sorted(sel)

    name = src.stem
    out = Path(args.out) if args.out else Path("corpus") / "sampled" / name
    out.mkdir(parents=True, exist_ok=True)

    # 章节全文
    ch_dir = out / "chapters"
    ch_dir.mkdir(exist_ok=True)
    for i in indices:
        (ch_dir / f"{i + 1:03d}.txt").write_text(chapters[i][1], encoding="utf-8")

    manifest = {
        "book": name,
        "total_chapters": len(chapters),
        "selected_count": len(indices),
        "selected_indices": [i + 1 for i in indices],
        "reasons": {str(i + 1): sel[i] for i in indices},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    (out / "pass1_structure.txt").write_text(
        "\n\n".join(f"## 第{c['index']}章 {c['title']}\n{c['text']}\n【章末500字】\n{c['tail500']}"
                    for c in slices["pass1_structure"]["chapters"]), encoding="utf-8")
    dlg = slices["pass2_character"]["dialogues"]
    (out / "pass2_dialogue.txt").write_text(
        "\n".join(f"[第{d['chapter']}章 {d['title']}] 前:{d['before']} | 对话:{d['line']} | 后:{d['after']}"
                  for d in dlg), encoding="utf-8")
    (out / "pass3_style.txt").write_text(
        "\n\n".join(f"## 第{c['index']}章 {c['title']}\n{c['text']}"
                    for c in slices["pass3_style"]["chapters"]), encoding="utf-8")
    (out / "pass4_commercial.txt").write_text(
        "\n\n".join(f"## 第{c['index']}章 {c['title']}\n{c['text']}"
                    for c in slices["pass4_commercial"]["chapters"]), encoding="utf-8")
    (out / "slices.json").write_text(json.dumps(slices, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] {name}: 共 {len(chapters)} 章，采样 {len(indices)} 章")
    print(f"  pass2 抽取对话 {len(dlg)} 条")
    print(f"  输出目录: {out}")


if __name__ == "__main__":
    raise SystemExit(main())
