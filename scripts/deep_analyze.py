#!/usr/bin/env python3
"""技法深度分析质量校验 + 组装器（纯标准库）。

不生成深度内容——深度内容由 Pass5 LLM 生成。
本模块只做：结构补齐、非空校验、10 段齐全性断言、缺段标记、写回 craft-card。
"""
import argparse
import json
from pathlib import Path

# 技法深度字段（字段名 → 是否必填）。
# 前 4 段来自现有 craft-card（description/effect/skeleton/anti_pattern），
# 后 7 段来自 deep_analysis 扩展。
TECHNIQUE_DEEP_FIELDS = [
    "reader_psychology",   # 读者心理机制
    "execution_steps",     # 执行步骤（1.2.3. 分步）
    "applicable_scene",    # 适用场景（题材/节奏/位置）
    "usage_boundary",      # 使用边界（何时不该用/副作用）
    "intensity_control",   # 强度控制（强/弱两档）
    "combo_patterns",      # 组合套路（与其他技法的搭配）
    "migration_checklist", # 迁移清单（换成自己的书怎么套用）
]  # 共 7 个新增字段

DEEP_FIELD_LABELS = {
    "reader_psychology": "读者心理机制",
    "execution_steps": "执行步骤",
    "applicable_scene": "适用场景",
    "usage_boundary": "使用边界",
    "intensity_control": "强度控制",
    "combo_patterns": "组合套路",
    "migration_checklist": "迁移清单",
}


def check_technique_depth(tech: dict) -> tuple:
    """校验单条技法的深度字段齐全性。

    Args:
        tech: 单条技法 dict（含可选的 ``deep_analysis`` 子对象）。

    Returns:
        (complete: bool, missing_fields: list[str])。complete 为 True 表示 7 个
        深度字段全部非空；missing_fields 列出缺失/空白的字段名。
    """
    missing = []
    da = tech.get("deep_analysis") or {}
    if not isinstance(da, dict):
        # deep_analysis 非 dict（如字符串），视为全部缺失
        missing = list(TECHNIQUE_DEEP_FIELDS)
        return (False, missing)
    for f in TECHNIQUE_DEEP_FIELDS:
        v = da.get(f)
        if not v or not str(v).strip():
            missing.append(f)
    return (len(missing) == 0, missing)


def ensure_technique_depth(tech: dict) -> dict:
    """为单条技法补齐 deep_analysis 结构（不填充内容，只保证键存在）。

    对已有 deep_analysis 就地补默认空串；对没有该键的技法创建空 dict。

    Args:
        tech: 单条技法 dict。

    Returns:
        返回原 tech（就地修改，便于链式使用）。
    """
    da = tech.setdefault("deep_analysis", {})
    if not isinstance(da, dict):
        # 若 deep_analysis 被污染为非 dict，重建为空 dict
        da = {}
        tech["deep_analysis"] = da
    for f in TECHNIQUE_DEEP_FIELDS:
        da.setdefault(f, "")
    return tech


def analyze_craft_card(craft: dict) -> dict:
    """对整张 craft-card 做深度校验，返回统计 + 就地补齐。

    遍历 ``craft.craft_analysis`` 各维度的 techniques，对每条技法：
        1. ensure_technique_depth 补齐 deep_analysis 的 7 键结构；
        2. check_technique_depth 检测非空齐全性；
        3. 缺段的技法计入 incomplete，并把缺失字段记录到 missing_map。

    Args:
        craft: craft-card dict。

    Returns:
        {"total": int, "complete": int, "incomplete": int,
         "missing_map": {technique_name: [missing_field, ...]}}
    """
    stats = {"total": 0, "complete": 0, "incomplete": 0, "missing_map": {}}
    analysis = craft.get("craft_analysis")
    if not isinstance(analysis, dict):
        return stats
    for dim_key, dim_val in analysis.items():
        if not isinstance(dim_val, dict):
            continue
        techniques = dim_val.get("techniques", [])
        if not isinstance(techniques, list):
            continue
        for tech in techniques:
            if not isinstance(tech, dict):
                continue
            ensure_technique_depth(tech)
            stats["total"] += 1
            complete, missing = check_technique_depth(tech)
            if complete:
                stats["complete"] += 1
            else:
                stats["incomplete"] += 1
                name = tech.get("name") or "<unnamed>"
                stats["missing_map"][name] = missing
    return stats


def main():
    """CLI 入口：python deep_analyze.py <craft-card.json> [--in-place]

    默认只打印统计，不写回；``--in-place`` 时把补齐后的 craft-card 写回原文件。
    """
    ap = argparse.ArgumentParser(description="技法深度分析质量校验 + 组装器")
    ap.add_argument("craft_card", help="craft-card JSON 文件路径")
    ap.add_argument("--in-place", action="store_true", help="就地补齐并写回原文件")
    args = ap.parse_args()

    path = Path(args.craft_card)
    if not path.exists():
        print(f"✗ 文件不存在: {path}", file=__import__("sys").stderr)
        raise SystemExit(1)
    craft = json.loads(path.read_text(encoding="utf-8"))

    stats = analyze_craft_card(craft)
    print(f"技法总数: {stats['total']}")
    print(f"深度齐全: {stats['complete']}")
    print(f"深度缺段: {stats['incomplete']}")
    if stats["missing_map"]:
        print("缺段明细:")
        for name, missing in stats["missing_map"].items():
            labels = "、".join(DEEP_FIELD_LABELS.get(f, f) for f in missing)
            print(f"  - {name}: 缺 [{labels}]")

    if args.in_place:
        path.write_text(json.dumps(craft, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓ 已就地补齐并写回: {path}")


if __name__ == "__main__":
    main()
