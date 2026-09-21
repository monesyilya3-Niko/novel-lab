#!/usr/bin/env python3
"""资产元数据回填：给已有资产补 `meta.source_fingerprint`。

背景
----
`source_fingerprint` 是 2026-09-21 新增的字段（组装时由 `assemble.py` 写入），
用于让 `asset_sync_check` 做**内容级**过期判定，替代原来的 mtime 启发式
（mtime 在"内容未变但文件被重写"时会误报）。

新增字段之前产出的资产没有它，只能退回 mtime。本脚本一次性补齐 ——
**只动 `meta.source_fingerprint` 一个字段**，不重新组装、不碰任何分析内容，
避免覆盖既有产出（尤其像 `Lord_of_the_Mysteries` 那样由会话手工撰写的资产）。

用法
----
  python backfill_meta.py --dry-run      # 预览将改动什么
  python backfill_meta.py                # 执行
  python backfill_meta.py 暮冬念春        # 只处理一本
  python novel.py 回填元数据 [书名]

退出码：0 成功（含"无需回填"）；1 有资产读取/写入失败。
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "corpus" / "raw"
ASSETS_DIR = ROOT / "assets"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assemble as asm  # noqa: E402


def backfill_one(name: str, dry_run: bool) -> tuple:
    """返回 (changes, errors, notes)。

    changes: [(资产文件名, 变更描述)]
    errors : [错误描述]
    notes  : [说明性提示，如「无来源 pass 文件，无法计算指纹」]
    """
    raw = RAW_DIR / name
    if not raw.is_dir():
        return [], [f"corpus/raw/{name}/ 不存在"], []

    changes, errors, notes = [], [], []
    no_source = []
    for kind in asm.SOURCE_PASSES:
        asset = ASSETS_DIR / f"{name}-{kind}.json"
        if not asset.exists():
            continue
        fp = asm.source_fingerprint(raw, kind)
        if not fp:
            no_source.append(asset.name)
            continue
        try:
            d = json.loads(asset.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{asset.name} 读取失败：{exc}")
            continue
        meta = d.get("meta")
        if not isinstance(meta, dict):
            errors.append(f"{asset.name} 的 meta 不是对象，跳过")
            continue
        if meta.get("source_fingerprint") == fp:
            continue                      # 已是最新，不动
        old = meta.get("source_fingerprint")
        changes.append((asset.name, "新增" if not old else f"{old} → {fp}"))
        if not dry_run:
            try:
                meta["source_fingerprint"] = fp
                asset.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
            except Exception as exc:
                errors.append(f"{asset.name} 写入失败：{exc}")

    if no_source:
        notes.append(
            f"{len(no_source)} 个资产无来源 pass 文件（该书的 corpus/raw/{name}/ 为空，"
            f"多为纯会话产出），无法计算指纹：{', '.join(no_source)}")
    return changes, errors, notes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="给已有资产补 meta.source_fingerprint（只动该字段）")
    ap.add_argument("book", nargs="?", help="书名；省略则处理全部已拆书")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写盘")
    args = ap.parse_args(argv)

    if args.book:
        books = [args.book]
    elif RAW_DIR.is_dir():
        books = sorted(d.name for d in RAW_DIR.iterdir() if d.is_dir())
    else:
        books = []
    if not books:
        print("corpus/raw/ 下没有已拆书，无需回填。")
        return 0

    print("=== 资产元数据回填（source_fingerprint）===")
    if args.dry_run:
        print("（dry-run：不会写盘）")
    print()

    total, all_errors = 0, []
    for name in books:
        changes, errors, notes = backfill_one(name, args.dry_run)
        all_errors += [f"{name}: {e}" for e in errors]
        if errors:
            print(f"[!] {name}")
            for e in errors:
                print(f"      · {e}")
        if changes:
            print(f"[{'预览' if args.dry_run else '已回填'}] {name}")
            for fname, desc in changes:
                print(f"      · {fname}: {desc}")
            total += len(changes)
        elif not errors:
            print(f"[跳过] {name}" + ("" if notes else "（已是最新）"))
        for n in notes:
            print(f"      ⚠ {n}")

    print()
    if total:
        print(f"{'将回填' if args.dry_run else '已回填'} {total} 个资产。"
              + ("去掉 --dry-run 执行。" if args.dry_run else ""))
    else:
        print("无需回填。")
    if all_errors:
        print(f"\n✗ {len(all_errors)} 个错误：")
        for e in all_errors:
            print(f"  · {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
