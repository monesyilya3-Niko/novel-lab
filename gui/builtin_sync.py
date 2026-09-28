"""内置资产增量同步（2026-09-29，交接待办⑥）。

问题：随包发布的内置资产（``<ROOT>/assets/*.json``，如新增题材包、桥段库更新）
不会自动进入已有用户的数据目录（``config.ASSETS_ROOT``）。此前靠手工复制，
这是交付缺口：用户升级后新内置资产不可见（如 2026-09-29 的 7 个新资产卡
与桥段库 8→32 条更新）。

安全策略（只增不改，永不覆盖）：
- 随包有、用户目录无 → 复制（新内置资产，用户不可能改过，安全）。
- 两边都有但内容不同 → 不覆盖，记入 ``modified`` 供人工裁决（可能是用户
  手工调整过，也可能是新版内置资产；自动覆盖会丢数据）。
- 用户目录独有 → 不动（用户自己的资产）。

调用点：
- ``GuiServer._start_inner`` 启动时自动跑一次（失败只记日志，不阻断服务）。
- ``python -m gui.migrate --sync-builtins`` 手动触发并打印报告。

纯标准库（铁律三）。运行时路径一律函数内实时求值（§4 规矩）。
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from gui import config
from gui.logging_setup import get_logger

_log = get_logger(__name__)


def shipped_dir() -> Path | None:
    """随包内置资产目录（``<项目根>/assets``）；缺失返回 None（优雅 no-op）。"""
    d = config.ROOT_DIR / "assets"
    return d if d.is_dir() else None


def _sha256(fp: Path) -> str:
    h = hashlib.sha256()
    with fp.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def diff() -> dict[str, Any]:
    """只读对账：随包目录 vs 用户数据目录。

    返回 ``{"missing": [...], "modified": [...], "extra": [...],
    "shipped_total": n, "runtime_total": m}``（文件名列表均已排序）。
    随包目录缺失时返回 ``{"noop": True, ...}``。
    """
    src = shipped_dir()
    if src is None:
        return {"noop": True, "missing": [], "modified": [],
                "extra": [], "shipped_total": 0, "runtime_total": 0}
    dst = config.ASSETS_ROOT
    shipped = {p.name: p for p in sorted(src.glob("*.json")) if p.is_file()}
    runtime = {p.name: p for p in sorted(dst.glob("*.json"))} if dst.is_dir() else {}
    missing = sorted(set(shipped) - set(runtime))
    extra = sorted(set(runtime) - set(shipped))
    modified = sorted(
        name for name in set(shipped) & set(runtime)
        if _sha256(shipped[name]) != _sha256(runtime[name])
    )
    return {"missing": missing, "modified": modified, "extra": extra,
            "shipped_total": len(shipped), "runtime_total": len(runtime)}


def sync() -> dict[str, Any]:
    """增量同步：只复制缺失的内置资产，永不覆盖。

    返回同 ``diff()`` 结构，另加 ``"copied": [...]``（本次实际复制的文件名）。
    """
    report = diff()
    if report.get("noop"):
        _log.info("内置资产同步：随包 assets 目录缺失，跳过")
        return {**report, "copied": []}
    src = shipped_dir()
    assert src is not None
    dst = config.ASSETS_ROOT
    dst.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in report["missing"]:
        try:
            shutil.copy2(src / name, dst / name)
            copied.append(name)
        except OSError as exc:
            _log.warning("内置资产同步失败 %s: %s", name, exc)
    report["copied"] = copied
    if copied:
        _log.info("内置资产同步：补齐 %d 个缺失文件：%s", len(copied), copied)
    if report["modified"]:
        _log.warning("内置资产同步：%d 个文件内容与随包版本不同，未覆盖：%s",
                     len(report["modified"]), report["modified"])
    return report


def sync_at_startup() -> None:
    """供 ``GuiServer._start_inner`` 调用：失败只记日志，永不阻断启动。"""
    try:
        sync()
    except Exception as exc:  # noqa: BLE001 — 同步失败不阻断服务。
        _log.warning("内置资产同步异常（已跳过）: %s", exc)
