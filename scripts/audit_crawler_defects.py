import os
import re
import sqlite3
from collections import Counter
from pathlib import Path

db_path = os.path.expandvars(r"%LOCALAPPDATA%\暮冬念春\index.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT id, book_id, title, genre, total_chapters, total_chars, source_path FROM essence_books ORDER BY id ASC").fetchall()

print(f"开始对全库 {len(rows)} 本书进行爬虫切片污染全量深度普查...\n")

defects = []

for r in rows:
    p = Path(r["source_path"])
    content = p.read_text(encoding="utf-8", errors="ignore")
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    
    # 提取所有章标题
    ch_titles = [l for l in lines if re.match(r'^(第[0-9零一二三四五六七八九十百千万]+[章节回卷]|Chapter [0-9]+)', l)]
    
    # 1. 标题含有正文特征（比如包含逗号、句号、冒号、省略号，或者过长 > 35 字）
    sentence_like_titles = [t for t in ch_titles if len(t) > 30 or any(punc in t for punc in ["，", "。", "！", "？", "……", "“", "”"])]
    sentence_ratio = len(sentence_like_titles) / max(len(ch_titles), 1)
    
    # 2. 物理短章切片 (< 150 字)
    raw_chaps = re.split(r'\n(?=第[0-9零一二三四五六七八九十百千万]+[章节回卷]|Chapter [0-9]+)', content)
    short_chaps = [c.strip() for c in raw_chaps if len(c.strip()) < 150]
    short_ratio = len(short_chaps) / max(len(raw_chaps), 1)
    
    # 3. 标题重复率（比如一本书里有几十个一模一样的“第一节”、“第三节”）
    title_counts = Counter(ch_titles)
    most_common = title_counts.most_common(1)
    max_dup_title, max_dup_count = most_common[0] if most_common else ("", 0)
    
    # 综合判定是否存在爬虫抓取残破
    is_defective = False
    reasons = []
    
    if short_ratio > 0.05 and len(short_chaps) > 10:
        is_defective = True
        reasons.append(f"短章率过高: {short_ratio:.1%} ({len(short_chaps)}/{len(raw_chaps)})")
        
    if sentence_ratio > 0.08 and len(sentence_like_titles) > 10:
        is_defective = True
        reasons.append(f"正文误作标题率高: {sentence_ratio:.1%} ({len(sentence_like_titles)}/{len(ch_titles)})")
        
    if max_dup_count > 15 and max_dup_title in ["第一节", "第二节", "第三节", "第四节", "第一章"]:
        is_defective = True
        reasons.append(f"重复标题过多: '{max_dup_title}' 出现 {max_dup_count} 次")
        
    if is_defective:
        defects.append((r["id"], r["title"], r["total_chapters"], r["total_chars"], reasons))

print(f"【普查结论】发现 {len(defects)} 部存在结构性爬虫污染的作品：")
for d in defects:
    print(f"ID={d[0]:03d} | 《{d[1]}》 | {d[2]}章 | {d[3]:,}字 | 原因: {'; '.join(d[4])}")
