"""迁移 CLI：``python -m gui.migrate``（执行 / --check 对账 / --rollback 回滚 / --backup 备份）。

职责（见 DESIGN_gui_persistence §5.2 / §6）：
1. 备份现有 index.db（若有）。
2. 建库（init_schema + apply_migrations）。
3. 扫描 assets/*.json + reports/*.md + corpus/*.txt。
4. 对每个资产 infer_kind / infer_book_id / infer_genre，UPSERT 入库（事务，幂等）。
5. 对账输出 {migrated, assets, reports, books}，与源目录扫描比对。

kind 推断（§6.2）：文件名 + JSON 内容双重判定，**不再用旧 _SUFFIX_KIND 硬编码**；
``trope-library.json`` 靠 ``tropes`` 键、``genre-prose-card-index.json`` 靠 ``cards`` 键识别。
``*-distilled.json``（跨书蒸馏卡）判为 ``distilled``、索引判为 ``prose_card_index``——
二者都是独立 kind，不冒充基础卡（voice/structure/commercial/craft）也不与 ``trope`` 混用；
蒸馏与索引在 ``assets`` 表 ``book_id`` 一律为 NULL。
未命中规则的资产归 ``trope`` 兜底（宁多勿丢），单列 ``unrecognized`` 清单供复核。

仅标准库：argparse / json / os / pathlib / shutil / sqlite3（经 gui.db）。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保项目根在 sys.path 上（直接 ``python gui/migrate.py`` 也可运行）。
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gui import config, db  # noqa: E402

# 书卡后缀（book_id 推断用，优先级从长到短，含 distilled）。
_BOOK_CARD_SUFFIXES = (
    "-voice-card-distilled", "-voice-card",
    "-structure-obs-distilled", "-structure-obs",
    "-commercial-obs-distilled", "-commercial-obs",
    "-craft-card-distilled", "-craft-card",
    "-genre-pack",
)

# 蒸馏卡后缀（跨书题材聚合产物）：kind=distilled，须在基础卡后缀之前判定，
# 否则 ``-voice-card`` 会先命中，把蒸馏卡冒充成 voice 基础卡。
_DISTILLED_SUFFIXES = (
    "-voice-card-distilled", "-structure-obs-distilled",
    "-commercial-obs-distilled", "-craft-card-distilled",
)

# 报告后缀 → 报告类型。
_REPORT_SUFFIX = (
    ("-拆书报告.md", "book"),
    ("-笔法分析.md", "craft"),
)

# 备份保留策略：只保留最近 N 个 ``*.bak-*``，超出自动清理最旧的（防运行时堆积）。
BACKUP_KEEP = 3


# ---------------------------------------------------------------------------
# 推断规则（§6.2 / 6.3 / 6.5）
# ---------------------------------------------------------------------------

def infer_book_id(stem: str) -> Optional[str]:
    """从文件名反推 book_id（§6.3）。

    书卡去后缀取前缀；题材文风卡 / trope / 索引 / 跨书蒸馏卡 / 题材包返回 None。
    单书名**不要求**含 ``_chosen``：中文书名（如「暮冬念春」）同样合法。
    """
    if not stem:
        return None
    # 题材文风卡 / trope 库 / 索引文件：无归属书。
    if "genre-prose-card-" in stem or stem in ("trope-library", "genre-prose-card-index"):
        return None
    # 跨书蒸馏卡（题材级聚合，无单书归属）：显式覆盖 distilled 后缀，
    # 避免被下面的基础卡后缀剥离出「看似有归属」的前缀。
    if stem.endswith(_DISTILLED_SUFFIXES):
        return None
    # 题材包是 genre 级资产，不是单书卡。
    if stem.endswith("-genre-pack"):
        return None
    # 基础书卡：剥离后缀取前缀（voice/craft/structure/commercial 等）。
    for suffix in _BOOK_CARD_SUFFIXES:
        if stem.endswith(suffix):
            prefix = stem[: -len(suffix)]
            return prefix or None
    # 其他未匹配命名：无明确归属。
    return None


def infer_kind(name: str, content: Dict[str, Any]) -> str:
    """文件名 + JSON 内容 → kind（§6.2 优先级从高到低）。

    trope-library 靠 ``tropes`` 键、genre-prose-card-index 靠 ``cards`` 键识别；
    未命中任何规则归 ``trope`` 兜底（宁多勿丢）。
    """
    stem = Path(name).stem if name.endswith(".json") else name
    meta = content.get("meta") if isinstance(content, dict) else None
    meta_kind = (meta or {}).get("kind") if isinstance(meta, dict) else None

    # 1. trope-library（含 tropes 键）→ trope
    if "trope-library" in stem and isinstance(content.get("tropes"), (dict, list)):
        return "trope"
    # 2. genre-prose-card-index（含 cards 键）→ prose_card_index（题材寻址表，
    #    独立 kind；须在通用 genre-prose-card- 之前判定，否则被吞成 prose_card）。
    if "genre-prose-card-index" in stem and isinstance(content.get("cards"), (dict, list)):
        return "prose_card_index"
    # 3. genre-prose-card-*（meta.kind == genre-prose-card）→ prose_card
    if "genre-prose-card-" in stem and meta_kind == "genre-prose-card":
        return "prose_card"
    # 3b. 兜底：文件名即含 genre-prose-card-（即便 meta.kind 缺失）也归 prose_card。
    if "genre-prose-card-" in stem:
        return "prose_card"
    # 4. 跨书蒸馏卡（*-distilled）→ distilled（须在基础卡后缀之前判定）。
    if stem.endswith(_DISTILLED_SUFFIXES):
        return "distilled"
    # 5-9. 基础书卡 / 题材包后缀。
    if stem.endswith("-voice-card"):
        return "voice"
    if stem.endswith("-structure-obs"):
        return "structure"
    if stem.endswith("-commercial-obs"):
        return "commercial"
    if stem.endswith("-craft-card"):
        return "craft"
    if stem.endswith("-genre-pack"):
        return "genre_pack"
    # 兜底（宁多勿丢）。
    return "trope"


def infer_genre(name: str, content: Dict[str, Any]) -> Optional[str]:
    """推断 genre（§6.5），优先级从高到低：

    1. ``meta.genre`` 字段（最高优先，既有规则不变）。
    2. 文件名 ``genre-prose-card-genre-{genre}`` 段（既有规则不变）。
    3. ``meta.id`` 以 ``genre-`` 开头 → 去前缀取题材 key（新增，覆盖题材包
       ``genre-campus-redemption`` → ``campus-redemption`` 这种「无 meta.genre」
       的命名形态）。

    返回 None 表示无法推断（不登记 genres 表）。
    """
    meta = content.get("meta") if isinstance(content, dict) else None
    if isinstance(meta, dict):
        g = meta.get("genre")
        if isinstance(g, str) and g:
            return g
    stem = Path(name).stem
    # genre-prose-card-genre-{genre}.json → 提取 {genre}（优先级高于 meta.id）。
    if "genre-prose-card-genre-" in stem:
        return stem.split("genre-prose-card-genre-", 1)[1]
    # meta.id = "genre-{genre}"（题材包命名）→ 去 "genre-" 前缀取题材 key。
    if isinstance(meta, dict):
        gid = meta.get("id")
        if isinstance(gid, str) and gid.startswith("genre-"):
            genre = gid[len("genre-"):].strip()
            if genre:
                return genre
    return None


# ---------------------------------------------------------------------------
# 扫描源目录
# ---------------------------------------------------------------------------

def scan_assets() -> List[Path]:
    """扫描 assets/*.json（平铺）。"""
    root = config.ASSETS_ROOT
    if not root.is_dir():
        return []
    return sorted(root.glob("*.json"))


def scan_reports() -> List[Path]:
    """扫描 reports/*.md。"""
    root = config.REPORTS_DIR
    if not root.is_dir():
        return []
    return sorted(root.glob("*.md"))


def scan_corpus() -> List[Path]:
    """扫描 corpus/*.txt（排除 raw/sampled/metrics/fanqie 子目录）。"""
    root = config.CORPUS_DIR
    if not root.is_dir():
        return []
    return sorted(p for p in root.glob("*.txt") if p.is_file())


# ---------------------------------------------------------------------------
# 备份 / 回滚
# ---------------------------------------------------------------------------

def prune_backups(keep: int = BACKUP_KEEP) -> List[Path]:
    """备份保留策略：只保留最近 ``keep`` 个 ``*.bak-*``，删除更旧的。

    备份文件名形如 ``index.db.bak-{YYYYmmdd-HHMMSS}``，时间戳可直接字符串排序，
    故按名字升序排列即时间先后。保留末位 ``keep`` 个，其余删除；``keep <= 0``
    时清空全部备份（谨慎使用）。

    Args:
        keep: 保留的最近备份数量，默认 ``BACKUP_KEEP``（3）。

    Returns:
        被删除的备份路径列表（按从旧到新）。
    """
    parent = db.db_path().parent
    if not parent.is_dir():
        return []
    backups = sorted(parent.glob("*.bak-*"))  # 名字含可排序时间戳 → 升序即时间先后
    keep = max(int(keep), 0)
    if len(backups) <= keep:
        return []
    stale = backups[: len(backups) - keep] if keep > 0 else backups
    removed: List[Path] = []
    for old in stale:
        try:
            old.unlink()
            removed.append(old)
        except OSError:
            pass
    if removed:
        print(f"[migrate] 备份保留策略：清理最旧 {len(removed)} 个备份"
              f"（保留最近 {keep} 个）: " + ", ".join(p.name for p in removed))
    return removed


def backup() -> Optional[Path]:
    """备份现有 index.db（若有）为 index.db.bak-{ts}，返回备份路径或 None。

    用 SQLite 原生 ``Connection.backup`` API 做在线备份，确保 WAL 未 checkpoint 的
    写入也一并落盘（``shutil.copy2`` 只复制主文件，会丢 WAL 中的最新数据）。

    备份后自动执行 ``prune_backups()``，保证 ``*.bak-*`` 收敛到最近 ``BACKUP_KEEP`` 个。
    """
    src = db.db_path()
    dst: Optional[Path] = None
    if src.is_file():
        ts = time.strftime("%Y%m%d-%H%M%S")
        dst = src.with_name(f"index.db.bak-{ts}")
        # M1：备份逻辑收口到 db.backup_to（db.py 是唯一 import sqlite3 的层）。
        db.backup_to(dst)
    # 保留策略：无论本次是否新建备份，都把备份数量收敛到最近 BACKUP_KEEP 个。
    prune_backups()
    return dst


def rollback() -> Optional[Path]:
    """从最新备份恢复 index.db（覆盖当前库），返回恢复的备份路径或 None。"""
    src = db.db_path()
    backups = sorted(src.parent.glob("index.db.bak-*"))
    if not backups:
        return None
    latest = backups[-1]
    db.close()  # 先关闭连接，避免 Windows 文件锁。
    # 若当前库存在，先移除（连同 WAL/SHM）。
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(src) + suffix)
        if p.is_file():
            p.unlink(missing_ok=True)
    shutil.copy2(latest, src)
    # 重建连接指向恢复后的库（下次 get_conn 会因 _conn_path 已清空而重连）。
    db._reset_conn()
    return latest


# ---------------------------------------------------------------------------
# 实体入库（UPSERT，幂等）
# ---------------------------------------------------------------------------

def _rel_path(fp: Path) -> str:
    """相对化路径（相对 ROOT_DIR），回退为 <目录名>/<文件名>。"""
    try:
        return str(fp.relative_to(config.ROOT_DIR))
    except ValueError:
        return f"{fp.parent.name}/{fp.name}"


def _upsert_book(conn: Any, book_id: str, title: str, source_path: Optional[str],
                 genre: Optional[str], status: str) -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn.execute(
        """
        INSERT INTO books (book_id, title, source_path, genre, status, imported_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(book_id) DO UPDATE SET
            title = excluded.title,
            source_path = COALESCE(excluded.source_path, books.source_path),
            genre = COALESCE(excluded.genre, books.genre),
            updated_at = excluded.updated_at
        """,
        (book_id, title, source_path, genre, status, now, now),
    )


def _upsert_asset(conn: Any, asset_key: str, kind: str, name: str, path: str,
                  book_id: Optional[str], genre: Optional[str], size: Optional[int],
                  mtime: Optional[float], meta_json: str) -> None:
    """资产 UPSERT（幂等）。链式 ``ON CONFLICT``（SQLite 3.35.0+）覆盖两个唯一约束：

    1. ``asset_key`` 冲突（``kind:stem`` 相同）→ 更新非键列，重复迁移不重复插行。
    2. ``path`` 冲突（同一文件已存在别的 ``asset_key``）→ **存量库被旧代码迁移过**的
       场景：老版本把 ``genre-prose-card-index.json`` 判为 ``trope``、把 ``*-distilled``
       判为对应基础卡，库里留有 ``trope:genre-prose-card-index`` /
       ``voice:xxx-voice-card-distilled`` 这类旧 kind 行（path 与文件一致）。新代码推断出的
       ``asset_key`` 与旧行不冲突，但 ``assets.path`` 是 UNIQUE——只处理 asset_key 会
       ``IntegrityError``，被 ``db.tx()`` 整体回滚，迁移**永久失败**、新 kind 进不了库。
       故按 path 命中时把历史行**原地**改写成新 ``asset_key`` + 新 ``kind``
       （``path`` 已等于 ``excluded.path``，无需回写）：既不删行、不重建库，也避免
       ``asset_key`` 与 ``get_asset_detail``/``_item_id`` 的 ``kind:stem`` 口径漂移。
    """
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn.execute(
        """
        INSERT INTO assets (asset_key, kind, name, path, book_id, genre, size, mtime,
                            meta_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(asset_key) DO UPDATE SET
            kind = excluded.kind,
            name = excluded.name,
            path = excluded.path,
            book_id = excluded.book_id,
            genre = excluded.genre,
            size = excluded.size,
            mtime = excluded.mtime,
            meta_json = excluded.meta_json,
            updated_at = excluded.updated_at
        ON CONFLICT(path) DO UPDATE SET
            asset_key = excluded.asset_key,
            kind = excluded.kind,
            name = excluded.name,
            book_id = excluded.book_id,
            genre = excluded.genre,
            size = excluded.size,
            mtime = excluded.mtime,
            meta_json = excluded.meta_json,
            updated_at = excluded.updated_at
        """,
        (asset_key, kind, name, path, book_id, genre, size, mtime, meta_json, now, now),
    )


def _upsert_report(conn: Any, report_key: str, rtype: str, book_id: Optional[str],
                   path: str, title: Optional[str], char_count: Optional[int]) -> None:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn.execute(
        """
        INSERT INTO reports (report_key, type, book_id, path, title, char_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(report_key) DO UPDATE SET
            type = excluded.type,
            book_id = excluded.book_id,
            path = excluded.path,
            title = excluded.title,
            char_count = excluded.char_count
        """,
        (report_key, rtype, book_id, path, title, char_count, now),
    )


# genres.kind 的合法枚举（schema 契约，见 0001_init.sql / DESIGN §2.2）。
# 「题材来源 kind」只允许这三类；voice/commercial/craft/structure 等**资产** kind
# 不得写入该列（L1：同题材多数资产逐个 UPSERT 会互相覆盖，最终落成 voice 等非法值）。
GENRE_KIND_ENUM = ("genre_pack", "prose_card", "book")
# 题材包优先：genre_pack 的 kind 权威，prose_card/book 仅作降级兜底。
GENRE_KIND_PRIORITY = {"genre_pack": 3, "book": 2, "prose_card": 1}


def _sanitize_genre_kind(kind: Optional[str]) -> Optional[str]:
    """把资产 kind 映射为 genres.kind 的**合法枚举值**；非法/不相关返回 None。

    L1 修复核心：调用方传入的资产 kind（voice/commercial/craft/structure/trope）
    **不在枚举内一律返回 None**，从而既不能覆盖已有值、也不写入非法值。
    """
    if isinstance(kind, str) and kind in GENRE_KIND_ENUM:
        return kind
    return None


def _upsert_genre(conn: Any, name: str, display_name: Optional[str], kind: Optional[str]) -> None:
    """题材登记：``genres.kind`` 只允许「题材包优先」的合法枚举写入（L1 修复）。

    策略（防后写覆盖）：
    1. 入参 ``kind`` 先过 ``_sanitize_genre_kind``：非枚举（voice/commercial/craft/
       structure/trope）→ None，**不写也不覆盖**。
    2. SQL 的 UPDATE 分支用 ``WHERE`` 子句做优先级裁决——仅当新值的优先级**严格高于**
       现有值时（题材包 genre_pack 胜出），才允许覆盖 ``kind``；同值/降级值一律保持原样。
       ``prose_card``/``book`` 因此只能在「原值为 NULL 或更低优先级」时写入（降级兜底）。
    """
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    sanitized = _sanitize_genre_kind(kind)
    priority = GENRE_KIND_PRIORITY.get(sanitized or "", 0)
    conn.execute(
        """
        INSERT INTO genres (name, display_name, kind, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            display_name = COALESCE(excluded.display_name, genres.display_name),
            kind = CASE
                       WHEN excluded.kind IS NULL THEN genres.kind
                       ELSE excluded.kind
                   END
        WHERE excluded.kind IS NOT NULL
          AND (? > CASE COALESCE(genres.kind, '')
                        WHEN 'genre_pack' THEN 3
                        WHEN 'book'       THEN 2
                        WHEN 'prose_card' THEN 1
                        ELSE 0
                    END)
        """,
        (name, display_name, sanitized, now, priority),
    )


def _report_char_count(fp: Path) -> int:
    """粗略字数：md 文本去空白后的字符数（支撑铁律二统计）。"""
    try:
        text = fp.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    return len("".join(text.split()))


def _load_json(fp: Path) -> Dict[str, Any]:
    """读 JSON，失败返回空 dict（不阻断迁移，宁多勿丢靠兜底 kind）。"""
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# 主迁移流程
# ---------------------------------------------------------------------------

def run_migrate() -> Dict[str, Any]:
    """建库→迁移→扫描实体→UPSERT→对账。返回统计 dict。

    幂等：asset_key/book_id/report_key 均 UNIQUE + ON CONFLICT UPDATE，重复跑不重复插。
    """
    backup()  # 先备份现有库（若有）。

    db.init_schema()
    applied = db.apply_migrations()

    asset_files = scan_assets()
    report_files = scan_reports()
    corpus_files = scan_corpus()

    # 推断「有资产卡/报告的书」（已拆书）与「已导入未拆书」。
    book_ids_with_assets: set[str] = set()
    for fp in asset_files:
        bid = infer_book_id(fp.stem)
        if bid:
            book_ids_with_assets.add(bid)
    for fp in report_files:
        # 报告 stem 如 ``chireng_chosen-拆书报告`` 不匹配卡后缀，infer_book_id 返回 None；
        # 这里额外按报告后缀剥离出 book_id，保证「仅有报告、无资产卡」的书也被计入已拆书。
        bid = infer_book_id(fp.stem)
        if not bid:
            for suffix, _rk in _REPORT_SUFFIX:
                if fp.name.endswith(suffix):
                    bid = fp.name[: -len(suffix)]
                    break
        if bid:
            book_ids_with_assets.add(bid)

    all_corpus_book_ids = {fp.stem for fp in corpus_files}

    unrecognized: List[str] = []

    with db.tx() as conn:
        # 1) 书：已拆书（status=done）+ 已导入未拆书（status=idle，D4）。
        for bid in sorted(book_ids_with_assets):
            _upsert_book(conn, bid, bid, None, None, "done")
        for bid in sorted(all_corpus_book_ids - book_ids_with_assets):
            src = _rel_path(config.CORPUS_DIR / f"{bid}.txt")
            _upsert_book(conn, bid, bid, src, None, "idle")
        # 兜底：corpus 里已拆书也补 source_path。
        for bid in sorted(all_corpus_book_ids & book_ids_with_assets):
            src = _rel_path(config.CORPUS_DIR / f"{bid}.txt")
            _upsert_book(conn, bid, bid, src, None, "done")

        # 2) 资产卡。
        # 同时收集「单书卡 → genre」，供 books.genre 回填（中文书/英文书同理）。
        book_genre_from_voice: Dict[str, str] = {}
        for fp in asset_files:
            content = _load_json(fp)
            kind = infer_kind(fp.name, content)
            genre = infer_genre(fp.name, content)
            book_id = infer_book_id(fp.stem)
            stem = fp.stem
            asset_key = f"{kind}:{stem}"
            # 显示名：优先 meta.name，其次 stem。
            meta = content.get("meta") if isinstance(content, dict) else None
            display_name = (meta or {}).get("name") if isinstance(meta, dict) else None
            name = display_name or stem
            st = fp.stat()
            meta_json = json.dumps(meta, ensure_ascii=False) if isinstance(meta, dict) else "{}"
            _upsert_asset(conn, asset_key, kind, name, _rel_path(fp), book_id, genre,
                          st.st_size, st.st_mtime, meta_json)
            if kind == "trope" and not (
                    "trope-library" in stem or "genre-prose-card-index" in stem):
                unrecognized.append(fp.name)
            # 题材登记（genres 表）。
            if genre:
                _upsert_genre(conn, genre, display_name if isinstance(display_name, str) else None, kind)
            # 单书 voice/craft 卡带 genre 时记录，用于回填 books.genre。
            if book_id and genre and kind in ("voice", "craft"):
                book_genre_from_voice.setdefault(book_id, genre)

        # 2b) books.genre 回填：仅在为空时写入，不覆盖已有值。
        for bid, g in sorted(book_genre_from_voice.items()):
            conn.execute(
                "UPDATE books SET genre = COALESCE(genre, ?), updated_at = datetime('now') "
                "WHERE book_id = ? AND (genre IS NULL OR genre = '')",
                (g, bid),
            )

        # 3) 报告。
        for fp in report_files:
            rtype = "book"
            book_id = fp.stem
            for suffix, rk in _REPORT_SUFFIX:
                if fp.name.endswith(suffix):
                    rtype = rk
                    book_id = fp.name[: -len(suffix)]
                    break
            report_key = f"{book_id}:{rtype}"
            _upsert_report(conn, report_key, rtype, book_id, _rel_path(fp), fp.stem,
                           _report_char_count(fp))

    # 对账。
    conn = db.get_conn()
    n_assets = conn.execute("SELECT COUNT(*) AS n FROM assets").fetchone()["n"]
    n_reports = conn.execute("SELECT COUNT(*) AS n FROM reports").fetchone()["n"]
    n_books = conn.execute("SELECT COUNT(*) AS n FROM books").fetchone()["n"]
    n_books_done = conn.execute("SELECT COUNT(*) AS n FROM books WHERE status='done'").fetchone()["n"]

    result = {
        "migrated": len(applied),
        "assets": n_assets,
        "assets_on_disk": len(asset_files),
        "reports": n_reports,
        "reports_on_disk": len(report_files),
        "books": n_books,
        "books_done": n_books_done,
        "corpus_on_disk": len(corpus_files),
        "unrecognized": unrecognized,
    }
    return result


def check() -> Dict[str, Any]:
    """只读对账：库 vs 源目录 diff，返回缺失/多余清单（不写库）。"""
    asset_files = scan_assets()
    report_files = scan_reports()
    corpus_files = scan_corpus()

    conn = db.get_conn()
    db_assets = {r["path"] for r in db.list_asset_rows(limit=100000)}
    db_reports = {r["path"] for r in db.list_reports()}

    disk_assets = {_rel_path(fp) for fp in asset_files}
    disk_reports = {_rel_path(fp) for fp in report_files}

    missing_assets = sorted(disk_assets - db_assets)
    extra_assets = sorted(db_assets - disk_assets)
    missing_reports = sorted(disk_reports - db_reports)
    extra_reports = sorted(db_reports - disk_reports)

    return {
        "assets": {"disk": len(disk_assets), "db": len(db_assets),
                   "missing": missing_assets, "extra": extra_assets},
        "reports": {"disk": len(disk_reports), "db": len(db_reports),
                    "missing": missing_reports, "extra": extra_reports},
        "corpus_on_disk": len(corpus_files),
        "ok": not (missing_assets or extra_assets or missing_reports or extra_reports),
    }


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def _print_result(result: Dict[str, Any]) -> None:
    print("[migrate] 迁移完成：")
    print(f"  migrated      = {result.get('migrated')}")
    print(f"  assets        = {result.get('assets')} (磁盘 {result.get('assets_on_disk')})")
    print(f"  reports       = {result.get('reports')} (磁盘 {result.get('reports_on_disk')})")
    print(f"  books         = {result.get('books')} (已拆 {result.get('books_done')}, 磁盘语料 {result.get('corpus_on_disk')})")
    if result.get("unrecognized"):
        print(f"  unrecognized  = {result['unrecognized']}")


def sync_asset(fp: Path) -> None:
    """单文件重索引：组装写完 assets/*.json 后调用，幂等 upsert 进 SQLite。

    复用 infer_kind / infer_book_id / infer_genre + _upsert_asset（db.tx 内）。
    不调 run_migrate()（避免每次 backup() 与全量扫描）。

    ``asset_key`` 与 ``path`` 必须与 :func:`run_migrate` / :meth:`AssetIndex._item_id`
    同口径（``f"{kind}:{stem}"`` / ``_rel_path``）：详情定位走
    ``get_asset_by_key(f"{kind}:{name}")``，若重索引用 ``asset_key=stem``，要么另插一行
    重复资产，要么在 path 冲突时把既有行的 ``asset_key`` 静默改写掉，详情查询随即落空。
    """
    from gui import db as _db

    fp = Path(fp)
    if not fp.is_file():
        return
    try:
        content = json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(content, dict):
        return

    stem = fp.stem
    kind = infer_kind(stem, content)
    book_id = infer_book_id(stem)
    genre = infer_genre(stem, content)
    meta_json = json.dumps(content.get("meta", {}), ensure_ascii=False)
    try:
        size = fp.stat().st_size
        mtime = fp.stat().st_mtime
    except OSError:
        size, mtime = None, None

    with _db.tx() as conn:
        _upsert_asset(
            conn, asset_key=f"{kind}:{stem}", kind=kind, name=stem, path=_rel_path(fp),
            book_id=book_id, genre=genre, size=size, mtime=mtime, meta_json=meta_json)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="novel-lab GUI 数据迁移 CLI")
    parser.add_argument("--check", action="store_true", help="只读对账，不写库")
    parser.add_argument("--rollback", action="store_true", help="从最新备份恢复 index.db")
    parser.add_argument("--backup", action="store_true", help="仅备份现有 index.db")
    args = parser.parse_args(argv)

    if args.backup:
        p = backup()
        print(f"[migrate] 已备份: {p}" if p else "[migrate] 无现有库，跳过备份")
        return 0

    if args.rollback:
        p = rollback()
        print(f"[migrate] 已回滚: {p}" if p else "[migrate] 无备份可回滚")
        return 0 if p else 1

    if args.check:
        result = check()
        print("[migrate] 对账结果：")
        print(f"  assets  : 磁盘 {result['assets']['disk']} / 库 {result['assets']['db']}"
              f"  missing={result['assets']['missing']} extra={result['assets']['extra']}")
        print(f"  reports : 磁盘 {result['reports']['disk']} / 库 {result['reports']['db']}"
              f"  missing={result['reports']['missing']} extra={result['reports']['extra']}")
        print(f"  一致    : {'YES' if result['ok'] else 'NO'}")
        return 0 if result["ok"] else 1

    result = run_migrate()
    _print_result(result)
    # 对账：库 vs 磁盘不一致时告警（非 0 退出码，PRD P0-8）。
    mismatch = (result["assets"] != result["assets_on_disk"]
                or result["reports"] != result["reports_on_disk"])
    if mismatch:
        print("[migrate] 警告: 库与磁盘数量不一致，请复核", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
