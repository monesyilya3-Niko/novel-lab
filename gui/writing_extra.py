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
import uuid
import xml.sax.saxutils
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from gui import config, db, engine_adapter
from gui.logging_setup import get_logger
from gui.services import ServiceError

_log = get_logger("writing_extra")

_WS_RE = re.compile(r"\s+")
# XML 1.0 合法字符过滤：剔除 \x00-\x08, \x0b, \x0c, \x0e-\x1f, \ufffe, \uffff 等非法控制字符
_ILLEGAL_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def _escape_xml(text: str) -> str:
    """过滤 XML 1.0 非法字符并转义实体字符 (&, <, >)。"""
    if not text:
        return ""
    cleaned = _ILLEGAL_XML_CHARS_RE.sub("", text)
    return xml.sax.saxutils.escape(cleaned)


_OUTLINE_KINDS = frozenset({"volume", "chapter"})
_OUTLINE_STATUSES = frozenset({"planned", "writing", "done"})


def count_words(text: str) -> int:
    """中文网文字数：去掉全部空白字符后的字符数。"""
    if not text:
        return 0
    return len(_WS_RE.sub("", text))


# CJK 统一表意文字及扩展区、兼容字、假名、谚文
_CJK_CHAR_RE = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]"
)
# 英文/西文独立单词（支持中划线连词如 state-of-the-art，撇号缩写如 it's, don't）
_EN_WORD_RE = re.compile(r"\b[a-zA-Z0-9]+(?:[-'][a-zA-Z0-9]+)*\b")


def count_words_i18n(text: str, mode: str = "auto") -> dict[str, Any]:
    """多语言 / 跨语种自适应字数与阅读时长统计引擎（Exoscribe 双语核心底座）。

    参数:
        text: 待统计文本。
        mode: 统计模式。
            - "auto": 默认自适应混合模式。CJK 按单字计，西文按单词正则切分计词数，
                      总数 = CJK 字符数 + 西文单词数。
            - "zh" / "cjk": 中文网文传统口径，全等同于 ``count_words(text)``（去空白字符数）。
            - "en": 纯西文统计口径，仅提取有效西文单词数。

    返回:
        dict:
            - total: int, 选定口径下的总字数/词数。
            - cjk_chars: int, 文本包含的 CJK 字符数。
            - en_words: int, 文本包含的英文/西文单词数。
            - reading_time_minutes: float, 预估阅读耗时（分钟，保留 1 位小数；中文 400 字/分，英文 220 词/分）。
            - primary_language: str, 主导语言 ("zh" | "en" | "unknown")。
    """
    if not text or not isinstance(text, str):
        return {
            "total": 0,
            "cjk_chars": 0,
            "en_words": 0,
            "reading_time_minutes": 0.0,
            "primary_language": "unknown",
        }

    cjk_matches = _CJK_CHAR_RE.findall(text)
    cjk_count = len(cjk_matches)
    en_matches = _EN_WORD_RE.findall(text)
    en_count = len(en_matches)

    # 确定主导语言
    if cjk_count == 0 and en_count == 0:
        primary_lang = "unknown"
    elif cjk_count >= en_count:
        primary_lang = "zh"
    else:
        primary_lang = "en"

    normalized_mode = (mode or "auto").strip().lower()
    if normalized_mode in ("zh", "cjk"):
        total = count_words(text)
        mins = total / 400.0
    elif normalized_mode == "en":
        total = en_count
        mins = en_count / 220.0
    else:  # auto
        total = cjk_count + en_count
        mins = (cjk_count / 400.0) + (en_count / 220.0)

    # 预估阅读时间归一化：有文本时最小 0.1 分钟（约 6 秒），无内容则 0.0
    if total > 0:
        reading_time = round(mins, 1)
        if reading_time == 0.0:
            reading_time = 0.1
    else:
        reading_time = 0.0

    return {
        "total": total,
        "cjk_chars": cjk_count,
        "en_words": en_count,
        "reading_time_minutes": reading_time,
        "primary_language": primary_lang,
    }


