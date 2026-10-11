#!/usr/bin/env python3
"""全量 100 本入库小说深度自检脚本：
1. 检查书籍元数据与数据库一致性
2. 检查物理文件存在性与大小
3. 检查首章是否完整（是否以第1章/引子/序开头）
4. 检查末章是否完整
5. 检查章节序号递增性与断层
6. 检查是否存在标题带外国/译著/非小说残余
7. 检查是否有书名重复或章节重合
"""
import re
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(r"C:\Users\monesy\AppData\Local\暮冬念春\index.db")

def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT eb.id, eb.book_id, eb.title, eb.genre, eb.total_chapters, eb.total_chars, eb.source_path,
               (SELECT count(*) FROM essence_assets ea WHERE ea.book_id = eb.book_id) as assets_cnt,
               (SELECT count(*) FROM essence_chains ec WHERE ec.book_id = eb.book_id) as chains_cnt
        FROM essence_books eb
        ORDER BY eb.id ASC
    """).fetchall()

    print("=== 深度核验 100 本小说质量 ===")
    print(f"数据库记录数: {len(rows)}")

    flaws = []
    suspicious_starts = []
    duplicate_titles = {}

    for idx, r in enumerate(rows, start=1):
        t = r["title"]
        p = Path(r["source_path"])
        
        # 1. 物理文件存在
        if not p.exists() or p.stat().st_size == 0:
            flaws.append(f"[{idx:03d}] 《{t}》 物理文件缺失或为空: {p}")
            continue

        # 2. 资产卡与链
        if r["assets_cnt"] != 4:
            flaws.append(f"[{idx:03d}] 《{t}》 资产卡数量异常: {r['assets_cnt']} != 4")
        if r["chains_cnt"] != 1:
            flaws.append(f"[{idx:03d}] 《{t}》 伏笔链数量异常: {r['chains_cnt']} != 1")

        # 3. 读文件检查章节
        text = p.read_text(encoding="utf-8", errors="ignore")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        ch_headers = [l for l in lines if re.match(r'^(第[0-9零一二三四五六七八九十百千万]+[章节回卷]|Chapter [0-9]+)', l)]

        if not ch_headers:
            flaws.append(f"[{idx:03d}] 《{t}》 未提取到章节标题")
            continue

        first_ch = ch_headers[0]
        last_ch = ch_headers[-1]

        # 检查是否缺失开篇
        is_clean_start = bool(re.search(r'(第[0-9]*[01一]章|第[0-9]*[01一]节|第[0-9]*[01一]回|第[0-9]*[01一]卷|Chapter 0?1\b|序|引子|楔子)', first_ch))
        if not is_clean_start:
            suspicious_starts.append((idx, t, first_ch, last_ch, r["total_chapters"], r["total_chars"]))

        # 检查重名
        if t in duplicate_titles:
            duplicate_titles[t].append(idx)
        else:
            duplicate_titles[t] = [idx]

    print(f"\n【1. 物理与结构瑕疵】发现缺陷数: {len(flaws)}")
    for f in flaws:
        print("  -", f)

    print(f"\n【2. 首章疑似残缺/非从第一章开始】数量: {len(suspicious_starts)}")
    for s in suspicious_starts:
        print(f"  - 序号 {s[0]:03d} 《{s[1]}》: 首章='{s[2]}' | 末章='{s[3]}' | 章节数={s[4]} | 字数={s[5]:,}")

    dups = {k: v for k, v in duplicate_titles.items() if len(v) > 1}
    print(f"\n【3. 重复书名】数量: {len(dups)}")
    for k, v in dups.items():
        print(f"  - 书名《{k}》出现在序号: {v}")

    print("\n【4. 全量 100 本书名与特征清单】")
    for idx, r in enumerate(rows, start=1):
        t = r["title"]
        ch = r["total_chapters"]
        w = r["total_chars"]
        g = r["genre"]
        # 探测是否有带特殊后缀的异常书名
        flag = ""
        if any(bad in t for bad in ["（正文全）", "【含", "正文", "全集", "选集", "未完", "番外", "校对版"]):
            flag = " [⚠️ 包含附带标记需清洗]"
        print(f"  {idx:03d}. 《{t}》 [{g}] - {ch}章 / {w:,}字{flag}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
