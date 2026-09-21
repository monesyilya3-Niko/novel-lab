#!/usr/bin/env python3
"""资产同步检查：`corpus/raw/<name>/` 的 pass 产出 与 `assets/` 的四卡是否对得上。

为什么需要它
------------
拆书是「pass 产出 JSON → 组装成资产」两段式。中间任何一步不同步，资产就会
**静默过期**：内容看着正常，实际已经落后于 pass 产出。此前没有任何检测手段，
只能靠人记得"改完 pass 要重新组装"。

检查三项
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

    # 3. 采样记录不一致
    # 注：不用「metrics.total_chars vs 资产 meta.total_sample_words」做判据 ——
    # 实测该字段语义不统一：assemble.py 填的是**全书** total_chars，而会话/手工产出的
    # 资产（如 Lord_of_the_Mysteries）填的是**采样**字数。两者本就不可比。
    # 改用 manifest.selected_indices（确定性）与资产 meta.sample_chapters 比对。
    voice_path = ASSETS_DIR / f"{name}-voice-card.json"
    manifest_path = SAMPLED_DIR / name / "manifest.json"
    if manifest_path.exists() and voice_path.exists():
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

    return issues


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="资产同步检查（corpus/raw 的 pass 产出 vs assets/ 的四卡）")
    ap.add_argument("book", nargs="?", help="书名；省略则检查全部已拆书")
    args = ap.parse_args(argv)

    books = [args.book] if args.book else list_books()
    if not books:
        print("corpus/raw/ 下没有任何已拆书，无需检查。")
        return 0

    print("=== 资产同步检查 ===")
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

    print()
    if total_issues:
        print(f"发现 {total_issues} 个同步问题。")
        print("修复方式：python novel.py 组装 <书名> --genre <题材>"
              "（组装含内存校验，通过才落盘）")
        return 1
    print(f"全部 {len(books)} 本资产与 pass 产出同步。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
