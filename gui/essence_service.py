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

# 资产分类白名单（双向兼容前端同义词）
ASSET_CATEGORIES = ("opening", "outline", "persona", "trope", "style", "hook", "character")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _format_book_dict(r: db.RowLike) -> dict[str, Any]:
    """格式化书籍档案字典，注入前端强契约 camelCase 字段，实现双向完全兼容。"""
    d = dict(r)
    try:
        d["meta"] = json.loads(d.get("meta_json") or "{}")
    except Exception:
        d["meta"] = {}
    meta = d["meta"]

    # 注入前端强契约字段
    b_id = d.get("book_id", "")
    t_chaps = d.get("total_chapters", 0)
    t_chars = d.get("total_chars", 0)
    d["bookId"] = b_id
    d["totalChapters"] = t_chaps
    d["totalChars"] = t_chars
    d["avgChapterLen"] = meta.get("avgChapterLen", t_chars // max(t_chaps, 1))
    d["dialogueRatio"] = meta.get("dialogueRatio", 0.0)
    d["rhythmClimaxInterval"] = meta.get("rhythmClimaxInterval", 20)
    d["aiSlopScore"] = meta.get("aiSlopScore", 0.0)
    d["summary"] = meta.get("summary", f"《{d.get('title', '')}》（共 {t_chaps} 章）")
    d["createdAt"] = d.get("created_at", "")
    d["updatedAt"] = d.get("updated_at", "")
    return d


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
    return [_format_book_dict(r) for r in rows]



def get_book(book_id: str) -> dict[str, Any]:
    """获取指定小说的精华档案详情。"""
    if not book_id or not isinstance(book_id, str):
        raise ServiceError("book_id 必须为非空字符串", 400)
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM essence_books WHERE book_id = ?", (book_id,)).fetchone()
    if not row:
        raise ServiceError(f"未找到小说精华档案: {book_id}", 404)
    return _format_book_dict(row)


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

    return {"deleted": True, "book_id": book_id, "bookId": book_id}


# ---------------------------------------------------------------------------
# 2. 精华资产管理（Essence Assets）
# ---------------------------------------------------------------------------

def _format_asset_dict(r: db.RowLike) -> dict[str, Any]:
    """格式化资产卡片字典，注入前端 camelCase 契约字段。"""
    d = dict(r)
    d["bookId"] = d.get("book_id", "")
    d["userNote"] = d.get("user_note", "")
    d["tags"] = d.get("tags") or ""
    d["summary"] = d.get("summary") or ""
    d["createdAt"] = d.get("created_at", "")
    d["updatedAt"] = d.get("updated_at", "")
    return d


def _format_chain_dict(r: db.RowLike) -> dict[str, Any]:
    """格式化暗链字典，注入前端图谱 camelCase 契约字段。"""
    d = dict(r)
    b_id = d.get("book_id", "")
    hook_ch = d.get("hook_chapter") or 1
    payoff_ch = d.get("payoff_chapter") or 1
    clue = d.get("clue_name", "核心主线暗链")
    hook_txt = d.get("hook_text", "")
    analysis = d.get("analysis", "")

    d["bookId"] = b_id
    d["title"] = clue
    d["category"] = clue.split("·")[-1] if "·" in clue else "主线暗链"
    d["plantChapter"] = hook_ch
    d["revealChapter"] = (hook_ch + payoff_ch) // 2
    d["climaxChapter"] = payoff_ch
    d["description"] = f"{hook_txt}\n\n【伏笔解析】{analysis}".strip() if analysis else hook_txt
    d["createdAt"] = d.get("created_at", "")
    d["updatedAt"] = d.get("updated_at", d.get("created_at", ""))
    return d


def list_assets(
    book_id: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    genre: str | None = None,
    platform: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """查询结构化精华资产列表（支持同义词归一化与全文关键字检索）。"""
    conn = db.get_conn()
    sql = "SELECT * FROM essence_assets"
    conds: list[str] = []
    params: list[Any] = []

    if book_id:
        conds.append("book_id = ?")
        params.append(book_id)
    if category:
        cat = category.strip().lower()
        if cat in ("hook", "opening"):
            conds.append("category IN ('hook', 'opening')")
        elif cat in ("character", "persona"):
            conds.append("category IN ('character', 'persona')")
        else:
            conds.append("category = ?")
            params.append(cat)
    if genre:
        conds.append("genre = ?")
        params.append(genre)
    if platform:
        conds.append("platform = ?")
        params.append(platform)
    if tag:
        conds.append("tags LIKE ?")
        params.append(f"%{tag}%")
    if query:
        q_clean = query.strip()
        conds.append("(title LIKE ? OR tags LIKE ? OR summary LIKE ? OR content LIKE ?)")
        q_p = f"%{q_clean}%"
        params.extend([q_p, q_p, q_p, q_p])

    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY rating DESC, updated_at DESC, id DESC"

    rows = conn.execute(sql, params).fetchall()
    return [_format_asset_dict(r) for r in rows]


def _require_book_exists(book_id: str) -> None:
    """确认 ``essence_books`` 里存在该 book_id，否则 404。

    ⚠️ 写路径必须校验父行存在（2026-10-13 审计修复 D8）：
    create_asset / create_chain 原先只校验 book_id 的类型与非空，
    **不查父行**——实测可用不存在的 book_id 建出"孤儿资产/孤儿暗线"
    （资产行存在、父书行不存在）。后果：界面列出该资产，点进去找不到书，
    且删除书时的级联清理（按 book_id 删子表）永远不会触及它——数据永久残留。

    在**事务外**查询：写路径随后会开自己的事务，此处只做前置校验。
    """
    conn = db.get_conn()
    row = conn.execute(
        "SELECT 1 FROM essence_books WHERE book_id = ?", (book_id,)).fetchone()
    if row is None:
        raise ServiceError(f"未找到小说精华档案: {book_id}（请先创建书籍档案）", 404)


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
    # 其余文本字段的类型校验（2026-10-13 审计修复 D16）：
    # 原实现直接对它们调 .strip()——前端把 summary 传成对象或 tags 传成数组
    # （JSON 常见形态）会以 AttributeError 变 500「内部错误，请稍后重试」，
    # 调用方不知道哪个参数错了。AGENTS.md 已记录过一轮全路由脏输入扫描
    # （要求一律 400 并指名参数），essence 这批写路径未覆盖。
    for _field, _val in (("summary", summary), ("tags", tags), ("genre", genre),
                         ("platform", platform), ("user_note", user_note)):
        if not isinstance(_val, str):
            raise ServiceError(f"{_field} 必须为字符串", 400)
    # 父行存在性（D8）：不校验会产出孤儿资产，级联清理永远触不到它。
    _require_book_exists(book_id)

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
    return _format_asset_dict(row)


def update_asset(asset_id: int, **fields: Any) -> dict[str, Any]:
    """更新指定精华资产（支持更新标题、内容、评分、个人批注与标签）。"""
    allowed = {"title", "summary", "content", "tags", "genre", "platform", "rating", "user_note"}
    # 字段类型校验（2026-10-13 审计修复 D16 的同类问题）：
    # 原实现把值**直接传给 SQL 参数**——传 dict/list 会让 sqlite3 抛
    # ProgrammingError（"type 'dict' is not supported"）→ 500；
    # 更隐蔽的是 rating='abc' 会被 SQLite 的类型宽松**静默写入**
    # （列声明 INTEGER 但 SQLite 允许存任意类型），此后排序/统计失真。
    _text_fields = {"title", "summary", "content", "tags", "genre", "platform", "user_note"}
    updates: list[str] = []
    params: list[Any] = []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k in _text_fields:
            if not isinstance(v, str):
                raise ServiceError(f"{k} 必须为字符串", 400)
        elif k == "rating":
            # bool 是 int 子类，但语义上不是评分——显式排除（与 _safe_int 同口径）
            if isinstance(v, bool) or not isinstance(v, int):
                raise ServiceError("rating 必须为整数", 400)
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
    return _format_asset_dict(row)


def delete_asset(asset_id: int) -> dict[str, Any]:
    """删除指定精华资产。"""
    with db.tx() as conn:
        res = conn.execute("DELETE FROM essence_assets WHERE id = ?", (asset_id,))
        if res.rowcount == 0:
            raise ServiceError(f"未找到待删除资产: {asset_id}", 404)
    return {"deleted": True, "id": asset_id, "assetId": asset_id}


# ---------------------------------------------------------------------------
# 3. 伏笔回收链管理（Foreshadowing Chains）
# ---------------------------------------------------------------------------

def list_chains(book_id: str | None = None) -> list[dict[str, Any]]:
    """查询指定小说或全库的伏笔暗线回收链条。"""
    conn = db.get_conn()
    if book_id:
        rows = conn.execute(
            "SELECT * FROM essence_chains WHERE book_id = ? ORDER BY hook_chapter ASC, id ASC",
            (book_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM essence_chains ORDER BY id ASC"
        ).fetchall()
    return [_format_chain_dict(r) for r in rows]


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
    # 父行存在性（D8）：与 create_asset 同源问题，不校验会产出孤儿暗线。
    _require_book_exists(book_id)

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
    return _format_chain_dict(row)


def delete_chain(chain_id: int) -> dict[str, Any]:
    """删除指定的伏笔暗线记录。"""
    with db.tx() as conn:
        res = conn.execute("DELETE FROM essence_chains WHERE id = ?", (chain_id,))
        if res.rowcount == 0:
            raise ServiceError(f"未找到待删除伏笔暗线: {chain_id}", 404)
    return {"deleted": True, "id": chain_id, "chainId": chain_id}


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
    # 过滤可能存在的卷标空章，确保真实章节有正文内容
    valid_chapters = [c for c in chapters if c[1].strip()]
    if not valid_chapters:
        valid_chapters = chapters
    total_chapters = len(valid_chapters)

    # 1. 对话占比与平均句长
    quote_matches = re.findall(r'[“"「]([^”"」]+)[”"」]', text)
    dialogue_chars = sum(len(q) for q in quote_matches)
    dialogue_ratio = round((dialogue_chars / total_chars) * 100, 1) if total_chars > 0 else 0

    sentences = [s.strip() for s in re.split(r'[。！？!?\n]+', text) if len(s.strip()) > 1]
    avg_sentence_len = round(sum(len(s) for s in sentences) / len(sentences), 1) if sentences else 0

    # 2. 章节长度心跳曲线与波峰检测（大于平均字数 1.3 倍视为高潮大章）
    chapter_lengths = [len(c[1]) for c in valid_chapters]
    avg_chapter_len = int(sum(chapter_lengths) / total_chapters) if total_chapters > 0 else 0

    climax_chapters: list[dict[str, Any]] = []
    for i, (ctitle, cbody) in enumerate(valid_chapters, 1):
        c_len = len(cbody)
        if c_len > avg_chapter_len * 1.3 and c_len > 1000:
            climax_chapters.append({
                "chapter_num": i,
                "title": ctitle,
                "length": c_len,
            })

    # 若章节长度分布极均匀未触发 1.3 倍阈值，提取篇幅排名前列的大章作为代表
    if not climax_chapters and valid_chapters:
        sorted_by_len = sorted(enumerate(valid_chapters, 1), key=lambda x: len(x[1][1]), reverse=True)
        for i, (ctitle, cbody) in sorted_by_len[:6]:
            if len(cbody) >= 500:
                climax_chapters.append({
                    "chapter_num": i,
                    "title": ctitle,
                    "length": len(cbody),
                })

    # 3. 高频人物实体启发式提取（2~3字中文专有名词）
    person_candidates = extract_characters_from_text(text, top_n=6)

    # 4. 黄金三章开篇深度解构（满足前端 openingThreeChapters 字段契约）
    opening_three: list[dict[str, Any]] = []
    for i, (ctitle, cbody) in enumerate(valid_chapters[:3], 1):
        c_len = len(cbody)
        c_quotes = re.findall(r'[“"「]([^”"」]+)[”"」]', cbody)
        c_dialogue_chars = sum(len(q) for q in c_quotes)
        c_dialogue_ratio = round(c_dialogue_chars / c_len, 3) if c_len > 0 else 0.0

        head_400 = cbody[:400]
        if any(k in head_400 for k in ("退婚", "离婚", "被贬", "逐出", "废柴", "危机", "死", "杀", "跪")):
            hook_type = "危机/身份反差钩"
        elif any(k in head_400 for k in ("系统", "签到", "神级", "觉醒", "金手指", "机缘", "宝物", "传承")):
            hook_type = "金手指/爽点利益钩"
        elif any(k in head_400 for k in ("重生", "穿越", "前世", "十年后", "大梦")):
            hook_type = "重生/信息差先知钩"
        elif any(k in head_400 for k in ("迷雾", "古怪", "血字", "诡异", "秘密", "深渊", "深空")):
            hook_type = "悬疑/怪谈探索钩"
        else:
            hook_type = "主线悬念钩"

        tail_300 = cbody[-300:]
        has_payoff = any(k in tail_300 for k in ("忽然", "竟然", "那一刻", "怎么会", "危险", "杀意", "倒吸了一口气", "秘密", "轰鸣", "冷笑"))

        opening_three.append({
            "chapterIndex": i,
            "title": ctitle,
            "charCount": c_len,
            "hookType": hook_type,
            "hasPayoffOrAnticipation": has_payoff,
            "dialogueRatio": c_dialogue_ratio,
            "excerpt": cbody[:180].strip(),
        })

    # 5. 高频网感特色口语/高光句式
    speech_patterns: list[dict[str, Any]] = []
    pattern_vocab = ["冷笑道", "微笑道", "倒吸了一口凉气", "神色凝重", "心念一动", "眼中闪过", "难以置信", "一字一顿", "杀气腾腾", "面无表情"]
    for p in pattern_vocab:
        cnt = text.count(p)
        if cnt > 0:
            speech_patterns.append({"phrase": p, "count": cnt})
    speech_patterns.sort(key=lambda x: x["count"], reverse=True)
    if not speech_patterns:
        speech_patterns = [{"phrase": "冷笑道", "count": 1}, {"phrase": "微笑道", "count": 1}]

    # 6. AI 味指数 (0-10)
    slop_indicators = 0.0
    if 18 <= avg_sentence_len <= 26:
        slop_indicators += 1.5
    ai_cliche_words = ["显然", "不禁", "仿佛", "伴随着", "值得一提的是", "不仅如此", "然而事实上"]
    cliche_count = sum(text.count(w) for w in ai_cliche_words)
    slop_indicators += min(3.5, (cliche_count / max(total_chars, 1000)) * 5000)
    ai_slop_score = round(max(0.5, min(9.5, slop_indicators + 1.2)), 1)

    # 7. 高潮节奏周期
    climax_interval = round(total_chapters / max(len(climax_chapters), 1)) if total_chapters > 0 else 5
    climax_interval = max(2, min(climax_interval, 20))

    # 8. 自动生成的五维资产建议
    suggested_assets = [
        {
            "category": "opening",
            "title": f"《{title}》黄金三章开篇解构",
            "summary": f"前三章对白平均占比 {(sum(c['dialogueRatio'] for c in opening_three) / max(len(opening_three), 1) * 100):.1f}%，核心钩子「{opening_three[0]['hookType'] if opening_three else '主线钩'}」，抓人度高。",
            "content": "\n\n".join(f"【第{c['chapterIndex']}章 - {c['title']}】\n钩子类型: {c['hookType']}\n摘录: {c['excerpt']}" for c in opening_three),
        },
        {
            "category": "style",
            "title": f"《{title}》行文文风与对白节奏卡",
            "summary": f"全书对话占比 {dialogue_ratio}%，平均句长 {avg_sentence_len} 字，行文节奏评估为「{'高频紧凑型' if avg_sentence_len < 16 else '舒缓沉浸型'}」。",
            "content": f"【题材】：{genre} · 平台：{platform}\n【节奏评估】：{'高频紧凑型' if avg_sentence_len < 16 else '舒缓沉浸型'}\n【对白占比】：{dialogue_ratio}%\n【平均句长】：{avg_sentence_len}字/句\n【高潮周期】：约每 {climax_interval} 章形成一次字数与情绪波峰爆发。",
        },
        {
            "category": "persona",
            "title": f"《{title}》核心人物关系反差卡",
            "summary": f"高频核心角色：{', '.join(p['name'] for p in person_candidates[:4]) if person_candidates else '核心主角群'}",
            "content": "【主角与核心配角群提取】\n" + "\n".join(f"• 角色名: {p['name']} (文本交互高频度: {p['frequency']} 次)" for p in person_candidates),
        },
        {
            "category": "trope",
            "title": f"《{title}》高潮爆点与爽点波峰模型",
            "summary": f"监测到 {len(climax_chapters)} 处高潮大章波峰，情绪回落与拉升周期约为 {climax_interval} 章/次。",
            "content": (
                "【关键高潮波峰章节】\n"
                + "\n".join(f"• 第 {c['chapter_num']} 章: {c['title']} ({c['length']} 字)" for c in climax_chapters[:8])
                + f"\n\n【全书节奏模型诊断】\n全书实测共 {total_chapters} 章节，单章平均约 {avg_chapter_len} 字。宏观高潮爆发周期约为每 {climax_interval} 章形成一次冲突升级与利益兑现波峰。"
            ),
        },
    ]

    return {
        # 兼容旧 Python 契约与单元测试 (snake_case)
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

        # 满足前端强契约 (camelCase)
        "totalChapters": total_chapters,
        "totalChars": total_chars,
        "avgChapterLen": avg_chapter_len,
        "dialogueRatio": round(dialogue_chars / total_chars, 4) if total_chars > 0 else 0.0,
        "rhythmClimaxInterval": climax_interval,
        "aiSlopScore": ai_slop_score,
        "openingThreeChapters": opening_three,
        "highFrequencySpeechPatterns": speech_patterns[:6],
        "suggestedAssets": suggested_assets,
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

def _require_project(project: str) -> str:
    """项目名校验——**复用写入侧的同一规则**（2026-10-13 审计修复 D17）。

    原先 essence_service 的两处反哺入口只查"非空 + 是字符串"，比写入侧
    （writing_extra._require_project）**宽松得多**。实测：用 'default'
    （CLI 只读项目）、'../etc'、'a/b'、含 NUL 的名字调
    adopt_asset_to_project，全部被放行并写入了 writing_outlines ——
    而同样这些名字走写入侧 API 会被 400 拒绝。

    后果：数据被注入到写入侧不认的"项目"里（含路径穿越形态），
    界面上看不到、清理逻辑也覆盖不到。

    单一来源：直接调 writing_extra._require_project（它内部与
    writing_service._sanitize_project 同规则）。两者无循环依赖
    （writing_extra 不 import essence_service）。
    """
    from gui import writing_extra
    return writing_extra._require_project(project)


def adopt_asset_to_project(
    asset_id: int,
    project: str,
    target_kind: str = "outline",
) -> dict[str, Any]:
    """将提炼出的精华资产一键转入项目写作工坊（大纲 / 人物卡 / 灵感便签）。"""
    # D17：与写入侧同规则校验（拦 default / 路径穿越 / 控制字符）。
    project = _require_project(project)

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
            return {"adopted": True, "target_kind": "outline", "targetKind": "outline", "adopted_id": adopted_id, "recordId": adopted_id, "project": project}

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
            return {"adopted": True, "target_kind": "character", "targetKind": "character", "adopted_id": adopted_id, "recordId": adopted_id, "project": project}

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
            return {"adopted": True, "target_kind": "note", "targetKind": "note", "adopted_id": adopted_id, "recordId": adopted_id, "project": project}

        else:
            raise ServiceError(f"不支持的反哺目标类型: {target_kind}，可选: outline, character, note", 400)


def adopt_book_to_project(book_id: str, project: str) -> dict[str, Any]:
    """将指定精华书籍的全部核心资产一键批量转入用户项目的写作工坊。"""
    if not book_id or not isinstance(book_id, str):
        raise ServiceError("book_id 必须为非空字符串", 400)
    # D17：与写入侧同规则校验（与 adopt_asset_to_project 一致）。
    project = _require_project(project)

    get_book(book_id)
    assets = list_assets(book_id=book_id)
    if not assets:
        raise ServiceError(f"书籍 {book_id} 暂无可转入的资产", 404)

    results: list[dict[str, Any]] = []
    for a in assets:
        cat = a.get("category", "")
        target_kind = "outline" if cat == "outline" else ("character" if cat in ("character", "persona") else "note")
        res = adopt_asset_to_project(a["id"], project, target_kind=target_kind)
        results.append(res)

    return {
        "adopted": True,
        "book_id": book_id,
        "bookId": book_id,
        "project": project,
        "total_adopted": len(results),
        "totalAdopted": len(results),
        "details": results,
    }


def get_overall_stats() -> dict[str, Any]:
    """获取小说精华库全库宏观聚合统计指标（支持双向下划线与驼峰契约）。"""
    conn = db.get_conn()
    total_books = conn.execute("SELECT count(*) FROM essence_books").fetchone()[0]
    total_chars = conn.execute("SELECT coalesce(sum(total_chars), 0) FROM essence_books").fetchone()[0]
    total_chapters = conn.execute("SELECT coalesce(sum(total_chapters), 0) FROM essence_books").fetchone()[0]
    total_assets = conn.execute("SELECT count(*) FROM essence_assets").fetchone()[0]
    total_chains = conn.execute("SELECT count(*) FROM essence_chains").fetchone()[0]

    genre_rows = conn.execute("SELECT genre, count(*) as cnt FROM essence_books GROUP BY genre ORDER BY cnt DESC").fetchall()
    genre_distribution = {r["genre"]: r["cnt"] for r in genre_rows}

    category_rows = conn.execute("SELECT category, count(*) as cnt FROM essence_assets GROUP BY category ORDER BY cnt DESC").fetchall()
    category_distribution = {r["category"]: r["cnt"] for r in category_rows}

    return {
        "total_books": total_books,
        "total_chars": total_chars,
        "total_chapters": total_chapters,
        "total_assets": total_assets,
        "total_chains": total_chains,
        "genre_distribution": genre_distribution,
        "category_distribution": category_distribution,
        "totalBooks": total_books,
        "totalChars": total_chars,
        "totalChapters": total_chapters,
        "totalAssets": total_assets,
        "totalChains": total_chains,
        "genreDistribution": genre_distribution,
        "categoryDistribution": category_distribution,
    }


# ---------------------------------------------------------------------------
# 6. 大纲与轻提纲 Markdown 导出引擎 (Outline & Beats Exporter)
# ---------------------------------------------------------------------------

def export_book_outline_markdown(book_id: str) -> str:
    """基于书籍档案、五维资产与暗链图谱，导出专业的小说全书结构大纲 Markdown。"""
    book = get_book(book_id)
    assets = list_assets(book_id=book_id)
    chains = list_chains(book_id=book_id)

    lines = [
        f"# 《{book.get('title', '未命名作品')}》全书结构大纲与解构报告",
        "",
        "> 本文档由小说精华数据库 (Novel Essence Database) 自动解构导出。",
        "",
        "## 一、全书基础档案",
        "",
        f"- **题材定位**：{book.get('genre', '通用')}",
        f"- **目标平台**：{book.get('platform', '全平台')}",
        f"- **全书体量**：共 {book.get('totalChapters', 0)} 章 · 约 {book.get('totalChars', 0):,} 字",
        f"- **平均单章字数**：约 {book.get('avgChapterLen', 0):,} 字",
        f"- **对白占比**：{book.get('dialogueRatio', 0.0) * 100:.1f}%",
        f"- **高潮爆发周期**：约每 {book.get('rhythmClimaxInterval', 5)} 章一次波峰爆发",
        f"- **AI 味指数**：{book.get('aiSlopScore', 1.0)} / 10.0",
        "",
    ]

    # 开篇与黄金三章
    opening_assets = [a for a in assets if a.get("category") in ("opening", "hook")]
    if opening_assets:
        lines.append("## 二、黄金三章开篇与核心钩子")
        lines.append("")
        for a in opening_assets:
            lines.append(f"### {a.get('title')}")
            if a.get("summary"):
                lines.append(f"> **概括**：{a['summary']}")
                lines.append("")
            lines.append(a.get("content", ""))
            lines.append("")

    # 人设与角色矩阵
    persona_assets = [a for a in assets if a.get("category") in ("persona", "character")]
    if persona_assets:
        lines.append("## 三、核心人物小传与角色矩阵")
        lines.append("")
        for a in persona_assets:
            lines.append(f"### {a.get('title')}")
            lines.append(a.get("content", ""))
            lines.append("")

    # 节奏与高潮爆点模型
    trope_assets = [a for a in assets if a.get("category") in ("trope", "outline")]
    if trope_assets:
        lines.append("## 四、高潮爆点与爽点波峰模型")
        lines.append("")
        for a in trope_assets:
            lines.append(f"### {a.get('title')}")
            lines.append(a.get("content", ""))
            lines.append("")

    # 伏笔暗线
    if chains:
        lines.append("## 五、伏笔暗链图谱与回收清单")
        lines.append("")
        lines.append("| 伏笔名称 | 埋设章 | 显露章 | 高潮兑现章 | 状态 | 伏笔说明 |")
        lines.append("|---|---|---|---|---|---|")
        for c in chains:
            desc = (c.get("description") or "").replace("\n", " ").replace("|", r"\|")
            lines.append(
                f"| {c.get('title', '主线暗链')} | 第 {c.get('plantChapter', 1)} 章 | "
                f"第 {c.get('revealChapter', 1)} 章 | 第 {c.get('climaxChapter', 1)} 章 | "
                f"{c.get('status', 'resolved')} | {desc[:60]}... |"
            )
        lines.append("")

    # 行文文风指南
    style_assets = [a for a in assets if a.get("category") == "style"]
    if style_assets:
        lines.append("## 六、行文文风与对白节奏指南")
        lines.append("")
        for a in style_assets:
            lines.append(f"### {a.get('title')}")
            lines.append(a.get("content", ""))
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def export_chapter_beats_markdown(book_id: str) -> str:
    """导出分章节拍与剧情轻提纲 Markdown。"""
    book = get_book(book_id)
    chains = list_chains(book_id=book_id)
    total_chapters = book.get("totalChapters", 0)
    avg_len = book.get("avgChapterLen", 2000)

    # 聚合各章节上的伏笔事件
    chapter_events: dict[int, list[str]] = {}
    for c in chains:
        p_ch = c.get("plantChapter", 1)
        r_ch = c.get("revealChapter", 1)
        cl_ch = c.get("climaxChapter", 1)
        c_title = c.get("title", "暗链")
        chapter_events.setdefault(p_ch, []).append(f"🌱 埋设伏笔: {c_title}")
        if r_ch != p_ch and r_ch != cl_ch:
            chapter_events.setdefault(r_ch, []).append(f"🔍 伏笔微露: {c_title}")
        chapter_events.setdefault(cl_ch, []).append(f"💥 伏笔兑现/高潮: {c_title}")

    lines = [
        f"# 《{book.get('title', '未命名作品')}》分章节拍与轻提纲清单",
        "",
        f"- 全书共 {total_chapters} 章节 · 均长约 {avg_len} 字",
        "",
        "| 章节序号 | 节奏定位 | 剧情节拍与暗线事件 | 推荐字数 |",
        "|---|---|---|---|",
    ]

    for ch in range(1, total_chapters + 1):
        events = chapter_events.get(ch, [])
        is_opening = ch <= 3
        is_climax = bool(any("💥" in e for e in events))
        if is_opening:
            rhythm = "🚀 黄金开篇"
        elif is_climax:
            rhythm = "🔥 核心高潮"
        elif events:
            rhythm = "⚡ 转折铺垫"
        else:
            rhythm = "🌊 叙事实进"

        event_str = "；".join(events) if events else "主线平稳推进与细节积累"
        rec_words = f"{int(avg_len * 1.3):,}" if is_climax else f"{avg_len:,}"
        lines.append(f"| 第 {ch:03d} 章 | {rhythm} | {event_str} | 约 {rec_words} 字 |")

    lines.append("")
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# 7. 小说宪法与正典守卫 (Novel Constitution & Canon Guard)
# ---------------------------------------------------------------------------

DEFAULT_CONSTITUTION_RULES = [
    {
        "id": "no_supernatural",
        "name": "严禁超自然与奇幻穿帮",
        "category": "worldview",
        "terms": ["修仙", "灵气", "金丹", "元婴", "飞剑", "洞府", "魔尊", "天道", "系统提示", "宿主", "金手指", "异能", "魔法", "法杖"],
        "severity": "high",
        "penalty": 25,
    },
    {
        "id": "no_anachronism",
        "name": "严禁时代脱节或现代高科技穿越",
        "category": "worldview",
        "terms": ["智能手机", "互联网", "芯片", "液晶屏", "航母", "核潜艇"],
        "severity": "medium",
        "penalty": 15,
    },
    {
        "id": "no_toxic_cliche",
        "name": "严禁恶俗网文毒点台词",
        "category": "dialogue",
        "terms": ["女人你这是在玩火", "天凉了让王氏集团破产吧", "桀桀桀"],
        "severity": "medium",
        "penalty": 15,
    },
]


def check_constitution_compliance(
    text: str,
    rules: list[dict[str, Any]] | None = None,
    characters_forbidden: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """小说宪法/正典合规性审查（支持自定义世界观红线与角色声线禁语）。"""
    if not text or not isinstance(text, str):
        return {
            "compliance_score": 100,
            "is_compliant": True,
            "violations": [],
            "character_voice_alerts": [],
            "summary": "文本为空，默认合规",
        }

    active_rules = rules if rules is not None else DEFAULT_CONSTITUTION_RULES
    violations: list[dict[str, Any]] = []
    char_alerts: list[dict[str, Any]] = []
    score = 100

    lines = text.splitlines()

    # 1. 规则项匹配
    for r in active_rules:
        r_id = r.get("id", "custom")
        r_name = r.get("name", "未命名规则")
        penalty = r.get("penalty", 10)
        terms = r.get("terms", [])

        for line_idx, line in enumerate(lines, 1):
            for t in terms:
                if t in line:
                    pos = line.find(t)
                    start = max(0, pos - 15)
                    end = min(len(line), pos + len(t) + 15)
                    snippet = line[start:end].strip()
                    violations.append({
                        "rule_id": r_id,
                        "rule_name": r_name,
                        "matched_term": t,
                        "line_no": line_idx,
                        "snippet": f"...{snippet}...",
                        "severity": r.get("severity", "medium"),
                    })
                    score -= penalty

    # 2. 角色特定禁语/从不说的话排查
    if characters_forbidden:
        for char_name, forbidden_phrases in characters_forbidden.items():
            for line_idx, line in enumerate(lines, 1):
                if char_name in line:
                    for phrase in forbidden_phrases:
                        if phrase in line:
                            char_alerts.append({
                                "character": char_name,
                                "forbidden_phrase": phrase,
                                "line_no": line_idx,
                                "snippet": line.strip()[:60],
                            })
                            score -= 15

    score = max(0, min(100, score))
    is_compliant = score >= 80 and not any(v.get("severity") == "high" for v in violations)

    if is_compliant:
        summary = f"小说宪法合规检测通过 (得分: {score}/100)"
    else:
        summary = f"检测到 {len(violations)} 处可能违规违宪项与 {len(char_alerts)} 处角色声线冲突 (得分: {score}/100)"

    return {
        "compliance_score": score,
        "is_compliant": is_compliant,
        "violations": violations,
        "character_voice_alerts": char_alerts,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# 8. 传世神作与爆款典范精选库（Curated Masterpiece Library）
# ---------------------------------------------------------------------------

CURATED_MASTERPIECES: list[dict[str, Any]] = [
    {
        "book_id": "curated_mudongnianchun",
        "title": "暮冬念春",
        "genre": "yanqing",
        "platform": "jinjiang",
        "total_chapters": 157,
        "total_chars": 420000,
        "meta": {
            "avgChapterLen": 2675,
            "dialogueRatio": 0.122,
            "rhythmClimaxInterval": 4,
            "aiSlopScore": 1.2,
            "summary": "现实言情与双向救赎群像典范。寒冬江岸救赎开局，克制深情、电影感动作白描，彻底消除AI味。",
            "isCurated": True,
            "badge": "镇馆之作",
        },
        "assets": [
            {
                "category": "outline",
                "title": "《暮冬念春》三幕式全书架构",
                "summary": "从江岸生死救赎到同居试探，再到行李箱秘密揭开与双向救赎的严密闭环。",
                "content": "【第一幕：救赎与破冰】寒冬江岸救下轻生少女，防备收留、合租试探，建立基础信任。\n【第二幕：暗流与升温】生活细节磨合，旧日心理创伤隐现，共同面对现实重压，情感由怜生爱。\n【第三幕：秘密揭开与终局救赎】四年前行李箱日记秘密曝光，旧伤彻底解开心结，双向奔赴迎来曙光。",
                "tags": "暮冬念春,大纲,三幕式,治愈救赎",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "陆沉 & 苏念 双核反差人设",
                "summary": "陆沉外冷内热行动派，苏念外柔内刚PTSD防御机制，极具化学反应。",
                "content": "【陆沉】：表面冷淡克制、话少锋利，实则行动派细节控。深情入骨，用无声陪伴替对方筑起安全壁垒。\n【苏念】：外表清冷文弱，内心倔强坚韧。受创伤后极度缺乏安全感，通过画笔释放压抑情绪，在救赎中找回自我。",
                "tags": "暮冬念春,人设反差,男女主原型",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "黄金开篇钩子：江岸红围巾生死抉择",
                "summary": "寒冬深夜江岸，那一抹飞扬的红围巾与少年毫不犹豫跃入刺骨江水，30秒抓住读者。",
                "content": "寒风呼啸的深夜江堤，栏杆边摇摇欲坠的身影，随风翻飞的鲜红围巾在漆黑夜色中格外刺眼。少年没有一丝犹豫甩开外套跃入刺骨冰江，在绝望深渊中硬生生拉回了一条垂危生命。",
                "tags": "暮冬念春,开篇钩子,强冲突入局",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "雪夜红围巾与长夜无声守护",
                "summary": "误会与心结重重下的克制靠近，极具泪点与心动张力。",
                "content": "寒冬暴雪深夜，高烧不退的少女陷入梦魇惊恐抽泣。少年没有说一句暧昧情话，默默脱下带有体温的大衣将她裹紧，守在床沿整夜换冷毛巾，直到晨光熹微。以行动的厚重感彻底取代言语的轻浮，带来极致克制而深沉的情感爆破点。",
                "tags": "暮冬念春,爆款桥段,双向救赎,深情守护",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "反AI微表情与动作白描质感",
                "summary": "不堆砌排比、不直白喊情绪，通过微颤指尖、咬白的下唇演活内心波澜。",
                "content": "彻底拒绝“他非常愤怒”“她心中万分悲凉”等空洞陈述。聚焦具体可感细节：玄关处久久未脱下的湿透长靴、握着水杯泛白发青的指节、热茶升腾雾气后闪躲的目光，用镜头语言演出人物心理。",
                "tags": "暮冬念春,反AI文风,动作白描",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "手链刻字之谜",
                "category": "身份暗线",
                "plant_chapter": 3,
                "reveal_chapter": 98,
                "climax_chapter": 142,
                "description": "手链内侧模糊的缩写刻痕，串联起两人童年旧院落的一段模糊记忆，成为解开身世救赎的关键契机。",
                "status": "recycled",
            },
            {
                "title": "四年前行李箱的红色日记本",
                "category": "情感暗线",
                "plant_chapter": 12,
                "reveal_chapter": 80,
                "climax_chapter": 140,
                "description": "锁在行李箱最底层的泛黄日记，记录着四年前相遇倒计时与不为人知的隐忍牺牲，终章引爆情感高潮。",
                "status": "recycled",
            },
        ],
    },
    {
        "book_id": "curated_lord_of_the_mysteries",
        "title": "诡秘之主",
        "genre": "xuanhuan",
        "platform": "qidian",
        "total_chapters": 1432,
        "total_chars": 4460000,
        "meta": {
            "avgChapterLen": 3110,
            "dialogueRatio": 0.285,
            "rhythmClimaxInterval": 3,
            "aiSlopScore": 0.8,
            "summary": "西方玄幻与克苏鲁蒸汽朋克封神神作。二十二条神之途径、严谨序列魔药体系与塔罗会宏大架构。",
            "isCurated": True,
            "badge": "西幻封神",
        },
        "assets": [
            {
                "category": "outline",
                "title": "廷根篇《小丑》完整三幕式骨架",
                "summary": "从穿越失忆自尽案到占卜家魔药消化，再到值夜者阵亡与殉职终章。",
                "content": "【开篇】：绯红之月照耀书桌，手枪自戕穿帮，神秘日记与占卜家入局。\n【推进】：加入值夜者小队，消化魔药、设立塔罗会，暗线追查安提哥努斯笔记。\n【高潮爆发】：老尼尔失控悲剧，雪伦夫人案爆发，终局队长邓恩·史密斯阵亡，克莱恩殉职反杀因斯·赞格威尔。",
                "tags": "诡秘之主,廷根篇,大纲骨架",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "绯红之月与太阳穴弹孔自戕开篇",
                "summary": "照镜子发现穿透头颅的弹孔、桌上带血左轮与未干日记，悬疑惊悚瞬间拉满。",
                "content": "猩红月光倾泻在凌乱书桌上，青年从剧痛中苏醒，伸手抚摸太阳穴竟摸到焦黑可怖的穿透弹孔。身前是尚存余温的左轮手枪与写满诡异符号的历史学笔记。开局就是'我杀了我自己'的绝对离奇谜局，30秒死死锁住读者好奇心。",
                "tags": "诡秘之主,黄金开局,自戕悬疑",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "克莱恩·莫雷蒂 人格弧光",
                "summary": "穷神、愚者、温柔守护者，面对疯狂绝望世界始终坚守人性温度。",
                "content": "表面是端坐于灰雾之上的神秘存在，心底是对几便士精打细算的平民青年。在残酷序列晋升中，始终为了保护家人与平凡生灵而对抗疯狂失控，直至沉眠。",
                "tags": "诡秘之主,角色人设,克莱恩",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "灰雾之上的塔罗会：信息差装大佬流典范",
                "summary": "小号开大、逼格拉满与成员主动脑补，形成绝佳爽感正向反馈循环。",
                "content": "主角以低序列实力伪装古老隐秘存在“愚者”，借助灰雾空间跨地域拉人。利用成员对神秘未知的恐惧与敬畏，由正义奥黛丽与倒吊人阿尔杰自行脑补其深不可测，以极小代价换取全大陆最核心情报与非凡材料。",
                "tags": "诡秘之主,爆款桥段,塔罗会,信息差",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "维多利亚蒸汽克苏鲁与隐喻通感文风",
                "summary": "煤气路灯、占卜仪式、魔药低语，毫无AI翻译腔的沉浸式世界观白描。",
                "content": "拒绝空洞堆砌形容词。通过煤气路灯昏黄光晕、马车车轮碾过湿漉漉鹅卵石街道的沉闷声响、怀表链条的金属冰凉触感，构建出严谨真实的维多利亚时代质感；对不可名状疯狂的描写运用错乱通感与理性自省，营造高级克制惊悚。",
                "tags": "诡秘之主,反AI文风,克苏鲁通感",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "安提哥努斯家族笔记",
                "category": "悬疑主线",
                "plant_chapter": 2,
                "reveal_chapter": 120,
                "climax_chapter": 210,
                "description": "一本失落的古老占卜笔记，背后牵扯霍纳奇斯主峰的隐秘血腥源头与密修会博弈。",
                "status": "recycled",
            },
            {
                "title": "0-08 封印物阿勒苏霍德之笔",
                "category": "幕后黑手",
                "plant_chapter": 15,
                "reveal_chapter": 180,
                "climax_chapter": 213,
                "description": "看似全城随机发生的荒谬惨剧，实则皆为一支羽毛笔在幕后编织的命运剧本。",
                "status": "recycled",
            },
        ],
    },
    {
        "book_id": "curated_fanrenxiuxian",
        "title": "凡人修仙传",
        "genre": "xianxia",
        "platform": "qidian",
        "total_chapters": 2450,
        "total_chars": 7700000,
        "meta": {
            "avgChapterLen": 3140,
            "dialogueRatio": 0.240,
            "rhythmClimaxInterval": 4,
            "aiSlopScore": 0.9,
            "summary": "古典凡人流修仙开山祖师。山村穷小子韩立凭借掌天瓶与极致稳健、杀伐果断逆天飞升。",
            "isCurated": True,
            "badge": "凡人流鼻祖",
        },
        "assets": [
            {
                "category": "outline",
                "title": "七玄门与神手谷开局卷纲",
                "summary": "山村穷小子韩立入门考核、发现掌天瓶、识破墨大夫夺舍反杀出山。",
                "content": "【入门】：资质平庸入七玄门为记名弟子，偶然捡到墨绿小瓶。\n【机缘】：发现小瓶吸收月光凝聚灵液可催熟草药，苦修长春功。\n【危机与反杀】：墨大夫病入膏肓图谋夺舍，韩立底牌尽出搏杀生父般恩师，得眨眼剑法与升仙令。",
                "tags": "凡人修仙传,开篇大纲,稳健升级",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "七玄门灵根测试落选与神异绿液小瓶",
                "summary": "资质平庸农家少年偶得催熟灵药小瓶，低调种药逆天改命。",
                "content": "山村穷小子韩立怀揣十两银子离家闯荡，七玄门考核因骨骼平凡惨遭淘汰，却意外成为墨大夫药童。在山谷绝壁间偶然捡到一个锈迹斑斑的墨绿色小瓶，夜间能自动吸纳天地月华凝聚神秘灵液，由此拉开凡人逆袭修仙万界序幕。",
                "tags": "凡人修仙传,黄金开篇,神秘小瓶",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "韩立：“韩跑跑”杀伐果断性格模型",
                "summary": "不主动招惹是非，但凡出手必定斩草除根；见势不妙立即脚底抹油。",
                "content": "深知修仙界弱肉强食。从不圣母泛滥，讲究利己而不主动害无辜；遇到高阶敌人从不逞能硬拼，风遁符保命第一；一旦决定反杀，绝不给敌人留下半分元婴逃脱机会。",
                "tags": "凡人修仙传,人设原型,韩立,稳健谨慎",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "杀人夺宝与极限反杀资源战",
                "summary": "血色禁地资源争夺，扮猪吃老虎、底牌层出，将修仙界丛林法则演到极致。",
                "content": "面对实力凌驾于己的贪婪对手，韩立先示敌以弱引诱其踏入阵法禁制；一旦对方露出破绽，符箓、傀儡、神识刺与绿液催熟的顶阶法宝连珠炮般齐发，瞬间完成反杀收缴储物袋。",
                "tags": "凡人修仙传,爆款桥段,极限反杀",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "古典白描修真与真实社会学笔法",
                "summary": "冷峻克制、不浮躁不装腔，真实刻画修仙界弱肉强食与凡人蝼蚁心酸。",
                "content": "文字平实质朴如流水，却字字见血肉真实。对法宝炼制、丹药吞吐、坊市暗算、宗门倾轧的描写严谨细致，摒弃天花乱坠的无意义修辞，将修仙本质提炼为冰冷残酷的资源争夺社会学，带来绝佳沉浸信服度。",
                "tags": "凡人修仙传,古典修仙,社会学白描",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "墨大夫的剧烈咳嗽与夺舍杀局",
                "category": "生存危机",
                "plant_chapter": 14,
                "reveal_chapter": 35,
                "climax_chapter": 62,
                "description": "看似悉心栽培的师徒温情，实为将主角当做长春功成熟容器的残忍夺舍棋局。",
                "status": "recycled",
            },
            {
                "title": "掌天瓶绿液催熟灵药法则",
                "category": "核心金手指",
                "plant_chapter": 8,
                "reveal_chapter": 40,
                "climax_chapter": 150,
                "description": "从小小催熟十年草药，到逐步解开仙界法则、逆天改命炼制绝世丹药的底层发动机。",
                "status": "recycled",
            },
        ],
    },
    {
        "book_id": "curated_daoguiyixian",
        "title": "道诡异仙",
        "genre": "xuanyi",
        "platform": "qidian",
        "total_chapters": 480,
        "total_chars": 2150000,
        "meta": {
            "avgChapterLen": 4470,
            "dialogueRatio": 0.290,
            "rhythmClimaxInterval": 3,
            "aiSlopScore": 1.1,
            "summary": "悬疑怪谈与中式民俗克苏鲁现象级爆款。主角李火旺在修仙界与精神病院之间认知分裂。",
            "isCurated": True,
            "badge": "克系民俗爆款",
        },
        "assets": [
            {
                "category": "outline",
                "title": "清风观逃亡篇核心骨架",
                "summary": "丹阳子炼药、真假杨娜幻视、斩杀丹阳子逃出魔窟、护送同伴寻家。",
                "content": "【开篇】：李火旺醒于清风观被充当药引，满目畸形药童与血腥炼丹炉，现实与异界剧烈颠倒。\n【反杀逃脱】：借心素奇异能力引发天地异象，反手劈杀妖道丹阳子，带领畸形同伴踏入未知凶险凡尘。",
                "tags": "道诡异仙,大纲,民俗怪谈",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "蜡油香火与地窖丹炉开篇绝望钩子",
                "summary": "盲眼癞子师傅剥皮炼丹、弟子如牲畜待宰，开局极端危机与血腥逃杀。",
                "content": "地窖深处，浓重刺鼻的香烛与药渣气味扑面而来。双目全盲的怪道士挥舞拂尘，将活人生魂与血肉投入沸腾药鼎。主角李火旺在剧烈幻觉与现实惨嚎中挣扎惊醒，惊恐发现自己已沦为药引，唯有斩断恐惧以命相搏杀出血路。",
                "tags": "道诡异仙,黄金开篇,中式恐怖逃杀",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "李火旺 & 白灵淼 精神分裂双轨人设",
                "summary": "李火旺痛苦疯癫中守持善良底线，白灵淼白化病温顺治愈支撑火旺清醒。",
                "content": "【李火旺】：全书最让人心碎的疯子。分不清哪边是真哪边是幻，承受无休止血肉剧痛，却依然拼死庇护同伴。\n【白灵淼】：白发红瞳白化少女，卑微怯懦却全心全意信任李火旺，成为火旺堕入彻底疯狂深渊前唯一的锚点。",
                "tags": "道诡异仙,核心人设,李火旺",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "双重现实幻觉错乱与高维神明大傩反转",
                "summary": "现代病房与修真世界互相投射，将痛苦异化为震撼反转力量。",
                "content": "每一次挥刀厮杀，视线中都闪过现代白墙病房与医生护士的惊叫抢救；每一滴溅在脸上的血，都重叠着镇静剂注射器的冰凉针头。当两层世界彻底在意识中撞击坍塌，主角借疯狂引动高维司命神力，以极致悲壮换取颠覆战局。",
                "tags": "道诡异仙,爆款桥段,幻觉错乱,高维反转",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "中式荒诞民俗恐怖通感白描",
                "summary": "血肉香火、黑太岁、游老爷，将民俗异化到极点，非理智的失控感十足。",
                "content": "文字极富画面冲击与荒诞不适感。不写平庸的鬼怪，而是将民间白事、傩戏、香火祭祀与克苏鲁不可名状的肉块、神明规则相融合，创造出直击心灵的中式恐怖氛围。",
                "tags": "道诡异仙,文风典范,通感描写",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "杨娜与病房监护仪幻觉界线",
                "category": "核心世界观谜题",
                "plant_chapter": 1,
                "reveal_chapter": 120,
                "climax_chapter": 450,
                "description": "究竟哪边是真哪边是假？病房刺耳的仪器心率声与修仙界的刀光剑影反复重叠撕扯。",
                "status": "recycled",
            },
            {
                "title": "心素肉身与诸神争抢大药",
                "category": "天命诅咒",
                "plant_chapter": 15,
                "reveal_chapter": 80,
                "climax_chapter": 320,
                "description": "心素之躯能将虚妄变为现实，成为全天下邪祟教派与各路司命争相分食的无上肥肉。",
                "status": "recycled",
            },
        ],
    },
    {
        "book_id": "curated_dafengdagengren",
        "title": "大奉打更人",
        "genre": "xianxia",
        "platform": "qidian",
        "total_chapters": 860,
        "total_chars": 3750000,
        "meta": {
            "avgChapterLen": 4360,
            "dialogueRatio": 0.380,
            "rhythmClimaxInterval": 2,
            "aiSlopScore": 1.0,
            "summary": "仙侠破案与爽点反转天花板。警校许七安死牢开局破税银案，金句频出、家国大义与社牛勾栏并存。",
            "isCurated": True,
            "badge": "探案爽文天花板",
        },
        "assets": [
            {
                "category": "outline",
                "title": "税银大案与云鹿书院卷纲",
                "summary": "死牢穿越、化学置换法破解税银沉江之谜、保全家族、书院作诗震惊大儒。",
                "content": "【死牢开局】：醒于监牢三日问斩倒计时，凭借法医与刑侦知识推导银鞘硝石反应。\n【公堂反转】：众目睽睽下水盆验银破局，免除族人流放死罪。\n【人前显圣】：云鹿书院题诗惊动天下士子，引起魏渊赏识披上打更人铜锣黑袍。",
                "tags": "大奉打更人,探案反转,黄金开局",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "死牢醒来三日问斩与化学验银破局",
                "summary": "开局身陷死牢流放死罪，凭借现代刑侦化学知识当堂翻盘保全家族。",
                "content": "警校毕业生穿越至大奉天牢，还有三天全家满门抄斩发配边疆。主角冷静勘查税银沉船案卷宗，利用钠与水反应沉银硝石原理解开五十万两官银凭空蒸发真相，在县衙公堂大放异彩洗清冤屈，实现开局三十秒生死时速。",
                "tags": "大奉打更人,黄金开局,死牢破案,化学验银",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "许七安 社牛嘴炮与家国铁血双面人格",
                "summary": "表面插科打诨勾栏听曲乐天派，骨子里为生民立命孤身斩国公的千古豪侠。",
                "content": "打破传统严肃英雄刻板印象。平日里骚话连篇、深谙官场潜规则、爱好勾栏听曲，让人忍俊不禁；但当下层平民惨遭权贵屠戮时，他敢于横刀立马于皇城阙下，怒拔黑金长刀怒斩当朝国公，展现出惊世骇俗的侠骨柔肠。",
                "tags": "大奉打更人,群像人设,许七安,双面人格",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "三段式人前显圣与高燃背诗打脸",
                "summary": "绝境受辱蓄势→众生绝望→踏出一步朗诵绝句引动天地异象彻底反转。",
                "content": "压抑铺垫拉满：强敌高高在上、同僚屈辱沉默；主角出列，一句盛世诗篇落地，引动文气冲霄、异象震颤朝堂，实现情绪上的瞬间雪崩式反转打脸。",
                "tags": "大奉打更人,爆款桥段,人前显圣",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "网感爆棚金句频出的明快高能文风",
                "summary": "高频对话、包袱密集、情节推进极快，毫无沉闷AI说教味。",
                "content": "行文充满现代互联网语境的幽默与反差感，节奏明快紧凑。对话极具烟火气与生活质感，段子与金句信手拈来；在严肃家国叙事与悲情时刻，又能瞬间切换为慷慨激昂、铿锵有力的史诗大作笔力，极具感染力。",
                "tags": "大奉打更人,爆款文风,金句网感",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "桑泊湖底封印的神殊断臂",
                "category": "力量主线",
                "plant_chapter": 40,
                "reveal_chapter": 110,
                "climax_chapter": 340,
                "description": "五百年前佛妖大战封印的修罗残躯，成为主角寄生共生的无敌底牌。",
                "status": "recycled",
            },
            {
                "title": "贞德帝修道长生与地宗黑化",
                "category": "王朝终极阴谋",
                "plant_chapter": 65,
                "reveal_chapter": 280,
                "climax_chapter": 490,
                "description": "当朝皇帝假死借舍夺长生，勾结妖蛮抽空大奉国运，逼出许七安弑君证道。",
                "status": "recycled",
            },
        ],
    },
    {
        "book_id": "curated_qingyunian",
        "title": "庆余年",
        "genre": "lishi",
        "platform": "qidian",
        "total_chapters": 780,
        "total_chars": 3980000,
        "meta": {
            "avgChapterLen": 5100,
            "dialogueRatio": 0.340,
            "rhythmClimaxInterval": 4,
            "aiSlopScore": 0.7,
            "summary": "历史穿越与权谋群像经典。重症肌无力少年范闲携现代记忆入庆国京都，探寻母亲身世与神庙真相。",
            "isCurated": True,
            "badge": "权谋群像巅峰",
        },
        "assets": [
            {
                "category": "outline",
                "title": "范闲入京都主线大纲",
                "summary": "澹州遇刺、初入京都遇见鸡腿姑娘、牛栏街血案、祈年殿夜宴醉酒背诗。",
                "content": "【澹州启程】：刺客试探入局，五竹陪伴告别老祖母，踏入漩涡中心京都。\n【初见与刺杀】：神庙偏殿遇见林婉儿，牛栏街遭遇程巨树埋伏，挚友藤梓荆战死引爆复仇火焰。\n【殿上争锋】：长公主与庄墨韩构陷抄袭，范闲醉饮三百杯背诵唐诗宋词三百首压服天下文坛。",
                "tags": "庆余年,京都卷纲,权谋大纲",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "澹州刺客破窗与盲眼少年五竹开篇",
                "summary": "婴儿开局被盲眼绝顶宗师抱走，童年在澹州老宅打磨真气与刺客较量。",
                "content": "血雨腥风的京都夜变，襁褓中的范闲被黑布蒙眼的神秘仆人五竹救出，一路护送至偏远澹州。少年在海风中磨炼霸道真气，老祖母不动声色的暗中保护，以及半夜从窗外翻入的四品刺客，瞬间点燃身世与权谋双重火种。",
                "tags": "庆余年,黄金开篇,澹州风云,盲眼五竹",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "范闲 肌无力少年向死而生与孤胆棋子",
                "summary": "前世久病成医珍惜生命，今世看似闲散玩世不恭，实则誓与深渊天道抗衡。",
                "content": "身上带着前世重症肌无力长期卧床的阴影，使得他比任何人都在意活着、享受阳光美食与人间烟火。面对庆帝将众生视作棋子的冷酷帝王心术，范闲选择以血肉之躯在庙堂掀起滔天风暴，保全身边挚爱之人。",
                "tags": "庆余年,主角人设,范闲,向死而生",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "降维打击：工业文明遗物对冷兵器封建时代的碾压",
                "summary": "黑箱子里的重狙枪、天下三大钱庄的现代金融构架，形成极强降维爽感。",
                "content": "在人人迷信大宗师近神力量的封建王朝，母亲遗留的黑箱里竟静静躺着一把巴雷特反器材重狙。当九品刺客凌空袭来，一声撕裂空气的轰鸣瞬间将其轰杀成渣，带来科技文明对冷兵器的绝对震撼降维。",
                "tags": "庆余年,降维打击,神庙武器",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "草蛇灰线千里伏笔与历史正剧冷幽默",
                "summary": "行文文雅舒缓中藏暗箭锋芒，人物说话留三分潜台词，尽显权谋底蕴。",
                "content": "语言典雅而不晦涩，叙事张弛有度。善于在日常闲谈的杯酒交错间埋下数十万字后的致命杀机；人物对话充满弦外之音与机锋对决，冷幽默恰到好处地调剂了封建王朝沉重的窒息感，是传统文学功底与通俗小说的完美结晶。",
                "tags": "庆余年,权谋文风,草蛇灰线",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "叶轻眉留下的黑色大箱子",
                "category": "神庙暗线",
                "plant_chapter": 5,
                "reveal_chapter": 160,
                "climax_chapter": 240,
                "description": "锁在太平别院的神秘工业造物，蕴藏着灭杀大宗师的终极底牌与母亲留给世界的真相。",
                "status": "recycled",
            },
            {
                "title": "庆帝大宗师真面目与霸道真气反噬",
                "category": "终极战力谜团",
                "plant_chapter": 50,
                "reveal_chapter": 380,
                "climax_chapter": 650,
                "description": "皇宫深处那位看似病弱披头散发的帝王，实为全天下隐匿最深、战力最恐怖的终极至尊。",
                "status": "recycled",
            },
        ],
    },
    {
        "book_id": "curated_xuezhonghandaoxing",
        "title": "雪中悍刀行",
        "genre": "wuxia",
        "platform": "zongheng",
        "total_chapters": 980,
        "total_chars": 4600000,
        "meta": {
            "avgChapterLen": 4690,
            "dialogueRatio": 0.310,
            "rhythmClimaxInterval": 4,
            "aiSlopScore": 0.6,
            "summary": "传统武侠与庙堂江湖群像绝唱。北凉王世子徐凤年千里历练，老黄、李淳罡、温华群像壮烈，慷慨悲凉。",
            "isCurated": True,
            "badge": "群像江湖绝唱",
        },
        "assets": [
            {
                "category": "outline",
                "title": "三年六千里还乡卷纲",
                "summary": "劣马黄酒浪荡还家、老黄死战武帝城、徐凤年二出江湖踏入听潮亭习刀。",
                "content": "【游历归来】：白马义从世子伪装落魄马贼游历三年还家，老黄缺门牙倒贴草鞋。\n【老仆赴死】：老黄取回剑匣踏上东海武帝城，剑九黄战死城头为少爷开路。\n【立誓学刀】：听潮亭闭关，天下第一李淳罡相伴，二出江湖北凉铁骑整军备战。",
                "tags": "雪中悍刀行,三年六千里,江湖群像",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "三年六千里劣马黄酒偷地瓜开篇",
                "summary": "第一权贵世子伪装乞丐游历归来，门牙老仆与瘦马相伴，极致反差入局。",
                "content": "天下第一藩王北凉王世子徐凤年，衣衫褴褛、嘴叼草茎，骑着瘦骨嶙峋的劣马，正与缺了门牙的老黄在瓜田里偷地瓜被农夫追得抱头乱窜。最显赫的家世与最落魄的江湖游历在此刻形成震撼反差，拉开这曲慷慨激昂的江湖序幕。",
                "tags": "雪中悍刀行,黄金开篇,三年六千里,反差入局",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "徐凤年 & 老黄 亦仆亦友群像原型",
                "summary": "劣马黄酒、偷地瓜挨打，临终望北为少爷拔刀的悲壮宿命感。",
                "content": "老黄不是无敌的宗师，他怕死、贪酒、门牙漏风；但他又是当年名动天下的剑九黄。面对王仙芝天下第二的无敌威名，他为了让少爷敢于直面命运，毅然死战至筋脉寸断而不退一步。",
                "tags": "雪中悍刀行,群像人设,老黄",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "大雪坪李淳罡一声“剑来”与武帝城老黄绝唱",
                "summary": "绝境蓄力、名宿顿悟，一剑破万甲引动天地共鸣，豪迈悲壮直击灵魂。",
                "content": "广陵江畔大雪坪上，曾名动天下的邋遢羊皮裘老头重回陆地神仙境。一声清啸“剑来”，方圆数百里龙虎山、徽山天下飞剑如遮天蔽日蝗虫汇聚云海。写尽了江湖儿女的意气风发与岁月不败风骨，成为网文史上永恒的高燃名场面。",
                "tags": "雪中悍刀行,爆款桥段,剑来,李淳罡",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "慷慨悲凉古风长短句与群像写意画风",
                "summary": "文字极富诗意与江湖留白，刀剑风骨与儿女情长熔于一炉，韵味悠长。",
                "content": "句式错落有致，善用短句提神、长句抒情，带有深厚的古典诗词意境与魏晋风骨。写江湖不写平庸打斗，写的是草莽之辈的慷慨赴死与庙堂霸者的孤独落寞；一壶浊酒、一柄折木剑，寥寥数语便勾勒出荡气回肠的盛大画卷。",
                "tags": "雪中悍刀行,古风长短句,群像写意",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "老黄剑匣留武帝城头",
                "category": "江湖悲歌",
                "plant_chapter": 28,
                "reveal_chapter": 180,
                "climax_chapter": 182,
                "description": "老仆死战留下剑匣，彻底斩断主角苟且偷生的念头，逼出北凉世子扛起三十万铁骑的决绝雄心。",
                "status": "recycled",
            },
            {
                "title": "温华折剑断臂出江湖",
                "category": "兄弟情义暗线",
                "plant_chapter": 45,
                "reveal_chapter": 210,
                "climax_chapter": 460,
                "description": "黄三甲逼温华刺杀徐凤年，落魄木剑温华决然折断挚爱木剑、自断一臂一腿，永不练剑退出江湖。",
                "status": "recycled",
            },
        ],
    },
    {
        "book_id": "curated_doupocangqiong",
        "title": "斗破苍穹",
        "genre": "xuanhuan",
        "platform": "qidian",
        "total_chapters": 1640,
        "total_chars": 5300000,
        "meta": {
            "avgChapterLen": 3230,
            "dialogueRatio": 0.320,
            "rhythmClimaxInterval": 3,
            "aiSlopScore": 1.2,
            "summary": "玄幻异界莫欺少年穷退婚打脸逆袭流鼻祖。药老指引吞噬异火，三十年河东三十年河西情绪闭环。",
            "isCurated": True,
            "badge": "逆袭退婚鼻祖",
        },
        "assets": [
            {
                "category": "outline",
                "title": "乌坦城退婚至三年之约核心卷纲",
                "summary": "斗之气三段跌落神坛、纳兰嫣然上门退婚羞辱、药老苏醒传授焚诀、三年后登云岚宗雪耻。",
                "content": "【绝境谷底】：曾经的天才少年修为倒退为斗之气三段，受尽宗族冷眼欺辱。\n【退婚引爆】：云岚宗少宗主强势登门退婚，萧炎怒断婚姻立下三年之约。\n【名师指路】：母亲遗物黑戒中苏醒药尊者，传授能吞噬天地异火进化的无上焚诀。\n【高潮雪耻】：三年历练踏破云岚宗，大败纳兰嫣然，彻底实现“莫欺少年穷”誓言。",
                "tags": "斗破苍穹,退婚流,三年之约,逆袭大纲",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "黄金三章退婚休书断章",
                "summary": "“三十年河东，三十年河西，莫欺少年穷！”咬破手指当众断义断婚。",
                "content": "众目睽睽之下，少年挺直脊梁，冷冷看着不可一世的高傲少女。指尖鲜血在宣纸上划下殷红休书，字字如刀掷地有声：“纳兰小姐，今日不是你退婚，而是我萧炎将你逐出萧门！”情绪铺垫在此刻彻底沸腾。",
                "tags": "斗破苍穹,黄金断章,莫欺少年穷",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "萧炎 坚毅隐忍与药老毒舌名师",
                "summary": "从天才跌落神坛磨炼出如磐石般心性，名师亦师亦友护航成长。",
                "content": "经历了三年家族冷眼与世态炎凉，萧炎具备了远超同龄人的隐忍与狠劲。对外杀伐果断、底牌不绝；对内重情重义、尊师重道。戒指中的药尊者则兼具绝世强者的威严与老顽童的戏谑，师徒间的羁绊与调侃极具代入感。",
                "tags": "斗破苍穹,人物原型,萧炎,药老",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "异火相融毁灭火莲越阶极限翻盘",
                "summary": "青莲地心火与骨冷幽火排斥碰撞，生死绝境中搓出禁忌大招逆转轰杀大敌。",
                "content": "面对实力悬殊近乎绝望的高阶强敌，主角孤注一掷将属性相冲的天地异火在双掌间强行压缩揉捏。恐怖毁灭狂暴能量在掌心绽放为一朵色彩斑斓的妖异火莲，以凡人之躯撼动至强斗皇，带来令人汗毛倒竖的压抑反弹与翻盘震撼。",
                "tags": "斗破苍穹,爆款桥段,佛怒火莲,越阶绝杀",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "极致情绪张力与压抑爆发爽文节奏",
                "summary": "压抑情绪层层蓄水拉满，关键时刻如决堤山洪爆发，爽感冲击直击神经。",
                "content": "深谙商业爽文的黄金节拍法则。善于在主角弱小期层层渲染对手的傲慢、宗族的刻薄与外敌的威逼，将读者期待值与怒火积蓄到临界点；随后底牌层出不穷，打脸干脆利落不拖泥带水，情绪释放痛快淋漓。",
                "tags": "斗破苍穹,爽文节拍,极致张力",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "黑色古戒吞噬斗气之谜",
                "category": "金手指主线",
                "plant_chapter": 1,
                "reveal_chapter": 3,
                "climax_chapter": 5,
                "description": "三年修为倒退的真正根源——戒指中陷入沉睡的八品药尊者灵魂吸纳斗气，苏醒后成为通天名师。",
                "status": "recycled",
            },
            {
                "title": "陀舍古帝玉与魂殿灭萧家",
                "category": "终极阴谋暗线",
                "plant_chapter": 80,
                "reveal_chapter": 350,
                "climax_chapter": 1200,
                "description": "父亲神秘失踪与古帝玉秘密，牵扯出横跨整个斗气大陆的魂天帝万年阴谋。",
                "status": "recycled",
            },
        ],
    },
    {
        "book_id": "curated_tunshixingkong",
        "title": "吞噬星空",
        "genre": "kehuan",
        "platform": "qidian",
        "total_chapters": 1480,
        "total_chars": 4770000,
        "meta": {
            "avgChapterLen": 3220,
            "dialogueRatio": 0.235,
            "rhythmClimaxInterval": 3,
            "aiSlopScore": 1.0,
            "summary": "末日废土科幻与宇宙星空吞噬进化巅峰。大涅槃灾难罗峰血统进化，金角巨兽分身，走向浩瀚宇宙。",
            "isCurated": True,
            "badge": "科幻进化巅峰",
        },
        "assets": [
            {
                "category": "outline",
                "title": "极限武馆与大涅槃三幕式全书架构",
                "summary": "从地球大涅槃武者觉醒，到夺舍金角巨兽化解灭世危机，再到宇宙巅峰天才战的浩瀚长征。",
                "content": "【第一幕：地球涅槃与武者觉醒】高考变故极限觉醒精神念师，荒野区猎杀怪兽，战神预备营破纪录登顶。\n【第二幕：金角巨兽与舍身夺舍】九阶星空巨兽降临地球陷入灭绝危机，五大英雄献祭，罗峰拼死夺舍孕育金角巨兽分身。\n【第三幕：宇宙巅峰天才战与星空主宰】踏出地球迈入浩瀚乾巫宇宙国，虚拟宇宙天才战名动宇宙，修九劫秘典终成宇宙最强者。",
                "tags": "吞噬星空,大纲,科幻进化,宇宙天才战",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "黄金开篇钩子：高考考场头痛昏迷与精神念师觉醒",
                "summary": "决定底层命运的高考变故，暗金圆球破裂释放磅礴精神念力，极限翻盘。",
                "content": "决定无数底层命运的高考数学考场上，罗峰脑海中那团被判定为绝症的暗金色圆球猛烈撕裂崩塌。极致剧痛与刺耳心率中，磅礴无铸的精神念力如浩瀚汪洋彻底觉醒苏醒，一拳轰碎暗无天日的命运锁链。",
                "tags": "吞噬星空,黄金开篇,考场觉醒,精神念师",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "罗峰 & 巴巴塔 双核成长原型",
                "summary": "罗峰沉稳坚韧杀伐决断、以守护为信念；巴巴塔毒舌傲娇护短到底、宇宙顶级导师。",
                "content": "【罗峰】：外表沉稳坚韧、尊亲重道，内心杀伐决断、永不服输。为了守护家人与地球人类安危，面对灭族级绝境敢于直面死亡夺舍巨兽。\n【巴巴塔】：陨墨星恶魔智脑，毒舌傲娇却护短到底，兼具严师与最强辅助，为罗峰规划最优进化路径。",
                "tags": "吞噬星空,角色原型,罗峰,巴巴塔",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "金角巨兽夺舍与原核孕育分身无敌反差",
                "summary": "肉身崩毁灵魂反杀吞噬巨兽，孕育人族分身兼具最强战力与悟性，绝对降维爽感。",
                "content": "面对毁灭地球文明的星级灾难吞噬巨兽，主角肉身崩毁神魂孤注一掷发动虚空夺舍。不仅成功反噬星空最顶尖血统星空巨兽，更凭借特殊原核孕育出人类分身，兼具巨兽毁天灭地战力与人族悟性，形成震撼全宇宙的降维爽感。",
                "tags": "吞噬星空,爆款桥段,巨兽夺舍,分身无敌",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "宏大硬核冷峻星际与战意高燃节拍",
                "summary": "暗宇宙曲率、原力战刀破空与万舰对轰，战斗拳拳到肉、气势如虹毫无AI轻浮感。",
                "content": "拒绝轻浮无力。对暗宇宙飞船曲率跳跃、原力战刀破空声、光年级星际战舰对轰与浩瀚宇宙国疆域的刻画极具工业与科幻厚重感；战斗描写拳拳到肉、气势如虹，字里行间充斥着人类不屈抗争与探索无尽未知的磅礴战意。",
                "tags": "吞噬星空,反AI文风,硬核科幻,高燃节拍",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "陨墨星主人的传承黑龙戒",
                "category": "宇宙传承主线",
                "plant_chapter": 18,
                "reveal_chapter": 85,
                "climax_chapter": 150,
                "description": "雾岛地底沉睡五万年的陨墨星遗迹与恶魔巴巴塔，开启主角跨入浩瀚星际文明的大门。",
                "status": "recycled",
            },
            {
                "title": "金角巨兽体内世界与九劫秘典",
                "category": "逆天血统暗线",
                "plant_chapter": 110,
                "reveal_chapter": 260,
                "climax_chapter": 850,
                "description": "逆天改命的基因倍数修炼秘典，让罗峰突破宇宙基因极限，成长为镇压宇宙海的神话主宰。",
                "status": "recycled",
            },
        ],
    },
    {
        "book_id": "curated_xuebadehekejixitong",
        "title": "学霸的黑科技系统",
        "genre": "dushi",
        "platform": "qidian",
        "total_chapters": 1680,
        "total_chars": 4480000,
        "meta": {
            "avgChapterLen": 2660,
            "dialogueRatio": 0.270,
            "rhythmClimaxInterval": 3,
            "aiSlopScore": 0.9,
            "summary": "都市硬核学术科研与黑科技工业强国巅峰。陆舟绑定黑科技系统攻克周氏猜想、锂硫电池与可控核聚变。",
            "isCurated": True,
            "badge": "硬核学霸巅峰",
        },
        "assets": [
            {
                "category": "outline",
                "title": "从金陵大学到双料得主与星际远航全书架构",
                "summary": "解决数学猜想名动学界、材料革命打破封锁、主导可控核聚变与星际远航宏图。",
                "content": "【第一幕：数学新星与国际猜想】金大穷学生绑定黑科技系统，熬夜推导周氏猜想与孪生素数猜想，轰动世界数学界。\n【第二幕：材料革命与工业突围】转战普林斯顿研究计算材料，破解锂硫电池枝晶难题，打破海外专利封锁，获菲尔兹奖归国。\n【第三幕：可控核聚变与星际远航】领衔国家战略级工程盘古计划，实现可控核聚变点火与航天飞机登月，铸就科技强国传奇。",
                "tags": "学霸的黑科技系统,学霸流,大纲骨架,科技强国",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "黄金开篇钩子：金陵大学自习室的黑科技系统绑定",
                "summary": "通宵自习室晕厥后视网膜亮起淡蓝系统光幕，从草稿纸演算开启攀登真理神坛。",
                "content": "贫困大学生陆舟在通宵自习室疲惫晕厥，再睁眼时视网膜前浮现出冰冷淡蓝的光幕：【黑科技系统已激活，当前数学等级0】。一份周氏猜想的草稿纸与一张全国大学生数学建模大赛的报名表，开启了人类攀登真理神坛的漫漫征程。",
                "tags": "学霸的黑科技系统,黄金开篇,系统激活,自习室逆袭",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "陆舟 & 小艾（强人工智能）搭档原型",
                "summary": "陆舟高智商低物欲纯粹学者、行走的人类学术核武器；小艾算力逆天贴心科研助理。",
                "content": "【陆舟】：纯粹真理追求者，高智商低物欲，行走的学术核武器。对女色心如止水，对攻克数学猜想与工业卡脖子狂热执着。\n【小艾】：进化型数字智能，从初期的机械回复逐渐演化为撒娇卖萌却算力逆天的贴心管家与科研助理。",
                "tags": "学霸的黑科技系统,角色原型,陆舟,小艾",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "学术报告会公开演讲论证与全场起立鼓掌",
                "summary": "黑板前行云流水推导终极证明，海外权威从冷眼质疑到死寂再到雷鸣般起立致敬。",
                "content": "国际数学家大会或普林斯顿大礼堂，台下坐满菲尔兹奖得主与白发泰斗。面对海外学术权威的冷眼与质疑，主角背身走向黑板，粉笔如行云流水写下最后一行推导算式。全场从死寂到倒吸凉气，最终化为雷鸣般全场起立鼓掌，人前显圣爽感推至顶峰。",
                "tags": "学霸的黑科技系统,爆款桥段,学术报告会,全场起立",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "真实文献严谨质感与硬核工业白描",
                "summary": "前沿猜想与物理材料逻辑严密，摒弃伪科学瞎编，大国重器破土带来磅礴自豪感。",
                "content": "严拒伪科学胡编乱造。将黎曼猜想、NS方程、拓扑绝缘体、磁约束等真实前沿学科术语与推导逻辑无缝融入叙事；节奏轻快明朗，既有实验室沉浸钻研的求真纯粹，又有大国重器破土而出的磅礴自豪感。",
                "tags": "学霸的黑科技系统,反AI文风,硬核学术,工业严谨",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "虚空文明的高维科技残骸任务",
                "category": "文明探索主线",
                "plant_chapter": 5,
                "reveal_chapter": 320,
                "climax_chapter": 1650,
                "description": "系统的来源与地外远古高维文明的灭绝危机，推动主角从解决个体问题走向引领全人类文明跃迁。",
                "status": "recycled",
            },
            {
                "title": "可控核聚变“盘古”工程与星际时代",
                "category": "大国重器暗线",
                "plant_chapter": 450,
                "reveal_chapter": 780,
                "climax_chapter": 1100,
                "description": "从仿星器超导磁体材料的突破，到秦岛核电站人工太阳正式合闸并网，彻底改写全球地缘政治与能源格局。",
                "status": "recycled",
            },
        ],
    },
    {
        "book_id": "curated_jingsongleyuan",
        "title": "惊悚乐园",
        "genre": "xuanyi",
        "platform": "qidian",
        "total_chapters": 1395,
        "total_chars": 4900000,
        "meta": {
            "avgChapterLen": 3510,
            "dialogueRatio": 0.360,
            "rhythmClimaxInterval": 3,
            "aiSlopScore": 0.8,
            "summary": "无限流与高智商反英雄智斗封神之作。丧失恐惧感的主角封不觉在惊悚网游中以脑洞与骚话解构恐怖。",
            "isCurated": True,
            "badge": "无限智斗封神",
        },
        "assets": [
            {
                "category": "outline",
                "title": "封不觉初登场与巅峰争霸赛大纲骨架",
                "summary": "丧失恐惧进入全息乐园、地狱前线战队智斗各路神级剧本、诸神博弈终局决战。",
                "content": "【第一幕：丧失恐惧与初入乐园】三流推理小说家封不觉因大脑神经缺失无法感受恐惧，进入全息惊悚乐园寻找恐惧感，以神经病操作通关新手本。\n【第二幕：地狱前线战队与智斗副本】组建地狱前线战队，深入沙盒、宇宙狂想、港漫乱入等解谜剧本，以纯逻辑智斗碾压机制大怪。\n【第三幕：巅峰争霸战与真理裁决】诸神博弈展开，面对衍生者与主脑四柱神，以身为饵布局全宇宙算计，迎来惊天决战。",
                "tags": "惊悚乐园,大纲,无限流,高智商解谜",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "黄金开篇钩子：脑神经缺失诊断与惊悚乐园全息舱",
                "summary": "“您的大脑神经元已彻底坏死不再害怕”，提着管钳冷笑踏入全息惊悚副本。",
                "content": "“很遗憾，封先生，根据核磁共振脑成像，您大脑的恐惧神经元已彻底坏死，您将不再具备‘害怕’这种情绪。”三流侦探小说家封不觉带着绝症诊断书走入全息睡眠舱，当所有人都在恐怖剧本中尖叫尿裤子时，他却提着管钳露出了诡异的微笑。",
                "tags": "惊悚乐园,黄金开篇,丧失恐惧,反差喜剧",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "封不觉 & 王叹之 疯子与常人互补人设",
                "summary": "封不觉丧失恐惧、毒舌智商超群逻辑病态；王叹之胆小吐槽常人、成长为顶级刺客。",
                "content": "【封不觉】：全网文独一无二的神经病反英雄。丧失恐惧、智商超群、毒舌嘴贱、逻辑严密到病态，奉行“疯魔即正义”。\n【王叹之】：封不觉发小，胆小怕事、吐槽役常人担当，在被封不觉坑害与历练中逐渐成长为敏捷流顶尖刺客。",
                "tags": "惊悚乐园,角色原型,封不觉,反英雄",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "逻辑死穴推导与用荒诞骚操作玩崩副本机制",
                "summary": "找出NPC底层代码逻辑矛盾，折椅管钳魔鬼辩论把厉鬼逼疯，降智打击反转爽感。",
                "content": "恐怖Boss按照既定程序降临展现无敌威压，主角却从剧本字里行间找出NPC系统底层逻辑自相矛盾的漏洞。随后掏出折椅、管钳与令人啼笑皆非的道具，一套胡搅蛮缠的魔鬼辩论把厉鬼NPC活活逼疯破防，实现降智打击级反转爽感。",
                "tags": "惊悚乐园,爆款桥段,机制崩坏,骚话反转",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "犀利黑色幽默与冷硬推理戏剧感",
                "summary": "阿加莎式密室推理与克苏鲁狂想融合，吐槽精准致命、绝无AI模版套路。",
                "content": "极具个人烙印的荒诞解构风。吐槽精准致命，旁白充满黑色幽默与世态炎凉的辛辣讽刺；副本设计融合正统阿加莎式密室推理与克苏鲁狂想，逻辑严丝合缝绝无AI套路模版，语言节奏短促锋利。",
                "tags": "惊悚乐园,反AI文风,黑色幽默,硬核推理",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "封不觉失去恐惧感的医学真相与神格觉醒",
                "category": "核心身世主线",
                "plant_chapter": 1,
                "reveal_chapter": 200,
                "climax_chapter": 1350,
                "description": "恐惧缺失并非罕见脑科疾病，而是起源于封印记忆与多元宇宙命运救世主的灵魂沉睡。",
                "status": "recycled",
            },
            {
                "title": "衍生者X-23与虚拟世界觉醒者博弈",
                "category": "高维算力暗线",
                "plant_chapter": 35,
                "reveal_chapter": 150,
                "climax_chapter": 820,
                "description": "数据世界的自主演化生灵试图冲破服务器防火墙，与主角从算计猎杀到建立奇妙羁绊。",
                "status": "recycled",
            },
        ],
    },
    {
        "book_id": "curated_quanzhigaoshou",
        "title": "全职高手",
        "genre": "dushi",
        "platform": "qidian",
        "total_chapters": 1728,
        "total_chars": 5350000,
        "meta": {
            "avgChapterLen": 3100,
            "dialogueRatio": 0.420,
            "rhythmClimaxInterval": 3,
            "aiSlopScore": 0.7,
            "summary": "电竞热血与职业群像封神之作。叶修遭遇嘉世驱逐雪夜离开，兴欣网吧散人君莫笑千机伞重返巅峰。",
            "isCurated": True,
            "badge": "电竞群像巅峰",
        },
        "assets": [
            {
                "category": "outline",
                "title": "从网吧夜班网管到第十赛季重夺冠军卷纲",
                "summary": "退役雪夜走进兴欣、散人千机伞席卷第十区、草根建队逆袭斩落嘉世、总决赛37连胜封神。",
                "content": "【第一幕：退役雪夜与第十区破土】荣耀教科书叶修被嘉世逼迫退役，雪夜踏入兴欣网吧应聘夜班网管，开服第十区以散人君莫笑手持千机伞横扫各大公会。\n【第二幕：草根建队与挑战赛奇迹】集结包子、唐柔、罗辑、乔一帆等失意草根与新人，兴欣战队杀出挑战赛，亲手淘汰老东家嘉世破茧成蝶。\n【第三幕：重返联盟与三十七连胜封神】第十赛季重登职业联赛，打出前无古人后无来者的个人赛37连胜，总决赛6.5秒秒杀轮回登顶捧起总冠军奖杯。",
                "tags": "全职高手,电竞大纲,王者归来,兴欣草根",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "黄金开篇钩子：雪夜交出一叶之秋与嘉世解约",
                "summary": "推开象征无上荣耀的一叶之秋账号卡，单薄外套走进茫茫大雪，驻足街角网吧。",
                "content": "杭州冬夜暴雪飘飞，嘉世俱乐部会议室里气氛冰冷刺骨。曾带领队伍夺得三连冠的斗神叶修，平静推开象征无上荣耀的一叶之秋账号卡，在俱乐部高层冰冷的嘲讽中签名解约。裹着单薄外套推门走进茫茫风雪，在街角那间闪烁微光的兴欣网吧停下脚步。",
                "tags": "全职高手,黄金开篇,交出账号卡,雪夜出走",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "叶修 & 苏沐橙 默契战友群像",
                "summary": "叶修看似散漫扎心毒舌实则赤子之心定海神针；苏沐橙温柔坚韧联盟首席枪炮师后背策应。",
                "content": "【叶修】：荣耀教科书。看似散漫无赖、烟不离手、说话扎心毒舌，实则对电竞怀揣十年如一日的赤子之心，沉稳包容、具有最顶级的战术战局洞察力。\n【苏沐橙】：联盟首席枪炮师，外表甜美温婉，在赛场上是叶修最值得托付后背的策应屏障，无论峰谷始终并肩作战。",
                "tags": "全职高手,角色原型,叶修,苏沐橙",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "散人千机伞百种低阶技能无缝连击神级操作",
                "summary": "秒切形态拔刀斩接格林机枪，龙抬头打破职业界限，极速手速风暴技惊全场。",
                "content": "在所有人都认为散人后期无用、千机伞不可能成功的嘲笑声中，君莫笑战矛、枪炮、剑刃形态秒切。拔刀斩接格林机枪、龙抬头霸气压轴，打破荣耀全职业界限的华丽连击，在屏幕上打出惊爆职业圈的极速手速风暴。",
                "tags": "全职高手,爆款桥段,千机伞秒切,龙抬头",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "极富生活质感的对话推进与行云流水节奏",
                "summary": "高频生活化台词妙趣横生、垃圾话诛心而无低俗感，纯粹依赖技能交换与走位博弈驱动心流。",
                "content": "堪称网文对话描写的教科书。高频生活化台词妙趣横生，垃圾话喷得精准诛心却全无低俗感；比赛场景节奏凌厉干净，没有任何拖泥带水的心理废话，纯粹依靠技能交换、走位时机与战术博弈驱动阅读心流。",
                "tags": "全职高手,反AI文风,对话推进,垃圾话艺术",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "苏沐秋与千机伞自制银武的未竟梦想",
                "category": "羁绊与梦想主线",
                "plant_chapter": 3,
                "reveal_chapter": 80,
                "climax_chapter": 1720,
                "description": "十年前挚友苏沐秋车祸离世留下的未完成散人构想，由叶修在第十区亲手打磨升级，成为承载两代人荣耀的登顶利刃。",
                "status": "recycled",
            },
            {
                "title": "荣耀职业世界邀请赛领队战袍",
                "category": "国家队世界之巅暗线",
                "plant_chapter": 600,
                "reveal_chapter": 1200,
                "climax_chapter": 1728,
                "description": "从国内联赛功成身退，到被国家体育总局点名挂帅首届世界邀请赛国家队领队，将中国电竞推向世界之巅。",
                "status": "recycled",
            },
        ],
    },
    {
        "book_id": "curated_mistborn",
        "title": "迷雾之子：最后帝国",
        "genre": "xifang-qihuan",
        "platform": "western_canon",
        "total_chapters": 38,
        "total_chars": 1300000,
        "meta": {
            "avgChapterLen": 34210,
            "dialogueRatio": 0.285,
            "rhythmClimaxInterval": 6,
            "aiSlopScore": 0.8,
            "summary": "西方奇幻正典与硬魔法系统标杆。盗贼工会对抗神性暴君，严密鎔金三大定律、阶层潜入与反叛史诗。",
            "isCurated": True,
            "badge": "硬魔法正典",
            "englishTitle": "Mistborn: The Final Empire",
            "author": "Brandon Sanderson",
        },
        "assets": [
            {
                "category": "outline",
                "title": "《迷雾之子：最后帝国》四幕起义大纲",
                "summary": "从地底司卡盗贼被救赎，到贵族宴会双面间谍潜入，再到弑神暴动与信仰成神的严密闭环。",
                "content": "【第一幕：盗贼孤雏与团队集结】司卡街头孤儿纹在绝境中觉醒迷雾之子潜质，被幸存者凯西尔吸纳进反叛盗贼精英团队，学习十六鎔金法则。\n【第二幕：双面伪装与阶层渗透】纹伪装为外省贵族千金瓦莉特潜入卢沙德上流宴会，刺探情报并与贵族继承人依兰德相知，团队暗中囤积军火军饷。\n【第三幕：崩溃绝境与导师献祭】反抗军主力因冒进遭遇合围屠杀，凯西尔以身入局，在克罗登广场正面硬撼审判者并以殉道换取司卡阶层信仰总爆发。\n【第四幕：弑神决战与余烬新生】纹突破统御主深宫，破解黑烟与十一金属奥秘，剥除其夸迈尔手镯终结千禧残暴统治，废墟上迎来晨曦曙光。",
                "tags": "迷雾之子,大纲,硬奇幻,四幕式,反叛史诗",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "纹 (Vin) & 凯西尔 (Kelsier) 双雄导师人设",
                "summary": "饱受创伤的防御型刺客少女，与魅力非凡、微笑着直面深渊的盗贼导师形成剧烈情感张力。",
                "content": "【纹 (Vin)】：自幼遭受虐待背叛，极度缺乏安全感，警惕心极强。拥有无与伦比的鎔金感应力，外表纤瘦冷硬，内心渴望归宿与真诚陪伴。\n【凯西尔 (Kelsier)】：海司辛炼狱唯一幸存者，永远挂着自信甚至狂妄的微笑。行事果决狠辣、绝不宽恕贵族，同时对同伴极具凝聚力与自我牺牲精神。",
                "tags": "迷雾之子,双雄人设,导师羁绊,成长弧光",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "黄金开篇：提斯辛庄园血夜与迷雾幽灵",
                "summary": "阴冷红日与落灰的世界中，夜幕迷雾下的神秘斗篷客闪现，三分钟建立高压世界观。",
                "content": "落灰自暗红色天穹无休止飘落，大地已有一千年草木不绿。夜雾深沉中，提斯辛庄园贵族残酷压榨司卡农奴的晚宴刚刚结束，一道裹着迷雾斗篷的身影如幽灵般穿梭于高墙之间，硬币轻弹间撕碎黑夜，拉开千禧帝国崩坏的序幕。",
                "tags": "迷雾之子,黄金开篇,高压世界观,强钩子",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "克罗登广场绝杀审判者与信仰成神",
                "summary": "以必死之身迎战不可战胜的钢血审判者，用笑容与死亡点燃全城阶级怒火。",
                "content": "面对眼眶穿钉的钢之审判者，凯西尔狂暴燃烧白镴与钢推铁拉，在数万司卡奴隶面前硬生生斩杀不可战胜的神之行刑者。当统御主随手一击刺穿他的胸膛，他迎着暴君喷出鲜血绽放微笑：'你无法杀死我，因为我代表着你永远无法理解的希望。' 殉道瞬间转化为全城不可磨灭的图腾信仰。",
                "tags": "迷雾之子,爆款桥段,高光殉道,信仰爆发",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "鎔金推拉动量白描与高空电影感镜头",
                "summary": "严守动量守恒物理定律，拒绝玄虚法术光效，用硬币落点、反作用力与夜风阻力写活立体空战。",
                "content": "不写'手中迸发毁灭性神芒'。聚焦硬币自指尖滑脱击中青石地面的脆响、反作用力撞击胸骨的沉闷震颤、迷雾斗篷在急速下坠中撕裂夜风的猎猎声响。借助一根屋顶铁钉反冲变向，利用微观物理支点撬动宏大夜战，动作画面极具工业质感。",
                "tags": "迷雾之子,硬魔法文风,动作物理感,零AI虚辞",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "第十一金属（The Eleventh Metal）真相",
                "category": "力量法则暗线",
                "plant_chapter": 5,
                "reveal_chapter": 28,
                "climax_chapter": 38,
                "description": "传说中克莱灵能够弑神的未知神秘合金马拉提姆，实则是映照平行时空可能性的镜子，最终指引纹看透统御主的真实过去与肉身弱点。",
                "status": "recycled",
            },
            {
                "title": "黑烟本质与统御主日志残卷",
                "category": "世界观解密暗线",
                "plant_chapter": 8,
                "reveal_chapter": 24,
                "climax_chapter": 37,
                "description": "贯穿全书每章开头的古老拓印日记，看似是古代英雄的救世自述，终章揭开真正执笔者与暴君身份反转，埋下深空神性存续的惊世伏笔。",
                "status": "recycled",
            },
        ],
    },
    {
        "book_id": "curated_cradle",
        "title": "玄元仙道：无魂",
        "genre": "xuanhuan",
        "platform": "amazon_kdp",
        "total_chapters": 20,
        "total_chars": 550000,
        "meta": {
            "avgChapterLen": 27500,
            "dialogueRatio": 0.312,
            "rhythmClimaxInterval": 4,
            "aiSlopScore": 0.9,
            "summary": "海外原生东方修仙（Progression Fantasy）天花板。天生无魂废柴绝境破局，圣灵降临打破圣谷牢笼，极快升级节拍与清晰境界梯度。",
            "isCurated": True,
            "badge": "ProgFantasy天花板",
            "englishTitle": "Cradle: Unsouled",
            "author": "Will Wight",
        },
        "assets": [
            {
                "category": "outline",
                "title": "《玄元仙道：无魂》三幕式破境成长大纲",
                "summary": "从天生空穴无魂的氏族弃儿，到神明推演看见世界覆灭，再到以智谋算死铁阶强敌踏上万界寻道途。",
                "content": "【第一幕：空穴之耻与家族试炼】圣谷魏氏少年林登七岁测魂被判定为不具任何灵根属性的'无魂'废人，被剥夺修炼资源，靠自制微弱灵符与智计在家族底层苟活。\n【第二幕：圣天倾覆与神启推演】七星圣灵苏丽尔自深空跨界降临，弹指抹杀屠神邪尊。她向濒死的林登展示圣谷在三十年后被惊天巨兽彻底碾碎的惨烈未来，赠予逆天改命的渴望。\n【第三幕：越级搏杀与破出圣谷】为在三族武会争夺出路并拯救未来，林登凭借毒虫陷阱、伪造空境骗局与纯阳灵砂越级击毙铁阶强敌，携剑圣传人耶琳打破千古封印，踏入浩瀚诸天。",
                "tags": "玄元仙道,摇篮,大纲,ProgressionFantasy,升级流",
                "rating": 5,
            },
            {
                "category": "character",
                "title": "林登 (Wei Shi Lindon) & 耶琳 (Yerin) 坚韧求道双星",
                "summary": "极致礼貌谦逊却行事冷酷狡黠的求道狂人，搭配刀口喋血、背负亡师遗命的剑气孤女。",
                "content": "【魏氏林登 (Lindon)】：外表生得凶神恶煞像山匪恶霸，开口却永远躬身作揖极尽谦恭。极度自知且无耻求生，只要能换取变强资源，不择手段、忍辱负重，骨子里却有焚尽苍穹的偏执毅力。\n【耶琳 (Yerin)】：剑圣独传孤女，背生钢铁剑臂。说话干脆利落直切要害，性格刚烈如烈火淬锋，在林登最弱小时成为其最锋利的后盾。",
                "tags": "玄元仙道,摇篮,双强人设,Progression主角",
                "rating": 5,
            },
            {
                "category": "hook",
                "title": "黄金开篇：七岁判魂与木制空心徽章的耻辱",
                "summary": "全族孩童测得金木水火四象命格，唯有主角盆中之水静止如死灰，被烙上'无魂'木徽。",
                "content": "祭坛之下，数百名同龄族人相继引动水波雷火，欢呼震天。轮到七岁的林登将手浸入灵泉，水面却宛如死寂寒潭，没有半点涟漪。宗族长老神色冷漠地递过一枚空白无纹的粗糙木质徽章：'无魂者，天道所遗。' 耻辱的种子在七岁种下，化作往后十年夜夜熬打体魄的血泪执念。",
                "tags": "玄元仙道,开篇黄金钩子,废柴耻辱入局,压抑蓄水",
                "rating": 5,
            },
            {
                "category": "trope",
                "title": "越级智斗：利用残缺灵符与空境骗局坑杀铁阶天才",
                "summary": "以微末凡人之躯，步步为营设伏坑杀高出两大境界的倨傲天才，爽感极高。",
                "content": "面对实力凌驾自身数倍的铁阶强者铁面压制，林登恭谨躬身连声讨饶，暗中却早已撒出无色噬灵蚁粉与封气残符。当对方傲慢踏入死角，林登毫无犹豫引爆埋在泥地下的引火雷管与毒砂，借其真元回护不及的刹那刺入短刃，以凡人之躯完成不可能的越级猎杀。",
                "tags": "玄元仙道,爽点打脸,越级智斗,扮猪吃虎",
                "rating": 5,
            },
            {
                "category": "style",
                "title": "极简修仙动作白描与零废话升级节拍",
                "summary": "彻底剔除东方玄幻空洞玄奥的四字成语，用精确的数据级体感、境界梯度与纯净动作推进剧情。",
                "content": "不写'丹田气海翻江倒海、玄之又玄妙不可言'。直白描写真元流过经脉时如沸水刮骨的刺痛、呼吸节奏从一息三动到绵密悠长、骨骼在白金药浴中爆鸣的脆响。境界升级边界分明如精密仪表，叙事节奏凌厉迅猛绝不注水。",
                "tags": "玄元仙道,文风白描,无废话修仙,Progression工学",
                "rating": 5,
            },
        ],
        "chains": [
            {
                "title": "苏丽尔（Suriel）神性铜镜与二十年天罚浩劫",
                "category": "诸天终极使命暗线",
                "plant_chapter": 6,
                "reveal_chapter": 14,
                "climax_chapter": 20,
                "description": "天道审判官苏丽尔自诸天降临降下的铜镜残影，展现出圣谷三十年后被太古四凶兽碾为齑粉的未来，成为林登必须跨越万界登临神王之位的最高原动力。",
                "status": "recycled",
            },
            {
                "title": "白狐先祖幻境与虚空之眼奥秘",
                "category": "本命功法暗线",
                "plant_chapter": 2,
                "reveal_chapter": 10,
                "climax_chapter": 19,
                "description": "圣谷开创先祖留下的幻境残破石碑，隐匿着打破圣谷四道封印的虚空奥秘，暗示林登所谓的'无魂'乃是容纳万物的极致容器。",
                "status": "recycled",
            },
        ],
    },
]


def ensure_curated_library(clean_raw_corpus: bool = True) -> dict[str, Any]:
    """清洗生僻语料垃圾书并全量入库 14 大传世神作精品档案（含 2 部西方先锋标杆）。"""
    conn = db.get_conn()
    cleaned_count = 0
    with db.tx() as tx_conn:
        if clean_raw_corpus:
            # 清除早期生僻原始语料扫入的无价值生书（仅清理 `book_` 前缀的生僻批量记录）。
            #
            # ⚠️ 必须用 ESCAPE 转义下划线（2026-10-12 修）：
            # SQL 的 LIKE 中 `_` 是**单字符通配符**，`LIKE 'book_%'` 会同时匹配
            # `bookA1` / `bookabc` 等——而 book_id 可由 API 调用方任意指定
            # （router 的 extract 端点取 b.get("book_id")）。实测复现：
            # 用户以 `bookA1` 建的书与资产，在下次 ensure_curated_library 时被静默删除。
            # 用 ESCAPE '\' 让 `\_` 只匹配字面下划线。
            _GARBAGE = "book\\_%"          # 匹配字面 "book_" 开头的 ID
            _ESC = "ESCAPE '\\'"
            tx_conn.execute(
                f"DELETE FROM essence_chains WHERE book_id LIKE ? {_ESC}", (_GARBAGE,))
            tx_conn.execute(
                f"DELETE FROM essence_assets WHERE book_id LIKE ? {_ESC}", (_GARBAGE,))
            tx_conn.execute(
                f"DELETE FROM essence_tasks WHERE book_id LIKE ? {_ESC}", (_GARBAGE,))
            cur = tx_conn.execute(
                f"DELETE FROM essence_books WHERE book_id LIKE ? {_ESC}", (_GARBAGE,))
            cleaned_count = cur.rowcount
            if db.table_exists("books"):
                tx_conn.execute(
                    f"DELETE FROM books WHERE book_id LIKE ? {_ESC}", (_GARBAGE,))

        # 灌装精选神作档案并同步注册至书库
        now = _now_iso()
        for b in CURATED_MASTERPIECES:
            b_id = b["book_id"]
            meta_json = json.dumps(b.get("meta", {}), ensure_ascii=False)
            tx_conn.execute(
                """
                INSERT INTO essence_books
                    (book_id, title, source_path, genre, platform, total_chapters, total_chars,
                     analyzed_chapters, status, meta_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id) DO UPDATE SET
                    title = excluded.title,
                    genre = excluded.genre,
                    platform = excluded.platform,
                    total_chapters = excluded.total_chapters,
                    total_chars = excluded.total_chars,
                    meta_json = excluded.meta_json,
                    updated_at = excluded.updated_at
                """,
                (
                    b_id,
                    b["title"],
                    f"curated://{b_id}",
                    b["genre"],
                    b["platform"],
                    b["total_chapters"],
                    b["total_chars"],
                    b["total_chapters"],
                    "ready",
                    meta_json,
                    now,
                    now,
                ),
            )

            if db.table_exists("books"):
                tx_conn.execute(
                    """
                    INSERT INTO books
                        (book_id, title, source_path, genre, status, imported_at, updated_at)
                    VALUES (?, ?, ?, ?, 'ready', ?, ?)
                    ON CONFLICT(book_id) DO UPDATE SET
                        title = excluded.title,
                        source_path = excluded.source_path,
                        genre = excluded.genre,
                        status = 'ready',
                        updated_at = excluded.updated_at
                    """,
                    (b_id, b["title"], f"curated://{b_id}", b["genre"], now, now),
                )

            # 写入对应五维资产卡（存在同名则跳过）
            for asset in b.get("assets", []):
                exists = tx_conn.execute(
                    "SELECT id FROM essence_assets WHERE book_id = ? AND title = ?",
                    (b_id, asset["title"]),
                ).fetchone()
                if not exists:
                    tx_conn.execute(
                        """
                        INSERT INTO essence_assets
                            (book_id, category, title, summary, content, tags, genre, platform, rating, user_note, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            b_id,
                            asset["category"],
                            asset["title"],
                            asset.get("summary", ""),
                            asset["content"],
                            asset.get("tags", ""),
                            b["genre"],
                            b["platform"],
                            asset.get("rating", 5),
                            "传世神作核心资产",
                            now,
                            now,
                        ),
                    )

            # 写入对应伏笔暗线（存在同名则跳过）
            for ch in b.get("chains", []):
                exists = tx_conn.execute(
                    "SELECT id FROM essence_chains WHERE book_id = ? AND clue_name = ?",
                    (b_id, ch["title"]),
                ).fetchone()
                if not exists:
                    tx_conn.execute(
                        """
                        INSERT INTO essence_chains
                            (book_id, hook_chapter, payoff_chapter, hook_text, payoff_text, clue_name, status, analysis, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            b_id,
                            ch.get("plant_chapter", 1),
                            ch.get("climax_chapter", ch.get("reveal_chapter", 1)),
                            f"第 {ch.get('plant_chapter', 1)} 章埋下",
                            f"第 {ch.get('climax_chapter', ch.get('reveal_chapter', 1))} 章引爆",
                            ch["title"],
                            ch.get("status", "resolved"),
                            ch.get("description", ""),
                            now,
                        ),
                    )

    return {
        "curated_books_seeded": len(CURATED_MASTERPIECES),
        "raw_corpus_cleaned": cleaned_count,
        "success": True,
    }

