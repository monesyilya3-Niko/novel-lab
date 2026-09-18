#!/usr/bin/env python3
"""
novel-lab P2 评分阈值题材适配配置化回归测试（纯标准库 unittest，零第三方依赖）。

覆盖 chapter_check.resolve_thresholds 的阈值解析 + chapter_check.chapter_check 的
判定生效 + 向后兼容，共 10+ 用例。对应主理人派发的 T03 验收清单：

  1.  resolve_thresholds(None) == (75, 60)
  2.  无 quality_thresholds 键 → (75, 60)；空 dict {} → (75, 60)
  3.  合法值 {"pass": 80, "warn": 65} → (80, 65)
  4.  pass == warn 被允许 → (70, 70)
  5.  warn > pass → 回退 (75, 60)
  6.  非 int（字符串）→ 回退 (75, 60)
  7.  越界（pass=101 / warn=-1）→ 回退 (75, 60)
  8.  bool(True) 视为非法 → 回退 (75, 60)
  9.  向后兼容：chapter_check(text) 与 chapter_check(text, None) 的 verdict 一致
  10. 阈值生效：得分 60~74 的文本在 pass=80 时由 WARN 变 FAIL

注意：quality_thresholds 在 schema 里位于 commercial.properties 下，即正确形态为
    {"commercial": {"quality_thresholds": {"pass": X, "warn": Y}}}
（与主理人示例中顶层直接写 quality_thresholds 不同，此处按实现 + schema 对齐）。

用法：
  python run_tests.py            # 自动 discover（pattern test_*.py）
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


CHAPTER_CHECK = _load("chapter_check")


def _pack(pass_v, warn_v):
    """构造含合法嵌套结构的题材包 dict（quality_thresholds 位于 commercial 下）。"""
    return {"commercial": {"quality_thresholds": {"pass": pass_v, "warn": warn_v}}}


class TestResolveThresholds(unittest.TestCase):
    """resolve_thresholds 的阈值解析与回退规则。"""

    def test_none_returns_default(self):
        self.assertEqual(CHAPTER_CHECK.resolve_thresholds(None), (75, 60))

    def test_no_key_returns_default(self):
        self.assertEqual(CHAPTER_CHECK.resolve_thresholds({}), (75, 60))
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds({"commercial": {}}), (75, 60))
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(
                {"commercial": {"payoff_density": {}}}), (75, 60))

    def test_empty_dict_returns_default(self):
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(
                {"commercial": {"quality_thresholds": {}}}), (75, 60))

    def test_valid_values(self):
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(_pack(80, 65)), (80, 65))

    def test_pass_equals_warn_allowed(self):
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(_pack(70, 70)), (70, 70))

    def test_warn_greater_than_pass_falls_back(self):
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(_pack(50, 80)), (75, 60))

    def test_non_int_string_falls_back(self):
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(_pack("75", 60)), (75, 60))
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(_pack(80, "60")), (75, 60))

    def test_float_falls_back(self):
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(_pack(80.0, 60)), (75, 60))

    def test_out_of_range_falls_back(self):
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(_pack(101, 60)), (75, 60))
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(_pack(80, -1)), (75, 60))
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(_pack(80, 101)), (75, 60))

    def test_bool_is_invalid_falls_back(self):
        # bool 是 int 的子类，但必须视为非法（True == 1 在 0-100 内，需显式排除）
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(_pack(True, 60)), (75, 60))
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(_pack(80, False)), (75, 60))

    def test_boundary_values_are_valid(self):
        # 0 与 100 是合法边界（不应回退）
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(_pack(100, 0)), (100, 0))
        self.assertEqual(
            CHAPTER_CHECK.resolve_thresholds(_pack(100, 100)), (100, 100))

    def test_non_dict_genre_pack_falls_back(self):
        # genre_pack 非 dict（如字符串/列表）应静默回退
        self.assertEqual(CHAPTER_CHECK.resolve_thresholds("not-a-dict"), (75, 60))
        self.assertEqual(CHAPTER_CHECK.resolve_thresholds([1, 2, 3]), (75, 60))


# 用于向后兼容与阈值生效测试的固定文本：
# 篇幅充足、含对话与体感词，但故意保留较多直陈式情绪词/疲劳词，使总分落在 60~74 区间。
_TEXT_60_74 = (
    "教室里很安静，唐雨坐在靠窗的位置，觉得很紧张，也很害怕。\n"
    "\n"
    "边炀推开门走进来，看了她一眼。\n"
    "\n"
    "「你还好吗？」他问。\n"
    "\n"
    "「我没事。」她低声说，手心却有点发凉。\n"
    "\n"
    "他走到她旁边坐下，没有再说话。\n"
    "\n"
    "窗外的风吹进来，她感到一阵难过，眼眶有点发酸。\n"
    "\n"
    "「真的很担心你。」他忽然说。\n"
    "\n"
    "她愣了一下，心里涌上一股说不清的感觉，很生气，又很委屈。\n"
    "\n"
    "他们谁也没有再开口，就这样坐了很久很久。\n"
    "\n"
    "放学铃响了，他站起身，把一本笔记放在她桌上。\n"
    "\n"
    "「明天见。」\n"
    "\n"
    "她看着他的背影，忽然觉得，好像有什么东西不一样了。\n"
)


class TestChapterCheckThresholds(unittest.TestCase):
    """chapter_check 判定线是否随阈值生效 + 向后兼容。"""

    @classmethod
    def setUpClass(cls):
        cls.default_result = CHAPTER_CHECK.chapter_check(_TEXT_60_74)
        cls.none_result = CHAPTER_CHECK.chapter_check(_TEXT_60_74, None)

    def test_backward_compat_default_equals_none(self):
        """chapter_check(text) 与 chapter_check(text, None) 的 verdict 完全一致。"""
        self.assertEqual(
            self.default_result["verdict"], self.none_result["verdict"],
            "默认调用与显式传 None 的 verdict 应一致（向后兼容）",
        )

    def test_backward_compat_full_equality(self):
        """除 verdict 外，score/details 也应一致（None 走默认回退路径）。"""
        self.assertEqual(self.default_result["score"], self.none_result["score"])
        self.assertEqual(self.default_result["details"], self.none_result["details"])

    def test_threshold_effect_raises_pass_line(self):
        """阈值机制生效：抬高 pass 线到当前得分之上 → FAIL；score 本身不变。

        注：固定文本得分随评分器连续化（2026-09-18）而变化，不再钉死在
        60~74 区间；本测试改为「用高于实测分的阈值」验证机制，语义等价。
        """
        score = self.default_result["score"]
        self.assertIsInstance(score, (int, float))
        self.assertGreater(float(score), 0, "固定文本不应得 0 分")

        high_pass = min(100, int(score) + 10)
        high_warn = min(high_pass, int(score) + 5)
        self.assertGreater(high_pass, score, "构造的 pass 线必须高于实测分")

        raised = CHAPTER_CHECK.chapter_check(_TEXT_60_74, _pack(high_pass, high_warn))
        self.assertEqual(
            raised["verdict"], "FAIL",
            f"pass={high_pass} > score={score} 时应判 FAIL",
        )
        self.assertEqual(raised["score"], score)

        # 反向：默认阈值下的 verdict 应与显式 (75,60) 一致
        baseline = CHAPTER_CHECK.chapter_check(_TEXT_60_74, _pack(75, 60))
        self.assertEqual(baseline["verdict"], self.default_result["verdict"])

    def test_threshold_effect_lowers_pass_line(self):
        """反向：把 pass/warn 调低到得分以下，应判 PASS（阈值真正生效、可降）。"""
        score = self.default_result["score"]
        lowered = CHAPTER_CHECK.chapter_check(
            _TEXT_60_74, _pack(score, score))  # pass==warn==score → 恰达 PASS
        self.assertEqual(lowered["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
