import re
import sqlite3
from pathlib import Path

conn = sqlite3.connect(r"C:\Users\monesy\AppData\Local\暮冬念春\index.db")
conn.row_factory = sqlite3.Row

print("=== 调查维度四：9 张资产卡内容过短/为空 ===")
rows = conn.execute("""
    SELECT ea.id, ea.book_id, eb.title, ea.category, ea.title as asset_title, length(ea.content) as c_len, ea.content
    FROM essence_assets ea
    JOIN essence_books eb ON ea.book_id = eb.book_id
    WHERE length(ea.content) < 20
""").fetchall()
for r in rows:
    t = r["title"]
    cat = r["category"]
    cl = r["c_len"]
    c = r["content"]
    print(f"Asset {r['id']}: 《{t}》 category={cat} len={cl} content={repr(c)}")

print("\n=== 调查维度四：6 条伏笔链钩子文本过短/为空 ===")
rows = conn.execute("""
    SELECT ec.id, ec.book_id, eb.title, length(ec.hook_text) as h_len, ec.hook_text
    FROM essence_chains ec
    JOIN essence_books eb ON ec.book_id = eb.book_id
    WHERE length(ec.hook_text) < 10
""").fetchall()
for r in rows:
    t = r["title"]
    hl = r["h_len"]
    ht = r["hook_text"]
    print(f"Chain {r['id']}: 《{t}》 len={hl} hook_text={repr(ht)}")

print("\n=== 调查维度二：异常短章作品与广告命中 ===")
for eb in conn.execute("SELECT book_id, title, source_path FROM essence_books").fetchall():
    p = Path(eb["source_path"])
    text = p.read_text(encoding="utf-8", errors="ignore")
    raw_chaps = re.split(r'\n(?=第[0-9零一二三四五六七八九十百千万]+[章节回卷]|Chapter [0-9]+)', text)
    short_cnt = sum(1 for c in raw_chaps if len(c.strip()) < 150)
    if short_cnt > len(raw_chaps) * 0.05 and short_cnt > 10:
        t = eb["title"]
        print(f"短章多: 《{t}》 短章数={short_cnt}/{len(raw_chaps)} ({short_cnt/len(raw_chaps)*100:.1f}%)")
    for m in ["防盗章", "点击下一页继续阅读", "请到.*首发", "本章未完", "小说网.*免费阅读"]:
        hit = re.search(m, text)
        if hit:
            t = eb["title"]
            print(f"广告命中: 《{t}》 模式={m}")
