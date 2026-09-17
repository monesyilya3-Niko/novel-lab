#!/usr/bin/env python3
"""重复检测召回专项测试（优化第二轮 Task A / 报告 P0-2）

背景（问题实证）：
  1. ``check_duplicate_sentences`` 只在同一句出现在 **≥3 章** 时才报 → 只在相邻两章
     重复的（读者最易察觉）永远不报；
  2. 段落检测只认「>30 字整段完全相同」→ 识别不了「同一句碎片散布在多个段落中」的
     形态。项目曾发生 2000 字里 937 字重复的 automerge 事故，却被 `novel 质检` 判 PASS。

本文件锁定以下契约：
  1. 跨章句子重复门槛 ≥3 章 → **≥2 章**；2 章 → ``severity=low`` + ``adjacent`` 标记；
     ≥3 章 → ``severity=medium``（与调整前一致，不回退）。
  2. 新增 ``check_intra_chapter_repeats``：按**章内重复句占比**定严重度
     （``>=0.25`` high / ``0.10~0.25`` medium / ``<0.10`` low），每章最多 1 条；
     句子总数 < 8 时小分母占比不可靠（2 句重复 1 句 = 50%），一律降为 ``low``
     并以 ``low_sample=True`` 标记（样本充足时该字段为 ``False``）。
  3. ``check_duplicate_paragraphs`` 口径不变（仍为「>30 字整段」），避免召回口径漂移。
  4. ``book_quality_check`` 在逐章循环内接入章内重复检测，且返回 dict 既有键不变。

测试全部使用内存 dict 或临时目录，不触碰真实 ``assets/``、``gui_state/``。

用法：
  python -m unittest discover -s tests -p "test_duplicate_recall.py" -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

# 用常规 import（而非 importlib 动态加载）：book_quality 在模块级 import chapter_loader，
# 动态加载会产生第二个模块实例，导致异常类身份不一致。
import book_quality  # noqa: E402

# --- 夹具：12~40 字、以句末标点结尾的句子（命中跨章正则 [^。！？\n]{12,40}[。！？]） ---
SENT_A = "他缓缓推开了那扇沉重的木门。"
SENT_B = "她把那封信折好放进了口袋。"
SENT_C = "窗外的雨声一直下个不停歇。"

# 短句（< 12 字）不参与跨章句子检测，用作不干扰断言的填充
FILL_1 = "天亮了。"
FILL_2 = "风停了。"
FILL_3 = "夜深了。"
FILL_4 = "雨住了。"


def _chapter(*sentences):
    """把若干句子拼成一章正文（换行分隔，避免正则跨句误切）。"""
    return "\n".join(sentences) + "\n"


def _unique_sentences(prefix, count):
    """生成 count 条互不相同、长度 >= 10 的句子。"""
    return [f"{prefix}第{i}条用于填充剩余位置的句子。" for i in range(count)]


def _high_repeat_text():
    """章内重复占比 6/13 ≈ 46%（high 档）的正文。

    3 个句子各出现 3 次（重复句数 3×(3-1)=6），另加 4 条独有句 → 共 13 句。
    """
    return "".join(
        [SENT_A] * 3 + [SENT_B] * 3 + [SENT_C] * 3
        + ["他站在门口迟迟没有走进去。",
           "桌上的茶杯早已凉透了。",
           "远处传来一阵急促的脚步声。",
           "她忽然想起许多年前的旧事。"]
    )


class TestCrossChapterSentenceRecall(unittest.TestCase):
    """跨章句子重复：门槛 ≥3 章 → ≥2 章（Task A 验收 1、2、5）。"""

    def test_two_adjacent_chapters_reported_low(self):
        """同一句出现在相邻 2 章 → 1 条 duplicate_sentence、low、adjacent=True。"""
        texts = {
            1: _chapter(SENT_A, FILL_1),
            2: _chapter(SENT_A, FILL_3),
        }
        issues = book_quality.check_duplicate_sentences(texts)
        self.assertEqual(len(issues), 1, f"相邻两章重复应报 1 条，实得: {issues}")
        issue = issues[0]
        self.assertEqual(issue["type"], "duplicate_sentence")
        self.assertEqual(issue["severity"], "low", "2 章档必须是 low，不得升级")
        self.assertTrue(issue["adjacent"], "相邻两章 adjacent 必须为 True")
        self.assertEqual(issue["chapters"], [1, 2])
        self.assertIn("（相邻章）", issue["detail"])

    def test_two_non_adjacent_chapters_low_without_adjacent_flag(self):
        """第 1、3 章重复（不相邻）→ 仍报 1 条 low，但 adjacent=False。"""
        texts = {
            1: _chapter(SENT_A, FILL_1),
            2: _chapter(SENT_B, FILL_2),
            3: _chapter(SENT_A, FILL_4),
        }
        issues = book_quality.check_duplicate_sentences(texts)
        self.assertEqual(len(issues), 1, f"实得: {issues}")
        issue = issues[0]
        self.assertEqual(issue["severity"], "low")
        self.assertFalse(issue["adjacent"], "第 1、3 章不相邻，adjacent 必须为 False")
        self.assertEqual(issue["chapters"], [1, 3])
        self.assertNotIn("（相邻章）", issue["detail"])

    def test_three_chapters_still_medium(self):
        """同一句出现在 3 章 → 1 条、severity=medium（与现状一致，不回退）。"""
        texts = {
            1: _chapter(SENT_A, FILL_1),
            2: _chapter(SENT_A, FILL_2),
            3: _chapter(SENT_A, FILL_3),
        }
        issues = book_quality.check_duplicate_sentences(texts)
        self.assertEqual(len(issues), 1, f"3 章重复应聚合为 1 条，实得: {issues}")
        issue = issues[0]
        self.assertEqual(issue["severity"], "medium", "≥3 章档必须保持 medium")
        self.assertTrue(issue["adjacent"], "1/2/3 章内部存在相邻章")
        self.assertEqual(issue["chapters"], [1, 2, 3])

    def test_no_duplicate_returns_empty(self):
        """无重复文本 → 0 条。"""
        texts = {
            1: _chapter(SENT_A, FILL_1),
            2: _chapter(SENT_B, FILL_2),
            3: _chapter(SENT_C, FILL_3),
        }
        self.assertEqual(book_quality.check_duplicate_sentences(texts), [])

    def test_single_chapter_never_reported_cross_chapter(self):
        """单章不构成「跨章重复」——跨章检查对单章必须 0 条。"""
        self.assertEqual(
            book_quality.check_duplicate_sentences({1: _chapter(SENT_A, SENT_A)}), [])


class TestParagraphCheckUnchanged(unittest.TestCase):
    """``check_duplicate_paragraphs`` 口径不变（Task A 设计第 3 项）。"""

    LONG_PARA = "这是一段超过三十个字的重复段落内容，用来验证段落检测口径没有漂移。"  # > 30 字

    def test_long_paragraph_still_reported_high(self):
        texts = {
            1: self.LONG_PARA + "\n" + SENT_A,
            2: self.LONG_PARA + "\n" + SENT_B,
        }
        issues = book_quality.check_duplicate_paragraphs(texts)
        self.assertEqual(len(issues), 1, f"实得: {issues}")
        self.assertEqual(issues[0]["type"], "duplicate_paragraph")
        self.assertEqual(issues[0]["severity"], "high")
        self.assertEqual(issues[0]["chapters"], [1, 2])

    def test_short_paragraph_not_reported(self):
        """≤30 字段落即便跨章相同也不报——口径保持「>30 字整段」，碎片形态交给章内检测。"""
        short_para = "这段只有二十来个字。"
        self.assertLessEqual(len(short_para), 30)
        texts = {1: short_para, 2: short_para}
        self.assertEqual(book_quality.check_duplicate_paragraphs(texts), [])


class TestIntraChapterRepeats(unittest.TestCase):
    """章内重复句检测：按重复句占比定严重度（Task A 验收 3、4、5）。"""

    def test_high_ratio_46_percent(self):
        """章内 46% 句子重复 → 1 条 intra_chapter_repeat、severity=high。"""
        issues = book_quality.check_intra_chapter_repeats({1: _high_repeat_text()})
        self.assertEqual(len(issues), 1, f"每章最多 1 条，实得: {issues}")
        issue = issues[0]
        self.assertEqual(issue["type"], "intra_chapter_repeat")
        self.assertEqual(issue["severity"], "high")
        self.assertEqual(issue["chapter"], 1)
        self.assertFalse(issue["low_sample"], "13 句样本充足，不得标记 low_sample")
        # detail 含重复句数 / 总句数 / 占比 / 最长重复句前 30 字
        self.assertIn("6/13", issue["detail"])
        self.assertIn("46%", issue["detail"])
        self.assertIn(SENT_A[:30], issue["detail"])

    def test_small_sample_repeat_downgraded_to_low(self):
        """最小样本保护：2 句里重复 1 句（ratio 50%）→ 仍报但降为 low + low_sample=True。

        小分母下占比不可靠——50% 若按比例判为 high，会使 `novel 质检` 因 `high > 0`
        从 PASS 变 WARN，属新引入的误报。
        """
        issues = book_quality.check_intra_chapter_repeats({1: "".join([SENT_A, SENT_A])})
        self.assertEqual(len(issues), 1, f"实得: {issues}")
        issue = issues[0]
        self.assertEqual(issue["severity"], "low", "小样本不得升级为 high/medium")
        self.assertTrue(issue["low_sample"])
        self.assertIn("1/2", issue["detail"])
        self.assertIn("50%", issue["detail"])

    def test_boundary_sample_size_8_is_sufficient(self):
        """边界：恰好 8 句（样本充足下限）→ 按比例判 high，low_sample=False。"""
        repeats = _unique_sentences("重复句", 2)
        text = "".join(repeats * 2 + _unique_sentences("独有句", 4))
        issues = book_quality.check_intra_chapter_repeats({1: text})
        self.assertEqual(len(issues), 1, f"实得: {issues}")
        self.assertIn("2/8", issues[0]["detail"])
        self.assertEqual(issues[0]["severity"], "high")
        self.assertFalse(issues[0]["low_sample"])

    def test_boundary_sample_size_7_is_low_sample(self):
        """边界：7 句（低于下限）即便占比 57% 也降为 low + low_sample=True。"""
        repeats = _unique_sentences("重复句", 2)
        text = "".join(repeats * 3 + _unique_sentences("独有句", 1))
        issues = book_quality.check_intra_chapter_repeats({1: text})
        self.assertEqual(len(issues), 1, f"实得: {issues}")
        self.assertIn("4/7", issues[0]["detail"])
        self.assertEqual(issues[0]["severity"], "low")
        self.assertTrue(issues[0]["low_sample"])

    def test_sufficient_sample_20_percent_is_medium(self):
        """样本充足（20 句）时 20% → medium，且 low_sample=False。"""
        repeats = _unique_sentences("重复句", 4)
        text = "".join(repeats * 2 + _unique_sentences("独有句", 12))
        issues = book_quality.check_intra_chapter_repeats({1: text})
        self.assertEqual(len(issues), 1, f"实得: {issues}")
        self.assertIn("4/20", issues[0]["detail"])
        self.assertEqual(issues[0]["severity"], "medium")
        self.assertFalse(issues[0]["low_sample"])

    def test_low_ratio_5_percent(self):
        """章内 5% 句子重复 → severity=low。"""
        text = "".join([SENT_A, SENT_A] + _unique_sentences("独有句", 18))
        issues = book_quality.check_intra_chapter_repeats({1: text})
        self.assertEqual(len(issues), 1, f"实得: {issues}")
        self.assertEqual(issues[0]["severity"], "low")
        self.assertFalse(issues[0]["low_sample"])
        self.assertIn("1/20", issues[0]["detail"])
        self.assertIn("5%", issues[0]["detail"])

    def test_medium_band_15_percent(self):
        """章内 15%（0.10 ≤ ratio < 0.25）→ severity=medium。"""
        repeats = _unique_sentences("重复句", 3)
        text = "".join(repeats * 2 + _unique_sentences("独有句", 14))
        issues = book_quality.check_intra_chapter_repeats({1: text})
        self.assertEqual(len(issues), 1, f"实得: {issues}")
        self.assertEqual(issues[0]["severity"], "medium")
        self.assertIn("3/20", issues[0]["detail"])

    def test_boundary_ratio_exactly_0_25_is_high(self):
        """边界：ratio 恰为 0.25 → high（阈值取 >=）。"""
        repeats = _unique_sentences("重复句", 5)
        text = "".join(repeats * 2 + _unique_sentences("独有句", 10))
        issues = book_quality.check_intra_chapter_repeats({1: text})
        self.assertEqual(len(issues), 1, f"实得: {issues}")
        self.assertIn("5/20", issues[0]["detail"])
        self.assertEqual(issues[0]["severity"], "high")

    def test_boundary_ratio_exactly_0_10_is_medium(self):
        """边界：ratio 恰为 0.10 → medium（阈值取 >=）。"""
        repeats = _unique_sentences("重复句", 2)
        text = "".join(repeats * 2 + _unique_sentences("独有句", 16))
        issues = book_quality.check_intra_chapter_repeats({1: text})
        self.assertEqual(len(issues), 1, f"实得: {issues}")
        self.assertIn("2/20", issues[0]["detail"])
        self.assertEqual(issues[0]["severity"], "medium")

    def test_no_repeat_returns_empty(self):
        """无重复文本 → 0 条（不得为每章报 low 噪声）。"""
        text = "".join(_unique_sentences("独有句", 12))
        self.assertEqual(book_quality.check_intra_chapter_repeats({1: text}), [])

    def test_sentences_shorter_than_10_chars_ignored(self):
        """< 10 字的句子不参与统计；全部过短 → 句子总数为 0 → 跳过该章。"""
        self.assertEqual(
            book_quality.check_intra_chapter_repeats({1: "短句。" * 20}), [])

    def test_empty_text_skipped(self):
        self.assertEqual(book_quality.check_intra_chapter_repeats({1: ""}), [])

    def test_at_most_one_issue_per_chapter(self):
        """每章最多 1 条（聚合），多章各报 1 条。"""
        text = _high_repeat_text()
        issues = book_quality.check_intra_chapter_repeats({1: text, 2: text, 3: text})
        self.assertEqual(len(issues), 3, f"实得: {issues}")
        self.assertEqual([i["chapter"] for i in issues], [1, 2, 3])
        self.assertTrue(all(i["type"] == "intra_chapter_repeat" for i in issues))


class TestBookQualityIntegration(unittest.TestCase):
    """``book_quality_check`` 接入契约：章内检测生效 + 返回键与语义不变。"""

    RESULT_KEYS = {"total_chapters", "total_issues", "severity", "types", "verdict", "issues"}

    def _write_chapters(self, root: Path, mapping: dict):
        for num, text in mapping.items():
            (root / f"chapter-{num:03d}.txt").write_text(text, encoding="utf-8")

    def test_intra_chapter_repeat_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_chapters(root, {
                1: _high_repeat_text(),
                2: _chapter(SENT_B, FILL_2),
            })
            result = book_quality.book_quality_check(str(root))
            self.assertNotIn("error", result)
            self.assertIn("intra_chapter_repeat", result["types"])
            issues = [i for i in result["issues"] if i["type"] == "intra_chapter_repeat"]
            self.assertEqual(len(issues), 1, f"实得: {issues}")
            self.assertEqual(issues[0]["severity"], "high")
            self.assertEqual(issues[0]["chapter"], 1)

    def test_two_adjacent_chapters_duplicate_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_chapters(root, {
                1: _chapter(SENT_A, FILL_1),
                2: _chapter(SENT_A, FILL_3),
            })
            result = book_quality.book_quality_check(str(root))
            self.assertNotIn("error", result)
            issues = [i for i in result["issues"] if i["type"] == "duplicate_sentence"]
            self.assertEqual(len(issues), 1, f"实得: {issues}")
            self.assertEqual(issues[0]["severity"], "low")
            self.assertTrue(issues[0]["adjacent"])

    def test_result_keys_and_semantics_unchanged(self):
        """返回 dict 既有键一个都不能变（含 verdict 判定规则）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_chapters(root, {
                1: _chapter(SENT_B, FILL_1),
                2: _chapter(SENT_C, FILL_2),
            })
            result = book_quality.book_quality_check(str(root))
            # 第二轮 Task B 起返回值**追加** "coverage" 键（加性契约）：既有 6 键
            # 一个都不能少，但不再要求键集合完全相等。
            self.assertTrue(
                self.RESULT_KEYS <= set(result.keys()),
                f"既有键不得缺失，实得: {sorted(result.keys())}",
            )
            self.assertEqual(result["total_chapters"], 2)
            self.assertEqual(result["total_issues"], len(result["issues"]))
            self.assertEqual(
                sum(result["severity"].values()),
                result["total_issues"],
                "severity 计数应覆盖全部 issue",
            )
            self.assertEqual(sum(result["types"].values()), result["total_issues"])
            self.assertIn(result["verdict"], {"PASS", "WARN", "FAIL"})

    def test_single_chapter_still_scanned_for_intra_repeats(self):
        """单章也要检测章内重复（逐章循环内调用，不依赖 len(texts) >= 2 分支）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_chapters(root, {1: _high_repeat_text()})
            result = book_quality.book_quality_check(str(root))
            self.assertNotIn("error", result)
            self.assertEqual(result["total_chapters"], 1)
            self.assertIn("intra_chapter_repeat", result["types"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
