"""全局资产索引服务：SQLite 查询为主 + 目录扫描为迁移/回退源。

设计要点（见 DESIGN_gui_persistence §1.2 / §4.2）：
- ``ASSET_KINDS`` 白名单常量在此文件顶部，作为**单一来源**，``migrate``/``services`` 引用。
- 查询方法（``list_assets``/``get_asset_detail``/``get_overview``/``count_by_kind``）优先走
  SQLite 聚合（``gui.db``），SQLite 为空（尚未迁移）时回退到目录扫描（阶段一行为），
  保证「迁移前旧测试/旧前端仍可用，迁移后以 SQLite 为权威」。
- 短 TTL 只读缓存仅提速，权威数据源始终是 SQLite；缓存可 ``invalidate()`` 重建。
- 返回前端的 ``path`` 一律 ``relative_to(ROOT_DIR)`` 相对化，不暴露绝对路径。
- ``kind`` 白名单校验防路径穿越。

kind 白名单（单一来源）：
    voice | structure | commercial | craft | genre_pack | prose_card | trope

除 7 类资产卡外，``list_assets``/``get_overview`` 为兼容阶段一前端，仍将
「报告（report）」与「书（book）」作为虚拟 kind 暴露（内部分别来自 reports/books 表）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from gui import config
from gui import db

# kind 白名单（资产卡，单一来源）。任何新 kind 需在此显式登记，防路径穿越与越权读取。
ASSET_KINDS = ("voice", "structure", "commercial", "craft", "genre_pack", "prose_card", "trope")

# 兼容阶段一的「虚拟 kind」：报告与书（内部映射到 reports/books 表，不落入 assets.kind）。
VIRTUAL_KINDS = ("report", "book")

# list_assets/get_asset_detail 可接受的全部 kind（资产卡 + 虚拟 kind）。
_ALL_KINDS = ASSET_KINDS + VIRTUAL_KINDS

# assets 目录文件名后缀 → kind 映射（顺序即匹配优先级，扫描回退源用）。
_SUFFIX_KIND = (
    ("-voice-card-distilled", "voice"),
    ("-voice-card", "voice"),
    ("-structure-obs-distilled", "structure"),
    ("-structure-obs", "structure"),
    ("-commercial-obs-distilled", "commercial"),
    ("-commercial-obs", "commercial"),
    ("-craft-card-distilled", "craft"),
    ("-craft-card", "craft"),
    ("-genre-pack", "genre_pack"),
    ("genre-prose-card-", "prose_card"),
)

# 报告文件名后缀 → 报告类型（用于拆书报告 / 笔法分析区分）。
_REPORT_SUFFIX = (
    ("-拆书报告.md", "book"),
    ("-笔法分析.md", "craft"),
)


def _default_ttl() -> int:
    """缓存 TTL（秒），默认 5 秒，可用环境变量覆盖（测试便利）。"""
    import os
    raw = os.environ.get("NOVEL_LAB_GUI_INDEX_TTL", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return 5


class AssetIndex:
    """资产索引：SQLite 查询为主 + 目录扫描回退 + 短 TTL 只读缓存。

    SQLite 为权威（``gui.db``），``scan()`` 目录扫描仅作为「尚未迁移/测试隔离」时的
    回退源与 ``migrate`` 的同步参照。查询方法优先 SQL，SQL 为空则回退 scan。
    """

    def __init__(self, ttl_seconds: Optional[int] = None) -> None:
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else _default_ttl()
        self._cache: Dict[str, Any] = {}
        self._cache_ts: float = 0.0

    # ------------------------------------------------------------------
    # SQLite 就绪判断
    # ------------------------------------------------------------------

    def _db_ready(self) -> bool:
        """判断 SQLite 是否已有索引数据（assets/books/reports 任一非空）。"""
        try:
            conn = db.get_conn()
            n = conn.execute(
                "SELECT (SELECT COUNT(*) FROM assets) + "
                "(SELECT COUNT(*) FROM books) + "
                "(SELECT COUNT(*) FROM reports) AS n"
            ).fetchone()
            return bool(n and n["n"] and int(n["n"]) > 0)
        except Exception:  # noqa: BLE001 — 库未初始化/损坏时回退扫描。
            return False

    # ------------------------------------------------------------------
    # 目录扫描（回退源，阶段一行为）
    # ------------------------------------------------------------------

    def scan(self, force: bool = False) -> Dict[str, Any]:
        """全量目录扫描，返回结构化索引 dict（含 items / counts）。

        保留作为 SQLite 为空时的回退源；生产迁移后一般不再调用。
        """
        now = time.time()
        if not force and self._cache and (now - self._cache_ts) < self.ttl_seconds:
            return self._cache

        items: List[Dict[str, Any]] = []
        items.extend(self._scan_assets())
        items.extend(self._scan_reports())
        items.extend(self._scan_corpus())

        counts: Dict[str, int] = {}
        for it in items:
            counts[it["kind"]] = counts.get(it["kind"], 0) + 1

        result = {
            "items": items,
            "counts": counts,
            "model_configured": self._model_configured(),
        }
        self._cache = result
        self._cache_ts = now
        return result

    def invalidate(self) -> None:
        """写操作后主动失效缓存。"""
        self._cache = {}
        self._cache_ts = 0.0

    def _scan_assets(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        root = config.ASSETS_ROOT
        if not root.is_dir():
            return out
        for fp in sorted(root.glob("*.json")):
            kind = self._classify_asset_name(fp.name)
            if kind is None:
                continue
            out.append(self._make_item(kind, fp, root))
        return out

    def _scan_reports(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        root = config.REPORTS_DIR
        if not root.is_dir():
            return out
        for fp in sorted(root.glob("*.md")):
            item = self._make_item("report", fp, root)
            item["report_kind"] = "book"
            item["book_id"] = fp.stem
            for suffix, rk in _REPORT_SUFFIX:
                if fp.name.endswith(suffix):
                    item["report_kind"] = rk
                    item["book_id"] = fp.name[: -len(suffix)]
                    break
            out.append(item)
        return out

    def _scan_corpus(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        root = config.CORPUS_DIR
        if not root.is_dir():
            return out
        for fp in sorted(root.glob("*.txt")):
            if fp.is_file():
                out.append(self._make_item("book", fp, root))
        return out

    def _model_configured(self) -> bool:
        fp = config.CONFIG_DIR / "models.json"
        if not fp.is_file():
            return False
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        models = data.get("models", {})
        return isinstance(models, dict) and len(models) > 0

    @staticmethod
    def _classify_asset_name(name: str) -> Optional[str]:
        """按文件名后缀归类 asset 文件（扫描回退源）；无法归类返回 None。"""
        for suffix, kind in _SUFFIX_KIND:
            if suffix in name:
                return kind
        return None

    def _make_item(self, kind: str, fp: Path, root: Path) -> Dict[str, Any]:
        try:
            rel = str(fp.relative_to(config.ROOT_DIR))
        except ValueError:
            rel = f"{root.name}/{fp.name}"
        st = fp.stat()
        return {
            "kind": kind,
            "id": self._item_id(kind, fp),
            "name": fp.stem,
            "path": rel,
            "size": st.st_size,
            "mtime": st.st_mtime,
            "book_id": self._book_id_from_name(kind, fp.stem),
        }

    @staticmethod
    def _item_id(kind: str, fp: Path) -> str:
        return f"{kind}:{fp.stem}"

    @staticmethod
    def _book_id_from_name(kind: str, stem: str) -> Optional[str]:
        if kind == "report":
            return stem
        for suffix in ("-voice-card", "-structure-obs", "-commercial-obs", "-craft-card", "-genre-pack"):
            if suffix in stem:
                return stem.split(suffix)[0]
        if "genre-prose-card-" in stem:
            return None
        return None

    # ------------------------------------------------------------------
    # 查询（SQLite 为主 + 扫描回退）
    # ------------------------------------------------------------------

    def list_assets(self, kind: Optional[str] = None, genre: Optional[str] = None,
                    book_id: Optional[str] = None, offset: int = 0, limit: int = 50) -> Dict[str, Any]:
        """资产清单分页。kind/genre/book_id 可选，缺省返回全部。

        兼容旧签名 ``list_assets(kind, offset, limit)``（阶段一测试/调用方）：当第 2、3
        个位置参数均为 int（而非 genre/book_id 字符串）时，视为旧式调用并平移
        ``offset``/``limit``。

        Returns:
            {"total": int, "items": [AssetItem, ...]}
        """
        # 旧签名兼容：list_assets(kind, offset, limit) —— genre/book_id 位置被 int 占据。
        if isinstance(genre, int) and isinstance(book_id, int):
            offset, limit = genre, book_id
            genre, book_id = None, None

        if kind is not None and kind not in _ALL_KINDS:
            raise ValueError(f"未知资产类型: {kind}")
        offset = max(0, int(offset))
        limit = max(1, min(int(limit), 500))

        if self._db_ready():
            return self._list_from_db(kind, genre, book_id, offset, limit)
        return self._list_from_scan(kind, genre, book_id, offset, limit)

    def _list_from_db(self, kind: Optional[str], genre: Optional[str],
                      book_id: Optional[str], offset: int, limit: int) -> Dict[str, Any]:
        """SQLite 查询：资产卡走 assets 表，report/book 走对应表，None 合并三类。"""
        if kind is None:
            kinds = list(ASSET_KINDS) + ["report", "book"]
        else:
            kinds = [kind]

        all_items: List[Dict[str, Any]] = []
        for k in kinds:
            all_items.extend(self._query_kind(k, genre, book_id))
        # 稳定排序（name）。
        all_items.sort(key=lambda it: it.get("name", ""))
        total = len(all_items)
        return {"total": total, "items": all_items[offset:offset + limit]}

    def _query_kind(self, kind: str, genre: Optional[str], book_id: Optional[str]) -> List[Dict[str, Any]]:
        """按单个 kind 查询（assets 卡 / report / book）。"""
        if kind == "report":
            rows = db.list_reports(book_id)
            return [self._report_row_to_item(r) for r in rows]
        if kind == "book":
            rows = db.get_books(book_id=book_id, genre=genre)
            return [self._book_row_to_item(r) for r in rows]
        # 资产卡。
        rows = db.list_asset_rows(kind=kind, genre=genre, book_id=book_id, offset=0, limit=100000)
        return [self._asset_row_to_item(r) for r in rows]

    @staticmethod
    def _asset_row_to_item(row: Dict[str, Any]) -> Dict[str, Any]:
        name = row.get("name") or ""
        stem = Path(row.get("path", "")).stem if row.get("path") else name
        return {
            "kind": row.get("kind"),
            "id": f"{row.get('kind')}:{stem}",
            "name": name,
            "path": row.get("path"),
            "size": row.get("size"),
            "mtime": row.get("mtime"),
            "book_id": row.get("book_id"),
            "genre": row.get("genre"),
        }

    @staticmethod
    def _report_row_to_item(row: Dict[str, Any]) -> Dict[str, Any]:
        path = row.get("path", "")
        stem = Path(path).stem if path else row.get("title", "")
        return {
            "kind": "report",
            "id": f"report:{stem}",
            "name": stem,
            "path": path,
            "size": None,
            "mtime": None,
            "book_id": row.get("book_id"),
            "report_kind": row.get("type", "book"),
        }

    @staticmethod
    def _book_row_to_item(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "kind": "book",
            "id": f"book:{row.get('book_id')}",
            "name": row.get("book_id"),
            "path": row.get("source_path"),
            "size": None,
            "mtime": None,
            "book_id": row.get("book_id"),
        }

    def _list_from_scan(self, kind: Optional[str], genre: Optional[str],
                        book_id: Optional[str], offset: int, limit: int) -> Dict[str, Any]:
        """扫描回退：阶段一行为（无 genre/book_id 过滤，报告/书也纳入）。"""
        data = self.scan()
        items = data["items"]
        if kind is not None:
            items = [it for it in items if it["kind"] == kind]
        total = len(items)
        return {"total": total, "items": items[offset:offset + limit]}

    def count_by_kind(self) -> Dict[str, int]:
        """按 kind 计数（SQLite GROUP BY，空则回退扫描计数）。"""
        if self._db_ready():
            counts = db.count_by_kind()
            # 合并 report/book 计数（兼容阶段一 overview）。
            counts["report"] = len(db.list_reports())
            counts["book"] = len(db.get_books())
            return counts
        return dict(self.scan()["counts"])

    def get_asset_detail(self, kind: str, asset_id: str) -> Dict[str, Any]:
        """资产详情：按 kind + id 定位并读取 JSON/文本内容。

        安全：kind 白名单 + id 校验（防路径穿越）。报告返回 markdown 原文。
        """
        if kind not in _ALL_KINDS:
            raise ValueError(f"未知资产类型: {kind}")
        name = self._resolve_name(kind, asset_id)
        if name is None:
            raise KeyError(f"资产不存在: {kind}:{asset_id}")

        # 优先 SQLite 定位 path（book_id 校验 + 相对 path 读取原文件）。
        if self._db_ready():
            detail = self._detail_from_db(kind, name, asset_id)
            if detail is not None:
                return detail

        # 回退：直接按目录读取（阶段一行为）。
        return self._detail_from_scan(kind, name, asset_id)

    def _detail_from_db(self, kind: str, name: str, asset_id: str) -> Optional[Dict[str, Any]]:
        if kind == "report":
            rows = db.list_reports()
            for r in rows:
                if Path(r.get("path", "")).stem == name:
                    fp = config.ROOT_DIR / r["path"]
                    if fp.is_file():
                        return {"kind": "report", "id": asset_id, "name": name,
                                "markdown": fp.read_text(encoding="utf-8")}
            return None
        if kind == "book":
            return None  # 书正文按需读 corpus，走 scan 回退。
        # 资产卡：按 asset_key = kind:name 定位 path。
        row = db.get_asset_by_key(f"{kind}:{name}")
        if row is None:
            return None
        fp = config.ROOT_DIR / row["path"]
        if not fp.is_file():
            return None
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        return {"kind": kind, "id": asset_id, "name": name, "content": data}

    def _detail_from_scan(self, kind: str, name: str, asset_id: str) -> Dict[str, Any]:
        if kind == "report":
            fp = config.REPORTS_DIR / f"{name}.md"
            if not fp.is_file():
                raise KeyError(f"报告不存在: {name}")
            return {"kind": "report", "id": asset_id, "name": name,
                    "markdown": fp.read_text(encoding="utf-8")}
        if kind == "book":
            fp = config.CORPUS_DIR / f"{name}.txt"
            if not fp.is_file():
                raise KeyError(f"语料不存在: {name}")
            return {"kind": "book", "id": asset_id, "name": name,
                    "size": fp.stat().st_size,
                    "preview": fp.read_text(encoding="utf-8")[:2000]}
        fp = config.ASSETS_ROOT / f"{name}.json"
        if not fp.is_file():
            raise KeyError(f"资产不存在: {name}")
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        return {"kind": kind, "id": asset_id, "name": name, "content": data}

    def get_overview(self) -> Dict[str, Any]:
        """首页概览聚合（SQL 聚合为主，空则回退扫描计数）。"""
        if self._db_ready():
            counts = db.count_by_kind()
            assets_by_kind = self.count_by_kind()
            return {
                "total_books": len(db.get_books()),
                "total_genre_packs": counts.get("genre_pack", 0),
                "total_reports": len(db.list_reports()),
                # M5：total_assets 必须等于 sum(assets_by_kind)，不能用另一套 counts。
                "total_assets": sum(assets_by_kind.values()),
                "assets_by_kind": assets_by_kind,
                "model_configured": self._model_configured(),
                "recent_activity": [],
            }
        data = self.scan()
        counts = data["counts"]
        return {
            "total_books": counts.get("book", 0),
            "total_genre_packs": counts.get("genre_pack", 0),
            "total_reports": counts.get("report", 0),
            "total_assets": sum(counts.values()),
            "assets_by_kind": counts,
            "model_configured": data["model_configured"],
            "recent_activity": [],
        }

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    def _resolve_name(self, kind: str, asset_id: str) -> Optional[str]:
        raw = str(asset_id)
        prefix = f"{kind}:"
        if not raw.startswith(prefix):
            return None
        name = raw[len(prefix):]
        if not name or any(ch in name for ch in ("/", "\\", "..")):
            return None
        if any(ch in name for ch in ("\x00", "\n", "\r")):
            return None
        return name


# 进程内单例（服务层与路由层共用）。
index = AssetIndex()
