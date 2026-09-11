"""M5 系统与合规服务层：系统状态 / 版权合规 / 模型配置 / 设置。

分层边界：只经 ``engine_adapter`` 触碰 scripts/，只经 ``config`` 取路径。
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from gui import config, engine_adapter
from gui.services import ServiceError


# ---------------------------------------------------------------------------
# 系统状态
# ---------------------------------------------------------------------------

def system_status() -> Dict[str, Any]:
    """系统状态总览：磁盘、数据库、模型、任务。"""
    # 磁盘占用
    def _dir_size(p: Path) -> int:
        if not p.is_dir():
            return 0
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())

    assets_size = _dir_size(config.ASSETS_ROOT)
    reports_size = _dir_size(config.REPORTS_DIR)
    corpus_size = _dir_size(config.CORPUS_DIR)
    novel_size = _dir_size(config.NOVEL_DIR)
    db_size = config.DB_PATH.stat().st_size if config.DB_PATH.is_file() else 0

    # 资产/报告计数
    assets_count = len(list(config.ASSETS_ROOT.glob("*.json"))) if config.ASSETS_ROOT.is_dir() else 0
    reports_count = len(list(config.REPORTS_DIR.rglob("*.md"))) if config.REPORTS_DIR.is_dir() else 0

    # 模型状态
    model_configured = engine_adapter.any_model_configured()
    models = engine_adapter.list_models() if model_configured else []

    # 书目
    corpus_raw = config.CORPUS_DIR / "raw"
    books = [d.name for d in corpus_raw.iterdir() if d.is_dir()] if corpus_raw.is_dir() else []

    return {
        "disk": {
            "assets_bytes": assets_size,
            "reports_bytes": reports_size,
            "corpus_bytes": corpus_size,
            "novel_bytes": novel_size,
            "db_bytes": db_size,
            "total_bytes": assets_size + reports_size + corpus_size + novel_size + db_size,
        },
        "counts": {
            "assets": assets_count,
            "reports": reports_count,
            "books": len(books),
            "book_names": books,
        },
        "model": {
            "configured": model_configured,
            "models": [{"id": m.get("model_id", ""), "name": m.get("model_name", "")} for m in models] if models else [],
        },
        "paths": {
            "root": str(config.ROOT_DIR),
            "assets": str(config.ASSETS_ROOT),
            "reports": str(config.REPORTS_DIR),
            "corpus": str(config.CORPUS_DIR),
            "novel": str(config.NOVEL_DIR),
            "db": str(config.DB_PATH),
        },
        "python": os.sys.version,
    }


# ---------------------------------------------------------------------------
# 版权合规扫描
# ---------------------------------------------------------------------------

def compliance_scan(voice: Optional[str] = None,
                    book_path: Optional[str] = None) -> Dict[str, Any]:
    """版权合规扫描：对指定资产或全部资产做 12 字原文匹配检查。"""
    results = []

    if voice:
        # HIGH：路径穿越防护
        name = voice.split(":")[-1]
        if not name or any(ch in name for ch in ("/", "\\", "..", "\x00", "\n", "\r")):
            raise ServiceError(f"非法资产引用: {voice}", 400)
        fp = (config.ASSETS_ROOT / f"{name}.json").resolve()
        if not fp.is_relative_to(config.ASSETS_ROOT.resolve()):
            raise ServiceError(f"非法资产引用: {voice}", 400)
        if not fp.is_file():
            raise ServiceError(f"资产不存在: {voice}", 404)
        try:
            asset = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ServiceError(f"资产文件损坏: {exc}", 500)

        # HIGH：book_path 也必须在项目根内
        book_text = ""
        if book_path:
            bp = Path(book_path).resolve()
            if not bp.is_relative_to(config.ROOT_DIR.resolve()):
                raise ServiceError("book_path 必须在项目目录内", 400)
            if not bp.is_file():
                raise ServiceError(f"原文不存在: {book_path}", 404)
            try:
                book_text = bp.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError) as exc:
                raise ServiceError(f"读取原文失败: {exc}", 400)

        # 调用 compliance.scan_asset（需要 ngram 索引）
        from gui import engine_adapter as ea
        # 构建 ngram 索引（简化：直接用 compliance 模块）
        import sys
        if str(config.SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(config.SCRIPTS_DIR))
        import compliance as compliance_mod

        ngram = set()
        if book_text:
            WINDOW = 12
            compact = "".join(book_text.split())
            for i in range(len(compact) - WINDOW + 1):
                ngram.add(compact[i:i + WINDOW])

        errors, warns = compliance_mod.scan_asset(asset, ngram)
        results.append({
            "name": name,
            "errors": errors,
            "warns": warns,
            "verdict": "REJECT" if errors else ("WARN" if warns else "PASS"),
        })
    else:
        # 全量扫描（不带原文，只做字段级检查）
        import sys
        if str(config.SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(config.SCRIPTS_DIR))
        import compliance as compliance_mod

        for fp in sorted(config.ASSETS_ROOT.glob("*.json")):
            try:
                asset = json.loads(fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            errors, warns = compliance_mod.scan_asset(asset, set())
            results.append({
                "name": fp.stem,
                "errors": errors,
                "warns": warns,
                "verdict": "REJECT" if errors else ("WARN" if warns else "PASS"),
            })

    total = len(results)
    rejected = sum(1 for r in results if r["verdict"] == "REJECT")
    warned = sum(1 for r in results if r["verdict"] == "WARN")
    passed = sum(1 for r in results if r["verdict"] == "PASS")

    return {
        "results": results,
        "summary": {"total": total, "passed": passed, "warned": warned, "rejected": rejected},
    }


# ---------------------------------------------------------------------------
# 模型配置（只读展示，修改走 CLI model_config.py）
# ---------------------------------------------------------------------------

def model_info() -> Dict[str, Any]:
    """模型配置信息（脱敏展示）。"""
    configured = engine_adapter.any_model_configured()
    models = engine_adapter.list_models() if configured else []
    return {
        "configured": configured,
        "models": [
            {
                "id": m.get("model_id", ""),
                "name": m.get("model_name", ""),
                "protocol": m.get("protocol", ""),
                "roles": m.get("roles", []),
            }
            for m in models
        ],
        "note": "模型增删改请使用 CLI：python scripts/model_config.py",
    }


# ---------------------------------------------------------------------------
# 设置（只读展示当前配置）
# ---------------------------------------------------------------------------

def get_settings() -> Dict[str, Any]:
    """当前系统设置（只读）。"""
    return {
        "port": config.resolve_port(),
        "batch_size": config.batch_size_from_env(),
        "paths": {
            "root": str(config.ROOT_DIR),
            "assets": str(config.ASSETS_ROOT),
            "reports": str(config.REPORTS_DIR),
            "corpus": str(config.CORPUS_DIR),
            "novel": str(config.NOVEL_DIR),
            "prompts": str(config.PROMPTS_DIR),
            "db": str(config.DB_PATH),
        },
        "env_overrides": {
            "NOVEL_LAB_GUI_PORT": os.environ.get("NOVEL_LAB_GUI_PORT", ""),
            "NOVEL_LAB_GUI_BATCH_SIZE": os.environ.get("NOVEL_LAB_GUI_BATCH_SIZE", ""),
        },
    }
