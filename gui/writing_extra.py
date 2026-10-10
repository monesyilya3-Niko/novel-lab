"""写作增值功能服务层（v2.0.2）：大纲 / 人物卡 / 灵感便签 / 码字统计 / 导出。

分层边界：
- 只经 ``gui.db`` 触碰 SQLite（本模块不直接 import sqlite3）。
- 章节文件只读 ``config.NOVEL_DIR/<project>/chapters/arc-N/chapter-NNN.txt``
  （与 writing_service / scripts/write.py 的落盘约定一致）。
- 项目名校验与 writing_service._sanitize_project 同规则（防路径穿越），
  此处独立实现以避免跨模块私函数耦合。
"""

from __future__ import annotations

import base64
import io
import json
import re
import xml.sax.saxutils
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from gui import config, db, engine_adapter
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
    if not isinstance(project, str):
        raise ServiceError("project 必须为字符串", 400)
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


def reorder_outlines(project: str, order_ids: list[int]) -> list[dict[str, Any]]:
    """批量更新大纲项排序（原子事务）。"""
    project = _require_project(project)
    if not isinstance(order_ids, list):
        raise ServiceError("order_ids 必须为列表", 400)
    now = _now_iso()
    with db.tx() as conn:
        for idx, oid in enumerate(order_ids):
            conn.execute(
                "UPDATE writing_outlines SET sort_order = ?, updated_at = ?"
                " WHERE id = ? AND project = ?",
                (idx, now, int(oid), project),
            )
    return list_outlines(project)


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


def _read_chapter(fp: Path) -> str:
    """读章节文件，编码口径与引擎一致（UTF-8 → GBK）。

    原来这里是 ``fp.read_text(encoding="utf-8")``：章节文件正常都由本应用写（UTF-8），
    但用户把稿子按 ``chapter-NNN.txt`` 摆进 novel/ 是常见操作，GBK 文件会让码字统计、
    导出、入库幂等记账直接抛 UnicodeDecodeError → 一路变成 500，而且不带文件名，
    用户根本不知道是哪一章坏了。
    """
    try:
        return engine_adapter.read_chapter_text(fp)
    except UnicodeError as exc:
        raise ServiceError(
            f"章节文件编码无法识别（仅支持 UTF-8 / GBK）：{fp.name}", 400) from exc


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
                return count_words(_read_chapter(fp))
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
            total_words += count_words(_read_chapter(fp))
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
            content = _read_chapter(fp).strip()
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
    return {"filename": filename, "content": body, "format": "txt",
            "chapters": len(files), "words": count_words(body)}


def export_project_md(project: str) -> dict[str, Any]:
    """导出全书 Markdown：规范章节结构与元数据。"""
    project = _require_project(project)
    files = _iter_chapter_files(project)
    if not files:
        raise ServiceError(f"项目尚无章节可导出: {project}", 404)
    
    today_str = date.today().isoformat()
    lines: list[str] = [
        f"# {project}",
        "",
        f"> 导出日期：{today_str} ｜ 章节总数：{len(files)}",
        "",
        "---",
        "",
    ]
    total_words = 0
    for no, fp in files:
        try:
            content = _read_chapter(fp).strip()
        except OSError:
            continue
        if not content:
            continue
        total_words += count_words(content)
        first_line = content.split("\n", 1)[0].strip()
        looks_like_title = bool(first_line) and len(first_line) <= 60 and "。" not in first_line and "，" not in first_line
        if looks_like_title:
            body = content[len(first_line):].strip()
            lines.append(f"## {first_line}")
            lines.append("")
            lines.append(body)
        else:
            lines.append(f"## 第{no}章")
            lines.append("")
            lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    full_md = "\n".join(lines)
    filename = f"{project}-全书导出-{today_str}.md"
    return {
        "filename": filename,
        "content": full_md,
        "format": "md",
        "chapters": len(files),
        "words": total_words,
    }


def export_project_docx(project: str) -> dict[str, Any]:
    """导出全书 Word (.docx)：纯 Python 标准库零依赖实现（生成合法 OpenXML ZIP 包）。"""
    project = _require_project(project)
    files = _iter_chapter_files(project)
    if not files:
        raise ServiceError(f"项目尚无章节可导出: {project}", 404)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>'
        ))
        z.writestr("_rels/.rels", (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>'
        ))

        doc_body = [
            '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="480"/></w:pPr>'
            f'<w:r><w:rPr><w:b/><w:sz w:val="52"/><w:szCs w:val="52"/></w:rPr><w:t>{xml.sax.saxutils.escape(project)}</w:t></w:r></w:p>'
        ]

        total_words = 0
        for no, fp in files:
            try:
                content = _read_chapter(fp).strip()
            except OSError:
                continue
            if not content:
                continue
            total_words += count_words(content)
            first_line = content.split("\n", 1)[0].strip()
            looks_like_title = bool(first_line) and len(first_line) <= 60 and "。" not in first_line and "，" not in first_line
            if looks_like_title:
                ch_title = first_line
                ch_body = content[len(first_line):].strip()
            else:
                ch_title = f"第{no}章"
                ch_body = content

            doc_body.append(
                '<w:p><w:pPr><w:spacing w:before="360" w:after="180"/></w:pPr>'
                f'<w:r><w:rPr><w:b/><w:sz w:val="36"/><w:szCs w:val="36"/></w:rPr><w:t>{xml.sax.saxutils.escape(ch_title)}</w:t></w:r></w:p>'
            )
            for para in ch_body.split("\n"):
                p = para.strip()
                if p:
                    doc_body.append(
                        '<w:p><w:pPr><w:ind w:firstLineChars="200" w:firstLine="400"/><w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
                        f'<w:r><w:rPr><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr><w:t>{xml.sax.saxutils.escape(p)}</w:t></w:r></w:p>'
                    )

        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body>{"".join(doc_body)}</w:body></w:document>'
        )
        z.writestr("word/document.xml", doc_xml)

    docx_bytes = buf.getvalue()
    b64_content = base64.b64encode(docx_bytes).decode("ascii")
    filename = f"{project}-全书导出-{date.today().isoformat()}.docx"
    return {
        "filename": filename,
        "content_base64": b64_content,
        "format": "docx",
        "chapters": len(files),
        "words": total_words,
    }


def export_project(project: str, fmt: str = "txt") -> dict[str, Any]:
    """统一多格式导出入口：txt / md / docx。"""
    fmt_clean = (fmt or "txt").lower().strip()
    if fmt_clean in ("docx", "word"):
        return export_project_docx(project)
    elif fmt_clean in ("md", "markdown"):
        return export_project_md(project)
    return export_project_txt(project)
