#!/usr/bin/env python3
"""inject.py render 函数覆盖测试（出版级补强）。

prompt 渲染是写书链路的核心纯逻辑，离线可测。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import inject as inject_mod


class TestRenderNarration(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(inject_mod.render_narration({}), "（无叙述层数据）")
        self.assertEqual(inject_mod.render_narration(None), "（无叙述层数据）")

    def test_basic(self):
        s = inject_mod.render_narration({"pov": "第一人称"})
        self.assertIn("第一人称", s)

    def test_full(self):
        s = inject_mod.render_narration({
            "pov": "第三人称",
            "pov_switch_rule": "不切换",
            "tense_feel": "近",
            "sentence_rhythm": {"burst_pattern": "打斗时短句"},
            "paragraph": {"usage_of_single_line": "强调"},
        })
        self.assertIn("第三人称", s)
        self.assertIn("打斗时短句", s)
        self.assertIn("强调", s)


class TestVtToStr(unittest.TestCase):
    def test_str(self):
        self.assertEqual(inject_mod._vt_to_str("呵呵"), "呵呵")

    def test_dict(self):
        r = inject_mod._vt_to_str({"情境": "开心", "规则": "多用"})
        self.assertIsInstance(r, str)
        self.assertTrue(r)


class TestRenderVoices(unittest.TestCase):
    def test_empty(self):
        s = inject_mod.render_voices([])
        self.assertIsInstance(s, str)

    def test_basic(self):
        s = inject_mod.render_voices([{"name": "主角", "voice": "冷静"}])
        self.assertIn("主角", s)


class TestRenderEmotion(unittest.TestCase):
    def test_empty(self):
        s = inject_mod.render_emotion({})
        self.assertIsInstance(s, str)

    def test_basic(self):
        s = inject_mod.render_emotion({"arc": "上升"})
        self.assertIsInstance(s, str)


class TestRenderImagery(unittest.TestCase):
    def test_empty(self):
        s = inject_mod.render_imagery({})
        self.assertIsInstance(s, str)

    def test_basic(self):
        s = inject_mod.render_imagery({"motifs": ["雪", "火"]})
        self.assertIsInstance(s, str)


class TestRenderBanned(unittest.TestCase):
    def test_basic(self):
        s = inject_mod.render_banned({"never_used_words": ["词1", "词2"]})
        self.assertIn("词1", s)

    def test_empty(self):
        self.assertEqual(inject_mod.render_banned({}), "（无禁忌数据）")


class TestRenderStructureObs(unittest.TestCase):
    def test_empty(self):
        s = inject_mod.render_structure_obs({})
        self.assertIsInstance(s, str)


class TestRenderGenrePack(unittest.TestCase):
    def test_empty(self):
        s = inject_mod.render_genre_pack({})
        self.assertIsInstance(s, str)


class TestRetrieveForIntent(unittest.TestCase):
    def test_basic(self):
        r = inject_mod.retrieve_for_intent("写对话", distilled=None, genre="campus")
        self.assertIsInstance(r, list)


if __name__ == "__main__":
    unittest.main()
