#!/usr/bin/env python3
"""
novel-lab P3 万字分析报告回归测试（纯标准库 unittest，零第三方依赖）。

对应架构师设计 system_design_P3_genre_isolation_report.md §4 T07，覆盖两条铁律二的
执行机制：

  1. deep_analyze 三函数对 7 个深度字段缺失/齐全时的行为：
     - check_technique_depth 识别缺失字段（绝不编造内容）；
     - ensure_technique_depth 只补结构（空串占位），不填充内容；
     - analyze_craft_card 统计 total/complete/incomplete + missing_map。
  2. 报告长度 <10000 字符时触发硬校验失败（MIN_REPORT_CHARS 门槛）；
     ≥10000 字符通过（用足够长的合成内容验证）。

用法：
  python run_tests.py            # 自动 discover 本文件（pattern test_*.py）
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    """按文件名从 scripts/ 动态加载模块（与 test_distill/test_trope_library 同模式）。"""
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


DEEP_ANALYZE = _load("deep_analyze")
REPORT_CRAFT = _load("report_craft")
REPORT = _load("report")


# 7 个深度字段（与 deep_analyze.TECHNIQUE_DEEP_FIELDS 对齐）
DEEP_FIELDS = [
    "reader_psychology",
    "execution_steps",
    "applicable_scene",
    "usage_boundary",
    "intensity_control",
    "combo_patterns",
    "migration_checklist",
]


def _full_deep_analysis():
    """构造 7 个深度字段全部非空的 deep_analysis dict。"""
    return {f: f"{f} 的深度分析内容" for f in DEEP_FIELDS}


def _partial_deep_analysis(missing_fields):
    """构造缺若干字段的 deep_analysis dict（缺失字段不含键）。"""
    da = _full_deep_analysis()
    for f in missing_fields:
        da.pop(f)
    return da


# --------------------------------------------------------------------------
# 1. check_technique_depth
# --------------------------------------------------------------------------

class TestCheckTechniqueDepth(unittest.TestCase):
    """check_technique_depth 的齐全性校验（绝不编造内容）。"""

    def test_all_fields_present_returns_complete(self):
        tech = {"name": "t", "deep_analysis": _full_deep_analysis()}
        complete, missing = DEEP_ANALYZE.check_technique_depth(tech)
        self.assertTrue(complete, "7 字段齐全应判 complete=True")
        self.assertEqual(missing, [], "齐全时 missing 应为空列表")

    def test_missing_fields_detected(self):
        tech = {"name": "t", "deep_analysis": _partial_deep_analysis(["reader_psychology", "combo_patterns"])}
        complete, missing = DEEP_ANALYZE.check_technique_depth(tech)
        self.assertFalse(complete, "缺字段应判 complete=False")
        self.assertEqual(
            sorted(missing),
            ["combo_patterns", "reader_psychology"],
            "缺失字段应被精确识别",
        )

    def test_no_deep_analysis_means_all_missing(self):
        tech = {"name": "t"}
        complete, missing = DEEP_ANALYZE.check_technique_depth(tech)
        self.assertFalse(complete)
        self.assertEqual(sorted(missing), sorted(DEEP_FIELDS), "无 deep_analysis 时 7 字段全缺")

    def test_empty_string_treated_as_missing(self):
        da = _full_deep_analysis()
        da["execution_steps"] = ""   # 空串视为缺失
        da["usage_boundary"] = "   "  # 空白串视为缺失
        tech = {"name": "t", "deep_analysis": da}
        complete, missing = DEEP_ANALYZE.check_technique_depth(tech)
        self.assertFalse(complete)
        self.assertIn("execution_steps", missing)
        self.assertIn("usage_boundary", missing)

    def test_non_dict_deep_analysis_all_missing(self):
        """deep_analysis 被污染为非 dict（如字符串）时，应视为全部缺失。"""
        tech = {"name": "t", "deep_analysis": "不是对象"}
        complete, missing = DEEP_ANALYZE.check_technique_depth(tech)
        self.assertFalse(complete)
        self.assertEqual(sorted(missing), sorted(DEEP_FIELDS))


# --------------------------------------------------------------------------
# 2. ensure_technique_depth
# --------------------------------------------------------------------------

class TestEnsureTechniqueDepth(unittest.TestCase):
    """ensure_technique_depth 只补结构、不填内容（核心边界）。"""

    def test_adds_all_seven_keys(self):
        tech = {"name": "t"}
        DEEP_ANALYZE.ensure_technique_depth(tech)
        da = tech["deep_analysis"]
        for f in DEEP_FIELDS:
            self.assertIn(f, da, f"ensure 后应包含键 '{f}'")

    def test_does_not_fill_content(self):
        """ensure 只保证键存在、值为空串，绝不编造深度内容（铁律二边界）。"""
        tech = {"name": "t"}
        DEEP_ANALYZE.ensure_technique_depth(tech)
        for f in DEEP_FIELDS:
            self.assertEqual(
                tech["deep_analysis"][f], "",
                f"ensure 不应填充 '{f}' 的内容（深度内容必须由 LLM 生成）",
            )

    def test_preserves_existing_content(self):
        """已有深度内容时，ensure 不应覆盖。"""
        da = _full_deep_analysis()
        tech = {"name": "t", "deep_analysis": da}
        DEEP_ANALYZE.ensure_technique_depth(tech)
        for f in DEEP_FIELDS:
            self.assertEqual(
                tech["deep_analysis"][f], f"{f} 的深度分析内容",
                f"ensure 不应覆盖已有内容 '{f}'",
            )

    def test_rebuilds_non_dict_deep_analysis(self):
        """deep_analysis 为非 dict 时，ensure 应重建为空 dict 并补齐键。"""
        tech = {"name": "t", "deep_analysis": "污染"}
        DEEP_ANALYZE.ensure_technique_depth(tech)
        self.assertIsInstance(tech["deep_analysis"], dict)
        for f in DEEP_FIELDS:
            self.assertEqual(tech["deep_analysis"][f], "")


# --------------------------------------------------------------------------
# 3. analyze_craft_card
# --------------------------------------------------------------------------

class TestAnalyzeCraftCard(unittest.TestCase):
    """analyze_craft_card 的统计 + 缺段标记（绝不编造）。"""

    def _craft(self, techniques_by_dim):
        return {"craft_analysis": techniques_by_dim}

    def test_complete_technique_counted(self):
        craft = self._craft({
            "foreshadowing": {"techniques": [
                {"name": "t1", "deep_analysis": _full_deep_analysis()},
            ]},
        })
        stats = DEEP_ANALYZE.analyze_craft_card(craft)
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["complete"], 1)
        self.assertEqual(stats["incomplete"], 0)
        self.assertEqual(stats["missing_map"], {})

    def test_incomplete_technique_marked_in_missing_map(self):
        craft = self._craft({
            "foreshadowing": {"techniques": [
                {"name": "t1", "deep_analysis": _partial_deep_analysis(["intensity_control"])},
            ]},
        })
        stats = DEEP_ANALYZE.analyze_craft_card(craft)
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["complete"], 0)
        self.assertEqual(stats["incomplete"], 1)
        self.assertEqual(stats["missing_map"], {"t1": ["intensity_control"]})

    def test_multiple_dimensions_and_techniques(self):
        craft = self._craft({
            "foreshadowing": {"techniques": [
                {"name": "ok", "deep_analysis": _full_deep_analysis()},
                {"name": "bad", "deep_analysis": _partial_deep_analysis(["combo_patterns", "migration_checklist"])},
            ]},
            "tension_building": {"techniques": [
                {"name": "bad2", "deep_analysis": {}},
            ]},
        })
        stats = DEEP_ANALYZE.analyze_craft_card(craft)
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["complete"], 1)
        self.assertEqual(stats["incomplete"], 2)
        self.assertEqual(sorted(stats["missing_map"].keys()), ["bad", "bad2"])
        self.assertEqual(
            sorted(stats["missing_map"]["bad"]),
            ["combo_patterns", "migration_checklist"],
        )

    def test_no_techniques_returns_zero_stats(self):
        craft = self._craft({"foreshadowing": {"techniques": []}})
        stats = DEEP_ANALYZE.analyze_craft_card(craft)
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["complete"], 0)
        self.assertEqual(stats["incomplete"], 0)
        self.assertEqual(stats["missing_map"], {})

    def test_craft_without_analysis_returns_zero_stats(self):
        """craft 缺少 craft_analysis 键时，应返回零统计而不 crash。"""
        stats = DEEP_ANALYZE.analyze_craft_card({"meta": {}})
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["complete"], 0)
        self.assertEqual(stats["incomplete"], 0)

    def test_craft_analysis_non_dict_returns_zero_stats(self):
        """craft_analysis 为非 dict 时，应返回零统计而不 crash。"""
        stats = DEEP_ANALYZE.analyze_craft_card({"craft_analysis": "not-a-dict"})
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["complete"], 0)


# --------------------------------------------------------------------------
# 4. 报告长度硬门槛（MIN_REPORT_CHARS = 10000）
# --------------------------------------------------------------------------

class TestReportLengthThreshold(unittest.TestCase):
    """报告字数 <10000 触发硬校验失败（铁律二）。"""

    def test_min_report_chars_is_10000(self):
        self.assertEqual(REPORT_CRAFT.MIN_REPORT_CHARS, 10000)
        self.assertEqual(REPORT.MIN_REPORT_CHARS, 10000)

    def _craft_with_content(self, technique_count, deep_text_len):
        """构造一张含 N 条技法、每条技法 7 段深度内容（每段 deep_text_len 字）的 craft-card。

        用于驱动 render_craft_report 产出足够/不足长度的报告。
        """
        techniques = []
        for i in range(technique_count):
            da = {f: "深" * deep_text_len for f in DEEP_FIELDS}
            techniques.append({
                "name": f"技法{i}",
                "description": "手法描述",
                "effect": "效果",
                "skeleton": "骨架",
                "anti_pattern": "反例",
                "deep_analysis": da,
            })
        return {
            "meta": {
                "source_title": "测试书",
                "author": "测试作者",
                "genre": "campus-redemption",
                "platform": "番茄",
                "confidence": 0.9,
                "sample_chapters": [1, 2, 3],
                "total_sample_words": 3000,
                "extracted_at": "2026-09-07",
            },
            "craft_analysis": {
                "foreshadowing": {"techniques": techniques},
            },
            "craft_summary": {
                "top_3_strengths": ["s1", "s2", "s3"],
                "unique_techniques": ["u1"],
                "reusable_patterns": ["r1"],
            },
        }

    def test_short_report_below_threshold(self):
        """技法极少、深度内容极短时，报告长度应 < 10000。"""
        craft = self._craft_with_content(technique_count=1, deep_text_len=10)
        report = REPORT_CRAFT.render_craft_report(craft)
        self.assertLess(
            len(report), REPORT_CRAFT.MIN_REPORT_CHARS,
            f"合成短报告长度 {len(report)} 应 < 10000（用于验证门槛前态）",
        )

    def test_long_report_meets_threshold(self):
        """足够多的技法 + 足够长的深度内容，报告长度应 ≥ 10000。"""
        # 每条技法 7 段 × 500 字 = 3500 字，4 条技法约 1.4 万字，稳超门槛
        craft = self._craft_with_content(technique_count=4, deep_text_len=500)
        report = REPORT_CRAFT.render_craft_report(craft)
        self.assertGreaterEqual(
            len(report), REPORT_CRAFT.MIN_REPORT_CHARS,
            f"合成长报告长度 {len(report)} 应 ≥ 10000",
        )

    def test_render_includes_deep_analysis_fields(self):
        """渲染器应把 7 段深度字段展开进报告（铁律二：深度字段是万字主要来源）。"""
        craft = self._craft_with_content(technique_count=1, deep_text_len=50)
        report = REPORT_CRAFT.render_craft_report(craft)
        for label in ["读者心理机制", "执行步骤", "适用场景", "使用边界",
                      "强度控制", "组合套路", "迁移清单"]:
            self.assertIn(label, report, f"报告应渲染深度字段标签 '{label}'")

    def test_old_craft_card_without_deep_analysis_does_not_crash(self):
        """旧 craft-card（无 deep_analysis）渲染不 crash（向后兼容）。"""
        craft = {
            "meta": {"source_title": "旧书", "author": "a", "genre": "campus-redemption",
                     "platform": "p", "confidence": 0.8, "sample_chapters": [1, 2, 3],
                     "total_sample_words": 1000, "extracted_at": "2026-01-01"},
            "craft_analysis": {
                "foreshadowing": {"techniques": [
                    {"name": "旧技法", "description": "d", "effect": "e",
                     "skeleton": "s", "anti_pattern": "a"},
                ]},
            },
            "craft_summary": {},
        }
        report = REPORT_CRAFT.render_craft_report(craft)
        self.assertIsInstance(report, str)
        self.assertTrue(len(report) > 0)


if __name__ == "__main__":
    unittest.main()