# ---------------------------------------------------------------------------
# 章节张力与黄金三章情绪波形动态分析模型（Tension & Emotion Wave Model）
# ---------------------------------------------------------------------------

_CONFLICT_KEYWORDS = frozenset({
    "生死", "性命", "杀", "斩", "死", "亡", "血", "逃", "截杀", "绝境", "毁灭", "危机",
    "暴怒", "轰", "爆", "崩", "撕裂", "剧毒", "敌", "剑芒", "枪声", "炸裂", "重伤",
    "断臂", "倒塌", "杀机", "狂暴", "破裂", "刺穿", "震颤", "怒吼", "咆哮", "搏杀",
    "陷阱", "阴谋", "绝望", "灭门", "血泊", "伏击", "反扑", "突变", "死绝", "屠戮",
})

_EMOTION_TENSION_KEYWORDS = frozenset({
    "冷汗", "窒息", "心脏狂跳", "剧痛", "发麻", "颤抖", "瞳孔紧缩", "目眦欲裂", "咬牙",
    "倒吸一口凉气", "紧绷", "煞白", "狂跳", "冷笑", "杀意", "惊恐", "骇然", "惨白",
    "青筋暴起", "汗毛倒竖", "惊悚", "心惊肉跳", "毛骨悚然", "慌乱", "狂怒", "暴躁",
})

_CONFRONTATION_DIALOGUE_KEYWORDS = frozenset({
    "你敢", "凭什么", "找死", "休想", "住手", "滚", "闭嘴", "为何", "不可", "绝不",
    "狂妄", "放肆", "纳命来", "受死", "交出来", "妄想", "谁给你的胆子", "饶命",
})

_BENCHMARK_PROFILES: dict[str, list[int]] = {
    # 经典起承转合黄金波形（开局抓人、中段铺垫蓄势、后段高潮爆发、末尾强留白）
    "classic": [35, 45, 52, 68, 60, 82, 92, 70, 86, 95],
    # 黄金三秒强入局波形（开篇即极端生死/悬疑危机，高压推行）
    "fast_hook": [82, 88, 65, 70, 75, 82, 90, 78, 88, 96],
    # 稳健发育层层递进波形（凡人流/修真升级，节奏厚重扎实）
    "steady": [25, 32, 42, 52, 62, 72, 82, 90, 95, 75],
    # 极限压抑逆袭反杀波形（退婚/受辱/逆袭，先抑后扬大爆发）
    "face_slap": [30, 22, 18, 28, 48, 65, 88, 96, 98, 75],
}

_BENCHMARK_NAMES = {
    "classic": "经典起承转合标杆",
    "fast_hook": "黄金三秒强入局标杆",
    "steady": "稳健递进厚积薄发标杆",
    "face_slap": "极限压抑逆袭打脸标杆",
}

_DEFAULT_10_LABELS = [
    "开端 (0-10%)", "伏笔 (10-20%)", "微冲突 (20-30%)", "试探 (30-40%)", "积蓄 (40-50%)",
    "爆发 (50-60%)", "高潮 (60-70%)", "喘息 (70-80%)", "反扑 (80-90%)", "收束 (90-100%)",
]


def _resample_curve(profile: list[int], target_len: int) -> list[int]:
    """对标杆曲线进行线性重采样，自适应目标分段数量。"""
    if target_len == len(profile):
        return list(profile)
    res: list[int] = []
    n = len(profile)
    for i in range(target_len):
        pos = i * (n - 1) / max(target_len - 1, 1)
        low = int(pos)
        high = min(low + 1, n - 1)
        weight = pos - low
        val = int(round(profile[low] * (1 - weight) + profile[high] * weight))
        res.append(max(0, min(100, val)))
    return res


