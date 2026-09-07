#!/usr/bin/env python3
"""
novel-lab CLI 统一入口 — 一条命令覆盖全部工作流

用法:
  novel 分析 <book.txt> --genre xxx           # 一键拆书+拆书报告+笔法报告
  novel 拆书 <book.txt> --genre xxx           # 拆书（pipeline）
  novel 批量 <corpus目录> --genre xxx [--report]  # 批量拆书
  novel 聚合 --genre xxx                      # Pass5 题材包（需≥3本）
  novel 蒸馏 --genre xxx [--books a b c]      # 跨书蒸馏四类资产（需≥2本）
  novel 注入 <voice-card.json> [--structure ...] [--commercial ...]  # 资产→写作prompt
  novel 写作 <voice-card.json> --chapter N --task "要点" [--target-score 90]  # 写章节
  novel 打分 <voice-card.json> <章节.txt>      # 一致性打分
  novel 报告 <voice-card.json> [--structure ...] [--commercial ...]  # 拆书报告
  novel 校验 <资产.json>                       # schema 校验
  novel 合规 <资产.json> <book.txt>            # 版权合规扫描
  novel 模型                                   # 查看模型配置
  novel 状态                                   # 项目概览
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent  # novel-lab/ 本身
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))  # 使 scripts/ 下的模块可直接 import
PY = sys.executable


def run_script(name: str, args: list) -> int:
    """运行 scripts/ 下的脚本，透传参数。"""
    script = SCRIPTS / name
    if not script.exists():
        print(f"✗ 脚本不存在: {script}")
        return 1
    cmd = [PY, str(script)] + [str(a) for a in args]
    return subprocess.call(cmd)


def cmd_status():
    """项目概览：资产/章节/报告状态。"""
    print("=" * 50)
    print("novel-lab 项目状态")
    print("=" * 50)
    assets = sorted((ROOT / "assets").glob("*-voice-card.json"))
    assets = [a for a in assets if not a.name.startswith("synthetic_")]
    print(f"\n[资产] {len(assets)} 本已拆:")
    for a in assets:
        vc = json.loads(a.read_text(encoding="utf-8"))
        meta = vc.get("meta", {})
        print(f"  - {a.name.replace('-voice-card.json','')}: "
              f"{meta.get('genre','?')} | 置信 {meta.get('confidence',0):.0%} | "
              f"角色 {len(vc.get('dialogue',{}).get('character_voices',[]))} 个")
    packs = sorted((ROOT / "assets").glob("*-genre-pack.json"))
    if packs:
        print(f"\n[题材包] {len(packs)} 份: {[p.name for p in packs]}")
    else:
        print("\n[题材包] 无（拆 ≥3 本同题材后跑 'novel 聚合'）")
    novels = sorted((ROOT / "novel").glob("*/state.json"))
    if novels:
        print("\n[创作项目]")
        for s in novels:
            state = json.loads(s.read_text(encoding="utf-8"))
            print(f"  - {state.get('name','?')}: 第{state.get('current_chapter',1)}章/"
                  f"第{state.get('current_arc',1)}卷, 今日{state.get('word_count_today',0)}字")
    reports = sorted((ROOT / "reports").glob("*.md"))
    if reports:
        print(f"\n[拆书报告] {len(reports)} 份: {[r.name for r in reports]}")
    models_path = ROOT / "config" / "models.json"
    if models_path.exists():
        models = json.loads(models_path.read_text(encoding="utf-8"))
        print(f"\n[模型] {list(models.get('models', {}).keys())}")
    else:
        print("\n[模型] 未配置外部模型 —— LLM 层由 WorkBuddy 内置智能承担"
              "（pass1-5 分析与写作改写由 AI 直接读文本完成，无 API 依赖）")
    print(f"\n提示: 'novel 拆书 --help' 查看各子命令详细用法")
    return 0


def main():
    ap = argparse.ArgumentParser(description="novel-lab CLI", prog="novel")
    sub = ap.add_subparsers(dest="cmd", help="子命令")

    p_check = sub.add_parser("检查", help="章节质量+一致性双维度检查")
    p_check.add_argument("chapter", help="章节文件路径")
    p_check.add_argument("--voice", help="voice-card 路径（一致性打分）")
    p_check.add_argument("--genre-pack", help="题材包路径（可选）")
    p_check.add_argument("--json", action="store_true")

    p_qa = sub.add_parser("质检", help="全书内容质检（重复/连贯/凑字数/乱编/AI味）")
    p_qa.add_argument("chapter_dir", help="章节目录或单章txt")
    p_qa.add_argument("--voice", help="voice-card 路径（可选）")
    p_qa.add_argument("--json", action="store_true")

    p0 = sub.add_parser("分析", help="一键拆书+拆书报告+笔法报告")
    p0.add_argument("book")
    p0.add_argument("--genre", required=True)
    p0.add_argument("--model-id")
    p0.add_argument("--dry-run", action="store_true")

    p1 = sub.add_parser("拆书", help="拆书：TXT → 资产")
    p1.add_argument("book")
    p1.add_argument("--genre", required=True)
    p1.add_argument("--model-id")
    p1.add_argument("--dry-run", action="store_true")

    p2 = sub.add_parser("批量", help="批量拆书：目录多本 TXT")
    p2.add_argument("corpus")
    p2.add_argument("--genre", required=True)
    p2.add_argument("--report", action="store_true")
    p2.add_argument("--dry-run", action="store_true")

    p3 = sub.add_parser("聚合", help="Pass5 题材包聚合（需 ≥3 本）")
    p3.add_argument("--genre", required=True)
    p3.add_argument("--books")

    p3b = sub.add_parser("蒸馏", help="跨书蒸馏四类资产（voice/craft/structure/commercial）")
    p3b.add_argument("--genre", required=True, help="题材目录名，如 campus-redemption")
    p3b.add_argument("--books", nargs="*", default=None, help="可选，限定参与蒸馏的书籍")

    p4 = sub.add_parser("注入", help="资产 → 写作 prompt")
    p4.add_argument("voice")
    p4.add_argument("--structure")
    p4.add_argument("--commercial")
    p4.add_argument("--genre-pack")
    p4.add_argument("--craft-card", help="craft-card JSON（可选，注入写作技法）")
    p4.add_argument("--distilled", help="蒸馏规则 JSON（可选，注入跨书聚合规则）")
    p4.add_argument("--out", help="输出路径，默认 prompts/generated/<名>-writing-prompt.md")

    p5 = sub.add_parser("写作", help="生成章节（含改写循环，默认目标 90）")
    p5.add_argument("voice")
    p5.add_argument("--prompt", help="写作 prompt（缺省自动注入）")
    p5.add_argument("--chapter", type=int, required=True)
    p5.add_argument("--task", required=True)
    p5.add_argument("--novel-dir", default="novel")
    p5.add_argument("--novel-name", default="新书")
    p5.add_argument("--words", type=int, default=2400)
    p5.add_argument("--target-score", type=int, default=90)
    p5.add_argument("--dry-run", action="store_true")

    p6 = sub.add_parser("打分", help="章节一致性打分")
    p6.add_argument("voice")
    p6.add_argument("chapter")

    p7 = sub.add_parser("报告", help="拆书报告（可变现）")
    p7.add_argument("voice")
    p7.add_argument("--structure")
    p7.add_argument("--commercial")
    p7.add_argument("--title")
    p7.add_argument("--out")

    p8 = sub.add_parser("校验", help="schema 校验")
    p8.add_argument("asset")
    p8.add_argument("--kind", choices=["voice-card", "genre-pack", "trope-library", "craft-card", "structure-obs", "commercial-obs"])

    p12 = sub.add_parser("笔法报告", help="craft-card → 笔法深度分析报告")
    p12.add_argument("craft_card", help="craft-card JSON 文件路径")
    p12.add_argument("--out")

    p9 = sub.add_parser("合规", help="版权合规扫描")
    p9.add_argument("asset")
    p9.add_argument("book")

    p13 = sub.add_parser("组装", help="组装 AI 产出的 pass1-5 JSON 为可入库资产（无模型模式必用）")
    p13.add_argument("name", help="书名（corpus/raw/ 下的目录名）")
    p13.add_argument("--genre", default="unknown", help="题材 id")
    p13.add_argument("--skip-craft", action="store_true", help="跳过 craft-card（pass5 缺失时）")

    p10 = sub.add_parser("模型", help="模型配置与连通性")
    p10.add_argument("--test", help="测试指定模型连通性")

    p11 = sub.add_parser("状态", help="项目概览")

    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return 0

    if args.cmd == "分析":
        # 一键：拆书 → 拆书报告 → 笔法报告 → 自动质检（Hook）
        src = Path(args.book)
        if not src.exists():
            sys.exit(f"文件不存在: {src}")
        name = src.stem
        # 1. 跑 pipeline（含 Pass5）
        rc1 = run_script("pipeline.py", [args.book, "--genre", args.genre] +
                         (["--model-id", args.model_id] if args.model_id else []) +
                         (["--dry-run"] if args.dry_run else []))
        if rc1 != 0:
            return rc1
        if args.dry_run:
            return 0
        # 2. 生成拆书报告
        vc = ROOT / "assets" / f"{name}-voice-card.json"
        so = ROOT / "assets" / f"{name}-structure-obs.json"
        co = ROOT / "assets" / f"{name}-commercial-obs.json"
        cc = ROOT / "assets" / f"{name}-craft-card.json"
        if vc.exists():
            rpt_args = [str(vc)]
            if so.exists():
                rpt_args += ["--structure", str(so)]
            if co.exists():
                rpt_args += ["--commercial", str(co)]
            run_script("report.py", rpt_args)
        # 3. 生成笔法报告
        cc = ROOT / "assets" / f"{name}-craft-card.json"
        if cc.exists():
            run_script("report_craft.py", [str(cc)])
        # 3. 自动质检 Hook（借鉴 oh-story：拆书完成后自动检查）
        print("\n[Hook] 自动质检:")
        corpus_file = ROOT / "corpus" / f"{name}.txt"
        if corpus_file.exists():
            import book_quality
            qa = book_quality.book_quality_check(str(corpus_file), str(vc) if vc.exists() else None)
            sev = qa.get("severity", {})
            if qa["total_issues"] == 0:
                print(f"  ✅ 质检通过（{qa['total_chapters']}章 0问题）")
            else:
                print(f"  ⚠ 质检 {qa['total_issues']} 个问题（{sev.get('critical',0)}严重/{sev.get('high',0)}高/{sev.get('medium',0)}中）")
                for issue in qa["issues"][:5]:
                    print(f"    · {issue['detail'][:60]}")

        print(f"\n分析完成。资产目录: assets/ | 报告目录: reports/")
        return 0

    if args.cmd == "拆书":
        return run_script("pipeline.py", [args.book, "--genre", args.genre] +
                          (["--model-id", args.model_id] if args.model_id else []) +
                          (["--dry-run"] if args.dry_run else []))
    if args.cmd == "批量":
        return run_script("batch.py", [args.corpus, "--genre", args.genre] +
                          (["--report"] if args.report else []) +
                          (["--dry-run"] if args.dry_run else []))
    if args.cmd == "检查":
        # 双维度检查：章节质量 + 一致性
        import json as _json
        ch_path = Path(args.chapter)
        if not ch_path.exists():
            sys.exit(f"文件不存在: {ch_path}")
        text = ch_path.read_text(encoding="utf-8")

        # 1. 章节质量
        import chapter_check
        gp = None
        if args.genre_pack:
            gp = _json.loads(Path(args.genre_pack).read_text(encoding="utf-8"))
        qc = chapter_check.chapter_check(text, gp)

        # 2. 一致性（如果有 voice-card）
        vc_score = None
        vc_details = []
        if args.voice:
            import consistency
            vc_data = _json.loads(Path(args.voice).read_text(encoding="utf-8"))
            vc_score, vc_details, _ = consistency.score_text(vc_data, text, label=ch_path.name)

        # 输出
        if args.json:
            out = {"quality": qc}
            if vc_score is not None:
                out["consistency"] = {"score": vc_score, "details": vc_details}
            print(_json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(f"章节检查: {ch_path.name}")
            print(f"{'='*50}")
            print(f"质量评分: {qc['score']}/100 ({qc['verdict']})")
            for d in qc['details']:
                print(f"  {d}")
            if vc_score is not None:
                print(f"\n一致性评分: {vc_score:.1f}/100")
                for d in vc_details:
                    print(f"  {d}")
            if qc['issues']:
                print(f"\n需改进:")
                for i in qc['issues']:
                    print(f"  ⚠ {i}")
        return 0

    if args.cmd == "质检":
        import book_quality
        result = book_quality.book_quality_check(args.chapter_dir, args.voice)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"全书内容质检")
            print(f"{'='*50}")
            print(f"章节: {result['total_chapters']} | 问题: {result['total_issues']} | 判定: {result['verdict']}")
            print()
            for sev in ['critical', 'high', 'medium', 'low']:
                count = result['severity'].get(sev, 0)
                if count:
                    print(f"  {sev}: {count}")
            print()
            for issue in result['issues'][:20]:
                sev_icon = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '⚪'}.get(issue['severity'], '⚪')
                print(f"  {sev_icon} {issue['detail']}")
        return 0

    if args.cmd == "聚合":
        return run_script("pass5_aggregate.py", ["--genre", args.genre] +
                          (["--books", args.books] if args.books else []))
    if args.cmd == "蒸馏":
        return run_script("distill.py", ["--genre", args.genre] +
                          (["--books"] + list(args.books) if args.books else []))
    if args.cmd == "注入":
        return run_script("inject.py", [args.voice] +
                          (["--structure", args.structure] if args.structure else []) +
                          (["--commercial", args.commercial] if args.commercial else []) +
                          (["--genre-pack", args.genre_pack] if args.genre_pack else []) +
                          (["--craft-card", args.craft_card] if args.craft_card else []) +
                          (["--distilled", args.distilled] if args.distilled else []) +
                          (["--out", args.out] if args.out else []))
    if args.cmd == "写作":
        # 缺省 prompt 时自动注入
        if args.prompt:
            prompt = args.prompt
        else:
            name = Path(args.voice).stem.replace("-voice-card", "")
            gen = ROOT / "prompts" / "generated" / f"{name}-writing-prompt.md"
            if not gen.exists():
                print(f"✗ 写作 prompt 不存在，先运行: novel 注入 {args.voice}")
                return 1
            prompt = str(gen)
        return run_script("write.py", [
            "--prompt", prompt, "--chapter", args.chapter, "--task", args.task,
            "--novel-dir", args.novel_dir, "--novel-name", args.novel_name,
            "--words", args.words, "--voice", args.voice,
            "--target-score", args.target_score] + (["--dry-run"] if args.dry_run else []))
    if args.cmd == "打分":
        return run_script("consistency.py", [args.voice, args.chapter])
    if args.cmd == "报告":
        return run_script("report.py", [args.voice] +
                          (["--structure", args.structure] if args.structure else []) +
                          (["--commercial", args.commercial] if args.commercial else []) +
                          (["--title", args.title] if args.title else []) +
                          (["--out", args.out] if args.out else []))
    if args.cmd == "笔法报告":
        return run_script("report_craft.py", [args.craft_card] +
                          (["--out", args.out] if args.out else []))
    if args.cmd == "校验":
        return run_script("validate.py", [args.asset] +
                          (["--kind", args.kind] if args.kind else []))
    if args.cmd == "合规":
        return run_script("compliance.py", [args.asset, args.book])
    if args.cmd == "组装":
        return run_script("assemble.py", [args.name, "--genre", args.genre] +
                          (["--skip-craft"] if args.skip_craft else []))
    if args.cmd == "模型":
        if args.test:
            return run_script("llm_client.py", [args.test])
        return run_script("model_config.py", ["list"])
    if args.cmd == "状态":
        return cmd_status()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
