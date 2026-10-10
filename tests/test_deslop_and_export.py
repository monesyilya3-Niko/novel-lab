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
