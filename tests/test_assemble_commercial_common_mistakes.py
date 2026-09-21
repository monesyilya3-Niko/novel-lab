#!/usr/bin/env python3
"""commercial-obs.common_mistakes 组装兜底回归（2026-09-21）。

背景：该字段**不来自** pass4_commercial.json，而是人工后补进资产文件的。
每次 `novel.py 组装` 重新生成 commercial-obs 都会静默丢掉它——
sangshi_chosen 与 暮冬念春 各踩一次，两次都靠人工从备份补回。

修复：`assemble_obs` 在 kind == "commercial" 且字段缺失时按同一口径兜底
（非新造观察）：
  1) 优先取 pass4 的 opening_analysis.common_mistakes；
  2) 否则由本卡 retention_risk_points 汇总，dict 项转成 "position：reason"。

设计约束：不读、不写任何真实资产，全部在内存里构造。

用法：
  python -m unittest tests.test_assemble_commercial_common_mistakes -v
  python run_tests.py     # 自动 discover
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import assemble  # noqa: E402

GENRE = "realistic-romance"


class TestCommercialCommonMistakes(unittest.TestCase):
    """commercial-obs 的 common_mistakes 兜底行为。"""

    def test_keeps_pass4_provided_field(self):
        """pass4 自带该字段时原样保留，不覆盖。"""
        out = assemble.assemble_obs("commercial", "书", GENRE, {
            "common_mistakes": ["A", "B"],
        })
        self.assertEqual(out["common_mistakes"], ["A", "B"])

    def test_prefers_opening_analysis(self):
        """有 opening_analysis.common_mistakes 时优先用它。"""
        out = assemble.assemble_obs("commercial", "书", GENRE, {
            "opening_analysis": {"common_mistakes": ["X"]},
            "retention_risk_points": ["不该被采用"],
        })
        self.assertEqual(out["common_mistakes"], ["X"])

    def test_falls_back_to_retention_risk_points(self):
        """无其他来源时由 retention_risk_points 汇总。"""
        out = assemble.assemble_obs("commercial", "书", GENRE, {
            "retention_risk_points": [
                {"position": "第1章", "reason": "驱动力后置"},
                {"position": "第2-4章", "reason": "兑付强度低"},
            ],
        })
        self.assertEqual(
            out["common_mistakes"],
            ["第1章：驱动力后置", "第2-4章：兑付强度低"],
        )

    def test_string_risk_points_kept_as_is(self):
        """字符串型风险点原样保留。"""
        out = assemble.assemble_obs("commercial", "书", GENRE, {
            "retention_risk_points": ["纯字符串风险"],
        })
        self.assertEqual(out["common_mistakes"], ["纯字符串风险"])

    def test_output_is_list_of_str(self):
        """兜底产物必须是字符串列表（下游按字符串消费）。"""
        out = assemble.assemble_obs("commercial", "书", GENRE, {
            "retention_risk_points": [{"position": "第1章", "reason": "R"}],
        })
        self.assertIsInstance(out["common_mistakes"], list)
        self.assertTrue(all(isinstance(x, str) for x in out["common_mistakes"]))

    def test_no_source_no_field(self):
        """三个来源都空时不生成该字段（不新造）。"""
        out = assemble.assemble_obs("commercial", "书", GENRE, {})
        self.assertNotIn("common_mistakes", out)

    def test_does_not_leak_into_structure(self):
        """structure-obs 分支不受影响。"""
        out = assemble.assemble_obs("structure", "书", GENRE, {
            "retention_risk_points": ["不应触发"],
        })
        self.assertNotIn("common_mistakes", out)

    def test_dict_without_position_still_usable(self):
        """dict 缺 position 时退化为只用 reason。"""
        out = assemble.assemble_obs("commercial", "书", GENRE, {
            "retention_risk_points": [{"reason": "只有原因"}],
        })
        self.assertEqual(out["common_mistakes"], ["只有原因"])


if __name__ == "__main__":
    unittest.main()
