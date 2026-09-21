"""英文章末钩：多语料检测不得对英文章恒 0 分。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from chapter_check import check_hook  # noqa: E402


class TestEnglishHook(unittest.TestCase):
    def test_english_question_hook(self):
        score, detail = check_hook(
            "He looked at the fog and wondered what would happen next.\n\n"
            "Could it be that the Fool was watching him?\n"
        )
        self.assertGreater(score, 0, detail)

    def test_english_suddenly_hook(self):
        score, detail = check_hook(
            "The potion settled in his stomach.\n\n"
            "Suddenly, the gray fog swallowed the room.\n"
        )
        self.assertGreater(score, 0, detail)

    def test_english_but_hook(self):
        score, detail = check_hook(
            "He smiled and counted the soli.\n\n"
            "But he did not know what waited on the deck.\n"
        )
        self.assertGreater(score, 0, detail)

    def test_chinese_hook_still_scores(self):
        score, detail = check_hook("她合上书，走到窗边。\n\n她不知道，门外已经站了人。\n")
        self.assertGreater(score, 0, detail)


if __name__ == "__main__":
    unittest.main()