def _split_into_segments(text: str, n: int) -> list[str]:
    """将篇章文本均分为 n 段，优先在换行与句尾标点处安全切分。"""
    clean_text = text.strip()
    if not clean_text:
        return [""] * n
    total_len = len(clean_text)
    if total_len <= n:
        return [clean_text[i:i + 1] for i in range(total_len)] + [""] * (n - total_len)

    step = total_len / n
    segments: list[str] = []
    prev_idx = 0
    for i in range(1, n):
        target_idx = int(round(i * step))
        search_start = max(prev_idx + 1, target_idx - 60)
        search_end = min(total_len - 1, target_idx + 60)
        window = clean_text[search_start:search_end]
        cut_candidates = [
            m.start() + search_start + 1
            for m in re.finditer(r"[\n。！？!?]", window)
        ]
        if cut_candidates:
            best_cut = min(cut_candidates, key=lambda pos: abs(pos - target_idx))
            if best_cut <= prev_idx or best_cut >= total_len:
                best_cut = target_idx
        else:
            best_cut = target_idx
        segments.append(clean_text[prev_idx:best_cut].strip())
        prev_idx = best_cut
    segments.append(clean_text[prev_idx:].strip())
    return segments


def _calculate_segment_tension(seg_text: str) -> int:
    """计算单个文本切片的张力指数（15-98 分区间）。"""
    if not seg_text or not seg_text.strip():
        return 20

    c = len(_WS_RE.sub("", seg_text))
    if c == 0:
        return 20

    # 1. 句子节奏与长短句爆发
    sentences = engine_adapter.split_sentences(seg_text)
    s_count = max(len(sentences), 1)
    avg_len = c / s_count

    pace_bonus = 0.0
    if avg_len < 12:
        pace_bonus = 10.0
    elif avg_len < 18:
        pace_bonus = 5.0
    elif avg_len > 35:
        pace_bonus = -8.0

    # 2. 感叹号与语气符号密集度
    exc_count = seg_text.count("！") + seg_text.count("!") + seg_text.count("？") + seg_text.count("?")
    exc_density = (exc_count / c) * 500
    punctuation_boost = min(15.0, exc_density * 6.0)

    # 3. 词汇特征命中
    conflict_hits = sum(seg_text.count(w) for w in _CONFLICT_KEYWORDS)
    emotion_hits = sum(seg_text.count(w) for w in _EMOTION_TENSION_KEYWORDS)
    dialogue_hits = sum(seg_text.count(w) for w in _CONFRONTATION_DIALOGUE_KEYWORDS)

    conflict_score = (conflict_hits / c) * 500 * 8.0
    emotion_score = (emotion_hits / c) * 500 * 7.0
    dialogue_score = (dialogue_hits / c) * 500 * 6.0

    raw_tension = 35.0 + pace_bonus + punctuation_boost + conflict_score + emotion_score + dialogue_score
    return max(15, min(98, int(round(raw_tension))))


