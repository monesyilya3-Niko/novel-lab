#!/usr/bin/env python3
"""
M2.2 章节生成 + 入库 — 资产驱动创作的正式入口

把「注入的写作 prompt + 章节要点」喂给 LLM 生成一章，
写入 novel-writing 项目结构（chapters/arc-N/chapter-NNN.txt），
更新 state.json，并自动跑一致性打分 + 冲突检测。

用法:
  python write.py --prompt prompts/generated/chireng_chosen-writing-prompt.md \
                  --chapter 1 --task "场景：期中考试后，边炀约唐雨复习" \
                  [--novel-dir novel] [--words 2500] [--voice assets/chireng_chosen-voice-card.json]

前置:
  python pipeline.py <book.txt> --genre xxx      # 拆书产出资产
  python inject.py <voice-card.json> ...         # 产出写作 prompt
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import llm_client


def ensure_novel_structure(novel_dir: Path, name: str = "新书"):
    """按 novel-writing 约定创建/确认项目结构。"""
    novel_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("settings", "chapters", "tracker"):
        (novel_dir / sub).mkdir(exist_ok=True)
    state_file = novel_dir / "state.json"
    if not state_file.exists():
        state = {
            "name": name,
            "current_arc": 1,
            "current_chapter": 1,
            "word_count_today": 0,
            "last_updated": "",
        }
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state_file


def save_chapter(novel_dir: Path, chapter_no: int, content: str) -> Path:
    """写入 chapters/arc-N/chapter-NNN.txt，更新 state.json。"""
    arc = (chapter_no - 1) // 30 + 1
    arc_dir = novel_dir / "chapters" / f"arc-{arc}"
    arc_dir.mkdir(exist_ok=True)
    ch_file = arc_dir / f"chapter-{chapter_no:03d}.txt"
    ch_file.write_text(content, encoding="utf-8")

    state_file = novel_dir / "state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["current_chapter"] = chapter_no
    state["current_arc"] = arc
    state["word_count_today"] = state.get("word_count_today", 0) + len(content)
    state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return ch_file


def run_consistency(voice_path: Path, ch_file: Path) -> None:
    """跑一致性打分（M2.3）。"""
    try:
        import consistency
    except ImportError:
        print("  [跳过] consistency.py 不可用")
        return
    try:
        consistency.main_probe(str(voice_path), str(ch_file))
    except SystemExit:
        pass  # 打分器用 sys.exit 表达结论，这里捕获即可
    except Exception as e:
        print(f"  [跳过] 一致性打分异常: {e}")


def run_conflict_check(novel_dir: Path, content: str) -> None:
    """跑实体冲突检测（M2.4，复用 novel-writing 的 novel.py 逻辑）。"""
    try:
        novel_py = Path.home() / ".workbuddy/skills/novel-writing/scripts/novel.py"
        if novel_py.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("novel_skill", novel_py)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            # NOVEL_DIR 是项目父目录，name 是项目名（novel.py 内部做 NOVEL_DIR / name）
            mod.NOVEL_DIR = novel_dir.parent
            mod.cmd_conflict(novel_dir.name, content)
    except Exception as e:
        print(f"  [跳过] 冲突检测异常: {e}")


def main():
    ap = argparse.ArgumentParser(description="M2.2 章节生成 + 入库（资产驱动）")
    ap.add_argument("--prompt", required=True, help="注入的写作 prompt（inject.py 产物）")
    ap.add_argument("--chapter", type=int, required=True, help="章节号")
    ap.add_argument("--task", required=True, help="本章要点（场景/事件/钩子要求）")
    ap.add_argument("--novel-dir", default="novel", help="novel-writing 项目目录")
    ap.add_argument("--novel-name", default="新书", help="书名")
    ap.add_argument("--words", type=int, default=2500, help="目标字数")
    ap.add_argument("--voice", help="voice-card 路径（用于一致性打分，可选）")
    ap.add_argument("--genre-pack", help="题材包路径（用于附加质量检查，可选）")
    ap.add_argument("--target-score", type=int, default=90, help="一致性目标分（默认 90，未达标自动改写）")
    ap.add_argument("--quality-target", type=int, default=75, help="章节质量目标分（默认 75，chapter_check 100 分制）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将调用的内容，不调 LLM")
    args = ap.parse_args()

    prompt_path = Path(args.prompt)
    if not prompt_path.exists():
        sys.exit(f"写作 prompt 不存在: {prompt_path}（先跑 inject.py 生成）")
    system = prompt_path.read_text(encoding="utf-8")

    novel_dir = Path(args.novel_dir)
    state_file = ensure_novel_structure(novel_dir, args.novel_name)

    # 读取大纲（如果有），提供上下文
    outline_path = novel_dir / "chapters" / "outline.md"
    outline_ctx = ""
    if outline_path.exists():
        oc = outline_path.read_text(encoding="utf-8").strip()
        if oc:
            outline_ctx = f"\n【已有大纲】\n{oc[:1500]}"

    user = f"""请用上面注入的文风资产，写《{args.novel_name}》第 {args.chapter} 章（约 {args.words} 字）。{outline_ctx}

