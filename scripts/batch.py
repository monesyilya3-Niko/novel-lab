#!/usr/bin/env python3
"""
M3 批量拆书 — 遍历目录多本 TXT，逐本拆解并生成报告

为 Pass5 聚合题材包铺路：拆 ≥3 本同题材书后，可聚合出题材包（genre-pack）。

用法:
  python batch.py <corpus目录> --genre campus-redemption
  python batch.py <corpus目录> --genre campus-redemption --report   # 每本生成拆书报告
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import sampler
import metrics as metrics_mod
import validate as validate_mod
import compliance as compliance_mod
import normalize as norm
import pipeline


def run_book(src: Path, genre: str, model_id: str | None, dry_run: bool) -> dict:
    """单本拆书（复用 pipeline 逻辑），返回 (voice_card, struct_obs, comm_obs)。"""
    name = src.stem
    print(f"\n{'='*56}\n▶ 拆书: {name}（{genre}）\n{'='*56}")

    # 1. 采样
    text = src.read_text(encoding="utf-8")
    chapters = sampler.split_chapters(text)
    if len(chapters) < 5:
        print(f"  ✗ 章节过少（{len(chapters)}），跳过")
        return None
    sel = sampler.select(chapters)
    slices = sampler.build_slices(chapters, sel)
    manifest = {
        "book": name,
        "total_chapters": len(chapters),
        "selected_count": len(sel),
        "selected_indices": [i + 1 for i in sorted(sel)],
    }
    sampled_dir = ROOT / "corpus" / "sampled" / name
    sampled_dir.mkdir(parents=True, exist_ok=True)
    (sampled_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (sampled_dir / "slices.json").write_text(json.dumps(slices, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [1/6] 采样: {len(chapters)} 章 → {len(sel)} 章")

    # 2. 量化
    m = metrics_mod.compute(text)
    metrics_dir = ROOT / "corpus" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / f"{name}.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [2/6] 量化: {m['total_chars']} 字, 对话占比 {m['dialogue_ratio']}")

    # 3. 四遍扫描
    print("  [3/6] 四遍扫描:")
    results = {}
    raw_dir = ROOT / "corpus" / "raw" / name  # 按书名隔离，避免多本书互相覆盖
    raw_dir.mkdir(parents=True, exist_ok=True)
    for kind in ("pass1_structure", "pass2_character", "pass3_style", "pass4_commercial"):
        results[kind] = pipeline.run_pass(kind, slices, m, dry_run, model_id)
        if not dry_run:
            (raw_dir / f"{kind}.json").write_text(
                json.dumps(results[kind], ensure_ascii=False, indent=2), encoding="utf-8")
    if dry_run:
        print("  [dry-run] 跳过组装/校验/合规")
        return None

    # 4. 组装资产
    print("  [4/6] 组装资产:")
    voices = norm.normalize_pass2(results["pass2_character"])
    narration, dialogue, emotion, imagery, banned = norm.normalize_pass3(results["pass3_style"])
    dialogue["dialogue_ratio"] = m.get("dialogue_ratio", 0)
    dialogue["character_voices"] = voices
    vc = pipeline.assemble_voice_card_v2(name, genre, manifest,
                                         voices, narration, dialogue, emotion, imagery, banned, m)
    so = pipeline.assemble_obs("structure", name, genre, results["pass1_structure"])
    co = pipeline.assemble_obs("commercial", name, genre, results["pass4_commercial"])
    assets_dir = ROOT / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for p, obj in ((assets_dir / f"{name}-voice-card.json", vc),
                   (assets_dir / f"{name}-structure-obs.json", so),
                   (assets_dir / f"{name}-commercial-obs.json", co)):
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"      ✓ {p.name}")

    # 5. 校验（voice-card 严格）
    print("  [5/6] Schema 校验:")
    errs_before = len(validate_mod.ERRORS)
    validate_mod.DISPATCH["voice-card"](vc)
    new_errs = validate_mod.ERRORS[errs_before:]
    print(f"      {'✓ voice-card 通过' if not new_errs else f'✗ {len(new_errs)} 条错误'}")

    # 6. 合规
    print("  [6/6] 合规扫描:")
    ok = True
    for p in (assets_dir / f"{name}-voice-card.json",
              assets_dir / f"{name}-structure-obs.json",
              assets_dir / f"{name}-commercial-obs.json"):
        asset = json.loads(p.read_text(encoding="utf-8"))
        ngram = compliance_mod.build_ngram_index(text)
        errs, warns = compliance_mod.scan_asset(asset, ngram)
        if errs:
            ok = False
            print(f"      ✗ {p.name}: {len(errs)} 条 REJECT")
        else:
            print(f"      ✓ {p.name}: 合规（{len(warns)} 警告）")
    if not ok:
        print(f"  ✗ {name} 合规失败，未产出报告")
        return None

    return {"voice": vc, "structure": so, "commercial": co, "name": name}


def generate_reports(results: list, out_dir: Path) -> None:
    """为每本生成拆书报告。"""
    import report as report_mod
    out_dir.mkdir(parents=True, exist_ok=True)
    for r in results:
        if not r:
            continue
        md = report_mod.build_report(r["voice"], r["structure"], r["commercial"], r["name"])
        p = out_dir / f"{r['name']}-拆书报告.md"
        p.write_text(md, encoding="utf-8")
        print(f"  ✓ 报告: {p.name}")


def main():
    ap = argparse.ArgumentParser(description="批量拆书：目录多本 TXT → 逐本拆解")
    ap.add_argument("corpus", help="包含多本 TXT 的目录")
    ap.add_argument("--genre", required=True, help="题材 id，如 campus-redemption")
    ap.add_argument("--model-id", help="显式指定模型")
    ap.add_argument("--dry-run", action="store_true", help="只走采样+量化，不调 LLM")
    ap.add_argument("--report", action="store_true", help="每本生成拆书报告")
    args = ap.parse_args()

    corpus_dir = Path(args.corpus)
    if not corpus_dir.is_dir():
        sys.exit(f"目录不存在: {corpus_dir}")

    books = sorted(corpus_dir.glob("*.txt"))
    if not books:
        sys.exit(f"目录中没有 TXT: {corpus_dir}")
    print(f"发现 {len(books)} 本 TXT:")

    results = []
    for b in books:
        r = run_book(b, args.genre, args.model_id, args.dry_run)
        if r:
            results.append(r)

    if args.report and results:
        print("\n生成拆书报告:")
        generate_reports(results, ROOT / "reports")

    print(f"\n完成: 成功 {len(results)} / {len(books)} 本")
    if len(results) >= 3:
        print("→ 已满足 Pass5 聚合条件（≥3 本），可运行 pass5_aggregate 生成题材包")
    elif len(results) > 0:
        print(f"→ 还需 {3 - len(results)} 本即可跑 Pass5 聚合题材包")


if __name__ == "__main__":
    main()
