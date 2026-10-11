import re
import sqlite3
from pathlib import Path

conn = sqlite3.connect(r"C:\Users\monesy\AppData\Local\暮冬念春\index.db")
conn.row_factory = sqlite3.Row

for title in ["暴力前锋", "孢子物语"]:
    r = conn.execute("SELECT title, source_path FROM essence_books WHERE title = ?", (title,)).fetchone()
    p = Path(r["source_path"])
    text = p.read_text(encoding="utf-8")
    raw_chaps = re.split(r'\n(?=第[0-9零一二三四五六七八九十百千万]+[章节回卷]|Chapter [0-9]+)', text)
    shorts = [c.strip() for c in raw_chaps if len(c.strip()) < 150]
    print(f"=== {title} === (total {len(raw_chaps)}, short {len(shorts)})")
    for s in shorts[:5]:
        print("  Sample short:", repr(s))
