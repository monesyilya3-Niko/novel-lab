#!/usr/bin/env python3
"""Task 3 专项测试：统一四类引号的对白字符抽取（纯标准库 unittest，零第三方依赖）。

被守护的单一事实来源：``metrics.dialogue_char_count(text) -> int``，
由 ``metrics.dialogue_ratio`` 与 ``chapter_check.check_dialogue_ratio`` 共用。

覆盖主理人 Task 3 验收清单：
  1. 四类引号（ASCII ``"``、中文双引号 ``“”``、直角引号 ``「」``、双直角引号 ``『』``）
     内部字符计数一致；
  2. 混合引号不互相闭合（``「甲“乙”丙」`` → 4）；
  3. 未闭合引号计到文末（``「甲乙`` → 2）；
  4. ``metrics.dialogue_ratio`` 分母仍是「去空白总字符」；
  5. ``chapter_check.check_dialogue_ratio`` 复用同一函数，分母仍是汉字数、
     评分档位与既有结果不回归。

分母口径说明（brief 中 ``dialogue_ratio('「甲乙」丙丁') == 0.5`` 与强制分母冲突）：
文本去空白共 6 字符、引号内 2 字符，唯一自洽结果是 ``2/6 ≈ 0.3333``；
0.5 只有在分母剔除引号本身（4）时才成立，而 brief 同时要求「保持去空白总字符分母」。
本测试按强制分母断言 0.3333，并额外用带空格文本锁定分母口径。

用法：
  python -m unittest discover -s tests -p "test_dialogue_quotes.py" -v
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
    """按文件名从 scripts/ 动态加载模块（与 test_thresholds/test_regressions 同模式）。"""
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# 先注册 metrics，使 chapter_check 的 `from metrics import dialogue_char_count`
# 命中同一模块对象（避免重复加载出两份状态）。
METRICS = _load("metrics")
CHAPTER_CHECK = _load("chapter_check")

# 基线（2026-09-18 连续打分后）：
#   metrics.dialogue_ratio('他说：“你好。”然后走了。') == 0.2308（分子分母口径未改）
#   ratio 50%（略高带）→ 连续分 _ramp(0.50, 0.40, 0.55, 12, 8) = 9.3
#   ratio 37.5%（满分区）→ 12
_BASELINE_CJK_MIXED_RATIO = 0.2308
_BASELINE_CJK_PAIR_CHAPTER_CHECK = (9.3, "对话占比 50.0%（略高）")
_BASELINE_ASCII_PAIR_CHAPTER_CHECK = (9.3, "对话占比 50.0%（略高）")
_BASELINE_SENTENCE_CHAPTER_CHECK = (12, "对话占比 37.5% ✓")


class TestDialogueQuotes(unittest.TestCase):
    """dialogue_char_count 对四类引号、混合引号与未闭合引号的抽取语义。"""

    def test_four_quote_pairs_count_same_inner_chars(self):
        texts = [
            '"甲乙"他说。',
            '“甲乙”他说。',
            '「甲乙」他说。',
            '『甲乙』他说。',
        ]
        for text in texts:
            self.assertEqual(
                METRICS.dialogue_char_count(text), 2,
                f"{text!r} 引号内应计 2 字（四类引号口径一致）")

    def test_mixed_pairs_do_not_close_each_other(self):
        self.assertEqual(METRICS.dialogue_char_count('「甲“乙”丙」'), 4)

    def test_unclosed_pair_counts_to_end(self):
        self.assertEqual(METRICS.dialogue_char_count('「甲乙'), 2)

    def test_chapter_check_recognizes_corner_quotes(self):
        score, detail = CHAPTER_CHECK.check_dialogue_ratio('「甲乙」他说。')
        self.assertNotIn('几乎无对话', detail)
        self.assertGreater(score, 0)

    def test_four_styles_share_one_implementation(self):
        """chapter_check 必须复用 metrics 的同一函数（禁止各写一套扫描）。"""
        src = (SCRIPTS / "chapter_check.py").read_text(encoding="utf-8")
        self.assertTrue("dialogue_char_count" in src,
                        "chapter_check.py 应复用 metrics.dialogue_char_count")

    def test_empty_and_no_quote_texts_count_zero(self):
        for text in ("", "「」", "只有旁白没有引号。", "\n  \n"):
            self.assertEqual(METRICS.dialogue_char_count(text), 0,
                             f"{text!r} 不应计出对白字符")

    def test_empty_dialogue_ratio_is_zero(self):
        self.assertEqual(METRICS.dialogue_ratio(""), 0.0)
        self.assertEqual(METRICS.dialogue_ratio("只有旁白没有引号。"), 0.0)

    def test_quotes_themselves_are_not_counted(self):
        """开闭引号本身不计入分子。"""
        self.assertEqual(METRICS.dialogue_char_count('「」'), 0)
        self.assertEqual(METRICS.dialogue_char_count('""'), 0)


class TestDialogueRatioDenominator(unittest.TestCase):
    """metrics.dialogue_ratio 的分母口径回归。"""

    def test_denominator_is_whitespace_stripped_total_chars(self):
        # 分子 2（甲乙），分母 6（「甲乙」丙丁 去空白）→ 2/6
        self.assertEqual(METRICS.dialogue_ratio('「甲乙」丙丁'), round(2 / 6, 4))
        # 显式锁定分母口径：插入空白后分母不变，结果不变
        self.assertEqual(METRICS.dialogue_ratio('「甲乙」 丙丁'), round(2 / 6, 4))
        self.assertEqual(METRICS.dialogue_ratio('「甲乙」\n丙丁'), round(2 / 6, 4))

    def test_ratio_agrees_across_four_quote_styles(self):
        expected = round(2 / 6, 4)
        for text in ('"甲乙"丙丁', '“甲乙”丙丁', '「甲乙」丙丁', '『甲乙』丙丁'):
            self.assertEqual(METRICS.dialogue_ratio(text), expected,
                             f"{text!r} 四类引号应给出同一占比")

    def test_cjk_pair_ratio_unchanged_from_baseline(self):
        """既有中文双引号/直角引号结果不回归（改动前实测 0.2857）。"""
        self.assertEqual(METRICS.dialogue_ratio('“甲乙”他说。'), 0.2857)
        self.assertEqual(METRICS.dialogue_ratio('「甲乙」他说。'), 0.2857)
        self.assertEqual(METRICS.dialogue_ratio('他说：“你好。”然后走了。'),
                         _BASELINE_CJK_MIXED_RATIO)

    def test_ascii_and_cjk_double_quotes_now_agree(self):
        """改动前 metrics 完全忽略 ASCII 引号（计 0）；现与中文双引号口径一致。"""
        self.assertEqual(
            METRICS.dialogue_ratio('"你好"他说。'),
            METRICS.dialogue_ratio('“你好”他说。'),
        )


class TestChapterCheckDialogueRatio(unittest.TestCase):
    """chapter_check.check_dialogue_ratio 复用函数后的分母与档位回归。"""

    def test_han_denominator_retained(self):
        # 分母是汉字数 4（甲乙丙丁），不是去空白总字符 6
        # ratio=50% → 连续分 9.3（略高带中点附近），不得打成 0
        score, detail = CHAPTER_CHECK.check_dialogue_ratio('「甲乙」丙丁')
        self.assertEqual(score, 9.3, detail)
        self.assertIn("50.0%", detail)

    def test_existing_ascii_and_cjk_pairs_unchanged(self):
        self.assertEqual(CHAPTER_CHECK.check_dialogue_ratio('“甲乙”他说。'),
                         _BASELINE_CJK_PAIR_CHAPTER_CHECK)
        self.assertEqual(CHAPTER_CHECK.check_dialogue_ratio('"甲乙"他说。'),
                         _BASELINE_ASCII_PAIR_CHAPTER_CHECK)
        self.assertEqual(CHAPTER_CHECK.check_dialogue_ratio('他说：“你好。”然后走了。'),
                         _BASELINE_SENTENCE_CHAPTER_CHECK)

    def test_four_quote_styles_score_identically(self):
        results = [CHAPTER_CHECK.check_dialogue_ratio(t) for t in
                   ('"甲乙"他说。', '“甲乙”他说。', '「甲乙」他说。', '『甲乙』他说。')]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], results[2])
        self.assertEqual(results[0], results[3])

    def test_mismatched_closing_quote_does_not_close(self):
        """『 开、」 收：类型不匹配的关闭引号不结束当前对白，作为正文字符累计。"""
        self.assertEqual(METRICS.dialogue_char_count('『甲乙」'), 3)
        self.assertEqual(METRICS.dialogue_char_count('「甲乙』'), 3)
        score, detail = CHAPTER_CHECK.check_dialogue_ratio('『甲乙」')
        self.assertGreater(score, 0)
        self.assertNotIn("几乎无对话", detail)

    def test_corner_quote_dialogue_scores_above_zero(self):
        for text in ('「你好？」', '『你好？』', '“你好？”', '"你好？"'):
            score, detail = CHAPTER_CHECK.check_dialogue_ratio(text)
            self.assertGreater(score, 0, f"{text!r} 不应被判为几乎无对话：{detail}")
            self.assertNotIn("几乎无对话", detail)

    def test_score_weights_and_thresholds_untouched(self):
        """满分区权重不变：对话占比在 15%-40% 区间仍给满分 12。"""
        for text in ('“甲乙”丙丁戊己庚辛', '「甲乙」丙丁戊己庚辛', '『甲乙』丙丁戊己庚辛'):
            score, detail = CHAPTER_CHECK.check_dialogue_ratio(text)
            self.assertEqual(score, 12, f"{text!r} 应给满分 12：{detail}")


if __name__ == "__main__":
    unittest.main()
