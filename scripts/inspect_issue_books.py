import os
import re
import sqlite3
from pathlib import Path

db_path = os.path.expandvars(r"%LOCALAPPDATA%\暮冬念春\index.db")
conn = sqlite3.connect(db_path)
row = conn.execute("SELECT title, source_path FROM essence_books WHERE title = '暴力前锋'").fetchone()
title, src_path = row
content = Path(src_path).read_text(encoding="utf-8", errors="ignore")

# 1. 包含节
chaps_with_jie = re.split(r'\n(?=第[0-9零一二三四五六七八九十百千万]+[章节回卷]|Chapter [0-9]+)', content)
short1 = [c.strip() for c in chaps_with_jie if len(c.strip()) < 150]
print(f"包含[节]: 总数={len(chaps_with_jie)}, 短章={len(short1)} ({len(short1)/len(chaps_with_jie):.1%})")

# 2. 排除节（只保留 章/回/卷）
chaps_no_jie = re.split(r'\n(?=第[0-9零一二三四五六七八九十百千万]+[章回卷]|Chapter [0-9]+)', content)
short2 = [c.strip() for c in chaps_no_jie if len(c.strip()) < 150]
print(f"排除[节]: 总数={len(chaps_no_jie)}, 短章={len(short2)} ({len(short2)/len(chaps_no_jie):.1%})")

if short2:
    for s in short2[:5]:
        print("剩余短章:", repr(s[:80]))