【本章要点】
{args.task}

要求（对照注入资产「写作执行清单」逐条执行）：
1. 严格按角色声线卡说话——每个出场角色的【口头禅/昵称/称呼方式】必须至少用 2 种（如「老子」「唐小雨」）
2. 情绪用「体感式」生理反应呈现，**密度要求：每 400 字至少 1 处**（心跳/指尖/耳根/手心/脊背/呼吸/发烫等身体词），2400 字约 6-8 处，零直陈式情绪词（禁止「很愤怒」「很难过」这类）
3. 比喻从「意象」指定领域取材（动物/日常物件），不用刀剑星辰类宏大比喻，2400 字至少 2 处比喻
4. 对话占比 25% 以上，节奏紧凑
5. 章末按「钩子骨架」留钩子
6. 规避「禁忌」清单
直接输出正文，不要任何解释。"""

    print(f"[1/4] 准备: {prompt_path.name} → 第{args.chapter}章 ({args.words}字)")
    if args.dry_run:
        print(f"  [dry-run] system {len(system)} 字, user {len(user)} 字，跳过 LLM")
        return

    # 2026-09-01 起：无外部模型模式——生成本地 AI 接管写作任务清单后优雅退出，
    # 正文生成与改写由 WorkBuddy 内置智能在会话内完成（与 pipeline.py 拆书降级对称）。
    if not llm_client.any_model_configured():
        arc = (args.chapter - 1) // 30 + 1
        guide = novel_dir / "AI接管写作任务.md"
        guide.write_text(
            "# WorkBuddy 内置智能接管写作任务（无外部模型模式）\n\n"
            f"书名: {args.novel_name} | 第 {args.chapter} 章 | 目标 {args.words} 字\n"
            f"写作 prompt（system）: {prompt_path.resolve()}\n"
            + (f"voice-card（一致性自检用）: {Path(args.voice).resolve()}\n" if args.voice else "")
            + "\n## 本章要点\n" + args.task + "\n\n"
            "## 接管步骤\n"
            "1. 完整阅读上述写作 prompt（inject.py 产物，含声线/情绪/意象/禁忌等全部资产约束）\n"
            f"2. 按 prompt 的「写作执行清单」逐条执行，在会话内写出第 {args.chapter} 章正文\n"
            "3. 正文存为: " + str((novel_dir / "chapters" / f"arc-{arc}" / f"chapter-{args.chapter:03d}.txt").resolve()) + "\n"
            "4. 运行本地自检（命令直接可复制）:\n"
            "   python novel.py 检查 " + str((novel_dir / "chapters" / f"arc-{arc}" / f"chapter-{args.chapter:03d}.txt").resolve())
            + (f" --voice {Path(args.voice).resolve()}" if args.voice else "") + "\n"
            f"5. 达标标准: 一致性 ≥{args.target_score}/100（consistency 五维），章节质量 ≥{args.quality_target}/100（chapter_check 12 维）\n"
            "6. 未达标则按扣分点改写后重检（对照「三维度改写循环」标准，最多 3 轮）\n\n"
            "## 写作要求全文（原 LLM user prompt）\n"
            "---\n" + user + "\n---\n\n"
            "本文件由 write.py 自动生成（无外部模型降级模式）。\n",
            encoding="utf-8")
        print("[2/4] 未配置外部模型 —— 已生成 AI 接管写作任务清单")
        print(f"      → {guide}")
        print("      写作由 WorkBuddy 会话内完成，写完用 novel.py 检查 自检")
        print("      （恢复外部模型可运行: python scripts/model_config.py add）")
        return 0

    # ---- 生成 + 自检 + 改写循环（目标 ≥ target_score）----
    target_score = getattr(args, "target_score", 90)
    content = ""
    for attempt in range(1, 4):  # 最多 3 轮（1 初稿 + 2 改写）
        print(f"[2/4] 生成 (第{attempt}稿): task='{args.task[:40]}...'")
        r = llm_client.chat(user=user, system=system, task="writing",
                            max_tokens=args.words * 3, temperature=0.8, json_mode=False)
        content = r["text"].strip()
        print(f"      → {len(content)} 字, {r['elapsed']}s, tokens {r['prompt_tokens']}+{r['completion_tokens']}")

        # 打分（双维度：一致性 + 章节质量）
        score, details, verdict = 0, [], 0
        quality_score = 0
        quality_issues = []
        if args.voice:
            try:
                import consistency
                vc_data = json.loads(Path(args.voice).read_text(encoding="utf-8"))
                score, details, verdict = consistency.score_text(vc_data, content, label=f"第{args.chapter}章 第{attempt}稿")
                print(f"      → 一致性 {score:.1f}/100 ({'PASS' if verdict == 0 else '需改写'})")
            except Exception as e:
                print(f"      → 一致性打分跳过: {e}")
        else:
            print("      → 未提供 voice-card，跳过一致性打分")

        # 章节质量自检
        try:
            import chapter_check
            import book_quality
            gp = None
            if args.genre_pack:
                gp = json.loads(Path(args.genre_pack).read_text(encoding="utf-8"))
            qc = chapter_check.chapter_check(content, gp)
            quality_score = qc["score"]
            quality_issues = qc["issues"]
            print(f"      → 章节质量 {quality_score}/100 ({qc['verdict']})")
            if quality_issues:
                for qi in quality_issues[:3]:
                    print(f"        ⚠ {qi}")
        except Exception as e:
            print(f"      → 章节质量检查跳过: {e}")

        # 全书质检（检查新章节与已有章节的重复/连贯性）
        qa_issues = []
        try:
            novel_chapters = Path(args.novel_dir) / "chapters"
            if novel_chapters.exists():
                # 收集已有章节文本
                existing = {}
                for ch_file in novel_chapters.rglob("*.txt"):
                    m = re.search(r'(\d+)', ch_file.stem)
                    if m:
                        existing[int(m.group(1))] = ch_file.read_text(encoding="utf-8")
                # 加入当前新章节
                existing[args.chapter] = content
                qa = book_quality.book_quality_check(str(novel_chapters))
                qa_issues = qa.get("issues", [])
                # 只关心当前章节的问题
                qa_issues = [i for i in qa_issues if i.get("chapter") == args.chapter or args.chapter in i.get("chapters", [])]
                if qa_issues:
                    print(f"      → 质检 {len(qa_issues)} 个问题")
                    for qi in qa_issues[:3]:
                        print(f"        ⚠ {qi['detail'][:60]}")
        except Exception as e:
            print(f"      → 质检跳过: {e}")

        # 三维度达标判断（一致性 + 章节质量 + 质检）
        consistency_ok = score >= target_score or not args.voice
        quality_ok = quality_score >= args.quality_target
        qa_ok = len(qa_issues) == 0
        if consistency_ok and quality_ok and qa_ok:
            print("      ✅ 三维度达标，无需改写")
            break
            print("      ✅ 达到质量线，无需改写")
            break
        if attempt < 3:
            # 提取扣分点作为改写指令（一致性 + 质量双维度）
            issues = [l.strip() for l in details if ("命中" in l or "→" in l) and "✓" not in l]
            # 加入质量扣分点
            if quality_issues:
                issues.extend([f"[质量] {qi}" for qi in quality_issues[:5]])
            issue_text = "\n".join(issues[:10])
            # 从 voice-card 提取每个出场角色必须出现的核心词，让模型知道具体写什么
            must_use = ""
            if args.voice:
                try:
                    vc_data = json.loads(Path(args.voice).read_text(encoding="utf-8"))
                    import consistency as _c
                    for v in vc_data.get("dialogue", {}).get("character_voices", []):
                        name = v.get("name", "")
                        if not name or (name not in content and name[:2] not in content):
                            continue  # 未出场角色跳过
                        ss = v.get("speech_signature") or {}
                        kws = []
                        for t in ss.get("verbal_tics", []):
                            if isinstance(t, str):
                                kws.extend(_c.extract_keywords(t))
                        kws = list(dict.fromkeys(kws))[:4]
                        if kws:
                            must_use += f"- {name}：务必让对话中出现「{'」「'.join(kws)}」中的至少 2 个\n"
                except Exception:
                    pass
            must_block = f"\n【每个出场角色必须出现的具体词】\n{must_use}" if must_use else ""
            user = f"""请【改写】上一稿《{args.novel_name}》第 {args.chapter} 章（保持情节不变，约 {args.words} 字）。
