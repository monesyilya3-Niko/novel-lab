#!/usr/bin/env python3
"""
chapter_check 连续打分回归测试（评估报告 P1-2「悬崖式档位」）。

目标：跨过旧硬阈值时分数必须平滑过渡，禁止「1 字 / 0.1pp 跳 2–4 分」。
约束：满分区与各维权重不变；detail 结构可读；纯标准库。

用法：
  python run_tests.py
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
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# metrics 必须先注册，chapter_check 顶部 `from metrics import ...`
_load("metrics")
CC = _load("chapter_check")


def _cn_text(cn: int, fill: str = "甲") -> str:
    return fill * cn


class TestRampHelper(unittest.TestCase):
    def test_ramp_endpoints_and_clamp(self):
        self.assertEqual(CC._ramp(10, 10, 20, 0, 100), 0)
        self.assertEqual(CC._ramp(20, 10, 20, 0, 100), 100)
        self.assertEqual(CC._ramp(5, 10, 20, 0, 100), 0)
        self.assertEqual(CC._ramp(25, 10, 20, 0, 100), 100)
        self.assertEqual(CC._ramp(15, 10, 20, 0, 100), 50)

    def test_ramp_midpoint(self):
        self.assertAlmostEqual(CC._ramp(1200, 1000, 1400, 0, 8), 4.0)


class TestWordCountContinuity(unittest.TestCase):
    """字数：1499→1500 不得再跳 2 分；锚点与旧档位端点一致。"""

    def test_full_score_at_1500(self):
        score, detail = CC.check_word_count(_cn_text(1500))
        self.assertEqual(score, 8, detail)
        self.assertIn("✓", detail)

    def test_no_cliff_at_1499_vs_1500(self):
        s1499, _ = CC.check_word_count(_cn_text(1499))
        s1500, _ = CC.check_word_count(_cn_text(1500))
        self.assertLess(abs(float(s1500) - float(s1499)), 0.5,
                        f"1499→1500 跳变过大：{s1499} → {s1500}")

    def test_old_anchors_still_reachable(self):
        # 旧端点：1200→6、1000→3（连续化后应接近）
        s1200, _ = CC.check_word_count(_cn_text(1200))
        s1000, _ = CC.check_word_count(_cn_text(1000))
        self.assertAlmostEqual(float(s1200), 6.0, delta=0.2)
        self.assertAlmostEqual(float(s1000), 3.0, delta=0.2)

    def test_monotonic_non_decreasing(self):
        prev = -1.0
        for cn in range(900, 1600, 25):
            score, _ = CC.check_word_count(_cn_text(cn))
            self.assertGreaterEqual(float(score), prev - 1e-9,
                                    f"字数 {cn} 分数回退：{score} < {prev}")
            prev = float(score)


class TestDialogueRatioContinuity(unittest.TestCase):
    """对话占比：14.9%→15.0% 不得再跳 4 分；满分区仍为 12。"""

    @staticmethod
    def _text_for_ratio(target: float, cn: int = 1000) -> str:
        """构造汉字数 cn、对话字符数 ≈ target*cn 的文本（用直角引号）。"""
        dialogue = max(0, int(round(target * cn)))
        # 「」各 1 字计入 dialogue_char_count；内部汉字计入 cn
        # dialogue_char_count 统计引号内文本；构造：引号内 dialogue 个汉字
        inner = "乙" * dialogue
        quoted = f"「{inner}」"
        quoted_cn = sum(1 for ch in quoted if "一" <= ch <= "鿿")
        filler = max(0, cn - quoted_cn)
        return quoted + "甲" * filler

    def test_full_zone_still_12(self):
        for r in (0.15, 0.25, 0.40):
            score, detail = CC.check_dialogue_ratio(self._text_for_ratio(r))
            self.assertEqual(score, 12, f"ratio={r}: {detail}")

    def test_no_cliff_around_15pct(self):
        s_lo, _ = CC.check_dialogue_ratio(self._text_for_ratio(0.149))
        s_hi, _ = CC.check_dialogue_ratio(self._text_for_ratio(0.150))
        self.assertLess(abs(float(s_hi) - float(s_lo)), 0.5,
                        f"14.9%→15.0% 跳变过大：{s_lo} → {s_hi}")

    def test_monotonic_toward_optimal_band(self):
        # 从 5% 爬到 15%，分数应非降
        prev = -1.0
        for i in range(5, 16):
            r = i / 100
            score, _ = CC.check_dialogue_ratio(self._text_for_ratio(r))
            self.assertGreaterEqual(float(score), prev - 1e-9,
                                    f"ratio={r} 分数回退：{score}")
            prev = float(score)


class TestLeDensityContinuity(unittest.TestCase):
    """了字密度：p75→p90 之间连续扣分，禁止 27.1 直接掉 1 分整档。"""

    @staticmethod
    def _make(cn: int, le: int) -> str:
        return "了" * le + "甲" * (cn - le)

    def test_below_p75_full(self):
        score, detail = CC.check_fatigue_words(self._make(1000, 27))
        self.assertEqual(score, 8, detail)

    def test_no_cliff_at_p75_boundary(self):
        s0, _ = CC.check_fatigue_words(self._make(10000, 270))  # 27.0
        s1, _ = CC.check_fatigue_words(self._make(10000, 271))  # 27.1
        self.assertLess(abs(float(s1) - float(s0)), 0.5,
                        f"27.0→27.1 跳变过大：{s0} → {s1}")

    def test_at_p90_deducts_about_3(self):
        score, detail = CC.check_fatigue_words(self._make(5000, 156))  # 31.2
        self.assertLessEqual(float(score), 5.2, detail)
        self.assertGreaterEqual(float(score), 4.8, detail)

    def test_above_p90_capped_at_3(self):
        score, _ = CC.check_fatigue_words(self._make(1000, 40))
        self.assertEqual(score, 5, "p90 之上子项扣分封顶 3")

    def test_midway_between_p75_p90(self):
        # 密度 29.1 → 扣分 ≈ 3*(29.1-27)/4.2 = 1.5 → score ≈ 6.5
        score, detail = CC.check_fatigue_words(self._make(10000, 291))
        self.assertGreater(float(score), 5.5, detail)
        self.assertLess(float(score), 7.5, detail)

    def test_monotonic_in_ramp_zone(self):
        prev = 99.0
        for le in range(27, 32):
            score, _ = CC.check_fatigue_words(self._make(10000, le * 10))
            self.assertLessEqual(float(score), prev + 1e-9,
                                 f"密度上升分数未降：le={le} score={score}")
            prev = float(score)


class TestRangAndEmotionTagContinuity(unittest.TestCase):
    def test_rang_no_cliff_at_density_1(self):
        # 旧档位：density<=1 → 5；刚超过 1 → 3（+1 个「让」掉 2 分）
        s1, _ = CC.check_rang_character("让" + "甲" * 999)       # d=1.000 → 5
        s2, _ = CC.check_rang_character("让" * 2 + "甲" * 1997)  # d≈1.0005
        self.assertEqual(s1, 5)
        self.assertLess(abs(float(s2) - float(s1)), 0.2,
                        f"density 1.0→1.0005 跳变过大：{s1} → {s2}")

    def test_direct_emotion_mid_score(self):
        # 1 个直陈式情绪词：旧档位 4，连续化应约为 6
        score, detail = CC.check_direct_emotion("他很愤怒地走了。" + "甲" * 100)
        self.assertGreater(float(score), 4.5, detail)
        self.assertLess(float(score), 7.5, detail)


class TestChapterCheckTotal(unittest.TestCase):
    def test_max_score_metadata_and_cap(self):
        text = (
            "她走进教室，脚步很轻，心跳与指尖都有反应。"
            "他说：「你来了。」她答：「嗯。」"
            + "窗外风吹过走廊操场宿舍食堂图书馆，冲突意外突然紧张害怕担心。" * 40
            + "明天见。忽然门开了，谁也没想到……"
        )
        result = CC.chapter_check(text)
        self.assertEqual(result["max_score"], 100)
        self.assertLessEqual(float(result["score"]), 100.0)
        self.assertIn(result["verdict"], ("PASS", "WARN", "FAIL"))

    def test_score_is_number(self):
        result = CC.chapter_check(_cn_text(2000, "她感到心跳指尖手心呼吸。"))
        self.assertIsInstance(result["score"], (int, float))


if __name__ == "__main__":
    unittest.main()