def analyze_tension_curve(
    text: str,
    benchmark: str = "classic",
    segments_count: int = 10,
) -> dict[str, Any]:
    """基于网文张力数学模型分析章节情绪张力起伏波形，并与神作标杆曲线比对。"""
    if not isinstance(text, str):
        raise ServiceError("text 必须为字符串", 400)

    # 限制切片数量范围在 3 到 20 之间
    n = max(3, min(20, int(segments_count or 10)))

    # 规范化标杆类型
    bm_key = (benchmark or "classic").strip().lower()
    if bm_key not in _BENCHMARK_PROFILES:
        bm_key = "classic"
    raw_bm_profile = _BENCHMARK_PROFILES[bm_key]
    benchmark_curve = _resample_curve(raw_bm_profile, n)
    bm_name = _BENCHMARK_NAMES.get(bm_key, "经典起承转合标杆")

    # 构建分段标签
    if n == 10:
        labels = list(_DEFAULT_10_LABELS)
    else:
        labels = [f"第{i + 1}段 ({int(round(i * 100 / n))}-{int(round((i + 1) * 100 / n))}%)" for i in range(n)]

    if not text.strip():
        return {
            "segments": labels,
            "tension_curve": [0] * n,
            "benchmark_curve": benchmark_curve,
            "benchmark_name": bm_name,
            "climax_index": 0,
            "climax_segment": labels[0],
            "max_tension": 0,
            "avg_tension": 0.0,
            "tension_variance": 0.0,
            "benchmark_alignment_score": 0,
            "flat_zones": [],
            "pacing_feedback": ["文本内容为空，无法计算张力曲线与节奏节拍。"],
        }

    # 切分文本段落并计算张力
    segments_text = _split_into_segments(text, n)
    tension_curve = [_calculate_segment_tension(seg) for seg in segments_text]

    # 极值与统计指标
    climax_idx = max(range(n), key=lambda i: tension_curve[i])
    max_t = tension_curve[climax_idx]
    avg_t = round(sum(tension_curve) / n, 1)
    variance = round((sum((t - avg_t) ** 2 for t in tension_curve) / n) ** 0.5, 1)

    # 平淡期检测（张力 < 35 且相邻仍 < 35）
    flat_zones = []
    for i, t in enumerate(tension_curve):
        is_flat = t < 35 and (
            (i > 0 and tension_curve[i - 1] < 35) or
            (i < n - 1 and tension_curve[i + 1] < 35)
        )
        if is_flat:
            flat_zones.append({
                "segment_index": i,
                "label": labels[i],
                "tension": t,
            })

    # 标杆拟合度得分 (100 - mean_absolute_error)
    diffs = [abs(t - b) for t, b in zip(tension_curve, benchmark_curve, strict=False)]
    mean_diff = sum(diffs) / len(diffs) if diffs else 0
    alignment_score = max(0, min(100, int(round(100 - mean_diff))))

    # 智能策展编辑建议反馈
    feedback: list[str] = []

    # 1. 开篇入局评价
    first_t = tension_curve[0]
    if first_t >= 65:
        feedback.append(f"【黄金开局】开篇第 1 段张力达 {first_t} 分，危机与冲突前置，具备出色的黄金三秒抓人效应。")
    elif first_t < 38:
        feedback.append(f"【开局平缓】开篇第 1 段张力为 {first_t} 分，起笔较为平静。若为商业网络小说连载首章，建议适度前置微冲突或悬念钩子。")

    # 2. 高潮位置评价
    if climax_idx in (n - 4, n - 3, n - 2, n - 1):
        feedback.append(f"【节奏合拍】全章最高潮出现在第 {climax_idx + 1} 段（{labels[climax_idx]}，张力 {max_t} 分），处于后半程蓄势爆发黄金区间。")
    elif climax_idx <= 1:
        feedback.append(f"【高潮前置】全章最高潮极度靠前（第 {climax_idx + 1} 段，张力 {max_t} 分），后半段若缺乏次级冲突承接，容易给读者造成'高开低走'之感。")

    # 3. 平淡期警戒
    if flat_zones:
        flat_labels = "、".join(z["label"].split()[0] for z in flat_zones[:3])
        feedback.append(f"【平淡区间】检测到 {len(flat_zones)} 处低张力连续平推区间（如 {flat_labels}），读者易产生疲倦，建议穿插环境压迫、人物机锋或暗线情报。")

    # 4. 动态波形跨度
    if variance < 8.0:
        feedback.append(f"【张力平稳】全章张力波动幅度较小（起伏标准差 {variance}），波峰与波谷对比不够鲜明，建议拉大'抑'与'扬'的反差。")
    else:
        feedback.append(f"【起伏鲜明】全章情绪张力波动起伏鲜明（起伏标准差 {variance}），具有清晰的起承转合层次。")

    return {
        "segments": labels,
        "tension_curve": tension_curve,
        "benchmark_curve": benchmark_curve,
        "benchmark_name": bm_name,
        "climax_index": climax_idx,
        "climax_segment": labels[climax_idx],
        "max_tension": max_t,
        "avg_tension": avg_t,
        "tension_variance": variance,
        "benchmark_alignment_score": alignment_score,
        "flat_zones": flat_zones,
        "pacing_feedback": feedback,
    }


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
    cleaned_ids: list[int] = []
    for oid in order_ids:
        try:
            cleaned_ids.append(int(oid))
        except (ValueError, TypeError):
            raise ServiceError(f"非法大纲 ID: {oid!r}", 400) from None
    now = _now_iso()
    with db.tx() as conn:
        for idx, oid in enumerate(cleaned_ids):
            conn.execute(
                "UPDATE writing_outlines SET sort_order = ?, updated_at = ?"
                " WHERE id = ? AND project = ?",
                (idx, now, oid, project),
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
        if not db.table_exists("writing_daily_stats"):
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
            '<w:r><w:rPr><w:rFonts w:hint="eastAsia" w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="宋体"/>'
            f'<w:b/><w:sz w:val="52"/><w:szCs w:val="52"/></w:rPr><w:t xml:space="preserve">{_escape_xml(project)}</w:t></w:r></w:p>'
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
                '<w:r><w:rPr><w:rFonts w:hint="eastAsia" w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="宋体"/>'
                f'<w:b/><w:sz w:val="36"/><w:szCs w:val="36"/></w:rPr><w:t xml:space="preserve">{_escape_xml(ch_title)}</w:t></w:r></w:p>'
            )
            for para in ch_body.split("\n"):
                p = para.strip()
                if p:
                    doc_body.append(
                        '<w:p><w:pPr><w:ind w:firstLineChars="200" w:firstLine="400"/><w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
                        '<w:r><w:rPr><w:rFonts w:hint="eastAsia" w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="宋体"/>'
                        f'<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr><w:t xml:space="preserve">{_escape_xml(p)}</w:t></w:r></w:p>'
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


def export_project_epub(project: str) -> dict[str, Any]:
    """导出全书标准 EPUB 3.0 电子书容器（纯 Python 标准库零依赖，适配 Amazon KDP / Apple Books / 各类电子阅读器）。"""
    project = _require_project(project)
    files = _iter_chapter_files(project)
    if not files:
        raise ServiceError(f"项目尚无章节可导出: {project}", 404)

    buf = io.BytesIO()
    book_uuid = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with zipfile.ZipFile(buf, "w") as z:
        # 1. mimetype (必须是第一个文件，且不得压缩)
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

        # 2. META-INF/container.xml
        container_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
            '  <rootfiles>\n'
            '    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
            '  </rootfiles>\n'
            '</container>'
        )
        z.writestr("META-INF/container.xml", container_xml, compress_type=zipfile.ZIP_DEFLATED)

        # 3. OEBPS/style.css
        style_css = (
            "body {\n"
            "  margin: 5% 6%;\n"
            "  font-family: serif, 'Times New Roman', 'Source Han Serif', 'Songti SC', 'SimSun';\n"
            "  line-height: 1.7;\n"
            "  color: #111;\n"
            "}\n"
            "h1, h2 {\n"
            "  text-align: center;\n"
            "  margin-top: 1.8em;\n"
            "  margin-bottom: 1.2em;\n"
            "  font-weight: bold;\n"
            "}\n"
            "p {\n"
            "  text-indent: 2em;\n"
            "  margin: 0.4em 0;\n"
            "}\n"
            ".stat-box {\n"
            "  border: 1px solid #777;\n"
            "  background: #fdfdfd;\n"
            "  padding: 12px 16px;\n"
            "  margin: 16px 0;\n"
            "  font-family: monospace;\n"
            "  font-size: 0.9em;\n"
            "  text-indent: 0;\n"
            "}\n"
        )
        z.writestr("OEBPS/style.css", style_css, compress_type=zipfile.ZIP_DEFLATED)

        manifest_items = [
            '<item id="style" href="style.css" media-type="text/css"/>',
            '<item id="nav" href="toc.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        ]
        spine_items = []
        toc_items = []
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

            ch_id = f"chapter_{no:03d}"
            ch_filename = f"{ch_id}.xhtml"

            # 组装段落 HTML
            p_html = []
            for line in ch_body.split("\n"):
                p = line.strip()
                if p:
                    p_html.append(f"  <p>{_escape_xml(p)}</p>")

            body_paragraphs = "\n".join(p_html)
            chapter_xhtml = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!DOCTYPE html>\n'
                '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-CN">\n'
                '<head>\n'
                '  <meta charset="utf-8"/>\n'
                f'  <title>{_escape_xml(ch_title)}</title>\n'
                '  <link rel="stylesheet" type="text/css" href="style.css"/>\n'
                '</head>\n'
                '<body>\n'
                f'  <h2>{_escape_xml(ch_title)}</h2>\n'
                f'{body_paragraphs}\n'
                '</body>\n'
                '</html>'
            )
            z.writestr(f"OEBPS/{ch_filename}", chapter_xhtml, compress_type=zipfile.ZIP_DEFLATED)

            manifest_items.append(f'<item id="{ch_id}" href="{ch_filename}" media-type="application/xhtml+xml"/>')
            spine_items.append(f'<itemref idref="{ch_id}"/>')
            toc_items.append(f'      <li><a href="{ch_filename}">{_escape_xml(ch_title)}</a></li>')

        # 4. OEBPS/toc.xhtml (EPUB 3 导航文档)
        toc_list_html = "\n".join(toc_items)
        toc_xhtml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-CN">\n'
            '<head>\n'
            '  <meta charset="utf-8"/>\n'
            '  <title>目录</title>\n'
            '  <link rel="stylesheet" type="text/css" href="style.css"/>\n'
            '</head>\n'
            '<body>\n'
            '  <nav epub:type="toc" id="toc">\n'
            f'    <h1>{_escape_xml(project)} - 目录</h1>\n'
            '    <ol>\n'
            f'{toc_list_html}\n'
            '    </ol>\n'
            '  </nav>\n'
            '</body>\n'
            '</html>'
        )
        z.writestr("OEBPS/toc.xhtml", toc_xhtml, compress_type=zipfile.ZIP_DEFLATED)

        # 5. OEBPS/content.opf (包元数据与清单)
        manifest_xml = "\n    ".join(manifest_items)
        spine_xml = "\n    ".join(spine_items)
        content_opf = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id">\n'
            '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            f'    <dc:identifier id="pub-id">urn:uuid:{book_uuid}</dc:identifier>\n'
            f'    <dc:title>{_escape_xml(project)}</dc:title>\n'
            '    <dc:language>zh-CN</dc:language>\n'
            '    <dc:creator>暮冬念春 / Exoscribe</dc:creator>\n'
            f'    <meta property="dcterms:modified">{now_iso}</meta>\n'
            '  </metadata>\n'
            '  <manifest>\n'
            f'    {manifest_xml}\n'
            '  </manifest>\n'
            '  <spine>\n'
            f'    {spine_xml}\n'
            '  </spine>\n'
            '</package>'
        )
        z.writestr("OEBPS/content.opf", content_opf, compress_type=zipfile.ZIP_DEFLATED)

    epub_bytes = buf.getvalue()
    b64_content = base64.b64encode(epub_bytes).decode("ascii")
    filename = f"{project}-全书导出-{date.today().isoformat()}.epub"
    return {
        "filename": filename,
        "content_base64": b64_content,
        "format": "epub",
        "chapters": len(files),
        "words": total_words,
    }


