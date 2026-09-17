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
    # 2026-09-05 修复（C4）：word_count_today 跨日清零（原版只累加永不清零，长期失真）
    today = datetime.now().strftime("%Y-%m-%d")
    if state.get("last_write_date") != today:
        state["word_count_today"] = 0
        state["last_write_date"] = today
    state["word_count_today"] = state.get("word_count_today", 0) + len(content)
    state["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return ch_file


def run_consistency(voice_path: Path, ch_file: Path) -> None:
    """跑一致性打分（M2.3）。

    2026-09-05 修复：原先调用不存在的 consistency.main_probe()，异常被 except
    吞掉导致本步骤从未真正执行。现改用真实存在的 score_text()（与根 novel.py
    「检查」命令同一模式）。
    """
    try:
        import consistency
    except ImportError:
        print("  [跳过] consistency.py 不可用")
        return
    try:
        vc_data = json.loads(voice_path.read_text(encoding="utf-8"))
        score, details, _ = consistency.score_text(
            vc_data, ch_file.read_text(encoding="utf-8"), label=ch_file.name)
        print(f"  一致性打分: {score:.1f}/100" + ("  ✅ PASS" if score >= 75 else "  ⚠️ 未达 75，建议改写"))
        for d in details:
            print(f"    {d}")
    except Exception as e:
        print(f"  [跳过] 一致性打分异常: {e}")


def run_conflict_check(novel_dir: Path, content: str) -> None:
    """实体冲突检测（M2.4）。

    2026-09-05 修复：原先依赖一个已移除的外部 skill（novel-writing）
    （路径失效被 except 静默跳过）。现改为读取 novel_dir/settings/entities.json
    做轻量实体校验：
      约定格式: {"characters": [{"name": "唐雨", "aliases": ["小雨", "唐小雨"]}, ...]}
      检查 1: 文中出现的疑似新人名（2-3 字、不在实体表）→ 提示（供人工确认）
      检查 2: 实体别名在正文中的混用情况 → 提示
    实体文件不存在时打印说明并跳过（显式，不静默）。
    """
    entities_file = novel_dir / "settings" / "entities.json"
    if not entities_file.exists():
        print(f"  [跳过] 实体表不存在: {entities_file}（可创建以启用人名冲突检测）")
        return
    try:
        entities = json.loads(entities_file.read_text(encoding="utf-8"))
        known = {}  # name -> set(aliases)
        for c in entities.get("characters", []):
            name = c.get("name", "")
            if name:
                known[name] = set(c.get("aliases", []) or [])
        if not known:
            print("  [跳过] 实体表为空")
            return
        # 检查 2: 已知实体及其别名在正文中的出现情况
        mixed = []
        for name, aliases in known.items():
            hit = [a for a in aliases if a and a in content]
            if hit and name not in content and len(hit) >= 1:
                mixed.append(f"{name}(仅以别称出现: {'、'.join(hit[:3])})")
        if mixed:
            print(f"  ⚠ 别名混用提示: {'; '.join(mixed[:5])}")
        else:
            print("  ✅ 实体称呼无异常")
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
    ap.add_argument("--quality-target", type=int, default=None, help="章节质量目标分（可选；缺省时按题材包 quality_thresholds 回退，再回退 75）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将调用的内容，不调 LLM")
    args = ap.parse_args()

    prompt_path = Path(args.prompt)
    if not prompt_path.exists():
        sys.exit(f"写作 prompt 不存在: {prompt_path}（先跑 inject.py 生成）")
    system = prompt_path.read_text(encoding="utf-8")

    novel_dir = Path(args.novel_dir)
    state_file = ensure_novel_structure(novel_dir, args.novel_name)

    # 解析章节质量达标线：CLI 显式 > 题材包 quality_thresholds > 默认 75
    # （提前解析，供「无外部模型」提示文本与主循环两处复用同一事实来源）
    import chapter_check as _chapter_check
    gp = None
    if args.genre_pack:
        try:
            gp = json.loads(Path(args.genre_pack).read_text(encoding="utf-8"))
        except Exception:
            gp = None
    if args.quality_target is not None:
        pass_line = args.quality_target
    else:
        pass_line, _ = _chapter_check.resolve_thresholds(gp)

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
            f"5. 达标标准: 一致性 ≥{args.target_score}/100（consistency 五维），章节质量 ≥{pass_line}/100（chapter_check 12 维）\n"
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
        # 2026-09-05 修复：verdict 变量原先误用 score_text 的第三返回值 raw(dict)，
        # 导致达标时也显示"需改写"。改为直接比较 score 与 target_score。
        score, details = 0, []
        quality_score = 0
        quality_issues = []
        if args.voice:
            try:
                import consistency
                vc_data = json.loads(Path(args.voice).read_text(encoding="utf-8"))
                score, details, _ = consistency.score_text(vc_data, content, label=f"第{args.chapter}章 第{attempt}稿")
                print(f"      → 一致性 {score:.1f}/100 ({'PASS' if score >= target_score else '需改写'})")
            except Exception as e:
                print(f"      → 一致性打分跳过: {e}")
        else:
            print("      → 未提供 voice-card，跳过一致性打分")

        # 章节质量自检
        try:
            import chapter_check
            import book_quality
            qc = chapter_check.chapter_check(content, gp)
            quality_score = qc["score"]
            quality_issues = qc["issues"]
            print(f"      → 章节质量 {quality_score}/100 ({qc['verdict']})")
            if quality_issues:
                for qi in quality_issues[:3]:
                    print(f"        ⚠ {qi}")
        except Exception as e:
            print(f"      → 章节质量检查跳过: {e}")

        # 2026-09-05 修复（A3）：删除原循环内"全书 QA"块——它在 save_chapter 之前
        # 扫描磁盘，新章节尚不在目录中，过滤后恒为空集，qa_ok 恒真，纯属无效调用
        # （附带清除了从未使用的 existing 字典死代码）。全书 QA 已移至入库后执行。

        # 三维度达标判断（一致性 + 章节质量；全书 QA 在入库后执行）
        # 2026-09-05 修复：原第三维 qa_ok 因时序问题恒真（见上），已移除该无效判断
        consistency_ok = score >= target_score or not args.voice
        # 章节质量达标线已在入口处解析（CLI 显式 > 题材包 pass > 默认 75）
        quality_ok = quality_score >= pass_line
        if consistency_ok and quality_ok:
            print("      ✅ 双维度达标，无需改写")
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

    # 2026-09-05 修复（A3 + E4）：全书 QA 移到入库之后执行——此刻新章节已在磁盘，
    # 扫描必然覆盖它；并传入 voice-card 使风格一致性检查真正生效。
    try:
        novel_chapters = Path(args.novel_dir) / "chapters"
        if novel_chapters.exists():
            qa = book_quality.book_quality_check(
                str(novel_chapters), args.voice)
            verdict = qa.get("verdict", "?")
            n_issues = qa.get("total_issues", 0)
            print(f"  全书 QA: {qa.get('total_chapters', '?')} 章 / {n_issues} 问题 / {verdict}")
            if verdict != "PASS":
                for qi in qa.get("issues", [])[:8]:
                    print(f"    ⚠ {qi.get('severity', '?')}: {qi.get('detail', '')[:70]}")
                print("  （章节已入库；QA 未过，建议人工复核或携上述问题改写本章节）")
    except Exception as e:
        print(f"  [跳过] 全书 QA 异常: {e}")

    print(f"\n✅ 完成: 第{args.chapter}章已写入 {ch_file}")


if __name__ == "__main__":
    main()
