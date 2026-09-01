#!/usr/bin/env python3
"""
合规扫描脚本 — 纯标准库，零依赖

对 LLM 拆书输出的资产 JSON 做版权合规检查：
  1. 连续 12 字以上与原文完全匹配      → REJECT（硬错误）
  2. abstraction_level == "verbal"    → REJECT（硬错误）
  3. contains_verbatim == true        → REJECT（硬错误）
  4. 引号内原文片段 > 20 字           → WARN（人工复核）

用法:
  python compliance.py <asset.json> <book.txt>

退出码: 0=PASS  1=REJECT  2=WARN
"""
import argparse
import json
import re
import sys
from pathlib import Path

WINDOW = 12          # 连续匹配判定长度
QUOTE_WARN = 20      # 引号内原文片段警告阈值

# 引号对：中文引号 + 英文引号（2026-09-01 补齐英文单/双引号，
# sangshi 的 pass2 用英文单引号 ' 夹带原文，此前漏检）
QUOTE_PAIRS = [('「', '」'), ('『', '』'), ('“', '”'), ('‘', '’'), ('"', '"'), ("'", "'")]


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"JSON 解析失败: {e}")
        sys.exit(1)


def build_ngram_index(text: str) -> set:
    """构建原文 12-gram 索引。整本书约 100 万字 → ~100 万窗口，set 查询 O(1)。"""
    # 去掉空白后建索引，避免原文换行破坏连续匹配
    text = re.sub(r'\s+', '', text)
    n = len(text)
    if n < WINDOW:
        return set()
    return {text[i:i + WINDOW] for i in range(n - WINDOW + 1)}


def walk_strings(node, path="", out=None):
    """递归收集 JSON 里所有字符串值及其路径，同时标记特殊字段位置。"""
    if out is None:
        out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, str):
                out.append((f"{path}.{k}" if path else k, v))
            else:
                walk_strings(v, f"{path}.{k}" if path else k, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_strings(v, f"{path}[{i}]", out)
    return out


def find_quoted_fragments(s: str) -> list:
    """提取字符串里所有中文引号包裹的片段（用于 >20 字警告）。"""
    frags = []
    for op, cl in QUOTE_PAIRS:
        pat = re.escape(op) + r'([^' + re.escape(cl) + r']+)' + re.escape(cl)
        frags.extend(m.group(1) for m in re.finditer(pat, s))
    return frags


def scan_asset(asset: dict, ngram: set) -> tuple:
    """
    扫描资产 JSON，返回 (errors, warns) 两组字符串。
    errors 任一命中即 REJECT，warns 需人工复核。
    """
    errors, warns = [], []
    # 检查特殊字段
    for path, val in walk_strings(asset):
        if path.endswith(".abstraction_level") and val == "verbal":
            errors.append(f"abstraction_level='verbal' → REJECT（版权红线） @ {path}")
        if path.endswith(".contains_verbatim") and val is True:
            errors.append(f"contains_verbatim=true → REJECT（版权红线） @ {path}")

    # 逐字段做 12 字连续匹配 + 引号内片段检查
    for path, val in walk_strings(asset):
        # 章节标题是书目元数据（功能性标识），不构成受版权保护的表达 → 豁免
        if path.endswith(".title"):
            continue
        if len(val) < WINDOW:
            continue
        # 去掉空白后滑窗比对
        compact = re.sub(r'\s+', '', val)
        for i in range(len(compact) - WINDOW + 1):
            if compact[i:i + WINDOW] in ngram:
                snippet = compact[max(0, i - 6):i + WINDOW + 6]
                errors.append(f"连续 {WINDOW} 字匹配原文 → REJECT @ {path} …{snippet}…")
                break
        for frag in find_quoted_fragments(val):
            frag_c = re.sub(r'\s+', '', frag)
            if len(frag_c) > QUOTE_WARN:
                warns.append(f"引号内片段 {len(frag_c)} 字 > {QUOTE_WARN} → WARN 人工复核 @ {path} …{frag_c[:30]}…")
    return errors, warns


def main():
    ap = argparse.ArgumentParser(description="拆书输出版权合规扫描")
    ap.add_argument("asset", help="资产 JSON（voice-card / genre-pack / trope-library）")
    ap.add_argument("book", help="原文整本 TXT（用于 12 字连续匹配检测）")
    args = ap.parse_args()

    asset = load_json(Path(args.asset))
    book_text = Path(args.book).read_text(encoding="utf-8")
    ngram = build_ngram_index(book_text)
    print(f"[i] 原文已建索引: {len(ngram):,} 个 {WINDOW}-gram 窗口")

    errors, warns = scan_asset(asset, ngram)

    print(f"\n硬错误 {len(errors)} 条，警告 {len(warns)} 条")
    for e in errors:
        print(f"  ✗ {e}")
    for w in warns:
        print(f"  ⚠ {w}")

    if errors:
        print("\n结论: REJECT（含版权风险，禁止入库）")
        sys.exit(1)
    if warns:
        print("\n结论: WARN（无硬错误，建议人工复核后入库）")
        sys.exit(2)
    print("\n结论: PASS（合规）")
    sys.exit(0)


if __name__ == "__main__":
    main()
