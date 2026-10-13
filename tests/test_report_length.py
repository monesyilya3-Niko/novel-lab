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
            da = dict.fromkeys(DEEP_FIELDS, "深" * deep_text_len)
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


class TestCombinedReportOkMissingField(unittest.TestCase):
    """combined_report_ok 的 missing 字段（2026-10-12 审计 CLI-02 引入）。

    该字段记录**哪一份报告为空**，供调用方明确点名（novel.py「分析」的
    铁律二校验用它打印"其中 XX 为空"），避免用户只看到"合计不足"却
    不知道是哪一份没生成。

    注意：曾短暂存在 require_both 参数（要求两份齐全才判 ok），
    2026-10-13 已移除——那是 CLI-12/13 两个 regression 的根源：
    pipeline 只产笔法分析、batch 只产拆书报告，单产一份的命令天然无法
    满足"两份齐全"。判定口径回到「合计 ≥ 10000」（铁律二原文）。
    """

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "report_missing", SCRIPTS / "report.py")
        self.report = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.report)

    def test_missing_empty_when_both_present(self):
        r = self.report.combined_report_ok(6000, 6000)
        self.assertEqual(r["missing"], [])
        self.assertTrue(r["ok"])

    def test_missing_names_the_absent_side(self):
        self.assertEqual(self.report.combined_report_ok(20000, 0)["missing"], ["craft"])
        self.assertEqual(self.report.combined_report_ok(0, 20000)["missing"], ["book"])
        self.assertEqual(self.report.combined_report_ok(0, 0)["missing"], ["book", "craft"])

    def test_ok_is_pure_sum_threshold(self):
        """判定只看合计（铁律二原文口径），与 missing 无关。"""
        self.assertTrue(self.report.combined_report_ok(20000, 0)["ok"],
                        "合计达标即通过——单份缺失不改变判定（铁律二只管合计）")
        self.assertFalse(self.report.combined_report_ok(100, 100)["ok"])
        self.assertTrue(self.report.combined_report_ok(5000, 5000)["ok"])

    def test_require_both_parameter_is_gone(self):
        """回归锚点：require_both 已随 CLI-12/13 一并移除，不得复活。

        复活它会重新引入误报——除非先解决「单产一份报告的命令无法满足
        两份齐全」这个语义错配。
        """
        import inspect
        sig = inspect.signature(self.report.combined_report_ok)
        self.assertNotIn("require_both", sig.parameters,
                         "require_both 复活了——它是 CLI-12/13 误报的根源")



class TestIronRule2AppliesToFullChainOnly(unittest.TestCase):
    """铁律二的适用边界（2026-10-13 修正）。

    背景：2026-10-12 修 CLI-01 时给「拆书」「批量」加了 enforce_iron_rule_2，
    但那是**语义错配**，引入两个 regression（CLI-12/CLI-13）：
      - pipeline.py 只产笔法分析一份，batch.py 只产拆书报告一份
      - 而铁律二的口径是「拆书报告 + 笔法分析**合计** ≥ 10000」
      - 实测仓库真实报告：单份拆书报告 4719~7204 字、单份笔法分析
        5163~22128 字（2/6 不足 10000）——单产一份的命令天然无法满足
    故两个命令会对正常产出**误报失败**，比原缺陷更糟。

    现行结论：铁律二由「分析」命令收口（它跑完整链路、两份都产，
    在 staging 上做合计校验后再原子发布）。拆书/批量的单份报告字数
    提示由 report.py 自己的 soft warning 承担。

    本类锁定两件事：
      1. 辅助函数 enforce_iron_rule_2 已随 regression 一并移除（不留死代码）
      2. 真正的校验入口（combined_report_ok）语义正确且被「分析」使用
    """

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("novel_ir2", ROOT / "novel.py")
        self.novel = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.novel)

        spec2 = importlib.util.spec_from_file_location("report_ir2", SCRIPTS / "report.py")
        self.report = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(self.report)

    def test_helper_removed_with_the_regression(self):
        """死代码不得残留——它会让人误以为 CLI-01 仍被覆盖着。"""
        self.assertFalse(
            hasattr(self.novel, "enforce_iron_rule_2"),
            "enforce_iron_rule_2 已确认是误报源并移除；若重新引入，"
            "必须先解决「单产一份报告无法满足合计门槛」这个语义错配",
        )

    def test_combined_gate_uses_sum_of_both(self):
        """铁律二的真实口径：两份相加 ≥ 10000（单一来源仍在 report.py）。"""
        self.assertTrue(self.report.combined_report_ok(6000, 6000)["ok"])
        self.assertFalse(self.report.combined_report_ok(9000, 0)["ok"],
                         "单份 9000 应不足（合计口径）")
        self.assertTrue(self.report.combined_report_ok(5000, 5000)["ok"],
                        "恰好 10000 应通过")

    def test_analysis_command_still_checks_on_staging(self):
        """「分析」的 staging 校验必须还在——那是铁律二的真正执行点。"""
        src = (ROOT / "novel.py").read_text(encoding="utf-8")
        self.assertIn("check_combined_report_length(staging, name)", src,
                      "分析命令的 staging 合计校验被删了——铁律二将失去唯一执行点")


if __name__ == "__main__":
    unittest.main()
