"""测试：去 AI 味诊断服务 (deslop_service) 与 Markdown/DOCX 规范化导出。

严格遵循项目规范：
- 使用 _isolation.isolate_paths 保证路径隔离与连接释放
- 纯标准库
"""

from __future__ import annotations

import base64
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_ROOT = _TESTS_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_TESTS_DIR))
import _isolation  # noqa: E402

from gui import config, db, deslop_service, router, writing_extra  # noqa: E402


class TestDeslopService(unittest.TestCase):
    def test_natural_text(self):
        text = "他在雪地里走了一整夜，皮靴踩碎冰壳发出沉闷的脆响。推开木门时，炉火已经熄了，只有余烬微微泛着暗红。"
        res = deslop_service.analyze_deslop(text)
        self.assertEqual(res["verdict"], "NATURAL")
        self.assertLess(res["ai_score"], 25.0)
        self.assertIn("word_count", res["stats"])

    def test_hollow_and_ai_tics_detected(self):
        bad_text = (
            "这一刻，时间仿佛凝固了。天地之间仿佛只剩下了他们两人。"
            "他十分愤怒感到生气，心中的愤怒无比绝望感到绝望。"
            "就在这时，猛然间，倒吸了一口凉气，瞳孔猛然收缩。"
            "这让他的心中升起了让天地让万物让所有人震惊的念头。"
            "他看见风雪；他看见长剑；他看见破碎的梦。"
        )
        res = deslop_service.analyze_deslop(bad_text)
        self.assertIn(res["verdict"], ("NOTICEABLE", "SEVERE"))
        self.assertGreater(res["ai_score"], 40.0)
        self.assertGreater(len(res["issues"]), 3)
        issue_types = {it["type"] for it in res["issues"]}
        self.assertTrue(issue_types & {"hollow_rhetoric", "tautology", "cliche", "parallelism"})

    def test_new_cliche_patterns_detected(self):
        text = (
            "他眼底闪过一丝复杂的暗芒，宛如一只断了线的风筝倒飞而出。"
            "嘴角微微勾起一抹玩味的笑意。毋庸置疑，这显而易见是不可置否的。"
        )
        res = deslop_service.analyze_deslop(text)
        self.assertGreater(len(res["issues"]), 0)
        labels = [it["label"] for it in res["issues"]]
        self.assertTrue(any("眼底" in lb for lb in labels))
        self.assertTrue(any("风筝" in lb for lb in labels))
        self.assertTrue(any("说明文论调" in lb for lb in labels))
        self.assertTrue(any("嘴角" in lb for lb in labels))

    def test_empty_and_non_cn(self):
        res = deslop_service.analyze_deslop("")
        self.assertEqual(res["stats"]["word_count"], 0)
        self.assertEqual(res["issues"], [])

    # --- 同构句检测回归（2026-10-11 修复四处缺陷） ---------------------------
    # 旧实现的失效模式：a) 要求前两字全同 → "他看见/他听见" 漏检；
    # b) 固定 3 句窗口 → 长链重复报告；c) index 恒指首次出现处 → 高亮错位；
    # d) 切句不认分号 → 分号串联的排比整段漏检。

    @staticmethod
    def _parallel_issues(res):
        return [it for it in res["issues"] if it["type"] == "parallelism"]

    def test_parallelism_detects_same_first_char_chain(self):
        """首字相同、后续不同（AI 腔最普遍形态）必须被检出。"""
        text = "他走进房间。他坐了下来。他看着窗外。"
        issues = self._parallel_issues(deslop_service.analyze_deslop(text))
        self.assertEqual(len(issues), 1, f"应检出 1 条同构句，实际 {len(issues)} 条")

    def test_parallelism_chain_is_not_reported_overlapping(self):
        """4 句同构链只报 1 条（旧版滑动窗口会报 2 条重叠问题）。"""
        text = "他看见天空。他看见大地。他看见海洋。他看见星辰。"
        issues = self._parallel_issues(deslop_service.analyze_deslop(text))
        self.assertEqual(len(issues), 1, f"长链应合并为 1 条，实际 {len(issues)} 条")
        # 整条链应完整出现在 snippet 中，而不是被截断成前 3 句
        self.assertIn("他看见星辰", issues[0]["snippet"])

    def test_parallelism_semicolon_clauses(self):
        """分号串联的排比必须被检出（旧版切句不认分号）。"""
        text = "他看见风雪；他看见长剑；他看见破碎的梦。"
        issues = self._parallel_issues(deslop_service.analyze_deslop(text))
        self.assertEqual(len(issues), 1, f"分号排比应检出 1 条，实际 {len(issues)} 条")

    def test_parallelism_index_points_at_real_occurrence(self):
        """重复文本中 index 必须指向该次真实出现位置，而非恒为首次。"""
        seg = "他看见天空。他看见大地。他看见海洋。"
        filler = "填充内容。" * 30
        text = seg + filler + seg
        issues = self._parallel_issues(deslop_service.analyze_deslop(text))
        self.assertEqual(len(issues), 2, f"两处同构链应各报 1 条，实际 {len(issues)} 条")
        offsets = sorted(it["index"] for it in issues)
        second_start = len(seg) + len(filler)
        self.assertEqual(offsets[0], 0)
        self.assertEqual(
            offsets[1], second_start,
            f"第二条 index 应为 {second_start}（真实位置），实际 {offsets[1]}",
        )

    def test_parallelism_does_not_flag_distinct_subjects(self):
        """不同主语的正常文学排比不得误报。"""
        text = "风卷起落叶。雨打湿窗棂。雷滚过天际。"
        issues = self._parallel_issues(deslop_service.analyze_deslop(text))
        self.assertEqual(issues, [], f"不应误报，实际 {len(issues)} 条")

    def test_parallelism_does_not_flag_first_person_narration(self):
        """第一人称连续「我」起句是正常写法，不得误报。

        2026-10-11 实测修正：首字集原本含「我」「你」，导致第一人称叙事
        被一律判为机械同构。而本项目 platform_service.PLATFORMS 里
        知乎盐言的定位正是「第一人称代入」——误报会打在最主流用户群上。
        修正为只收第三人称代词：叙述者反复点名「他」才是 AI 腔特征。
        """
        first_person = (
            "我走进那间屋子。我看见了墙上那张照片。我想起十年前的事。",
            "我没说话。我不想解释。我不需要谁来理解。",
            "你知道吗。你觉得呢。你倒是说句话啊。",
        )
        for text in first_person:
            res = deslop_service.analyze_deslop(text)
            self.assertEqual(
                self._parallel_issues(res), [],
                f"第一/第二人称叙事被误报为机械同构: {text}",
            )

    def test_parallelism_still_flags_third_person(self):
        """反向守卫：第三人称连续同主语仍须检出（修正不能过头）。"""
        for text in (
            "他走进房间。他坐了下来。他看着窗外。",
            "她走进房间。她坐了下来。她看着窗外。",
        ):
            res = deslop_service.analyze_deslop(text)
            self.assertEqual(
                len(self._parallel_issues(res)), 1,
                f"第三人称同构漏检: {text}",
            )

    def test_parallel_lead_char_set_excludes_first_person(self):
        """直接守卫首字集本身：不得再包含第一/第二人称代词。

        此前的缺口正是"判定集无任何测试守卫"——改坏了也没人知道。
        """
        chars = deslop_service._PARALLEL_LEAD_CHARS | deslop_service._PARALLEL_TAIL_LEAD_CHARS
        for ch in ("我", "你", "您", "咱"):
            self.assertNotIn(ch, chars, f"首字集不应包含第一/第二人称代词 {ch!r}")
        for ch in ("他", "她", "它"):
            self.assertIn(ch, chars, f"首字集应包含第三人称代词 {ch!r}")

    def test_parallelism_requires_three_clauses(self):
        """仅 2 句同构不构成机械排比，不报。"""
        text = "他看见天空。他看见大地。"
        issues = self._parallel_issues(deslop_service.analyze_deslop(text))
        self.assertEqual(issues, [])

    # --- 2026-10-11 新增规则组：补齐业界高毒级句式覆盖 ---------------------
    # 依据外部成熟实践（GitHub zenstory-ai/oh-story-claudecode, MIT 的
    # banned-words.md / deslop-gates.md 规则体系）做行为对照测试后补入。
    # 移植的是**规则与毒级分档**，实现仍为纯标准库正则，不引入其 JS 依赖。

    @staticmethod
    def _types(res):
        return {it["type"] for it in res["issues"]}

    def test_negation_flip_detected(self):
        """「不是A，而是B」——业界列为最高毒级的标志性 AI 判断式句式。"""
        for text in ("他不是冷漠，而是绝望。", "这并非巧合，而是安排。"):
            res = deslop_service.analyze_deslop(text)
            self.assertIn("negation_flip", self._types(res), f"未检出: {text}")

    def test_negation_flip_weight_is_highest(self):
        """该句式毒级最高，权重应高于普通俗套口癖（cliche=5）。"""
        res = deslop_service.analyze_deslop("他不是冷漠，而是绝望。")
        flip = [it for it in res["issues"] if it["type"] == "negation_flip"]
        self.assertTrue(flip)
        self.assertGreater(flip[0]["weight"], 5)

    def test_dangling_zhe_detected(self):
        """「，带着……」万能状语。"""
        res = deslop_service.analyze_deslop("他笑了一下，带着一丝不易察觉的嘲讽。")
        self.assertIn("dangling_zhe", self._types(res))

    def test_telling_cognition_detected(self):
        """「他知道…」认知直述：应改为用行为展示。"""
        for text in ("他知道这一切都来不及了。", "他这才意识到自己错了。"):
            res = deslop_service.analyze_deslop(text)
            self.assertIn("telling_cognition", self._types(res), f"未检出: {text}")

    def test_enumeration_detected(self):
        """机械列举式排比。"""
        res = deslop_service.analyze_deslop("有的人来了，有的人走了，有的人站着。")
        self.assertIn("enumeration", self._types(res))

    def test_enumeration_two_items_not_flagged(self):
        """反向守卫：「一边…一边」两项属正常写法，不得误报。"""
        res = deslop_service.analyze_deslop("他一边走一边看。")
        self.assertNotIn("enumeration", self._types(res))

    # --- 密度型检测（2026-10-11 新增） -------------------------------------
    # 单个「仿佛」「了一下」是正常中文，单点匹配必然误报；聚集才构成 AI 腔。
    # 移植业界「每千字密度门控」方法论，阈值按本项目文本规模重设。

    def test_micro_tic_density_flagged_when_clustered(self):
        """「了一下」式微动作口癖聚集时报。"""
        text = "他看了一眼，顿了一下，颤了一下，停了一下，想了一下。" * 2
        res = deslop_service.analyze_deslop(text)
        self.assertIn("micro_tic", self._types(res))

    def test_metaphor_density_flagged_when_clustered(self):
        """比喻词成片出现时报（advisory 级）。"""
        text = "好像要下雨。仿佛有风。宛如梦境。如同昨日。像刀一样。像是要哭。犹如潮水。"
        res = deslop_service.analyze_deslop(text)
        self.assertIn("metaphor_density", self._types(res))

    def test_cliched_modifier_density_flagged(self):
        """弱化副词（缓缓/微微/轻轻/淡淡）聚集时报。"""
        text = "她缓缓走来，微微低头，轻轻开口，淡淡一笑，一丝不安，一抹红晕，些许迟疑，几分犹豫。"
        res = deslop_service.analyze_deslop(text)
        self.assertIn("cliched_modifier", self._types(res))

    def test_reasoning_chain_flagged(self):
        """论证连接词（这意味着/也就是说）是小说叙事里最出戏的 AI 腔。"""
        text = "这意味着失败。也就是说没戏。关键在于时机。"
        res = deslop_service.analyze_deslop(text)
        self.assertIn("reasoning_chain", self._types(res))

    def test_density_rules_do_not_flag_isolated_usage(self):
        """反向守卫：孤立使用「微微」「看了一眼」属正常中文，不得误报。

        这是密度门控存在的全部理由——若退化成单点匹配，正常稿件会被
        大量误伤，用户会直接关掉这个功能。
        """
        text = (
            "他在雪地里走了一整夜，皮靴踩碎冰壳发出沉闷的脆响。"
            "推开木门时，炉火已经熄了，只有余烬微微泛着暗红。"
            "他看了一眼窗外，天快亮了。"
        )
        res = deslop_service.analyze_deslop(text)
        density_types = {"micro_tic", "metaphor_density", "cliched_modifier",
                         "reasoning_chain", "action_list", "negation_pair"}
        hit = density_types & self._types(res)
        self.assertEqual(hit, set(), f"孤立使用被误报为聚集: {hit}")

    def test_repeated_pattern_chain_reported_once(self):
        """连续重复的输入不得逐位置刷屏。

        实测缺陷：`re.finditer` 对「一边」×10000 会在每个位置各匹配一次，
        enumeration 规则产出上万条目，把 issues[:30] 配额占满，真实问题
        被挤出视野。同构句那边已用贪心链解决，此处对规则表统一做重叠合并。
        """
        res = deslop_service.analyze_deslop("一边" * 500)
        enum = [it for it in res["issues"] if it["type"] == "enumeration"]
        self.assertEqual(len(enum), 1, f"重复链应合并为 1 条，实际 {len(enum)} 条")

    def test_separated_hits_are_not_merged(self):
        """反向守卫：彼此分离的多处命中不得被合并（合并只针对位置重叠）。"""
        text = "他一边走一边看一边想。" + "正常叙述内容。" * 50 + "她一边哭一边笑一边喊。"
        res = deslop_service.analyze_deslop(text)
        enum = [it for it in res["issues"] if it["type"] == "enumeration"]
        self.assertEqual(len(enum), 2, f"两处分离命中应各报 1 条，实际 {len(enum)} 条")

    def test_new_rules_do_not_false_positive_on_natural_prose(self):
        """反向守卫：自然白话散文不得被新增规则误伤。"""
        text = (
            "他在雪地里走了一整夜，皮靴踩碎冰壳发出沉闷的脆响。"
            "推开木门时，炉火已经熄了，只有余烬微微泛着暗红。"
        )
        res = deslop_service.analyze_deslop(text)
        self.assertEqual(res["issues"], [], f"误报: {res['issues']}")
        self.assertEqual(res["verdict"], "NATURAL")

    # --- Exoscribe 英文去 AI 味排毒引擎测试（International Edition） ---

    def test_english_natural_text(self):
        """反向守卫：地道自然的英文文本不得被误报。"""
        text = (
            "He walked through the damp alley, boots crunching on broken glass. "
            "The cold rain seeped through his coat collar, soaking the back of his neck. "
            "A stray cat dashed past a row of rusted trash bins."
        )
        res = deslop_service.analyze_deslop(text)
        self.assertEqual(res["verdict"], "NATURAL")
        self.assertLess(res["ai_score"], 18.0)
        self.assertEqual(res["issues"], [])
        self.assertGreater(res["stats"]["word_count"], 25)

    def test_english_hollow_rhetoric_and_cliches(self):
        """检出英文 LLM 高频俗套虚辞（testament to / delve into / tapestry / beacon of hope 等）。"""
        text = (
            "His bravery was a testament to the human spirit, a beacon of hope in the dark. "
            "She decided to delve deep into the rich tapestry of ancient mysteries. "
            "The dance of shadows flickered on the wall, and the air was thick with tension. "
            "A shiver ran down his spine as he felt a palpable sense of dread."
        )
        res = deslop_service.analyze_deslop(text)
        self.assertIn(res["verdict"], ("NOTICEABLE", "SEVERE"))
        self.assertGreater(res["ai_score"], 35.0)
        self.assertGreaterEqual(len(res["issues"]), 4)
        issue_types = {it["type"] for it in res["issues"]}
        self.assertIn("hollow_rhetoric", issue_types)

    def test_english_filter_words_and_negation_flip(self):
        """检出英文感知过滤词 (could see/hear, watched as) 与否定翻转句式。"""
        text = (
            "He could hear the distant footsteps echoing down the hall. "
            "She watched as the dark carriage rolled away into the mist. "
            "It was not just fear, but a desperate instinct to survive. "
            "She whispered softly while he replied coldly."
        )
        res = deslop_service.analyze_deslop(text)
        types = {it["type"] for it in res["issues"]}
        self.assertTrue(types & {"filter_words", "negation_flip", "adverb_tics"})

    def test_english_extended_slop_patterns(self):
        """检出扩展的英文八股指纹 (labyrinthine / resonated deeply / palpable tension / shivers / 分词悬垂)。"""
        text = (
            "They navigated the labyrinthine corridors beneath the castle. "
            "Her tragic story resonated deeply with his own sorrow. "
            "The tension was palpable between the two generals. "
            "A dark voice sent shivers down their spines. "
            "Looking up at the night sky, he wondered if they would survive."
        )
        res = deslop_service.analyze_deslop(text)
        self.assertGreaterEqual(len(res["issues"]), 5)
        labels = [it["label"] for it in res["issues"]]
        self.assertTrue(any("Labyrinthine" in lb for lb in labels))
        self.assertTrue(any("Resonated deeply" in lb for lb in labels))
        self.assertTrue(any("Palpable tension" in lb for lb in labels))
        self.assertTrue(any("Shiver down spine" in lb for lb in labels))
        self.assertTrue(any("Dangling participial" in lb for lb in labels))

    def test_english_parallelism_starters(self):
        """连续 3 句以相同代词起句（He... He... He...）应检出句式单调排比。"""
        text = (
            "He opened the wooden door. "
            "He walked to the dust-covered desk. "
            "He picked up the old brass key."
        )
        res = deslop_service.analyze_deslop(text)
        parallel = [it for it in res["issues"] if it["type"] == "parallelism"]
        self.assertEqual(len(parallel), 1)
        self.assertIn("He", parallel[0]["label"])

    def test_english_adverb_overuse_density(self):
        """当篇幅超过 50 词且 -ly 副词比例过高时，应触发副词密度告警。"""
        text = (
            "He quickly ran, breathing heavily and staring wildly at the dark road. "
            "She suddenly stopped, completely shocked and utterly confused. "
            "They slowly walked, carefully watching, quietly waiting, deeply hoping, "
            "nervously trembling, excitedly whispering, and terribly shaking in the cold night."
        )
        res = deslop_service.analyze_deslop(text)
        types = {it["type"] for it in res["issues"]}
        self.assertIn("adverb_overuse", types)
        self.assertGreater(res["stats"]["adverb_density"], 4.5)

    def test_english_lang_dispatch_and_router(self):
        """验证 lang 显式分发与 router 接口连通性。"""
        # 显式 lang="en" 即使包含少量其他字符也能进入英文管线
        res = deslop_service.analyze_deslop("A testament to our resolve.", lang="en")
        self.assertEqual(res["stats"]["word_count"], 5)
        self.assertTrue(any(it["type"] == "hollow_rhetoric" for it in res["issues"]))

        # router _h_writing_deslop 连通性
        body = {"text": "She decided to delve deep into the rich tapestry of life.", "lang": "en"}
        resp = router._h_writing_deslop({}, body)
        self.assertEqual(resp["code"], 0)
        self.assertIn("ai_score", resp["data"])
        self.assertGreater(resp["data"]["stats"]["word_count"], 0)


