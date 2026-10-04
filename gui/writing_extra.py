"""写作增值功能服务层（v2.0.2）：大纲 / 人物卡 / 灵感便签 / 码字统计 / 导出。

分层边界：
- 只经 ``gui.db`` 触碰 SQLite（本模块不直接 import sqlite3）。
- 章节文件只读 ``config.NOVEL_DIR/<project>/chapters/arc-N/chapter-NNN.txt``
  （与 writing_service / scripts/write.py 的落盘约定一致）。
- 项目名校验与 writing_service._sanitize_project 同规则（防路径穿越），
  此处独立实现以避免跨模块私函数耦合。
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from gui import config, db
from gui.logging_setup import get_logger
from gui.services import ServiceError

_log = get_logger("writing_extra")

_WS_RE = re.compile(r"\s+")

_OUTLINE_KINDS = frozenset({"volume", "chapter"})
_OUTLINE_STATUSES = frozenset({"planned", "writing", "done"})


def count_words(text: str) -> int:
    """中文网文字数：去掉全部空白字符后的字符数。"""
    if not text:
        return 0
    return len(_WS_RE.sub("", text))


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today_str() -> str:
    return date.today().isoformat()


def _require_project(project: str) -> str:
    """项目名校验（与 writing_service._sanitize_project 同规则）。"""
    if not project or not project.strip():
        raise ServiceError("project 不能为空", 400)
    p = project.strip()
    if any(ch in p for ch in ("/", "\\", "..", "\x00", "\n", "\r")):
        raise ServiceError(f"非法项目名: {project!r}", 400)
    if p == "default":
        raise ServiceError("default 为 CLI 只读项目", 400)
    return p


def _novel_dir(project: str) -> Path:
    return config.NOVEL_DIR / _require_project(project)


# ---------------------------------------------------------------------------
# 大纲
# ---------------------------------------------------------------------------

def list_outlines(project: str) -> list[dict[str, Any]]:
    project = _require_project(project)
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT id, project, kind, title, summary, status, sort_order,"
        " created_at, updated_at FROM writing_outlines"
        " WHERE project = ? ORDER BY sort_order ASC, id ASC",
        (project,),
    ).fetchall()
    return [db.row_to_dict(r) for r in rows]


def create_outline(project: str, kind: str = "chapter", title: str = "",
                   summary: str = "", status: str = "planned",
                   sort_order: int = 0) -> dict[str, Any]:
    project = _require_project(project)
    kind = kind if kind in _OUTLINE_KINDS else "chapter"
    status = status if status in _OUTLINE_STATUSES else "planned"
    if not title or not title.strip():
        raise ServiceError("大纲标题不能为空", 400)
    now = _now_iso()
    with db.tx() as conn:
        cur = conn.execute(
            "INSERT INTO writing_outlines"
            " (project, kind, title, summary, status, sort_order, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project, kind, title.strip(), summary or "", status,
             int(sort_order), now, now),
        )
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT id, project, kind, title, summary, status, sort_order,"
            " created_at, updated_at FROM writing_outlines WHERE id = ?",
            (new_id,),
        ).fetchone()
    return db.row_to_dict(row)


def update_outline(outline_id: int, **fields: Any) -> dict[str, Any]:
    allowed = {"kind", "title", "summary", "status", "sort_order"}
    sets: list[str] = []
    vals: list[Any] = []
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        if k == "kind" and v not in _OUTLINE_KINDS:
            raise ServiceError(f"非法 kind: {v}", 400)
        if k == "status" and v not in _OUTLINE_STATUSES:
            raise ServiceError(f"非法 status: {v}", 400)
        if k == "title" and not str(v).strip():
            raise ServiceError("大纲标题不能为空", 400)
        sets.append(f"{k} = ?")
        vals.append(v)
    if not sets:
        raise ServiceError("没有可更新的字段", 400)
    vals.append(_now_iso())
    vals.append(int(outline_id))
    with db.tx() as conn:
        cur = conn.execute(
            f"UPDATE writing_outlines SET {', '.join(sets)}, updated_at = ? WHERE id = ?",
            vals,
        )
        if cur.rowcount == 0:
            raise ServiceError(f"大纲不存在: {outline_id}", 404)
        row = conn.execute(
            "SELECT id, project, kind, title, summary, status, sort_order,"
            " created_at, updated_at FROM writing_outlines WHERE id = ?",
            (int(outline_id),),
        ).fetchone()
    return db.row_to_dict(row)


def delete_outline(outline_id: int) -> None:
    with db.tx() as conn:
        cur = conn.execute("DELETE FROM writing_outlines WHERE id = ?",
                           (int(outline_id),))
        if cur.rowcount == 0:
            raise ServiceError(f"大纲不存在: {outline_id}", 404)


# ---------------------------------------------------------------------------
# 人物卡
# ---------------------------------------------------------------------------

def list_characters(project: str) -> list[dict[str, Any]]:
    project = _require_project(project)
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT id, project, name, role, description, extra, created_at, updated_at"
        " FROM writing_characters WHERE project = ? ORDER BY id ASC",
        (project,),
    ).fetchall()
    return [db.row_to_dict(r) for r in rows]


def create_character(project: str, name: str, role: str = "",
                     description: str = "",
                     extra: dict[str, Any] | None = None) -> dict[str, Any]:
    project = _require_project(project)
    if not name or not name.strip():
        raise ServiceError("人物姓名不能为空", 400)
    now = _now_iso()
    with db.tx() as conn:
        cur = conn.execute(
            "INSERT INTO writing_characters"
            " (project, name, role, description, extra, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (project, name.strip(), role or "", description or "",
             json.dumps(extra or {}, ensure_ascii=False), now, now),
        )
        row = conn.execute(
            "SELECT id, project, name, role, description, extra, created_at, updated_at"
            " FROM writing_characters WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return db.row_to_dict(row)


def update_character(char_id: int, **fields: Any) -> dict[str, Any]:
    allowed = {"name", "role", "description", "extra"}
    sets: list[str] = []
    vals: list[Any] = []
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        if k == "name" and not str(v).strip():
            raise ServiceError("人物姓名不能为空", 400)
        if k == "extra" and isinstance(v, dict):
            v = json.dumps(v, ensure_ascii=False)
        sets.append(f"{k} = ?")
        vals.append(v)
    if not sets:
        raise ServiceError("没有可更新的字段", 400)
    vals.append(_now_iso())
    vals.append(int(char_id))
    with db.tx() as conn:
        cur = conn.execute(
            f"UPDATE writing_characters SET {', '.join(sets)}, updated_at = ? WHERE id = ?",
            vals,
        )
        if cur.rowcount == 0:
            raise ServiceError(f"人物不存在: {char_id}", 404)
        row = conn.execute(
            "SELECT id, project, name, role, description, extra, created_at, updated_at"
            " FROM writing_characters WHERE id = ?",
            (int(char_id),),
        ).fetchone()
    return db.row_to_dict(row)


def delete_character(char_id: int) -> None:
    with db.tx() as conn:
        cur = conn.execute("DELETE FROM writing_characters WHERE id = ?",
                           (int(char_id),))
        if cur.rowcount == 0:
            raise ServiceError(f"人物不存在: {char_id}", 404)


# ---------------------------------------------------------------------------
# 灵感便签
# ---------------------------------------------------------------------------

def list_notes(project: str) -> list[dict[str, Any]]:
    project = _require_project(project)
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT id, project, title, content, created_at, updated_at"
        " FROM writing_notes WHERE project = ?"
        " ORDER BY updated_at DESC, id DESC",
        (project,),
    ).fetchall()
    return [db.row_to_dict(r) for r in rows]


def create_note(project: str, title: str = "", content: str = "") -> dict[str, Any]:
    project = _require_project(project)
    if not (title or "").strip() and not (content or "").strip():
        raise ServiceError("便签标题与内容不能同时为空", 400)
    now = _now_iso()
    with db.tx() as conn:
        cur = conn.execute(
            "INSERT INTO writing_notes (project, title, content, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (project, title or "", content or "", now, now),
        )
        row = conn.execute(
            "SELECT id, project, title, content, created_at, updated_at"
            " FROM writing_notes WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
    return db.row_to_dict(row)


def update_note(note_id: int, **fields: Any) -> dict[str, Any]:
    allowed = {"title", "content"}
    sets: list[str] = []
    vals: list[Any] = []
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        sets.append(f"{k} = ?")
        vals.append(v)
    if not sets:
        raise ServiceError("没有可更新的字段", 400)
    vals.append(_now_iso())
    vals.append(int(note_id))
    with db.tx() as conn:
        cur = conn.execute(
            f"UPDATE writing_notes SET {', '.join(sets)}, updated_at = ? WHERE id = ?",
            vals,
        )
        if cur.rowcount == 0:
            raise ServiceError(f"便签不存在: {note_id}", 404)
        row = conn.execute(
            "SELECT id, project, title, content, created_at, updated_at"
            " FROM writing_notes WHERE id = ?",
            (int(note_id),),
        ).fetchone()
    return db.row_to_dict(row)


def delete_note(note_id: int) -> None:
    with db.tx() as conn:
        cur = conn.execute("DELETE FROM writing_notes WHERE id = ?",
                           (int(note_id),))
        if cur.rowcount == 0:
            raise ServiceError(f"便签不存在: {note_id}", 404)


# ---------------------------------------------------------------------------
# 码字统计
# ---------------------------------------------------------------------------

def record_words(project: str, words: int, chapters: int = 1) -> None:
    """记录一次写作产出（章节入库 / AI 生成完成时调用）。失败只记日志，不阻断主流程。

    words 可为负：重复入库同一章节时只记增量（改短了就扣减），保证统计幂等。
    words 为 0 时直接返回（等价无操作；调用方传 chapters=0 即可表达"非新章节"）。
    """
    try:
        project = _require_project(project)
        words = int(words)
        if words == 0:
            return
        with db.tx() as conn:
            conn.execute(
                "INSERT INTO writing_daily_stats (date, project, words, chapters)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(date, project) DO UPDATE SET"
                " words = writing_daily_stats.words + excluded.words,"
                " chapters = writing_daily_stats.chapters + excluded.chapters",
                (_today_str(), project, words, int(chapters)),
            )
    except Exception as exc:  # noqa: BLE001 — 统计不得阻断写作主流程
        _log.warning("码字统计记录失败（已忽略）: %s", exc)


def _iter_chapter_files(project: str) -> list[tuple[int, Path]]:
    """按章节号排序列出章节文件。"""
    novel_dir = _novel_dir(project)
    chapters_dir = novel_dir / "chapters"
    out: list[tuple[int, Path]] = []
    if not chapters_dir.is_dir():
        return out
    for fp in chapters_dir.rglob("chapter-*.txt"):
        m = re.fullmatch(r"chapter-(\d+)\.txt", fp.name)
        if m:
            out.append((int(m.group(1)), fp))
    out.sort(key=lambda t: t[0])
    return out


def get_chapter_words(project: str, chapter_no: int) -> int | None:
    """返回已落盘章节的字数（count_words 口径）；章节不存在返回 None。

    供入库幂等使用：重复入库同一章节时只记录字数增量，不重复累加。
    """
    for no, fp in _iter_chapter_files(project):
        if no == chapter_no:
            try:
                return count_words(fp.read_text(encoding="utf-8"))
            except OSError:
                return 0
    return None


def get_stats(project: str, days: int = 30) -> dict[str, Any]:
    """码字统计：今日 / 累计 / 历史曲线 / 连更天数。"""
    project = _require_project(project)
    days = max(1, min(int(days), 365))
    today = date.today()
    start = (today - timedelta(days=days - 1)).isoformat()

    conn = db.get_conn()
    rows = conn.execute(
        "SELECT date, words, chapters FROM writing_daily_stats"
        " WHERE project = ? AND date >= ? ORDER BY date ASC",
        (project, start),
    ).fetchall()
    by_date = {r["date"]: {"words": r["words"], "chapters": r["chapters"]}
               for r in rows}
    history = []
    for i in range(days):
        d = (today - timedelta(days=days - 1 - i)).isoformat()
        history.append({"date": d, "words": by_date.get(d, {}).get("words", 0),
                        "chapters": by_date.get(d, {}).get("chapters", 0)})

    # 连更天数：从今天（或昨天）往前数 words>0 的连续天数
    streak = 0
    cursor = today
    if by_date.get(cursor.isoformat(), {}).get("words", 0) == 0:
        cursor -= timedelta(days=1)
    while by_date.get(cursor.isoformat(), {}).get("words", 0) > 0:
        streak += 1
        cursor -= timedelta(days=1)

    # 累计：直接扫描章节文件（权威），不受统计表影响
    total_words = 0
    total_chapters = 0
    for _no, fp in _iter_chapter_files(project):
        try:
            total_words += count_words(fp.read_text(encoding="utf-8"))
            total_chapters += 1
        except OSError:
            continue

    return {
        "project": project,
        "today_words": by_date.get(today.isoformat(), {}).get("words", 0),
        "today_chapters": by_date.get(today.isoformat(), {}).get("chapters", 0),
        "total_words": total_words,
        "total_chapters": total_chapters,
        "streak_days": streak,
        "history": history,
    }


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------

def export_project_txt(project: str) -> dict[str, Any]:
    """导出全书 TXT：章节按号拼接，返回 {filename, content}（前端转 blob 下载）。"""
    project = _require_project(project)
    files = _iter_chapter_files(project)
    if not files:
        raise ServiceError(f"项目尚无章节可导出: {project}", 404)
    parts: list[str] = []
    for no, fp in files:
        try:
            content = fp.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not content:
            continue
        # 首行若像标题则直接沿用正文（避免标题重复输出），否则补一个默认标题
        first_line = content.split("\n", 1)[0].strip()
        looks_like_title = bool(first_line) and len(first_line) <= 60 and "。" not in first_line and "，" not in first_line
        if looks_like_title:
            parts.append(content + "\n")
        else:
            parts.append(f"第{no}章\n\n{content}\n")
    body = "\n\n".join(parts)
    filename = f"{project}-全书导出-{date.today().isoformat()}.txt"
    return {"filename": filename, "content": body,
            "chapters": len(files), "words": count_words(body)}
