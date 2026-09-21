#!/usr/bin/env python3
"""
原文引用自动清洗器 — 从资产 JSON 中清除夹带的原文台词

Pass2/3 模型输出常把「例如」示例写成原文引用（如 '例如：'她把我衣服扒了，拍几张裸照散出去''），
这违反合规红线（连续12字匹配原文）。本脚本自动清洗：
- 删除「例如/比如/如」后紧跟的引号包裹片段（>8字视为疑似原文）
- 删除所有引号内 >12 字且与原文匹配的片段
- 保留抽象描述

用法:
  python clean_verbatim.py <asset.json> <book.txt> [--apply]
  （不带 --apply 只报告；带 --apply 原地修改）
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import compliance as comp


def clean_string(s: str, ngram: set, path: str) -> tuple:
    """清洗单个字符串，返回 (清洗后, 是否改动)。"""
    orig = s
    # 引号字符集：中文引号 + 英文引号（2026-09-01 补齐英文单/双引号，
    # sangshi 的 pass2 用英文单引号 ' 夹带原文，此前漏检导致 compliance REJECT）
    OPEN = "「『“‘'\""
    CLOSE = "」』”’'\""
    # 1. 删除「例如/比如/如」后引号内 >8 字的片段（模型常把原文当示例）
    s = re.sub(r'(例如|比如|如)\s*[：:]\s*[' + OPEN + r']([^' + CLOSE + r']{9,})[' + CLOSE + r']', r'\1', s)
    # 2. 删除引号内 >12 字且与原文匹配的片段（保留短的、非原文的引号短语）
    def drop_quoted(m):
        frag = m.group(2)
        frag_c = re.sub(r'\s+', '', frag)
        if len(frag_c) > 12 and frag_c[:12] in ngram:
            # 2026-09-01 修复：整组删除（含前后引号），避免残留孤立引号
            # 与相邻片段形成错误配对（sangshi 曾因此产生 26 字误报）。
            return ""
        return m.group(0)
    s = re.sub(r'([' + OPEN + r'])([^' + CLOSE + r']{1,40})([' + CLOSE + r'])', drop_quoted, s)
    # 3. 清理清洗后可能残留的孤立引号（连续两个引号中间无内容，或句读旁的单引号）
    s = re.sub(r'[' + OPEN + r'][' + CLOSE + r']{2,}', lambda m: m.group(0)[0], s)
    s = re.sub(r'[、，,]\s*[' + OPEN + r']\s*[' + CLOSE + r']\s*[、，,]', '、', s)
    s = re.sub(r'[、，,]\s*[' + OPEN + r']\s*[' + CLOSE + r']', '', s)
    # 4. 清理删除片段后产生的标点冗余（如"、。"、"、、"、"，，"）
    s = re.sub(r'[、，,]\s*[。；;]', '。', s)
    s = re.sub(r'[、，,]{2,}', '、', s)
    return s, s != orig


def main():
    ap = argparse.ArgumentParser(description="原文引用清洗器")
    ap.add_argument("asset", help="资产 JSON")
    ap.add_argument("book", help="原文 TXT")
    ap.add_argument("--apply", action="store_true", help="原地修改（缺省只报告）")
    args = ap.parse_args()

    asset_path = Path(args.asset)
    asset = json.loads(asset_path.read_text(encoding="utf-8"))
    book = Path(args.book).read_text(encoding="utf-8")
    ngram = comp.build_ngram_index(book)

    changes = []

    def walk(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str):
            cleaned, changed = clean_string(node, ngram, path)
            if changed:
                changes.append((path, node, cleaned))
                # 需要写回——用指针方式麻烦，这里收集后统一处理

    # 用引用方式收集写回点
    write_points = []

    def walk2(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str):
                    cleaned, changed = clean_string(v, ngram, path)
                    if changed:
                        write_points.append((node, k, v, cleaned))
                else:
                    walk2(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, str):
                    cleaned, changed = clean_string(v, ngram, path)
                    if changed:
                        write_points.append((node, i, v, cleaned))
                else:
                    walk2(v, f"{path}[{i}]")

    walk2(asset)
    print(f"发现 {len(write_points)} 处原文引用待清洗：")
    for parent, key, old, new in write_points[:10]:
        print(f"  {key}: …{old[:50]}…")
        print(f"    → …{new[:50]}…")

    if args.apply and write_points:
        for parent, key, old, new in write_points:
            parent[key] = new
        asset_path.write_text(json.dumps(asset, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✓ 已清洗 {len(write_points)} 处并保存")

    # 复扫
    errs, warns = comp.scan_asset(asset, ngram)
    print(f"\n复扫: {len(errs)} 硬错误, {len(warns)} 警告")
    for e in errs[:5]:
        print(f"  ✗ {e}")


if __name__ == "__main__":
    sys.exit(main())
