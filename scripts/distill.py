"""蒸馏主控：编排蒸馏并落盘 distilled JSON。

调用流程：
    collect_assets → align → aggregate → resolve_conflict → score_confidence
    → detect_blindspots → 落盘 assets/<genre>-{dimension}-distilled.json。

用法：
    python scripts/distill.py --genre campus-redemption [--books chireng_chosen qingning_chosen sangshi_chosen]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 保证可被独立执行与从 novel.py 透传调用。
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from distill_core import DIMENSIONS, distill_genre  # noqa: E402
from validate import validate_asset_data  # noqa: E402

# HIGH：genre 用于拼接输出文件名，必须白名单校验防路径穿越。
_GENRE_RE = re.compile(r"[A-Za-z0-9_-]+")


def validate_distilled_payload(distilled: dict) -> tuple[list[str], list[str]]:
    """校验单份 distilled 资产，返回 ``(硬错误, 警告)`` 纯文本列表。

    Task 1 的 ``validate_asset_data("distilled", ...)`` 薄包装：
      * 硬错误按 ``meta.dimension`` 加 ``[dimension]`` 前缀，便于写盘门禁定位；
      * 警告原样保留，**不阻断**写盘（如 ``sources`` 为空的溯源提示）。
    """
    errors, warns = validate_asset_data("distilled", distilled)
    dimension = ""
    if isinstance(distilled, dict):
        meta = distilled.get("meta")
        if isinstance(meta, dict):
            dimension = str(meta.get("dimension") or "")
    label = dimension or "unknown"
    return [f"[{label}] {e}" for e in errors], list(warns)


def write_distilled_outputs(distilled_by_dim: dict, assets_dir: Path) -> list[str]:
    """全量校验四维 distilled 后落盘，返回写入的绝对路径列表。

    门禁语义（HIGH）：先对固定 :data:`DIMENSIONS` 逐维确认存在、``meta.dimension``
    与 key 一致，并执行 distilled 专用校验；任一硬错误立即抛 ``ValueError``，
    且**校验全部完成前不做任何 mkdir/写文件**——失败时不留半成品，也不产生
    空 assets 目录。警告不阻断写盘。通过后按既有命名
    ``f"{genre}-{dimension}-distilled.json"`` 写入（``ensure_ascii=False, indent=2``）。
    """
    assets_dir = Path(assets_dir)
    payloads = distilled_by_dim if isinstance(distilled_by_dim, dict) else {}
    errors: list[str] = []

    # 阶段一：全量校验（此阶段禁止任何文件系统写操作）。
    for dimension in DIMENSIONS:
        distilled = payloads.get(dimension)
        if not isinstance(distilled, dict):
            errors.append(
                f"[{dimension}] 缺少维度 payload（实际 {type(distilled).__name__}）"
            )
            continue
        meta = distilled.get("meta")
        meta_dimension = meta.get("dimension") if isinstance(meta, dict) else None
        if meta_dimension != dimension:
            errors.append(
                f"[{dimension}] meta.dimension={meta_dimension!r} 与输出维度不一致"
            )
        genre = meta.get("genre") if isinstance(meta, dict) else None
        if not isinstance(genre, str) or not _GENRE_RE.fullmatch(genre):
            errors.append(f"[{dimension}] 非法 meta.genre: {genre!r}")
        errors.extend(validate_distilled_payload(distilled)[0])

    if errors:
        raise ValueError(
            "distilled 写盘门禁失败（未写入任何文件）：\n" + "\n".join(errors)
        )

    # 阶段二：校验通过后创建目录并落盘。
    assets_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for dimension in DIMENSIONS:
        distilled = payloads[dimension]
        genre = distilled["meta"]["genre"]
        out_path = assets_dir / f"{genre}-{dimension}-distilled.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(distilled, fh, ensure_ascii=False, indent=2)
        written.append(str(out_path))
    return written


def run_distill(genre: str, book_names: list[str] | None = None) -> dict:
    """执行蒸馏，返回 ``{dimension: distilled_dict}`` 并落盘。"""
    distilled_by_dim = distill_genre(genre, book_names=book_names)

    # HIGH：genre 用于拼接输出路径，必须白名单校验防路径穿越
    if not _GENRE_RE.fullmatch(genre):
        raise ValueError(f"非法 genre 名（仅允许字母/数字/下划线/连字符）: {genre!r}")

    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    written = write_distilled_outputs(distilled_by_dim, assets_dir)

    return {
        "genre": genre,
        "written": written,
        "dimensions": distilled_by_dim,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(description="蒸馏层主控：跨书聚合四类资产并落盘")
    parser.add_argument("--genre", required=True, help="题材目录名，如 campus-redemption")
    parser.add_argument(
        "--books",
        nargs="*",
        default=None,
        help="可选，限定参与蒸馏的书籍（默认自动发现全部）",
    )
    args = parser.parse_args(argv)

    # ── 题材存在性校验（2026-10-12 审计修复 CLI-07）─────────────────────
    # 原实现只校验字符合法性（_GENRE_RE），**不校验题材是否真实存在**。
    # 实测：`novel 蒸馏 --genre definitely-not-a-genre` 会写出 4 个
    # **0 规则**的空壳资产（voice-card/craft-card/structure-obs/
    # commercial-obs 各一个）并 EXIT=0——既是"假成功"，又把垃圾文件灌进
    # assets/ 污染资产库与后续校验。
    #
    # 判据取自 genre_registry（磁盘派生，与铁律一"磁盘是唯一真相源"一致），
    # 不另造题材清单。校验**先于** run_distill，因为后者会落盘——
    # 与项目既有的"校验先于副作用"原则同口径。
    genre = args.genre
    if not _GENRE_RE.fullmatch(genre):
        print(f"✗ 非法 genre 名（仅允许字母/数字/下划线/连字符）: {genre!r}")
        return 1
    try:
        import genre_registry
        known = genre_registry.known_genres()
    except Exception as exc:  # noqa: BLE001 — 注册表不可用时不阻断，退化为警告
        print(f"⚠ 题材注册表不可用，跳过存在性校验: {exc}")
        known = None
    if known is not None and genre not in known:
        hint = "、".join(sorted(known)[:8])
        print(f"✗ 题材不存在: {genre!r}（无任何该题材的资产卡）")
        print(f"  已知题材示例: {hint}{'…' if len(known) > 8 else ''}")
        print("  请先用 `novel 拆书` 拆解该题材的书，或检查题材名是否写错。")
        return 1

    result = run_distill(genre, book_names=args.books)

    for path in result["written"]:
        print(f"已落盘: {path}")

    # 简要摘要。
    print("\n蒸馏摘要:")
    total_rules = 0
    for dimension in DIMENSIONS:
        stats = result["dimensions"][dimension]["stats"]
        meta = result["dimensions"][dimension]["meta"]
        total_rules += int(stats["total_rules"] or 0)
        print(
            f"  [{dimension}] 书数={meta['books_count']} "
            f"规则={stats['total_rules']} (硬{stats['hard_rules']}/"
            f"软{stats['soft_rules']}/个人{stats['personal_styles']}) "
            f"冲突={stats['conflicts']} 盲区={stats['blindspots']}"
        )

    # 题材合法但确实无资产时（如资产卡全被删），同样不该产出空壳当成功。
    if total_rules == 0:
        print("\n✗ 蒸馏结果为 0 条规则：该题材下没有可用于聚合的资产卡"
              "（产出空壳会污染资产库）。已落盘的文件请手动删除。")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
