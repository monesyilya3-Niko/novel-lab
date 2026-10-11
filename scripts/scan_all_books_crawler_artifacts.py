import os
import re
import sqlite3
from pathlib import Path

db_path = os.path.expandvars(r"%LOCALAPPDATA%\暮冬念春\index.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT id, book_id, title, genre, total_chapters, total_chars, source_path FROM essence_books ORDER BY id ASC").fetchall()

suspicious_books = []

for r in rows:
    p = Path(r["source_path"])
    if not p.exists():
        suspicious_books.append((r["title"], "文件不存在"))
        continue
    content = p.read_text(encoding="utf-8", errors="ignore")
    raw_chaps = re.split(r'\n(?=第[0-9零一二三四五六七八九十百千万]+[章节回卷]|Chapter [0-9]+)', content)
    
    # 统计短章 (<150字)
    short_chaps = [c.strip() for c in raw_chaps if len(c.strip()) < 150]
    short_ratio = len(short_chaps) / max(len(raw_chaps), 1)
    
    # 统计可疑标题（比如标题含有句号、感叹号、问号、逗号，或者标题含有“第一天/第一次/第一步/第一轮/第一名/第一分队/第一时间”）
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    ch_titles = [l for l in lines if re.match(r'^(第[0-9零一二三四五六七八九十百千万]+[章节回卷]|Chapter [0-9]+)', l)]
    
    bad_title_count = 0
    for ct in ch_titles:
        if any(w in ct for w in ["第一天", "第二天", "第三天", "第四天", "第一次", "第二次", "第一轮", "第二轮", "第一小队", "第一节", "第二节", "第三节", "第四节", "第一球", "第二球", "第三球", "第四球", "第五球"]):
            bad_title_count += 1
            
    bad_title_ratio = bad_title_count / max(len(ch_titles), 1)
    
    if short_ratio > 0.03 or bad_title_ratio > 0.02:
        suspicious_books.append((r["title"], f"短章率={short_ratio:.1%}({len(short_chaps)}/{len(raw_chaps)}), 假标题率={bad_title_ratio:.1%}({bad_title_count})"))

print(f"全库 100 本书扫描完成，发现可疑书籍数: {len(suspicious_books)}")
for sb in suspicious_books:
    print(f"  - 《{sb[0]}》: {sb[1]}")
