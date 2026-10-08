"""内置资产增量同步（2026-09-29 起：manifest 驱动的版本感知同步）。

问题：随包发布的内置资产（``<ROOT>/assets/*.json``，如新增题材包、桥段库更新）
不会自动进入已有用户的数据目录（``config.ASSETS_ROOT``）。此前靠手工复制，
这是交付缺口：用户升级后新内置资产不可见（如 2026-09-29 的 7 个新资产卡
与桥段库 8→32 条更新）。

版本感知（2026-09-29 补齐）：
随包附带 ``<ROOT>/assets-manifest.json``（``python -m gui.builtin_sync
--write-manifest`` 生成），记录每个内置资产的 ``version``、当前 ``sha256``
与历史上所有官方旧版 ``previous_hashes``。``diff()`` 据此把「两边都有但内容
不同」的文件安全区分为两类：

- ``upgradable``：用户目录文件的 hash 命中某官方旧版 → 官方出过新版，
  可提示用户手动更新（仍不自动覆盖，由人工裁决）。
- ``modified``：hash 与官方任何版本都不匹配 → 疑似用户手工改过，
  永不触碰。

安全策略（只增不改，永不覆盖）：
- 随包有、用户目录无 → 复制（新内置资产，用户不可能改过，安全），
  并立即单文件重索引进 SQLite（``migrate.sync_asset``），保证 UI 可见。
- 两边都有但内容不同 → 不覆盖，记入 ``modified``/``upgradable`` 供人工裁决。
- 用户目录独有 → 不动（用户自己的资产）。

调用点：
- ``GuiServer._start_inner`` 启动时自动跑一次（失败只记日志，不阻断服务）。
- ``python -m gui.migrate --sync-builtins`` 手动触发并打印报告。
- ``python -m gui.builtin_sync --write-manifest`` 生成/刷新随包 manifest。
- ``python -m gui.builtin_sync --diff`` 只读打印对账报告。

纯标准库（铁律三）。运行时路径一律函数内实时求值（§4 规矩）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from gui import __version__, config
from gui.logging_setup import get_logger

_log = get_logger(__name__)

#: 随包 manifest 文件名。刻意放在仓库根而非 ``assets/`` 内：
#: ``assets/*.json`` 会被 migrate/asset_index 按「宁多勿丢」兜底归类为资产卡，
#: manifest 一旦落进去会被误索引成一条假 trope 资产并污染资产计数。
MANIFEST_NAME = "assets-manifest.json"


def shipped_dir() -> Path | None:
    """随包内置资产目录（``<项目根>/assets``）；缺失返回 None（优雅 no-op）。"""
    d = config.ROOT_DIR / "assets"
    return d if d.is_dir() else None


def manifest_path() -> Path:
    """随包 manifest 路径（``<项目根>/assets-manifest.json``，函数内实时求值）。"""
    return config.ROOT_DIR / MANIFEST_NAME


def load_manifest() -> dict[str, Any] | None:
    """读取并校验随包 manifest；缺失或结构非法返回 None（降级为旧行为）。"""
    fp = manifest_path()
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    files = data.get("files")
    if not isinstance(files, dict):
        return None
    for _name, entry in files.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str):
            return None
        prev = entry.get("previous_hashes", [])
        if not isinstance(prev, list) or not all(isinstance(h, str) for h in prev):
            return None
    return data


def write_manifest() -> dict[str, Any]:
    """生成/刷新随包 manifest（发版前跑一次）。

    扫描 ``assets/*.json``：新文件直接登记；已登记文件的 hash 若变化，
    把旧 current 追加进 ``previous_hashes``（官方旧版 hash 就此累积，
    供 ``diff()`` 识别「官方旧版」）。幂等：无变化时重跑**不写文件**，
    直接返回现有 manifest（连 ``generated_at`` 都不变，避免假脏）。
    """
    src = shipped_dir()
    if src is None:
        return {"noop": True, "files": {}}
    old = load_manifest() or {}
    old_files: dict[str, Any] = old.get("files", {}) if isinstance(old.get("files"), dict) else {}
    files: dict[str, Any] = {}
    for p in sorted(src.glob("*.json")):
        if not p.is_file():
            continue
        new_hash = _sha256(p)
        entry = old_files.get(p.name)
        prev: list[str] = []
        if isinstance(entry, dict):
            raw_prev = entry.get("previous_hashes") or []
            prev = [h for h in raw_prev if isinstance(h, str)]
            old_current = entry.get("sha256")
            if (isinstance(old_current, str) and old_current != new_hash
                    and old_current not in prev):
                prev.append(old_current)
        files[p.name] = {"sha256": new_hash, "previous_hashes": prev}
    if old.get("version") == __version__ and old_files == files:
        _log.info("manifest 无变化，跳过写入")
        return {"version": __version__,
                "generated_at": old.get("generated_at", ""),
                "files": files}
    manifest = {
        "version": __version__,
        "generated_at": datetime.now().astimezone().isoformat(),
        "files": files,
    }
    manifest_path().write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _log.info("manifest 已写入 %s：%d 个内置资产，版本 %s",
              manifest_path(), len(files), __version__)
    return manifest


def _sha256(fp: Path) -> str:
    h = hashlib.sha256()
    with fp.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _shipped_files(src: Path) -> dict[str, Path]:
    return {p.name: p for p in sorted(src.glob("*.json")) if p.is_file()}


def diff() -> dict[str, Any]:
    """只读对账：随包目录 vs 用户数据目录。

    返回 ``{"missing": [...], "modified": [...], "upgradable": [...],
    "extra": [...], "shipped_total": n, "runtime_total": m,
    "manifest_version": v | None}``（文件名列表均已排序）。

    分类规则（两边都有但内容不同时）：
    - 有 manifest 且用户文件 hash ∈ 该文件的 ``previous_hashes``
      → ``upgradable``（官方旧版，可提示更新）；
    - 否则 → ``modified``（疑似用户修改，永不自动覆盖）。
    无 manifest 时退化为旧行为：内容不同一律 ``modified``。
    随包目录缺失时返回 ``{"noop": True, ...}``。
    """
    src = shipped_dir()
    if src is None:
        return {"noop": True, "missing": [], "modified": [], "upgradable": [],
                "extra": [], "shipped_total": 0, "runtime_total": 0,
                "manifest_version": None}
    dst = config.ASSETS_ROOT
    shipped = _shipped_files(src)
    runtime = {p.name: p for p in sorted(dst.glob("*.json"))} if dst.is_dir() else {}
    missing = sorted(set(shipped) - set(runtime))
    extra = sorted(set(runtime) - set(shipped))
    manifest = load_manifest()
    manifest_files = manifest["files"] if manifest else {}
    modified: list[str] = []
    upgradable: list[str] = []
    for name in sorted(set(shipped) & set(runtime)):
        if _sha256(shipped[name]) == _sha256(runtime[name]):
            continue
        entry = manifest_files.get(name)
        prev = entry.get("previous_hashes") if isinstance(entry, dict) else None
        if isinstance(prev, list) and _sha256(runtime[name]) in prev:
            upgradable.append(name)
        else:
            modified.append(name)
    return {"missing": missing, "modified": modified, "upgradable": upgradable,
            "extra": extra, "shipped_total": len(shipped),
            "runtime_total": len(runtime),
            "manifest_version": manifest.get("version") if manifest else None}


def _reindex_copied(dst: Path, copied: list[str]) -> list[str]:
    """把本次复制的文件逐个重索引进 SQLite（失败只记日志，永不抛异常）。

    背景：AssetIndex 以 SQLite 为权威；只拷文件不入库，新资产在 UI 里不可见。
    用 ``migrate.sync_asset`` 单文件幂等 upsert（与 run_migrate 同 asset_key 口径，
    见 tests/test_migrate.py::TestSyncAssetKeyConvention）。延迟 import 避免
    模块级循环依赖。
    """
    reindexed: list[str] = []
    try:
        from gui import migrate
    except Exception as exc:  # noqa: BLE001 — 索引失败不阻断同步。
        _log.warning("内置资产重索引跳过（migrate 不可用）: %s", exc)
        return reindexed
    for name in copied:
        try:
            migrate.sync_asset(dst / name)
            reindexed.append(name)
        except Exception as exc:  # noqa: BLE001 — 单文件失败不影响其余。
            _log.warning("内置资产重索引失败 %s: %s", name, exc)
    return reindexed


def sync() -> dict[str, Any]:
    """增量同步：只复制缺失的内置资产，永不覆盖；复制后刷新 SQLite 索引。

    返回同 ``diff()`` 结构，另加 ``"copied": [...]``（本次实际复制的文件名）
    与 ``"reindexed": [...]``（成功入库 SQLite 的文件名）。
    """
    report = diff()
    if report.get("noop"):
        _log.info("内置资产同步：随包 assets 目录缺失，跳过")
        return {**report, "copied": [], "reindexed": []}
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
    report["reindexed"] = _reindex_copied(dst, copied) if copied else []
    if copied:
        _log.info("内置资产同步：补齐 %d 个缺失文件：%s", len(copied), copied)
    if report["modified"]:
        _log.warning("内置资产同步：%d 个文件内容与随包版本不同，未覆盖：%s",
                     len(report["modified"]), report["modified"])
    if report["upgradable"]:
        _log.warning("内置资产同步：%d 个文件是官方旧版，可手动更新：%s",
                     len(report["upgradable"]), report["upgradable"])
    return report


def sync_at_startup() -> None:
    """供 ``GuiServer._start_inner`` 调用：失败只记日志，永不阻断启动。"""
    try:
        sync()
    except Exception as exc:  # noqa: BLE001 — 同步失败不阻断服务。
        _log.warning("内置资产同步异常（已跳过）: %s", exc)


def _print_report(result: dict[str, Any]) -> None:
    if result.get("noop"):
        print("[builtin_sync] 随包 assets 目录缺失，跳过")
        return
    print(f"[builtin_sync] manifest 版本: {result.get('manifest_version') or '无（降级比对）'}")
    print(f"[builtin_sync] 随包 {result['shipped_total']} / 用户目录 {result['runtime_total']}")
    print(f"[builtin_sync] 缺失待补: {result['missing'] or '无'}")
    print(f"[builtin_sync] 官方旧版（可手动更新）: {result['upgradable'] or '无'}")
    print(f"[builtin_sync] 疑似用户修改（永不覆盖）: {result['modified'] or '无'}")
    print(f"[builtin_sync] 用户自有: {result['extra'] or '无'}")
    if "copied" in result:
        print(f"[builtin_sync] 本次复制: {result['copied'] or '无'}")
    if "reindexed" in result:
        print(f"[builtin_sync] 本次入库 SQLite: {result['reindexed'] or '无'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="内置资产增量同步（manifest 版本感知）")
    parser.add_argument("--write-manifest", action="store_true",
                        help="生成/刷新随包 assets-manifest.json（发版前跑）")
    parser.add_argument("--diff", action="store_true",
                        help="只读对账并打印报告，不写文件")
    args = parser.parse_args(argv)
    if args.write_manifest:
        manifest = write_manifest()
        if manifest.get("noop"):
            print("[builtin_sync] 随包 assets 目录缺失，未生成 manifest")
            return 1
        print(f"[builtin_sync] manifest 已写入 {manifest_path()}："
              f"{len(manifest['files'])} 个文件，版本 {manifest['version']}")
        return 0
    if args.diff:
        _print_report(diff())
        return 0
    _print_report(sync())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
