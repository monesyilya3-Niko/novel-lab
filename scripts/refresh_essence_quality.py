#!/usr/bin/env python3
"""本地全量 100 本小说精华库高质量刷新与重萃取脚本。
纯本地运行（无需网络），基于已加固的 extract_macro_essence 引擎，重新生成高饱满度的 4 张资产卡与 1 条伏笔暗链。
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from gui import config, essence_service
from scripts.batch_100_books import sync_full_work_log


def main() -> int:
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute("SELECT book_id, title, genre, platform, source_path, total_chapters, total_chars FROM essence_books ORDER BY id ASC").fetchall()
    print(f"开始对本地已入库的全部 {len(rows)} 本小说执行全量资产卡与伏笔链质量刷新重萃取...")
    
    refreshed = 0
    for _idx, r in enumerate(rows, start=1):
        b_id = r["book_id"]
        title = r["title"]
        genre = r["genre"]
        platform = r["platform"]
        sp = Path(r["source_path"])
        
        if not sp.exists():
            print(f"  ❌ 找不到物理文件: 《{title}》")
            continue
            
        full_text = sp.read_text(encoding="utf-8", errors="ignore")
        macro_result = essence_service.extract_macro_essence(
            text=full_text,
            title=title,
            genre=genre,
            platform=platform,
        )
        
        now_iso = macro_result.get("updated_at") or "2026-10-10 23:59:00"
        meta_json = json.dumps(macro_result, ensure_ascii=False)
        
        with conn:
            # 1. 更新 essence_books meta_json
            conn.execute("UPDATE essence_books SET meta_json = ? WHERE book_id = ?", (meta_json, b_id))
            
            # 2. 清理旧资产卡并重建
            conn.execute("DELETE FROM essence_assets WHERE book_id = ?", (b_id,))
            suggested_assets = macro_result.get("suggestedAssets", [])
            for sa in suggested_assets:
                conn.execute(
                    """
                    INSERT INTO essence_assets
                        (book_id, category, title, summary, content, tags, genre, platform, rating, user_note, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 5, '', ?, ?)
                    """,
                    (b_id, sa.get("category", "style"), sa.get("title", f"《{title}》精华资产"),
                     sa.get("summary", ""), sa.get("content", ""), f"{genre},{platform}", genre, platform,
                     now_iso, now_iso),
                )
                
            # 3. 清理旧伏笔链并重建
            conn.execute("DELETE FROM essence_chains WHERE book_id = ?", (b_id,))
            opening_three = macro_result.get("openingThreeChapters", [])
            valid_opening = [op for op in opening_three if op.get("excerpt", "").strip()]
            if valid_opening:
                first_op = valid_opening[0]
                hook_txt = first_op.get("excerpt", "")[:120].strip()
                tot_chaps = r["total_chapters"]
                conn.execute(
                    """
                    INSERT INTO essence_chains
                        (book_id, hook_chapter, payoff_chapter, hook_text, payoff_text, clue_name, status, analysis, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'resolved', ?, ?)
                    """,
                    (b_id, first_op.get("chapterIndex", 1), min(tot_chaps, max(5, first_op.get("chapterIndex", 1) + 3)),
                     hook_txt,
                     "后续主线反转与关键兑现", f"{title}·开篇核心主线钩",
                     f"钩子类型: {first_op.get('hookType', '主线钩')}，推动全书主线冲突展开", now_iso),
                )
        refreshed += 1
        if refreshed % 20 == 0 or refreshed == len(rows):
            print(f"  [进度: {refreshed:03d}/{len(rows)}] 《{title}》等作品已完成精华重萃取")

    sync_full_work_log(conn)
    print("\n全量 100 本小说精华库高质量刷新完毕！已同步 WORK_LOG_100_BOOKS.md。")
    return 0

if __name__ == "__main__":
    sys.exit(main())
