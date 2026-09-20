#!/usr/bin/env python3
"""钩子/开头口径重标定回归（2026-09-21）。按文件动态加载 scripts/chapter_check.py。"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("chapter_check", ROOT / "scripts" / "chapter_check.py")
cc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cc)


class TestHookRecalibration(unittest.TestCase):
    def test_three_hits_plus_close_is_full(self):
        # 句末标点 + 忽然 + 她不知道，且末行正常收束（>15字避免 short 路径干扰断言）
        text = "前面是日常的铺垫。\n忽然手机响了。\n她不知道那通电话究竟意味着什么。\n"
        score, detail = cc.check_hook(text)
        self.assertEqual(score, 12.0)
        self.assertIn("hits=", detail)
        self.assertIn("closed=1", detail)

    def test_two_hits_long_close_is_nine(self):
        # 仅句末标点 + 忽然，末行较长（>15字）→ 9 分
        text = "前面是安静的日常铺垫段落。\n忽然一切安静下来，安静得让人不安。\n"
        score, detail = cc.check_hook(text)
        self.assertEqual(score, 9.0)
        self.assertIn("hits=2", detail)
        self.assertIn("closed=1", detail)
        self.assertIn("short=0", detail)

    def test_two_hits_short_close_is_ten(self):
        # 仅句末标点 + 忽然，末行极短且不含其它钩子词
        text = "前面说了许多。\n忽然一切安静。\n他停住了。\n"
        score, detail = cc.check_hook(text)
        self.assertEqual(score, 10.0)
        self.assertIn("hits=2", detail)
        self.assertIn("short=1", detail)

    def test_unclosed_with_hits_scores_below_full(self):
        text = "忽然手机响了。她不知道明天会怎样。她转身推开门"
        score, detail = cc.check_hook(text)
        self.assertLessEqual(score, 9.0)
        self.assertIn("closed=0", detail)

    def test_truncation_flagged(self):
        text = "忽然手机响了。她不知道明天会怎样。这个答案悬在半空没有说完"
        score, detail = cc.check_hook(text)
        self.assertIn("trunc=1", detail)
        self.assertLessEqual(score, 6.0)

    def test_contrast_words_count_as_hit(self):
        text = "可是他没有回头。\n"
        score, detail = cc.check_hook(text)
        self.assertGreaterEqual(score, 6.0)
        self.assertIn("hits=", detail)

    def test_old_cliff_gone(self):
        """回归：3 命中 + 收束不得再停在 11。"""
        text = "日常叙述。\n忽然有人敲门。\n她不知道是谁。\n明天再说吧。\n"
        score, _ = cc.check_hook(text)
        self.assertNotEqual(score, 11.0)
        self.assertEqual(score, 12.0)

    def test_no_hook_no_close_is_zero(self):
        text = "平淡的一段叙述没有任何起伏"
        score, detail = cc.check_hook(text)
        self.assertLessEqual(score, 3.0)
        self.assertIn("closed=0", detail)


class TestOpeningVocabulary(unittest.TestCase):
    def test_leading_blank_lines_stripped(self):
        text = "\n\n\n会议室里灯亮着，大家坐下开会。\n"
        score, detail = cc.check_opening(text)
        self.assertIn("场景建立", detail)
        self.assertGreaterEqual(score, 4)

    def test_lane_and_meeting_room_counted(self):
        text = "巷口的灯坏了一半。会议室的门开着。她走进去。"
        score, detail = cc.check_opening(text)
        self.assertIn("场景建立", detail)

    def test_action_words_recount(self):
        text = "她把围裙叠好，递过去，签完字才走。"
        score, detail = cc.check_opening(text)
        self.assertIn("动作开场", detail)

    def test_dare_not_counts_as_conflict(self):
        text = "会议室灯亮着，谁都不敢先开口。她坐下。"
        score, detail = cc.check_opening(text)
        self.assertIn("冲突引入", detail)
        self.assertIn("场景建立", detail)


if __name__ == "__main__":
    unittest.main()
