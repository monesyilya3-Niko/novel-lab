# -*- coding: utf-8 -*-
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
import sys
from pathlib import Path
from typing import List, Optional

# 保证可被独立执行与从 novel.py 透传调用。
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from distill_core import DIMENSIONS, distill_genre  # noqa: E402


def run_distill(genre: str, book_names: Optional[List[str]] = None) -> dict:
    """执行蒸馏，返回 ``{dimension: distilled_dict}`` 并落盘。"""
    distilled_by_dim = distill_genre(genre, book_names=book_names)

    # HIGH：genre 用于拼接输出路径，必须白名单校验防路径穿越
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9_-]+", genre):
        raise ValueError(f"非法 genre 名（仅允许字母/数字/下划线/连字符）: {genre!r}")

    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    written: List[str] = []
    for dimension in DIMENSIONS:
        distilled = distilled_by_dim[dimension]
        out_path = assets_dir / f"{genre}-{dimension}-distilled.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(distilled, fh, ensure_ascii=False, indent=2)
        written.append(str(out_path))

    return {
        "genre": genre,
        "written": written,
        "dimensions": distilled_by_dim,
    }


def main(argv: Optional[List[str]] = None) -> int:
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

    result = run_distill(args.genre, book_names=args.books)

    for path in result["written"]:
        print(f"已落盘: {path}")

    # 简要摘要。
    print("\n蒸馏摘要:")
    for dimension in DIMENSIONS:
        stats = result["dimensions"][dimension]["stats"]
        meta = result["dimensions"][dimension]["meta"]
        print(
            f"  [{dimension}] 书数={meta['books_count']} "
            f"规则={stats['total_rules']} (硬{stats['hard_rules']}/"
            f"软{stats['soft_rules']}/个人{stats['personal_styles']}) "
            f"冲突={stats['conflicts']} 盲区={stats['blindspots']}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
