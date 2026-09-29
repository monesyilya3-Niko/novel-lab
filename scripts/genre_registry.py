#!/usr/bin/env python3
"""题材注册表 —— 铁律一（题材隔离）的可校验封闭集。

2026-09-27 企业级整改 P0-2。

背景
----
铁律一对外宣称「题材隔离」，但 ``scripts/validate.py`` 里的 ``KNOWN_GENRES`` 是
**手写的 3 个题材**，而 ``assets/`` 下 genre-prose-card 实际覆盖 32 个题材，其
``meta.id`` slug **没有任何合法性校验**——slug 拼错、漏登记、越界写入都不会被
发现。三条题材隔离机制中只有第三条是硬阻断（见 baseline/A06 断言 4 复核）。

设计原则：不造第二个真相源
--------------------------
刻意**不引入** ``config/genres.json`` 这类人工清单：把 32 个 slug 抄进配置文件
等于再造一个会漂移的副本，正是本次整改要根除的病（12 维权重空转守卫的同源事故）。
题材集一律**从磁盘资产派生**，与 ``AGENTS.md`` §7「所有资产/报告数字以实测磁盘
为准」红线保持一致——磁盘是唯一真相源，本模块只是它的只读视图。

铁律三：纯标准库。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"

#: genre-prose-card 的 meta.id 必须满足的格式（硬校验用，不依赖磁盘）
PROSE_ID_RE = re.compile(r"^genre-[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

#: genre-prose-card 的 slug 前缀；去掉后即题材 slug
PROSE_SLUG_PREFIX = "genre-"

#: 无法扫描到资产时的兜底（如精简打包环境），与 validate.py 历史字面量一致
FALLBACK_CORE_GENRES = frozenset({"campus-redemption", "realistic-romance", "xuanhuan"})

#: 携带 meta.genre 的完整链资产类型（这类资产的 genre 越界属于真错误）
_CHAIN_KINDS = ("craft-card", "voice-card", "structure-obs", "commercial-obs", "genre-pack")


def _iter_asset_meta() -> list[tuple[str, dict]]:
    """扫描 assets/*.json，返回 (文件名, meta) 列表；解析失败的文件被跳过但不抛错。"""
    out: list[tuple[str, dict]] = []
    if not ASSETS_DIR.is_dir():
        return out
    for path in sorted(ASSETS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        meta = data.get("meta")
        if isinstance(meta, dict):
            out.append((path.name, meta))
    return out


def prose_genre_slugs(metas: list[tuple[str, dict]] | None = None) -> frozenset[str]:
    """全部 genre-prose-card 的 ``meta.id``（含 ``genre-`` 前缀）。"""
    metas = _iter_asset_meta() if metas is None else metas
    return frozenset(
        str(m["id"])
        for _, m in metas
        if m.get("kind") == "genre-prose-card" and isinstance(m.get("id"), str)
    )


def slug_to_genre(slug: str) -> str:
    """``genre-xuanhuan`` -> ``xuanhuan``；无前缀者原样返回。"""
    s = str(slug)
    return s[len(PROSE_SLUG_PREFIX):] if s.startswith(PROSE_SLUG_PREFIX) else s


def prose_genres(metas: list[tuple[str, dict]] | None = None) -> frozenset[str]:
    """genre-prose-card 覆盖的题材 slug（已去掉前缀）。"""
    return frozenset(slug_to_genre(s) for s in prose_genre_slugs(metas))


def core_genres(metas: list[tuple[str, dict]] | None = None) -> frozenset[str]:
    """拥有完整资产链（craft-card 等）的题材——即历史上手写的 KNOWN_GENRES。

    从磁盘派生而非硬编码：哪些题材有完整链会随业务变化，抄在代码里必然过期。
    扫描不到时（精简打包环境）退回兜底集合，避免下游校验整体失效。
    """
    metas = _iter_asset_meta() if metas is None else metas
    found = frozenset(
        str(m["genre"])
        for _, m in metas
        if m.get("kind") in _CHAIN_KINDS or (m.get("kind") is None and "genre" in m)
    )
    return found or FALLBACK_CORE_GENRES


def known_genres(metas: list[tuple[str, dict]] | None = None) -> frozenset[str]:
    """全部合法题材 = 完整链题材 ∪ prose-card 题材。"""
    return core_genres(metas) | prose_genres(metas)


def is_known_genre(genre: str, metas: list[tuple[str, dict]] | None = None) -> bool:
    return str(genre) in known_genres(metas)


def malformed_prose_ids(metas: list[tuple[str, dict]] | None = None) -> list[tuple[str, str]]:
    """返回 (文件名, 非法 meta.id) —— 供守卫测试与 CLI 使用。"""
    metas = _iter_asset_meta() if metas is None else metas
    bad = []
    for name, m in metas:
        if m.get("kind") != "genre-prose-card":
            continue
        mid = m.get("id")
        if not isinstance(mid, str) or not PROSE_ID_RE.match(mid):
            bad.append((name, str(mid)))
    return bad


def duplicate_prose_genres(metas: list[tuple[str, dict]] | None = None) -> dict[str, list[str]]:
    """同一题材存在多张 prose 卡的情况（题材隔离的前提是一题材一卡）。"""
    metas = _iter_asset_meta() if metas is None else metas
    seen: dict[str, list[str]] = {}
    for name, m in metas:
        if m.get("kind") != "genre-prose-card" or not isinstance(m.get("id"), str):
            continue
        seen.setdefault(slug_to_genre(m["id"]), []).append(name)
    return {g: names for g, names in seen.items() if len(names) > 1}


def registry_snapshot() -> dict:
    """一次性快照，供守卫测试、CLI 与报告取数使用。"""
    metas = _iter_asset_meta()
    prose = prose_genre_slugs(metas)
    return {
        "assets_dir_exists": ASSETS_DIR.is_dir(),
        "core_genres": sorted(core_genres(metas)),
        "prose_genres": sorted(slug_to_genre(s) for s in prose),
        "prose_card_count": len(prose),
        "known_genre_count": len(known_genres(metas)),
        "malformed_prose_ids": malformed_prose_ids(metas),
        "duplicate_prose_genres": duplicate_prose_genres(metas),
    }


def main() -> int:
    snap = registry_snapshot()
    print(f"题材注册表（派生自磁盘 {ASSETS_DIR}）")
    print(f"  完整链题材 {len(snap['core_genres'])}: {', '.join(snap['core_genres'])}")
    print(f"  prose-card 题材 {snap['prose_card_count']} / 合法题材合计 {snap['known_genre_count']}")
    if snap["malformed_prose_ids"]:
        print(f"  ✗ 非法 meta.id {len(snap['malformed_prose_ids'])} 个: {snap['malformed_prose_ids']}")
        return 1
    if snap["duplicate_prose_genres"]:
        print(f"  ✗ 题材重复的 prose 卡: {snap['duplicate_prose_genres']}")
        return 1
    print("  ✓ slug 格式与唯一性检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
