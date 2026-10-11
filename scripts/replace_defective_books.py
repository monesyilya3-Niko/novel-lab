#!/usr/bin/env python3
"""剔除劣质爬虫断章作品，并以超严苛六维标准补齐真正高质量主流长篇网络小说。
"""
import json
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.batch_100_books import (
    FOREIGN_BLACKLIST,
    clean_title_and_author,
    get_opener,
    init_db_connection,
    sanitize_book_id,
    sync_full_work_log,
)

DEFECTIVE_TITLES = ["孢子物语", "暴力前锋"]

def is_strictly_acceptable_webnovel(raw_title: str, clean_title: str, chapters: list[dict[str, str]]) -> tuple[bool, str]:
    """超严苛长篇网文门槛检测"""
    for b in FOREIGN_BLACKLIST:
        if b in raw_title or b in clean_title:
            return False, f"命中黑名单: {b}"
    if re.search(r'[\(（](?:美|英|俄|日|法|德|意|加|瑞典|波兰|捷克|澳|前苏联)[\)）]', raw_title):
        return False, "包含外国作者标记"
    if any(k in raw_title for k in ('(美)', '(英)', '(俄)', '(日)', '·', '世界名著', '名著', '中短篇', '短篇', '选集', '全集')):
        return False, "包含名著/译作标识"
        
    ch_count = len(chapters)
    if ch_count < 60:
        return False, f"章节数不足 60 (实际 {ch_count})"
        
    total_chars = sum(len(c.get("text", "")) for c in chapters)
    if total_chars < 250000:
        return False, f"总字数不足 25 万字 (实际 {total_chars:,})"
        
    avg_chars = total_chars / ch_count
    if avg_chars < 1000:
        return False, f"单章平均字数不足 1000 字 (实际 {avg_chars:.1f})"
        
    # 首章校验
    first_ch = chapters[0].get("chapter", "").strip() if chapters else ""
    is_clean_start = bool(re.search(
        r'(第[0-9零]*[1一]章|第[0-9零]*[1一]节|第[0-9零]*[1一]回|第[0-9零]*[1一]卷|Chapter 0?1\b|第0章|序|引子|楔子)',
        first_ch,
    ))
    if not is_clean_start:
        return False, f"首章非正常起始: '{first_ch}'"
        
    # 短章率严控：短于 150 字的章节比例不得超过 3%，且绝对数量不超过 10
    short_chaps = [c for c in chapters if len(c.get("text", "").strip()) < 150]
    short_ratio = len(short_chaps) / ch_count
    if short_ratio > 0.03 and len(short_chaps) > 8:
        return False, f"短章率超标: {short_ratio:.1%} ({len(short_chaps)}/{ch_count})"
        
    # 标题重复率严控：禁止大面积重复章节标题（如几十个第一节）
    ch_names = [c.get("chapter", "").strip() for c in chapters]
    from collections import Counter
    cnts = Counter(ch_names)
    top_title, top_count = cnts.most_common(1)[0] if cnts else ("", 0)
    if top_count > 10 and top_title in ["第一节", "第二节", "第三节", "第四节", "第一章"]:
        return False, f"重复标题过多: '{top_title}' 出现 {top_count} 次"
        
    return True, "合格"


def purge_defective_books(conn: sqlite3.Connection):
    """干净、级联剔除有缺陷的作品"""
    print("【步骤 1】清理有缺陷的劣质爬虫作品...")
    for t in DEFECTIVE_TITLES:
        row = conn.execute("SELECT book_id, source_path FROM essence_books WHERE title = ?", (t,)).fetchone()
        if row:
            b_id, p_str = row[0], row[1]
            print(f"  正在级联删除《{t}》(book_id={b_id})...")
            with conn:
                conn.execute("DELETE FROM essence_assets WHERE book_id = ?", (b_id,))
                conn.execute("DELETE FROM essence_chains WHERE book_id = ?", (b_id,))
                conn.execute("DELETE FROM essence_books WHERE book_id = ?", (b_id,))
                conn.execute("DELETE FROM books WHERE book_id = ?", (b_id,))
            p = Path(p_str)
            if p.exists():
                try:
                    p.unlink()
                    print(f"  已删除物理语料文件: {p.name}")
                except Exception as e:
                    print(f"  删除物理语料失败: {e}")
        else:
            print(f"  《{t}》在库中不存在，无需清理。")
    conn.commit()


