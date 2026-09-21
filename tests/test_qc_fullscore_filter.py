"""QC：满分成功日志不得记为 craft / character_arc issue。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import qc  # noqa: E402


class TestDetailIsMeaningfulIssue(unittest.TestCase):
    def test_full_score_voice_log_not_issue(self):
        self.assertFalse(
            qc._detail_is_meaningful_issue("温霜禾: 命中 5/5 核心词 → 7.0/7"))

    def test_full_score_partial_hit_still_not_issue(self):
        # 命中 4/5 但子项满分 → 不记 issue（维度满分成功日志）
        self.assertFalse(
            qc._detail_is_meaningful_issue("周敏: 命中 4/5 → 7.0/7"))

    def test_full_score_craft_subdims_not_issue(self):
        self.assertFalse(qc._detail_is_meaningful_issue("体感词命中 47 → 20.0/20"))
        self.assertFalse(qc._detail_is_meaningful_issue("意象领域命中 26 → 10/10"))

    def test_partial_score_is_issue(self):
        self.assertTrue(
            qc._detail_is_meaningful_issue("温霜禾: 命中 2/5 核心词 → 2.8/7"))
        self.assertTrue(qc._detail_is_meaningful_issue("体感词命中 3 → 4.0/20"))

    def test_no_arrow_not_issue(self):
        self.assertFalse(qc._detail_is_meaningful_issue("本章无角色出场"))

    def test_arrow_without_fraction_kept_as_issue(self):
        self.assertTrue(qc._detail_is_meaningful_issue("声线漂移 → 需人工复核"))


class TestDimIssuesFilter(unittest.TestCase):
    def test_character_arc_full_score_no_issues(self):
        card = {"dialogue": {"character_voices": [{"name": "温霜禾", "catchphrases": ["没事"]}]}}
        texts = {1: "温霜禾说：没事。"}
        dim = qc._dim_character_arc(texts, card)
        # 无论得分如何，若 raw details 皆为满分形态，issues 应为空
        for it in dim.issues:
            self.assertNotIn("→ 7.0/7", it["detail"])
            self.assertNotIn("→ 20.0/20", it["detail"])
            self.assertNotIn("→ 10/10", it["detail"])


if __name__ == "__main__":
    unittest.main()