class TestWritingExportAndReorder(unittest.TestCase):
    def setUp(self):
        self._iso = _isolation.isolate_paths(Path(tempfile.mkdtemp(prefix="deslop_exp_")))
        self._iso.__enter__()
        db.init_schema()
        db.apply_migrations()

        # 准备一个测试项目和章节
        self.project = "测试导出项目"
        pdir = config.NOVEL_DIR / self.project / "chapters" / "arc-1"
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "chapter-001.txt").write_text("第一章 问剑雪山\n\n寒风凛冽，少年拔剑。", encoding="utf-8")
        (pdir / "chapter-002.txt").write_text("第二章 破空一击\n\n剑气如虹，划破夜空。", encoding="utf-8")

    def tearDown(self):
        db.close()
        self._iso.__exit__(None, None, None)

    def test_export_txt(self):
        res = writing_extra.export_project(self.project, fmt="txt")
        self.assertEqual(res["format"], "txt")
        self.assertEqual(res["chapters"], 2)
        self.assertIn("第一章 问剑雪山", res["content"])

    def test_export_md(self):
        res = writing_extra.export_project(self.project, fmt="md")
        self.assertEqual(res["format"], "md")
        self.assertEqual(res["chapters"], 2)
        self.assertTrue(res["filename"].endswith(".md"))
        self.assertIn(f"# {self.project}", res["content"])
        self.assertIn("## 第一章 问剑雪山", res["content"])

    def test_export_docx_validity(self):
        res = writing_extra.export_project(self.project, fmt="docx")
        self.assertEqual(res["format"], "docx")
        self.assertEqual(res["chapters"], 2)
        self.assertTrue(res["filename"].endswith(".docx"))
        self.assertIn("content_base64", res)

        # 校验 base64 解码并解开合法的 zip 包
        raw_docx = base64.b64decode(res["content_base64"])
        buf = io.BytesIO(raw_docx)
        self.assertTrue(zipfile.is_zipfile(buf))
        with zipfile.ZipFile(buf, "r") as z:
            names = z.namelist()
            self.assertIn("[Content_Types].xml", names)
            self.assertIn("_rels/.rels", names)
            self.assertIn("word/document.xml", names)
            doc_xml = z.read("word/document.xml").decode("utf-8")
            self.assertIn("第一章 问剑雪山", doc_xml)
            self.assertIn("破空一击", doc_xml)

    def test_reorder_outlines(self):
        # 插入两条大纲
        o1 = writing_extra.create_outline(self.project, "chapter", "初始第1章", "概要1", "planned", 0)
        o2 = writing_extra.create_outline(self.project, "chapter", "初始第2章", "概要2", "planned", 1)
        # 调换顺序
        reordered = writing_extra.reorder_outlines(self.project, [o2["id"], o1["id"]])
        self.assertEqual(len(reordered), 2)
        self.assertEqual(reordered[0]["id"], o2["id"])
        self.assertEqual(reordered[0]["sort_order"], 0)
        self.assertEqual(reordered[1]["id"], o1["id"])
        self.assertEqual(reordered[1]["sort_order"], 1)

        # 非法 ID 与非列表类型防御断言
        with self.assertRaises(writing_extra.ServiceError) as cm:
            writing_extra.reorder_outlines(self.project, ["invalid_id"])
        self.assertEqual(cm.exception.code, 400)
        with self.assertRaises(writing_extra.ServiceError) as cm:
            writing_extra.reorder_outlines(self.project, "not_a_list")  # type: ignore
        self.assertEqual(cm.exception.code, 400)

    def test_docx_illegal_xml_control_chars_filtered(self):
        # 写入含有 XML 1.0 非法控制字符的内容（如 \x00, \x08, \x0b, \x1f）
        dirty_project = "测试XML过滤项目"
        pdir = config.NOVEL_DIR / dirty_project / "chapters" / "arc-1"
        pdir.mkdir(parents=True, exist_ok=True)
        dirty_text = "第三章 绝壁暗涌\x00\x08\x0b\x1f\n\n寒芒一闪\x0c，生死已分。"
        (pdir / "chapter-003.txt").write_text(dirty_text, encoding="utf-8")

        res = writing_extra.export_project(dirty_project, fmt="docx")
        self.assertEqual(res["format"], "docx")
        raw_docx = base64.b64decode(res["content_base64"])
        buf = io.BytesIO(raw_docx)
        self.assertTrue(zipfile.is_zipfile(buf))
        with zipfile.ZipFile(buf, "r") as z:
            doc_xml = z.read("word/document.xml").decode("utf-8")
            # 非法控制字符已被过滤
            for bad_char in ["\x00", "\x08", "\x0b", "\x0c", "\x1f"]:
                self.assertNotIn(bad_char, doc_xml)
            # 合法文字正常保留
            self.assertIn("第三章 绝壁暗涌", doc_xml)
            self.assertIn("寒芒一闪", doc_xml)
            # 校验排版保真：xml:space 与 中文字体规范
            self.assertIn('xml:space="preserve"', doc_xml)
            self.assertIn('w:eastAsia="宋体"', doc_xml)

    def test_export_epub_validity(self):
        res = writing_extra.export_project(self.project, fmt="epub")
        self.assertEqual(res["format"], "epub")
        self.assertEqual(res["chapters"], 2)
        self.assertTrue(res["filename"].endswith(".epub"))
        self.assertIn("content_base64", res)

        raw_epub = base64.b64decode(res["content_base64"])
        buf = io.BytesIO(raw_epub)
        self.assertTrue(zipfile.is_zipfile(buf))
        with zipfile.ZipFile(buf, "r") as z:
            infos = z.infolist()
            # EPUB 规范硬性要求：mimetype 必须是第一个 entry 且必须无压缩 (ZIP_STORED)
            self.assertEqual(infos[0].filename, "mimetype")
            self.assertEqual(infos[0].compress_type, zipfile.ZIP_STORED)
            self.assertEqual(z.read("mimetype").strip(), b"application/epub+zip")

            names = z.namelist()
            self.assertIn("META-INF/container.xml", names)
            self.assertIn("OEBPS/content.opf", names)
            self.assertIn("OEBPS/toc.xhtml", names)
            self.assertIn("OEBPS/style.css", names)
            self.assertIn("OEBPS/chapter_001.xhtml", names)
            self.assertIn("OEBPS/chapter_002.xhtml", names)

            opf_xml = z.read("OEBPS/content.opf").decode("utf-8")
            self.assertIn("urn:uuid:", opf_xml)
            self.assertIn("chapter_001", opf_xml)

            ch1_xml = z.read("OEBPS/chapter_001.xhtml").decode("utf-8")
            self.assertIn("第一章 问剑雪山", ch1_xml)
            self.assertIn("寒风凛冽，少年拔剑。", ch1_xml)

    def test_export_shunn_validity(self):
        res = writing_extra.export_project_shunn(
            self.project,
            author_name="Lin Dong",
            contact_info="lindong@example.com",
        )
        self.assertEqual(res["format"], "shunn")
        self.assertEqual(res["chapters"], 2)
        self.assertTrue(res["filename"].endswith(".txt"))
        content = res["content"]
        self.assertIn("Lin Dong", content)
        self.assertIn("lindong@example.com", content)
        self.assertIn("About ", content)
        self.assertIn("words", content)
        self.assertIn(self.project.upper(), content)
        self.assertIn("by Lin Dong", content)
        self.assertIn("#\n\n", content)  # Shunn 标杆分卷/章节切换符
        self.assertIn("第一章 问剑雪山", content)

        # 验证统一路由别名
        res_alias = writing_extra.export_project(self.project, fmt="shunn")
        self.assertEqual(res_alias["format"], "shunn")
        res_alias_ms = writing_extra.export_project(self.project, fmt="manuscript")
        self.assertEqual(res_alias_ms["format"], "shunn")

    def test_export_empty_project_raises_404(self):
        empty_project = "空项目测试"
        with self.assertRaises(writing_extra.ServiceError) as cm_epub:
            writing_extra.export_project_epub(empty_project)
        self.assertEqual(cm_epub.exception.code, 404)

        with self.assertRaises(writing_extra.ServiceError) as cm_shunn:
            writing_extra.export_project_shunn(empty_project)
        self.assertEqual(cm_shunn.exception.code, 404)

    def test_router_deslop_endpoint(self):
        res = router._h_writing_deslop({}, {"text": "这一刻时间仿佛凝固了。"})
        self.assertEqual(res["code"], 0)
        self.assertIn("ai_score", res["data"])


if __name__ == "__main__":
    unittest.main()
