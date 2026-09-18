#!/usr/bin/env python3
"""
chapter_check.check_fatigue_words「了」字密度阈值按语料分位数重标定回归测试
（纯标准库 unittest，零第三方依赖）。

对应 Task 3.1 验收清单：
  1.  le_density = 10（旧口径扣 3 分）→ 新口径 8/8 不扣分
  2.  le_density ≈ 29 → 扣 1 分 → 7/8
  3.  le_density ≈ 35 → 扣 3 分 → 5/8
  4.  边界：恰好 27.0 → 不扣分；恰好 31.2 → 扣 1 分（`<=` 与 `>` 语义）
  5.  情绪标签词子项 `> cn/200` 扣 2 分 —— 保持不变（回归断言）
  6.  连接词子项 `> 5` 扣 1 分 —— 保持不变（回归断言）
  7.  返回结构 `(score, detail)` 与 `detail` 文案结构不变，满分仍为 8
  8.  阈值确实由模块常量驱动（可改常量即改行为）

口径变更（2026-09-17 分位数标定）：旧绝对值 `>5`/`>8` 对 6 本语料 54 章
100% 扣满分，维度零区分度；改为语料 p75/p90 = 27.0/31.2。

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
    """按文件名从 scripts/ 动态加载模块（与 test_thresholds 同模式）。"""
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


CHAPTER_CHECK = _load("chapter_check")

# 分位数标定常量（Task 3.1）：语料 p75 / p90
PENALTY_LINE = 27.0
HEAVY_LINE = 31.2


def _make_text(cn: int, le_count: int) -> str:
    """构造恰好 cn 个汉字、其中 le_count 个「了」的内存文本。

    「了」本身属 CJK 统一表意文字（\\u4e00-\\u9fff），计入 cn；
    填充字用「甲」，不含任何疲劳词/情绪标签词/连接词，保证子项互不干扰。
    """
    assert le_count <= cn, "「了」数不得超过总汉字数"
    return "了" * le_count + "甲" * (cn - le_count)


def _make_text_with(cn: int, le_count: int, extra: str) -> str:
    """构造 cn 个汉字（含 le_count 个「了」）且嵌入 extra 的内存文本。"""
    body = "了" * le_count + extra
    filler = cn - sum(1 for ch in body if '\u4e00' <= ch <= '\u9fff')
    assert filler >= 0, "extra 已超出目标汉字数"
    return body + "甲" * filler


class TestLeDensityCalibration(unittest.TestCase):
    """了字密度按 p75/p90 分位数标定后的档位。"""

    def test_density_10_no_penalty(self):
        """le_density = 10（旧口径 >8 扣 3 分）→ 新口径 8/8 不扣分。"""
        score, detail = CHAPTER_CHECK.check_fatigue_words(_make_text(1000, 10))
        self.assertEqual(score, 8, f"密度 10 应不扣分，实际 {score}：{detail}")
        self.assertNotIn("了字密度", detail)

    def test_density_29_penalty_continuous(self):
        """le_density ≈ 29（p75-p90 区间）→ 连续扣分，约 1.4 分（不再整档 -1）。"""
        score, detail = CHAPTER_CHECK.check_fatigue_words(_make_text(1000, 29))
        self.assertGreater(float(score), 5.5, f"密度 29 连续分应 >5.5：{detail}")
        self.assertLess(float(score), 7.5, f"密度 29 连续分应 <7.5：{detail}")
        self.assertIn("了字密度 29.0/千字", detail)

    def test_density_35_penalty_capped(self):
        """le_density ≈ 35（> p90）→ 子项扣满 3 → 5/8。"""
        score, detail = CHAPTER_CHECK.check_fatigue_words(_make_text(1000, 35))
        self.assertEqual(score, 5, f"密度 35 应扣 3 分，实际 {score}：{detail}")
        self.assertIn("了字密度 35.0/千字（过高）", detail)

    def test_old_thresholds_would_have_failed_these(self):
        """对照：旧的 >5/>8 口径下这三档都会扣 3 分（记录口径变更动机）。"""
        scores = [
            CHAPTER_CHECK.check_fatigue_words(_make_text(1000, n))[0]
            for n in (10, 29, 35)
        ]
        self.assertEqual(scores[0], 8)
        self.assertEqual(scores[2], 5)
        self.assertGreater(float(scores[1]), 5.5)
        self.assertLess(float(scores[1]), 7.5)
        self.assertEqual(len(set(scores)), 3, "维度必须有区分度（旧口径恒为 5）")


class TestLeDensityBoundaries(unittest.TestCase):
    """边界语义：`<= 27.0` 不扣分；p75→p90 连续 0→3；`> p90` 扣满 3。"""

    def test_exactly_27_0_no_penalty(self):
        """恰好 27.0 → 不扣分（用 `<=`）。"""
        score, detail = CHAPTER_CHECK.check_fatigue_words(_make_text(1000, 27))
        self.assertEqual(score, 8, f"恰好 27.0 应不扣分，实际 {score}：{detail}")

    def test_just_above_27_0_small_penalty(self):
        """27.1 → 连续扣分极小（≪1），不得整档跳到 -1。"""
        score, detail = CHAPTER_CHECK.check_fatigue_words(_make_text(10000, 271))
        self.assertGreater(float(score), 7.5, f"27.1 不应整档掉到 7：{detail}")
        self.assertLess(float(score), 8.0, f"27.1 应已开始扣分：{detail}")

    def test_exactly_31_2_full_heavy(self):
        """恰好 31.2（p90）→ 连续分扣满 3 → 5/8。"""
        score, detail = CHAPTER_CHECK.check_fatigue_words(_make_text(5000, 156))
        self.assertEqual(score, 5, f"恰好 31.2 应扣满 3，实际 {score}：{detail}")

    def test_just_above_31_2_still_capped(self):
        """31.3 → 仍扣 3（子项封顶）。"""
        score, detail = CHAPTER_CHECK.check_fatigue_words(_make_text(10000, 313))
        self.assertEqual(score, 5, f"31.3 应扣 3 分，实际 {score}：{detail}")
        self.assertIn("（过高）", detail)

    def test_density_zero_no_penalty(self):
        """密度 0 → 不扣分（下限不误伤）。"""
        score, _ = CHAPTER_CHECK.check_fatigue_words(_make_text(1000, 0))
        self.assertEqual(score, 8)


class TestThresholdConstants(unittest.TestCase):
    """阈值必须提为模块常量，且行为由常量驱动（非硬编码）。"""

    def test_constants_exist_with_calibrated_values(self):
        self.assertAlmostEqual(
            getattr(CHAPTER_CHECK, "LE_DENSITY_PENALTY_LINE", None), PENALTY_LINE,
            msg="缺少模块常量 LE_DENSITY_PENALTY_LINE = 27.0（语料 p75）")
        self.assertAlmostEqual(
            getattr(CHAPTER_CHECK, "LE_DENSITY_HEAVY_LINE", None), HEAVY_LINE,
            msg="缺少模块常量 LE_DENSITY_HEAVY_LINE = 31.2（语料 p90）")

    def test_constants_are_ordered(self):
        self.assertLess(
            CHAPTER_CHECK.LE_DENSITY_PENALTY_LINE,
            CHAPTER_CHECK.LE_DENSITY_HEAVY_LINE,
            "p75 标定线必须低于 p90 标定线",
        )

    def test_calibration_provenance_documented(self):
        """常量上方注释须写明标定依据（语料/章数/分位数/日期/重算提示）。"""
        src = (SCRIPTS / "chapter_check.py").read_text(encoding="utf-8")
        for token in ("corpus", "54", "p75", "p90", "2026-09-17", "重算"):
            self.assertIn(
                token, src,
                f"标定依据注释缺少关键信息：{token}")

    def test_behavior_follows_constants(self):
        """临时改常量应改变行为 —— 证明判断读的是常量而非字面量。"""
        text = _make_text(1000, 10)  # 新口径下不扣分
        self.assertEqual(CHAPTER_CHECK.check_fatigue_words(text)[0], 8)

        saved_penalty = CHAPTER_CHECK.LE_DENSITY_PENALTY_LINE
        saved_heavy = CHAPTER_CHECK.LE_DENSITY_HEAVY_LINE
        try:
            # 仅调低 PENALTY：密度 10 落入 p75→p90 连续区，应开始扣分但未满 3
            CHAPTER_CHECK.LE_DENSITY_PENALTY_LINE = 5.0
            mid = CHAPTER_CHECK.check_fatigue_words(text)[0]
            self.assertGreater(float(mid), 5.0,
                               "调低 PENALTY_LINE 后密度 10 不应仍满分")
            self.assertLess(float(mid), 8.0,
                            "调低 PENALTY_LINE 后密度 10 应已扣分")

            # 两条线都压到密度之下 → 扣满 3
            CHAPTER_CHECK.LE_DENSITY_HEAVY_LINE = 8.0
            self.assertEqual(
                CHAPTER_CHECK.check_fatigue_words(text)[0], 5,
                "调低 HEAVY_LINE 到 8.0 后密度 10 应扣 3 分")
        finally:
            CHAPTER_CHECK.LE_DENSITY_PENALTY_LINE = saved_penalty
            CHAPTER_CHECK.LE_DENSITY_HEAVY_LINE = saved_heavy


class TestSubItemsUnchanged(unittest.TestCase):
    """情绪标签词与连接词两个子项必须逐项不变（回归断言）。"""

    def test_emotion_tags_over_cn_200_still_penalty_2(self):
        """情绪标签词 > cn/200 → 仍扣 2 分（1000 汉字 → 阈值 5，用 6 处）。"""
        text = _make_text_with(1000, 0, "紧张" * 6)
        score, detail = CHAPTER_CHECK.check_fatigue_words(text)
        self.assertEqual(score, 6, f"情绪标签词 6 处应扣 2 分，实际 {score}：{detail}")
        self.assertIn("情绪标签词 6 处（过多）", detail)

    def test_emotion_tags_at_threshold_not_penalized(self):
        """恰好 cn/200（1000 汉字 → 5 处）不扣分（保持 `>` 严格大于语义）。"""
        text = _make_text_with(1000, 0, "紧张" * 5)
        score, detail = CHAPTER_CHECK.check_fatigue_words(text)
        self.assertEqual(score, 8, f"恰好 5 处不应扣分，实际 {score}：{detail}")

    def test_connectors_over_5_still_penalty_1(self):
        """连接词 > 5 → 仍扣 1 分（用 6 处）。"""
        text = _make_text_with(1000, 0, "突然" * 6)
        score, detail = CHAPTER_CHECK.check_fatigue_words(text)
        self.assertEqual(score, 7, f"连接词 6 处应扣 1 分，实际 {score}：{detail}")
        self.assertIn("连接词 6 处（过多）", detail)

    def test_connectors_at_5_not_penalized(self):
        """恰好 5 处连接词不扣分（保持 `> 5` 语义）。"""
        text = _make_text_with(1000, 0, "突然" * 5)
        score, _ = CHAPTER_CHECK.check_fatigue_words(text)
        self.assertEqual(score, 8)

    def test_subitems_stack_with_le_penalty(self):
        """三子项可叠加：le 35(-3) + 标签 6(-2) + 连接词 6(-1) → 2/8。"""
        text = _make_text_with(1000, 35, "紧张" * 6 + "突然" * 6)
        score, detail = CHAPTER_CHECK.check_fatigue_words(text)
        self.assertEqual(score, 2, f"三子项应叠加扣分，实际 {score}：{detail}")
        self.assertIn("了字密度", detail)
        self.assertIn("情绪标签词", detail)
        self.assertIn("连接词", detail)


class TestReturnShapeUnchanged(unittest.TestCase):
    """返回结构、文案结构与满分不变。"""

    def test_empty_text_unchanged(self):
        self.assertEqual(CHAPTER_CHECK.check_fatigue_words(""), (0, "无文本"))

    def test_no_text_for_non_cjk(self):
        self.assertEqual(CHAPTER_CHECK.check_fatigue_words("abc 123 !!!"), (0, "无文本"))

    def test_clean_text_full_score_and_detail_prefix(self):
        score, detail = CHAPTER_CHECK.check_fatigue_words(_make_text(1000, 0))
        self.assertEqual(score, 8)
        self.assertTrue(detail.startswith("疲劳词 8/8: "), detail)
        self.assertIn("无异常", detail)

    def test_returns_tuple_of_number_and_str(self):
        result = CHAPTER_CHECK.check_fatigue_words(_make_text(1000, 35))
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], (int, float))
        self.assertIsInstance(result[1], str)

    def test_detail_prefix_matches_score(self):
        for n in (0, 10, 29, 35):
            score, detail = CHAPTER_CHECK.check_fatigue_words(_make_text(1000, n))
            # 连续分可能带 1 位小数；前缀用与实现相同的格式
            from chapter_check import _fmt_score  # noqa: PLC0415
            self.assertTrue(
                detail.startswith(f"疲劳词 {_fmt_score(score)}/8: "),
                f"detail 前缀应与得分一致：{detail}")

    def test_score_never_negative(self):
        text = _make_text_with(1000, 35, "紧张" * 6 + "突然" * 6)
        score, _ = CHAPTER_CHECK.check_fatigue_words(text)
        self.assertGreaterEqual(score, 0)


if __name__ == "__main__":
    unittest.main()
