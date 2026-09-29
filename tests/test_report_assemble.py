#!/usr/bin/env python3
"""report.py / assemble.py 纯函数覆盖测试（出版级补强）。

报告长度门禁、置信度计算、章节构建等核心纯逻辑，离线可测。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import assemble as assemble_mod
import report as report_mod


class TestCombinedReportOk(unittest.TestCase):
    def test_below_threshold(self):
        r = report_mod.combined_report_ok(3000, 3000)
        self.assertFalse(r["ok"])
        self.assertEqual(r["total"], 6000)

    def test_above_threshold(self):
        r = report_mod.combined_report_ok(6000, 6000)
        self.assertTrue(r["ok"])

    def test_zero(self):
        r = report_mod.combined_report_ok(0, 0)
        self.assertFalse(r["ok"])
        self.assertEqual(r["total"], 0)

    def test_none_safe(self):
        r = report_mod.combined_report_ok(None, None)
        self.assertEqual(r["total"], 0)


class TestJoin(unittest.TestCase):
    def test_list(self):
        self.assertEqual(report_mod._join(["a", "b"]), "a、b")

    def test_custom_sep(self):
        self.assertEqual(report_mod._join(["a", "b"], sep=","), "a,b")

    def test_non_list(self):
        self.assertEqual(report_mod._join("x"), "x")


class TestSectionMeta(unittest.TestCase):
    def test_basic(self):
        s = report_mod.section_meta({"genre": "校园", "source_title": "测试书"})
        self.assertIn("校园", s)
        self.assertIn("测试书", s)

    def test_empty(self):
        s = report_mod.section_meta({})
        self.assertIsInstance(s, str)


class TestConfidence(unittest.TestCase):
    def test_few_chapters_capped(self):
        self.assertEqual(assemble_mod._confidence(5), 0.6)

    def test_many_chapters(self):
        c = assemble_mod._confidence(20)
        self.assertGreater(c, 0.6)
        self.assertLessEqual(c, 0.9)

    def test_boundary(self):
        self.assertEqual(assemble_mod._confidence(9), 0.6)


class TestSampleWords(unittest.TestCase):
    def test_basic(self):
        n = assemble_mod._sample_words({"selected_count": 5}, {"avg_words": 2000})
        self.assertIsInstance(n, int)

    def test_empty(self):
        n = assemble_mod._sample_words({}, {})
        self.assertIsInstance(n, int)


class TestLoadJson(unittest.TestCase):
    def test_missing(self):
        with self.assertRaises(OSError):
            assemble_mod.load_json(Path("/nonexistent/x.json"))


if __name__ == "__main__":
    unittest.main()
