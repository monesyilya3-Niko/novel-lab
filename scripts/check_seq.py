import os
import sqlite3
from pathlib import Path

conn = sqlite3.connect(os.path.expandvars(r'%LOCALAPPDATA%\暮冬念春\index.db'))
p = conn.execute("SELECT source_path FROM essence_books WHERE title = '奥术神座'").fetchone()[0]
lines = Path(p).read_text(encoding='utf-8').split('\n')
for j in range(9210, 9245):
    print(f"{j}: {repr(lines[j])}")