def scan_and_supplement(conn: sqlite3.Connection, target_count: int = 100):
    """从 900MB+ 开始扫描补足高质量长篇小说"""
    print(f"\n【步骤 2】从 HuggingFace 扫描高质量真长篇作品至目标 {target_count} 本...")
    opener = get_opener()
    
    current_count = conn.execute("SELECT count(*) FROM essence_books").fetchone()[0]
    print(f"当前剩余书籍数: {current_count}，需补足: {target_count - current_count} 本")
    
    chunk_size = 16 * 1024 * 1024
    current_offset = 920 * 1024 * 1024
    max_offset = 3500 * 1024 * 1024
    
    current_book_title = None
    current_book_chapters = []
    line_buffer = ""
    
    from scripts.batch_100_books import check_book_exists, ingest_book_atomic
    
    while current_count < target_count and current_offset < max_offset:
        start_byte = current_offset
        end_byte = current_offset + chunk_size - 1
        print(f">> 扫描区间: {start_byte // (1024*1024)}MB - {end_byte // (1024*1024)}MB (当前: {current_count}/{target_count})...")
        
        req = urllib.request.Request(
            "https://huggingface.co/datasets/wdndev/webnovel-chinese/resolve/main/data/webnovel_0.jsonl",
            headers={"User-Agent": "Mozilla/5.0", "Range": f"bytes={start_byte}-{end_byte}"},
        )
        try:
            with opener.open(req, timeout=45) as resp:
                chunk_text = line_buffer + resp.read().decode("utf-8", errors="ignore")
                lines = chunk_text.split("\n")
                line_buffer = lines[-1]
                valid_lines = lines[:-1]
                
                for line in valid_lines:
                    if not line.strip(): continue
                    try:
                        item = json.loads(line)
                    except Exception:
                        continue
                    raw_t = item.get("title", "").strip()
                    if not raw_t: continue
                    
                    if raw_t != current_book_title:
                        if current_book_title and len(current_book_chapters) >= 60:
                            clean_t, author, genre = clean_title_and_author(current_book_title)
                            ok, reason = is_strictly_acceptable_webnovel(current_book_title, clean_t, current_book_chapters)
                            if ok:
                                b_id = sanitize_book_id(clean_t)
                                if not check_book_exists(conn, b_id, clean_t):
                                    t0 = time.time()
                                    rec = ingest_book_atomic(conn, b_id, clean_t, author, genre, "general", current_book_chapters)
                                    sync_full_work_log(conn)
                                    current_count = conn.execute("SELECT count(*) FROM essence_books").fetchone()[0]
                                    dt = round(time.time() - t0, 2)
                                    print(f"  ✅ 成功补齐入库 [{current_count:03d}/{target_count}]: 《{clean_t}》 ({author} | {rec['chapters']}章 | {rec['chars']:,}字 | 耗时 {dt}s)")
                                    if current_count >= target_count:
                                        break
                                else:
                                    print(f"  [已存在跳过]: 《{clean_t}》")
                            else:
                                pass # 不合格静默跳过
                        current_book_title = raw_t
                        current_book_chapters = [item]
                    else:
                        current_book_chapters.append(item)
        except Exception as e:
            print(f"  扫描出错: {e}，2秒后重试...")
            time.sleep(2.0)
            
        current_offset += chunk_size
        
    sync_full_work_log(conn)
    print("\n补齐工作完成！当前全库书籍总数:", conn.execute("SELECT count(*) FROM essence_books").fetchone()[0])


def main():
    conn = init_db_connection()
    purge_defective_books(conn)
    scan_and_supplement(conn, target_count=100)
    return 0

if __name__ == "__main__":
    sys.exit(main())
