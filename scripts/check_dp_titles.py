import os
import sqlite3
from pathlib import Path

db_path = os.path.expandvars(r'%LOCALAPPDATA%\暮冬念春\index.db')
conn = sqlite3.connect(db_path)
p = conn.execute("SELECT source_path FROM essence_books WHERE title = '斗破苍穹'").fetchone()[0]
lines = [l.strip() for l in Path(p).read_text(encoding='utf-8').split('\n') if l.strip()]
ch_titles = [l for l in lines if l.startswith('第') or l.startswith('Chapter')]
bad = [t for t in ch_titles if len(t) > 30 or any(punc in t for punc in ['，', '。', '！', '？', '……', '“', '”'])]
print(f'斗破苍穹总章数: {len(ch_titles)}, 命中数: {len(bad)}')
for b in bad[:10]:
    print(' ', repr(b))
