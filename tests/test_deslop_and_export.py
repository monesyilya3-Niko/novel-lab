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

    def test_new_rules_do_not_false_positive_on_natural_prose(self):
        """反向守卫：自然白话散文不得被新增规则误伤。"""
        text = (
            "他在雪地里走了一整夜，皮靴踩碎冰壳发出沉闷的脆响。"
            "推开木门时，炉火已经熄了，只有余烬微微泛着暗红。"
        )
        res = deslop_service.analyze_deslop(text)
        self.assertEqual(res["issues"], [], f"误报: {res['issues']}")
        self.assertEqual(res["verdict"], "NATURAL")


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

    def test_router_deslop_endpoint(self):
        res = router._h_writing_deslop({}, {"text": "这一刻时间仿佛凝固了。"})
        self.assertEqual(res["code"], 0)
        self.assertIn("ai_score", res["data"])


if __name__ == "__main__":
    unittest.main()
