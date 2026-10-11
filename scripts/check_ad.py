import re
import sqlite3
from pathlib import Path

conn = sqlite3.connect(r"C:\Users\monesy\AppData\Local\暮冬念春\index.db")
conn.row_factory = sqlite3.Row
r = conn.execute("SELECT title, source_path FROM essence_books WHERE title = '暴力前锋'").fetchone()
p = Path(r["source_path"])
text = p.read_text(encoding="utf-8")
hit = re.search(r"请到.*首发", text)
if hit:
    print("Match in 暴力前锋:", repr(text[max(0, hit.start()-30):hit.end()+30]))