风格一致性评分 {score:.1f}/100，未达 {target_score}。以下是扣分明细，请逐条修正后重写：

{issue_text}
{must_block}
重点修正：
- 角色声线：上面列出的具体词必须实际出现在角色对话里（不是叙述里提一句）
- 情绪写法：补足体感式生理反应描写（心跳/指尖/耳根/手心/脊背等），**2400 字至少 6-8 处**，删掉直陈式情绪词
- 比喻：从「意象」指定领域取材（动物/日常物件），**至少 2 处**
- 保持原情节、原对话意图，只改表达方式

【硬性要求】只输出小说正文本身，禁止输出任何元文本——不要「风格执行自查」「本章钩子」「说明」等段落，不要 markdown 标题（#、##），不要章节号。
直接输出修正后的完整正文。"""
            print(f"      ⚠ 未达标，携带扣分明细改写（第{attempt+1}轮）...")

    ch_file = save_chapter(novel_dir, args.chapter, content)
    print(f"[3/4] 已入库: {ch_file}")

    print("[4/4] 质量门禁:")
    if args.voice:
        run_consistency(Path(args.voice), ch_file)
    run_conflict_check(novel_dir, content)

    print(f"\n✅ 完成: 第{args.chapter}章已写入 {ch_file}")


if __name__ == "__main__":
    main()
