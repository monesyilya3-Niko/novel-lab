#!/usr/bin/env python3
"""资产同步检查：`corpus/raw/<name>/` 的 pass 产出 与 `assets/` 的四卡是否对得上。

为什么需要它
------------
拆书是「pass 产出 JSON → 组装成资产」两段式。中间任何一步不同步，资产就会
**静默过期**：内容看着正常，实际已经落后于 pass 产出。此前没有任何检测手段，
只能靠人记得"改完 pass 要重新组装"。

检查四项
--------
1. **资产缺失**：pass 已产出但对应资产不存在（漏组装）。
2. **资产过期**：优先用**内容指纹**判定 —— 资产 `meta.source_fingerprint` 记着来源
   pass 的 sha256 前 16 位，与当前文件比对即可确定内容是否真的变了。老资产没有指纹时
   退回 **mtime 启发式**（内容未变但文件被重写会误报）。
3. **采样记录不一致**：`corpus/sampled/<name>/manifest.json` 的 `selected_indices`
   与资产 meta 里的 `sample_chapters` 不同（重新采样了但没重组装）。

   > 注：**不**用 `metrics.total_chars` 与资产 `meta.total_sample_words` 比对。
   > 该字段已于 2026-09-21 修正为「采样字数」（此前误填全书字数），但**老资产仍是旧值**
   > —— 例如 `Lord_of_the_Mysteries` 记的是采样字数、`暮冬念春` 的旧版记的是全书字数，
   > 语义仍不统一，故改用确定性的采样索引比对。

4. **报告铁律二不达标**（2026-09-23 新增）：`reports/` 里已有的报告，其
   「拆书报告 + 笔法分析」合计字符数必须 ≥ `MIN_REPORT_CHARS`(10000)。

   > 为什么必须回头复核：铁律二的合计校验只发生在**生成时**（CLI 的 `novel 分析`
   > 与 GUI 的 `_generate_reports`）。校验上线之前产出的、或写盘后校验失败的次品
   > 报告，会永久留在 `reports/` 里冒充合格品，此前**没有任何手段能发现**。
   > 实测：6 本书里 4 本合计仅 5612–7024 字，全部低于门槛。

用法
----
  python asset_sync_check.py                # 检查所有已拆书
  python asset_sync_check.py 暮冬念春        # 只检查一本
  python novel.py 同步检查 [书名]

退出码：全部同步 → 0；发现任何问题 → 1。
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "corpus" / "raw"
ASSETS_DIR = ROOT / "assets"
SAMPLED_DIR = ROOT / "corpus" / "sampled"
REPORTS_DIR = ROOT / "reports"

# 资产 kind → 其来源 pass 文件（voice-card 同时来自 pass2 与 pass3）
KIND_SOURCES = {
    "voice-card": ["pass2_character.json", "pass3_style.json"],
    "structure-obs": ["pass1_structure.json"],
    "commercial-obs": ["pass4_commercial.json"],
    "craft-card": ["pass5_craft.json"],
}


def list_books() -> list:
    if not RAW_DIR.is_dir():
        return []
    return sorted(d.name for d in RAW_DIR.iterdir() if d.is_dir())


def has_pipeline_outputs(raw: Path) -> bool:
    """该书是否有**流水线 pass 产出**。

    「资产过期」与「采样一致性」两项比对都以 pass 产出为前提——没有 pass 产出就
    无从谈起"资产是否落后于 pass"或"重新采样了但没重组装"。
    """
    return any((raw / p).exists() for passes in KIND_SOURCES.values() for p in passes)


def provenance_note(name: str) -> str:
    """返回该书产出方式的说明；流水线产出或无 raw 目录时返回空串。

    2026-09-23（总工排查）新增：``corpus/raw/Lord_of_the_Mysteries/`` 是**空目录**
    ——该书资产由**会话直接产出**（`novel.py 组装` 会明确报错「缺少
    pass1_structure.json（AI 会话内应先产出该 pass JSON）」），这是受支持的模式。
    但旧实现仍拿「后来的采样器 manifest」去比「会话当时选的章」，报出一条
    **无法成立**的漂移（27 章 vs 19 章）——两者是两次独立决策，本不可比。

    这类书必须**显式说明**而不是静默跳过（AGENTS.md 铁律一要求"禁止静默跳过"）。
    """
    raw = RAW_DIR / name
    if not raw.is_dir() or has_pipeline_outputs(raw):
        return ""
    return (f"非流水线产出（corpus/raw/{name}/ 下无 pass 文件，资产由会话直接产出）"
            f"→ 跳过「资产过期」与「采样一致性」比对（这两项以 pass 产出为前提）")


def check_one(name: str) -> list:
    """返回该书的同步问题清单（空列表 = 同步正常）。"""
    raw = RAW_DIR / name
    issues = []
    if not raw.is_dir():
        return [f"corpus/raw/{name}/ 不存在（该书未拆）"]

    # 1. 资产缺失
    for kind, passes in KIND_SOURCES.items():
        asset = ASSETS_DIR / f"{name}-{kind}.json"
        if any((raw / p).exists() for p in passes) and not asset.exists():
            issues.append(f"缺资产 {asset.name}（{passes[0]} 等已产出但未组装）")

    # 2. 资产过期
    #    2a. 首选**内容指纹**（确定性）：资产 meta.source_fingerprint 记着来源 pass 的
    #        sha256 前 16 位，与当前文件比对即可判定内容是否真的变了。
    #    2b. 老资产没有指纹时退回 **mtime 启发式** —— 内容未变但文件被重写会误报
    #        （实测撞到过一次），故提示里明确标注不确定性。
    for kind, passes in KIND_SOURCES.items():
        asset = ASSETS_DIR / f"{name}-{kind}.json"
        if not asset.exists():
            continue
        try:
            recorded = (json.loads(asset.read_text(encoding="utf-8"))
                        .get("meta") or {}).get("source_fingerprint") or {}
        except Exception:
            recorded = {}
        for pf in passes:
            src = raw / pf
            if not src.exists():
                continue
            if recorded:
                old = recorded.get(pf)
                new = hashlib.sha256(src.read_bytes()).hexdigest()[:16]
                if old and old != new:
                    issues.append(
                        f"{pf} 内容已变（指纹 {old} → {new}）→ {asset.name} 已过期，"
                        f"请重新组装")
            elif src.stat().st_mtime > asset.stat().st_mtime:
                issues.append(
                    f"{pf} 比 {asset.name} 新 → 资产可能过期（mtime 启发式；"
                    f"该资产无来源指纹，建议重新组装以生成指纹）")

    # 3. 采样记录不一致（**仅对流水线产出适用**）
    # 注：不用「metrics.total_chars vs 资产 meta.total_sample_words」做判据 ——
    # 实测该字段语义不统一：assemble.py 填的是**全书** total_chars，而会话/手工产出的
    # 资产（如 Lord_of_the_Mysteries）填的是**采样**字数。两者本就不可比。
    # 改用 manifest.selected_indices（确定性）与资产 meta.sample_chapters 比对。
    # 2026-09-23：再加一道前提——**该书必须有 pass 产出**。否则 manifest 与资产是
    # 两次独立决策（后来的采样器 vs 会话当时的选取），比对不成立，只会产生误报。
    voice_path = ASSETS_DIR / f"{name}-voice-card.json"
    manifest_path = SAMPLED_DIR / name / "manifest.json"
    if manifest_path.exists() and voice_path.exists() and has_pipeline_outputs(raw):
        try:
            mf = json.loads(manifest_path.read_text(encoding="utf-8"))
            v = json.loads(voice_path.read_text(encoding="utf-8"))
            m_idx = list(mf.get("selected_indices") or [])
            v_idx = list((v.get("meta") or {}).get("sample_chapters") or [])
            if m_idx and v_idx and m_idx != v_idx:
                issues.append(
                    f"采样已变但资产未更新：manifest 采了 {len(m_idx)} 章"
                    f"（前 6 个 {m_idx[:6]}），资产记录 {len(v_idx)} 章"
                    f"（前 6 个 {v_idx[:6]}）→ 请重新组装")
        except Exception as exc:
            issues.append(f"采样比对失败：{exc}")

    # 4. 报告铁律二：拆书报告 + 笔法分析合计 ≥ MIN_REPORT_CHARS。
    #    只对**已产出报告**的书检查；完全没报告的书不在此项管辖（属业务选择，非缺陷）。
    issues.extend(check_report_compliance(name))

    return issues


def check_report_compliance(name: str) -> list:
    """检查 `reports/` 下该书报告的合计字符数是否满足铁律二。

    判定口径复用 `scripts/report.py::check_combined_report_length`（单一来源），
    不在此另写一份阈值——否则两处口径必然漂移。

    Returns:
        问题描述列表（空 = 达标或无报告）。
    """
    book_path = REPORTS_DIR / f"{name}-拆书报告.md"
    craft_path = REPORTS_DIR / f"{name}-笔法分析.md"
    if not book_path.exists() and not craft_path.exists():
        return []  # 未产出报告：不报（是否该产出由业务决定）
    try:
        # 延迟导入：scripts/ 需在 sys.path（直接执行本脚本或由 novel.py 调用时均满足），
        # 且避免在被当作库 import 时对同级模块产生硬依赖。
        from report import MIN_REPORT_CHARS, check_combined_report_length
    except ImportError as exc:  # pragma: no cover - 仅在 sys.path 未含 scripts/ 时触发
        return [f"报告铁律二校验不可用（无法导入 report 模块）：{exc}"]

    r = check_combined_report_length(REPORTS_DIR, name)
    if r["ok"]:
        return []
    return [
        f"报告铁律二不达标：拆书报告 {r['book_chars']} 字 + 笔法分析 {r['craft_chars']} 字 "
        f"= 合计 {r['total']} 字 < 硬门槛 {MIN_REPORT_CHARS} 字"
        f"（缺 {MIN_REPORT_CHARS - r['total']} 字）→ 请重新生成报告"
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="同步检查（corpus/raw 的 pass 产出 vs assets/ 四卡；reports/ 报告铁律二）")
    ap.add_argument("book", nargs="?", help="书名；省略则检查全部已拆书")
    args = ap.parse_args(argv)

    books = [args.book] if args.book else list_books()
    if not books:
        print("corpus/raw/ 下没有任何已拆书，无需检查。")
        return 0

    print("=== 资产与报告同步检查 ===")
    print()
    total_issues = 0
    for name in books:
        issues = check_one(name)
        if issues:
            total_issues += len(issues)
            print(f"[✗] {name}")
            for it in issues:
                print(f"      · {it}")
        else:
            print(f"[✓] {name}")
        # 产出方式说明：非流水线产出的书要**显式告知**（不静默跳过），但不计为问题。
        note = provenance_note(name)
        if note:
            print(f"      [说明] {note}")

    print()
    if total_issues:
        print(f"发现 {total_issues} 个同步问题。")
        print("修复方式：资产类 → python novel.py 组装 <书名> --genre <题材>"
              "（组装含内存校验，通过才落盘）")
        print("          报告类 → python novel.py 分析 <书名> --genre <题材>"
              "（合计不足 10000 字会被硬校验阻断）")
        return 1
    print(f"全部 {len(books)} 本资产与报告同步。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