def export_project_shunn(
    project: str,
    author_name: str = "Author Name",
    contact_info: str = "author@example.com",
) -> dict[str, Any]:
    """导出全书为 William Shunn 国际标准文稿投稿格式（Standard Manuscript Format）。"""
    project = _require_project(project)
    files = _iter_chapter_files(project)
    if not files:
        raise ServiceError(f"项目尚无章节可导出: {project}", 404)

    lines: list[str] = []
    total_words = 0
    chapter_contents: list[tuple[str, str]] = []

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
            ch_title = f"CHAPTER {no}"
            ch_body = content
        chapter_contents.append((ch_title, ch_body))

    # Page 1 Header
    approx_words = max(100, int(round(total_words / 100.0) * 100))
    lines.append(f"{author_name}\n")
    if contact_info:
        lines.append(f"{contact_info}\n")
    lines.append(f"About {approx_words:,} words\n\n\n\n")

    # Title Block
    lines.append(f"{project.upper()}\n\nby {author_name}\n\n\n")

    # Chapters
    for i, (ch_title, ch_body) in enumerate(chapter_contents):
        if i > 0:
            lines.append("\n\n#\n\n")  # Standard Shunn scene/chapter break
        lines.append(f"{ch_title.upper()}\n\n")
        for para in ch_body.split("\n"):
            p = para.strip()
            if p:
                lines.append(f"    {p}\n\n")  # 5-space indentation, double spaced

    full_text = "".join(lines)
    filename = f"{project}-Shunn文稿-{date.today().isoformat()}.txt"
    return {
        "filename": filename,
        "content": full_text,
        "format": "shunn",
        "chapters": len(files),
        "words": total_words,
    }


