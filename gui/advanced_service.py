"""M1 高级分析 + M4 资产写入服务层。

M1：蒸馏 / 题材聚合 / 批量拆书状态
M4：资产编辑 / 新建 / 删除
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from gui import config, engine_adapter, migrate
from gui.services import ServiceError


# ---------------------------------------------------------------------------
# M1: 蒸馏
# ---------------------------------------------------------------------------

def distill_genre(genre: str, book_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """触发题材蒸馏：跨书聚合资产 → distilled JSON。"""
    if not genre or not genre.strip():
        raise ServiceError("genre 不能为空", 400)
    genre = genre.strip()

    # 收集该题材的书
    assets_root = config.ASSETS_ROOT
    books = []
    for fp in sorted(assets_root.glob("*-voice-card.json")):
        if "distilled" in fp.stem:
            continue
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            if data.get("meta", {}).get("genre") == genre:
                books.append(fp.stem.replace("-voice-card", ""))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[warn] 跳过无法解析的 voice-card {fp.name}: {exc}")
            continue

    if book_names:
        books = [b for b in books if b in book_names]

    if len(books) < 2:
        raise ServiceError(f"题材 {genre} 仅有 {len(books)} 本书，蒸馏需要 ≥2 本", 400)

    # HIGH：genre 用于拼路径，必须白名单校验
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9_-]+", genre):
        raise ServiceError(f"非法 genre 名: {genre!r}", 400)

    # 调用 distill（CRITICAL：必须调 run_distill 而非 distill_genre，后者不写盘）
    import sys
    if str(config.SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(config.SCRIPTS_DIR))
    import distill as distill_mod

    result = distill_mod.run_distill(genre, book_names=books)
    written = result.get("written", [])

    # 重索引
    for fp_str in written:
        fp = Path(fp_str)
        if fp.is_file():
            migrate.sync_asset(fp)

    return {
        "genre": genre,
        "books": books,
        "written": [Path(w).name for w in written],
        "dimensions": list(result.get("dimensions", {}).keys()),
    }


def distill_status(genre: str) -> Dict[str, Any]:
    """查看题材蒸馏状态：已有 distilled 资产 + 可蒸馏的书。"""
    if not genre or not genre.strip():
        raise ServiceError("genre 不能为空", 400)
    genre = genre.strip()

    # 已有 distilled 资产
    distilled = []
    for fp in sorted(config.ASSETS_ROOT.glob(f"{genre}-*-distilled.json")):
        distilled.append(fp.stem)

    # 可蒸馏的书
    books = []
    for fp in sorted(config.ASSETS_ROOT.glob("*-voice-card.json")):
        if "distilled" in fp.stem:
            continue
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            if data.get("meta", {}).get("genre") == genre:
                books.append(fp.stem.replace("-voice-card", ""))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[warn] 跳过无法解析的 voice-card {fp.name}: {exc}")
            continue

    return {
        "genre": genre,
        "books": books,
        "book_count": len(books),
        "distilled_assets": distilled,
        "can_distill": len(books) >= 2,
    }


# ---------------------------------------------------------------------------
# M1: 题材聚合
# ---------------------------------------------------------------------------

def aggregate_genre(genre: str) -> Dict[str, Any]:
    """聚合题材包：≥3 本同题材 → genre-pack。"""
    if not genre or not genre.strip():
        raise ServiceError("genre 不能为空", 400)
    genre = genre.strip()

    import sys
    if str(config.SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(config.SCRIPTS_DIR))
    import pass5_aggregate as agg_mod

    # 检查书数
    books = []
    for fp in sorted(config.ASSETS_ROOT.glob("*-voice-card.json")):
        if "distilled" in fp.stem:
            continue
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            if data.get("meta", {}).get("genre") == genre:
                books.append(fp.stem.replace("-voice-card", ""))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[warn] 跳过无法解析的 voice-card {fp.name}: {exc}")
            continue

    if len(books) < 3:
        raise ServiceError(f"题材 {genre} 仅有 {len(books)} 本书，聚合需要 ≥3 本", 400)

    # HIGH：genre 白名单校验
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9_-]+", genre):
        raise ServiceError(f"非法 genre 名: {genre!r}", 400)

    # 聚合需调用 pass5_aggregate 的 CLI 入口（GUI 内直接调用尚未封装）
    out_path = config.ASSETS_ROOT / f"{genre}-genre-pack.json"

    # 简化：标记为需要 CLI 执行
    return {
        "genre": genre,
        "books": books,
        "book_count": len(books),
        "note": f"请在 CLI 执行：python novel.py 聚合 --genre {genre}",
        "target_path": str(out_path),
    }


# ---------------------------------------------------------------------------
# M1: 批量拆书状态
# ---------------------------------------------------------------------------

def batch_status() -> Dict[str, Any]:
    """批量拆书状态：corpus/raw/ 下各书的 pass 完成情况。"""
    raw_root = config.CORPUS_DIR / "raw"
    books = []
    if raw_root.is_dir():
        for child in sorted(raw_root.iterdir()):
            if not child.is_dir():
                continue
            passes = {}
            for p in ["pass1_structure", "pass2_character", "pass3_style", "pass4_commercial", "pass5_craft"]:
                fp = child / f"{p}.json"
                passes[p] = fp.is_file()
            has_assets = any(config.ASSETS_ROOT.glob(f"{child.name}-*.json"))
            books.append({
                "name": child.name,
                "passes": passes,
                "pass_count": sum(1 for v in passes.values() if v),
                "has_assets": has_assets,
            })
    return {"books": books, "total": len(books)}


# ---------------------------------------------------------------------------
# M4: 资产写入
# ---------------------------------------------------------------------------

def update_asset(kind: str, asset_id: str, content: Dict[str, Any]) -> Dict[str, Any]:
    """更新资产 JSON 内容。"""
    if not content or not isinstance(content, dict):
        raise ServiceError("content 必须为 JSON 对象", 400)

    name = asset_id.split(":")[-1] if ":" in asset_id else asset_id
    if not name or any(ch in name for ch in ("/", "\\", "..", "\x00")):
        raise ServiceError(f"非法资产 ID: {asset_id}", 400)

    fp = (config.ASSETS_ROOT / f"{name}.json").resolve()
    if not fp.is_relative_to(config.ASSETS_ROOT.resolve()):
        raise ServiceError(f"非法资产 ID: {asset_id}", 400)
    if not fp.is_file():
        raise ServiceError(f"资产不存在: {asset_id}", 404)

    # 写入
    fp.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")

    # 重索引
    migrate.sync_asset(fp)

    return {"name": name, "path": str(fp.relative_to(config.ROOT_DIR)), "updated": True}


def delete_asset(kind: str, asset_id: str) -> Dict[str, Any]:
    """删除资产（移到回收站而非硬删除）。"""
    name = asset_id.split(":")[-1] if ":" in asset_id else asset_id
    if not name or any(ch in name for ch in ("/", "\\", "..", "\x00")):
        raise ServiceError(f"非法资产 ID: {asset_id}", 400)

    fp = (config.ASSETS_ROOT / f"{name}.json").resolve()
    if not fp.is_relative_to(config.ASSETS_ROOT.resolve()):
        raise ServiceError(f"非法资产 ID: {asset_id}", 400)
    if not fp.is_file():
        raise ServiceError(f"资产不存在: {asset_id}", 404)

    # 移到 trash 目录（软删除）
    trash_dir = config.STATE_ROOT / "trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    import uuid
    ts = time.strftime("%Y%m%d-%H%M%S")
    dst = trash_dir / f"{name}-{ts}-{uuid.uuid4().hex[:6]}.json"
    shutil.move(str(fp), str(dst))

    return {"name": name, "trashed_to": str(dst.relative_to(config.ROOT_DIR)), "deleted": True}


def create_asset(name: str, kind: str, content: Dict[str, Any]) -> Dict[str, Any]:
    """新建资产。"""
    if not name or any(ch in name for ch in ("/", "\\", "..", "\x00")):
        raise ServiceError(f"非法资产名: {name}", 400)
    if not content or not isinstance(content, dict):
        raise ServiceError("content 必须为 JSON 对象", 400)

    fp = config.ASSETS_ROOT / f"{name}.json"
    if fp.exists():
        raise ServiceError(f"资产已存在: {name}", 409)

    fp.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    migrate.sync_asset(fp)

    return {"name": name, "path": str(fp.relative_to(config.ROOT_DIR)), "created": True}
