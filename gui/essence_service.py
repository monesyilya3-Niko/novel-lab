"""小说精华数据库核心服务层（Novel Essence Database Service）。

职责：
1. 100% 纯 Python 标准库零依赖实现（sqlite3 / json / re / collections / datetime / difflib）。
2. 提供小说精华书籍档案、五维资产（开篇/大纲/人设/桥段/文风/伏笔）、伏笔回收链的 CRUD 与级联清理。
3. 提供全离线宏观节奏与文风快速萃取、黄金三章开篇解构、核心高频角色提取。
4. 提供一键反哺至写作工坊（一键转入大纲 writing_outlines、人物卡 writing_characters 或灵感便签 writing_notes）。

约束与铁律：
- 运行时路径在函数内实时求值（不设模块级路径常量）；
- 耗时计算在事务外完成，写库采用微事务（with db.tx()）；
- 遵循题材隔离与级联收敛原则，删除书籍时原子化清理关联资产。
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from gui import db
from gui.logging_setup import get_logger
from gui.services import ServiceError

_log = get_logger("essence_service")

# 资产分类白名单
ASSET_CATEGORIES = ("opening", "outline", "persona", "trope", "style", "hook")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# 1. 书籍档案管理（Essence Books）
# ---------------------------------------------------------------------------

def list_books(genre: str | None = None, platform: str | None = None) -> list[dict[str, Any]]:
    """获取所有已归档或分析的小说精华书籍列表。"""
    conn = db.get_conn()
    query = "SELECT * FROM essence_books"
    params: list[Any] = []
    conds: list[str] = []
    if genre:
        conds.append("genre = ?")
        params.append(genre)
    if platform:
        conds.append("platform = ?")
        params.append(platform)
    if conds:
        query += " WHERE " + " AND ".join(conds)
    query += " ORDER BY updated_at DESC, id DESC"

    rows = conn.execute(query, params).fetchall()
    res = []
    for r in rows:
        d = dict(r)
        try:
            d["meta"] = json.loads(d.get("meta_json") or "{}")
        except Exception:
            d["meta"] = {}
        res.append(d)
    return res


def get_book(book_id: str) -> dict[str, Any]:
    """获取指定小说的精华档案详情。"""
    if not book_id or not isinstance(book_id, str):
        raise ServiceError("book_id 必须为非空字符串", 400)
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM essence_books WHERE book_id = ?", (book_id,)).fetchone()
    if not row:
        raise ServiceError(f"未找到小说精华档案: {book_id}", 404)
    d = dict(row)
    try:
        d["meta"] = json.loads(d.get("meta_json") or "{}")
    except Exception:
        d["meta"] = {}
    return d


def create_or_update_book(
    book_id: str,
    title: str,
    source_path: str = "",
    genre: str = "general",
    platform: str = "general",
    total_chapters: int = 0,
    total_chars: int = 0,
    analyzed_chapters: int = 0,
    status: str = "ready",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """创建或更新小说精华档案记录。"""
    if not book_id or not isinstance(book_id, str):
        raise ServiceError("book_id 必须为非空字符串", 400)
    if not title or not isinstance(title, str):
        raise ServiceError("title 必须为非空字符串", 400)

    now = _now_iso()
    meta_str = json.dumps(meta or {}, ensure_ascii=False)

    with db.tx() as conn:
        conn.execute(
            """
            INSERT INTO essence_books
                (book_id, title, source_path, genre, platform, total_chapters, total_chars,
                 analyzed_chapters, status, meta_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(book_id) DO UPDATE SET
                title = excluded.title,
                source_path = CASE WHEN excluded.source_path != '' THEN excluded.source_path ELSE essence_books.source_path END,
                genre = excluded.genre,
                platform = excluded.platform,
                total_chapters = CASE WHEN excluded.total_chapters > 0 THEN excluded.total_chapters ELSE essence_books.total_chapters END,
                total_chars = CASE WHEN excluded.total_chars > 0 THEN excluded.total_chars ELSE essence_books.total_chars END,
                analyzed_chapters = excluded.analyzed_chapters,
                status = excluded.status,
                meta_json = excluded.meta_json,
                updated_at = excluded.updated_at
            """,
            (book_id, title.strip(), source_path, genre, platform,
             total_chapters, total_chars, analyzed_chapters, status, meta_str, now, now),
        )
    return get_book(book_id)


def delete_book(book_id: str) -> dict[str, Any]:
    """级联删除指定小说的全部精华档案、资产、伏笔链与任务记录（收敛清理无残留）。"""
    if not book_id or not isinstance(book_id, str):
        raise ServiceError("book_id 必须为非空字符串", 400)

    with db.tx() as conn:
        conn.execute("DELETE FROM essence_assets WHERE book_id = ?", (book_id,))
        conn.execute("DELETE FROM essence_chains WHERE book_id = ?", (book_id,))
        conn.execute("DELETE FROM essence_tasks WHERE book_id = ?", (book_id,))
        res = conn.execute("DELETE FROM essence_books WHERE book_id = ?", (book_id,))
        if res.rowcount == 0:
            raise ServiceError(f"未找到待删除小说档案: {book_id}", 404)

    return {"deleted": True, "book_id": book_id}


# ---------------------------------------------------------------------------
# 2. 精华资产管理（Essence Assets）
# ---------------------------------------------------------------------------

def list_assets(
    book_id: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    genre: str | None = None,
    platform: str | None = None,
) -> list[dict[str, Any]]:
    """查询结构化精华资产列表。"""
    conn = db.get_conn()
    query = "SELECT * FROM essence_assets"
    conds: list[str] = []
    params: list[Any] = []

    if book_id:
        conds.append("book_id = ?")
        params.append(book_id)
    if category:
        conds.append("category = ?")
        params.append(category)
    if genre:
        conds.append("genre = ?")
        params.append(genre)
    if platform:
        conds.append("platform = ?")
        params.append(platform)
    if tag:
        conds.append("tags LIKE ?")
        params.append(f"%{tag}%")

    if conds:
        query += " WHERE " + " AND ".join(conds)
    query += " ORDER BY rating DESC, updated_at DESC, id DESC"

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def create_asset(
    book_id: str,
    category: str,
    title: str,
    content: str,
    summary: str = "",
    tags: str = "",
    genre: str = "general",
    platform: str = "general",
    rating: int = 5,
    user_note: str = "",
) -> dict[str, Any]:
    """新增一条小说精华资产卡片。"""
    if not book_id or not isinstance(book_id, str):
        raise ServiceError("book_id 必须为非空字符串", 400)
    if category not in ASSET_CATEGORIES:
        raise ServiceError(f"不支持的资产分类: {category}，有效选项: {', '.join(ASSET_CATEGORIES)}", 400)
    if not title or not isinstance(title, str):
        raise ServiceError("title 必须为非空字符串", 400)
    if not content or not isinstance(content, str):
        raise ServiceError("content 必须为非空字符串", 400)

    now = _now_iso()
    with db.tx() as conn:
        cur = conn.execute(
            """
            INSERT INTO essence_assets
                (book_id, category, title, summary, content, tags, genre, platform,
                 rating, user_note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (book_id, category, title.strip(), summary.strip(), content.strip(),
             tags.strip(), genre, platform, int(rating), user_note.strip(), now, now),
        )
        asset_id = cur.lastrowid

    row = db.get_conn().execute("SELECT * FROM essence_assets WHERE id = ?", (asset_id,)).fetchone()
    return dict(row)


def update_asset(asset_id: int, **fields: Any) -> dict[str, Any]:
    """更新指定精华资产（支持更新标题、内容、评分、个人批注与标签）。"""
    allowed = {"title", "summary", "content", "tags", "genre", "platform", "rating", "user_note"}
    updates: list[str] = []
    params: list[Any] = []
    for k, v in fields.items():
        if k in allowed:
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        raise ServiceError("无有效更新字段", 400)

    now = _now_iso()
    updates.append("updated_at = ?")
    params.append(now)
    params.append(asset_id)

    with db.tx() as conn:
        res = conn.execute(f"UPDATE essence_assets SET {', '.join(updates)} WHERE id = ?", params)
        if res.rowcount == 0:
            raise ServiceError(f"未找到资产: {asset_id}", 404)

    row = db.get_conn().execute("SELECT * FROM essence_assets WHERE id = ?", (asset_id,)).fetchone()
    return dict(row)


def delete_asset(asset_id: int) -> dict[str, Any]:
    """删除指定精华资产。"""
    with db.tx() as conn:
        res = conn.execute("DELETE FROM essence_assets WHERE id = ?", (asset_id,))
        if res.rowcount == 0:
            raise ServiceError(f"未找到待删除资产: {asset_id}", 404)
    return {"deleted": True, "id": asset_id}


# ---------------------------------------------------------------------------
# 3. 伏笔回收链管理（Foreshadowing Chains）
# ---------------------------------------------------------------------------

def list_chains(book_id: str) -> list[dict[str, Any]]:
    """查询指定小说的伏笔暗线回收链条。"""
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM essence_chains WHERE book_id = ? ORDER BY hook_chapter ASC, id ASC",
        (book_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def create_chain(
    book_id: str,
    clue_name: str,
    hook_chapter: int = 1,
    payoff_chapter: int = 1,
    hook_text: str = "",
    payoff_text: str = "",
    status: str = "resolved",
    analysis: str = "",
) -> dict[str, Any]:
    """创建一条伏笔暗线回收记录。"""
    if not book_id or not isinstance(book_id, str):
        raise ServiceError("book_id 必须为非空字符串", 400)
    if not clue_name or not isinstance(clue_name, str):
        raise ServiceError("clue_name 必须为非空字符串", 400)

    now = _now_iso()
    with db.tx() as conn:
        cur = conn.execute(
            """
            INSERT INTO essence_chains
                (book_id, hook_chapter, payoff_chapter, hook_text, payoff_text,
                 clue_name, status, analysis, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (book_id, int(hook_chapter), int(payoff_chapter), hook_text.strip(),
             payoff_text.strip(), clue_name.strip(), status, analysis.strip(), now),
        )
        chain_id = cur.lastrowid

    row = db.get_conn().execute("SELECT * FROM essence_chains WHERE id = ?", (chain_id,)).fetchone()
    return dict(row)


# ---------------------------------------------------------------------------
# 4. 纯离线宏观节奏与文风快速萃取（标准库毫秒级）
# ---------------------------------------------------------------------------

_CHAPTER_SPLIT_RE = re.compile(
    r"(?m)^\s*(第\s*[0-9零〇一二三四五六七八九十百千万两]{1,8}\s*[章节回卷幕部]"
    r"|Chapter\s+[0-9]+|楔子|序言|尾声|番外[0-9]*)\s*([^\n\r]*)$",
    re.IGNORECASE
)


def split_chapters_simple(text: str) -> list[tuple[str, str]]:
    """纯标准库智能切章，返回 [(title, content), ...] 列表。"""
    matches = list(_CHAPTER_SPLIT_RE.finditer(text))
    if not matches:
        # 无显式章名时，按约 3000 字分段
        step = 3000
        parts = []
        for i in range(0, len(text), step):
            idx = (i // step) + 1
            parts.append((f"第{idx}章", text[i:i + step]))
        return parts

    chapters: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        raw_title = m.group(0).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        chapters.append((raw_title, body))
    return chapters


def extract_macro_essence(
    text: str,
    title: str,
    genre: str = "general",
    platform: str = "general",
) -> dict[str, Any]:
    """提取整本书的离线宏观数据：全书文风指标、章节节奏心电图、高频角色候选。"""
    total_chars = len(text)
    chapters = split_chapters_simple(text)
    total_chapters = len(chapters)

    # 1. 对话占比与平均句长
    quote_matches = re.findall(r'[“"「]([^”"」]+)[”"」]', text)
    dialogue_chars = sum(len(q) for q in quote_matches)
    dialogue_ratio = round((dialogue_chars / total_chars) * 100, 1) if total_chars > 0 else 0

    sentences = [s.strip() for s in re.split(r'[。！？!?\n]+', text) if len(s.strip()) > 1]
    avg_sentence_len = round(sum(len(s) for s in sentences) / len(sentences), 1) if sentences else 0

    # 2. 章节长度心跳曲线与波峰检测（大于平均字数 1.3 倍视为高潮大章）
    chapter_lengths = [len(c[1]) for c in chapters]
    avg_chapter_len = int(sum(chapter_lengths) / total_chapters) if total_chapters > 0 else 0

    climax_chapters: list[dict[str, Any]] = []
    for i, (ctitle, cbody) in enumerate(chapters, 1):
        c_len = len(cbody)
        if c_len > avg_chapter_len * 1.3 and c_len > 1000:
            climax_chapters.append({
                "chapter_num": i,
                "title": ctitle,
                "length": c_len,
            })

    # 3. 高频人物实体启发式提取（2~3字中文专有名词）
    person_candidates = extract_characters_from_text(text, top_n=6)

    return {
        "title": title,
        "genre": genre,
        "platform": platform,
        "total_chars": total_chars,
        "total_chapters": total_chapters,
        "avg_chapter_len": avg_chapter_len,
        "dialogue_ratio": dialogue_ratio,
        "avg_sentence_len": avg_sentence_len,
        "climax_peaks": climax_chapters[:8],
        "top_characters": person_candidates,
        "rhythm_assessment": "高频紧凑型" if avg_sentence_len < 16 else "舒缓沉浸型",
    }


def extract_characters_from_text(text: str, top_n: int = 5) -> list[dict[str, Any]]:
    """纯标准库正则提取高频出现的中文主角与配角名字候选。"""
    # 匹配常见人物称谓与后接名字或常见中文名格式（姓氏+名）
    # 排除常见代词与语气词
    stopwords = {"什么", "怎么", "这个", "那个", "他们", "我们", "自己", "一个", "有些", "这时", "突然", "虽然", "如果", "为了", "因为", "所以", "不过", "然而", "只见", "若是"}
    pattern = re.compile(r'(?:说|道|问|叹|笑|喝|喝道|冷笑|暗想|心道|喊道|喝问)\s*[,，:：]?\s*["“]')

    # 扫描对话前导名字（如 林轩冷笑道 / 萧炎叹息道）
    names_counter: Counter[str] = Counter()
    for m in re.finditer(r'([\u4e00-\u9fa5]{2,3})(?:冷笑|微笑道|大笑道|叹道|沉声道|怒喝道|摇了摇头|点了点头|拔出长剑|向前一步)', text):
        name = m.group(1).strip()
        if name not in stopwords:
            names_counter[name] += 2

    # 常规双字三字高频词补充
    for m in re.finditer(r'(?:主角|公子|小姐|师兄|师弟|师姐|长老|前辈|宗主|道友)\s*([\u4e00-\u9fa5]{2,3})', text):
        name = m.group(1).strip()
        if name not in stopwords:
            names_counter[name] += 3

    top = names_counter.most_common(top_n)
    return [{"name": name, "frequency": count} for name, count in top]


def extract_opening_slice(chapters: list[tuple[str, str]]) -> dict[str, Any]:
    """提取前三章黄金开篇深度解构切片。"""
    if not chapters:
        return {"opening_analysis": "正文为空"}

    first_ch_title, first_ch_body = chapters[0]
    opening_snippet = first_ch_body[:400].strip()

    # 检查开篇危机或入戏冲突
    conflict_keywords = ["退婚", "杀", "死", "剑", "血", "逃", "跪", "离婚", "雷霆", "系统", "绝望", "穿越", "重生"]
    has_conflict = any(k in opening_snippet for k in conflict_keywords)

    # 检查首章断章钩子（后 300 字）
    closing_snippet = first_ch_body[-300:].strip()
    hook_keywords = ["忽然", "竟然", "那一刻", "怎么会", "危险", "杀意", "倒吸了一口气", "秘密", "未完"]
    has_hook = any(k in closing_snippet for k in hook_keywords)

    return {
        "chapter_title": first_ch_title,
        "first_300_words": opening_snippet[:300],
        "has_immediate_conflict": has_conflict,
        "end_of_chapter_hook": closing_snippet[-150:],
        "hook_detected": has_hook,
        "opening_grade": "A（开篇紧凑抓人）" if (has_conflict and has_hook) else "B（可适度强化首尾冲突）",
    }


# ---------------------------------------------------------------------------
# 5. 一键反哺至现有写作工坊（One-Click Adopt）
# ---------------------------------------------------------------------------

def adopt_asset_to_project(
    asset_id: int,
    project: str,
    target_kind: str = "outline",
) -> dict[str, Any]:
    """将提炼出的精华资产一键转入项目写作工坊（大纲 / 人物卡 / 灵感便签）。"""
    if not project or not isinstance(project, str):
        raise ServiceError("project 必须为非空字符串", 400)

    asset_row = db.get_conn().execute("SELECT * FROM essence_assets WHERE id = ?", (asset_id,)).fetchone()
    if not asset_row:
        raise ServiceError(f"未找到待转入资产: {asset_id}", 404)

    asset = dict(asset_row)
    now = _now_iso()

    with db.tx() as conn:
        if target_kind == "outline":
            # 导入到 writing_outlines
            cur = conn.execute(
                """
                INSERT INTO writing_outlines (project, kind, title, summary, status, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project, "chapter", asset["title"], asset.get("summary") or asset["content"][:200], "planned", 999, now, now),
            )
            adopted_id = cur.lastrowid
            return {"adopted": True, "target_kind": "outline", "adopted_id": adopted_id, "project": project}

        elif target_kind == "character":
            # 导入到 writing_characters
            extra_meta = {"from_essence_id": asset_id, "category": asset["category"], "genre": asset["genre"]}
            cur = conn.execute(
                """
                INSERT INTO writing_characters (project, name, role, description, extra, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (project, asset["title"], "核心参考原型", asset["content"], json.dumps(extra_meta, ensure_ascii=False), now, now),
            )
            adopted_id = cur.lastrowid
            return {"adopted": True, "target_kind": "character", "adopted_id": adopted_id, "project": project}

        elif target_kind == "note":
            # 导入到 writing_notes
            cur = conn.execute(
                """
                INSERT INTO writing_notes (project, title, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project, f"【精华灵感】{asset['title']}", asset["content"], now, now),
            )
            adopted_id = cur.lastrowid
            return {"adopted": True, "target_kind": "note", "adopted_id": adopted_id, "project": project}

        else:
            raise ServiceError(f"不支持的反哺目标类型: {target_kind}，可选: outline, character, note", 400)