def export_project(project: str, fmt: str = "txt") -> dict[str, Any]:
    """统一多格式导出入口：txt / md / docx / epub / shunn。"""
    fmt_clean = (fmt or "txt").lower().strip()
    if fmt_clean in ("docx", "word"):
        return export_project_docx(project)
    elif fmt_clean in ("md", "markdown"):
        return export_project_md(project)
    elif fmt_clean in ("epub", "ebook"):
        return export_project_epub(project)
    elif fmt_clean in ("shunn", "manuscript"):
        return export_project_shunn(project)
    return export_project_txt(project)


def get_project_meta(project: str) -> dict[str, Any]:
    """获取项目的平台生态、题材与企划元数据。"""
    proj = _require_project(project)
    conn = db.get_conn()
    row = conn.execute(
        "SELECT * FROM writing_projects_meta WHERE project = ?", (proj,)
    ).fetchone()
    if row:
        d = dict(row)
        try:
            d["meta"] = json.loads(d.get("meta_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["meta"] = {}
        return d
    # 若尚无元数据，返回默认预设
    return {
        "project": proj,
        "platform": "fanqie",
        "genre": "general",
        "target_words": 1000000,
        "summary": "",
        "meta": {},
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def update_project_meta(
    project: str,
    platform: str | None = None,
    genre: str | None = None,
    target_words: int | None = None,
    summary: str | None = None,
    meta: dict | None = None,
) -> dict[str, Any]:
    """更新或创建项目的平台生态与企划元数据。"""
    proj = _require_project(project)
    current = get_project_meta(proj)
    new_platform = str(platform) if platform is not None else current["platform"]
    new_genre = str(genre) if genre is not None else current["genre"]
    new_target_words = int(target_words) if target_words is not None else current["target_words"]
    new_summary = str(summary) if summary is not None else current["summary"]
    new_meta = meta if meta is not None else current.get("meta", {})
    now = datetime.now().isoformat()

    with db.tx() as conn:
        conn.execute(
            """
            INSERT INTO writing_projects_meta
                (project, platform, genre, target_words, summary, meta_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project) DO UPDATE SET
                platform = excluded.platform,
                genre = excluded.genre,
                target_words = excluded.target_words,
                summary = excluded.summary,
                meta_json = excluded.meta_json,
                updated_at = excluded.updated_at
            """,
            (proj, new_platform, new_genre, new_target_words, new_summary, json.dumps(new_meta, ensure_ascii=False), now, now),
        )
    return get_project_meta(proj)

