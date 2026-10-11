import os
import sqlite3

conn = sqlite3.connect(os.path.expandvars(r'%LOCALAPPDATA%\暮冬念春\index.db'))
rows = conn.execute("SELECT id, title, content FROM essence_assets WHERE content LIKE '%萧炎%' OR title LIKE '%萧炎%'").fetchall()
print('Direct SQL matching 萧炎:', len(rows))
for r in rows:
    print(' ', r[0], r[1])
