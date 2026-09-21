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

    def test_fractional_per_full_marks_not_issue(self):
        """角色数不整除 35 时 per 为分数，分子分母必须同精度显示。

        回归：13 角色 → per=2.6923。曾因分母用 :.0f 显示为「3」、分子用
        :.1f 显示为「2.7」，使**满分**角色被记为假 issue（真实书稿上 13 角色
        × 2 维度 = 26 条假 low）。
        """
        per = 35 / 13
        full_line = f"温霜禾: 命中 6/6 核心词(['没事']) → {round(per, 1):.1f}/{per:.1f}"
        self.assertEqual(full_line, "温霜禾: 命中 6/6 核心词(['没事']) → 2.7/2.7")
        self.assertFalse(qc._detail_is_meaningful_issue(full_line))

    def test_fractional_per_partial_marks_still_issue(self):
        """同一精度修正在「真不满分」时不得吞掉 issue（保召回）。"""
        per = 35 / 13
        low_line = f"温霜禾: 命中 1/6 核心词(['没事']) → {round(per * 0.7, 1):.1f}/{per:.1f}"
        self.assertTrue(qc._detail_is_meaningful_issue(low_line))


class TestVoiceIssueNotDoubleLogged(unittest.TestCase):
    """逐角色声线明细只归 character_arc，craft 不得重复登记同一条。"""

    CARD = {"dialogue": {"character_voices": [
        {"name": "温霜禾", "speech_signature": {"verbal_tics": ["没事", "好", "嗯", "谢谢"]}},
        {"name": "江春屿", "speech_signature": {"verbal_tics": ["顺路", "习惯了", "算", "知道了"]}},
    ]}}

    def test_below_full_voice_line_not_duplicated_in_craft(self):
        texts = {1: "江春屿说：嗯。"}  # 只命中 1 个核心词 → 声线真不满分
        arc = qc._dim_character_arc(texts, self.CARD)
        craft = qc._dim_craft(texts, self.CARD)
        arc_lines = {i["detail"].strip() for i in arc.issues}
        craft_lines = {i["detail"].strip() for i in craft.issues}
        self.assertTrue(arc_lines, "声线不满分时应由 character_arc 登记")
        self.assertEqual(arc_lines & craft_lines, set(), "craft 不得重复登记声线明细")

    def test_craft_keeps_its_own_issues(self):
        """去重不得误伤 craft 自有子项（情绪/意象等）。"""
        texts = {1: "江春屿说：嗯。"}
        craft = qc._dim_craft(texts, self.CARD)
        types = " ".join(i["detail"] for i in craft.issues)
        self.assertTrue(any(k in types for k in ("体感词", "意象", "直陈")),
                        f"craft 自有 issue 被误删：{craft.issues}")


if __name__ == "__main__":
    unittest.main()
