#!/usr/bin/env python3
"""QC 十二维 D9「句子重复」接入章内重复检测（优化第三轮 Task 3.2）

背景（双命令不对称）：
  ``book_quality.check_intra_chapter_repeats``（第二轮 Task A 新增，按章内重复句
  占比定档）此前**未被任何维度消费**。后果：同一份稿子，``novel 质检`` 会因
  「章内 46% 重复」报 WARN，而 ``novel qc`` 的总分与 D9 完全不受影响 —— 两个
  命令给出相反结论。

本文件锁定以下契约：
  1. D9「句子重复」并列消费**两个**句子级检测器：
     ``check_duplicate_sentences``（跨章句）+ ``check_intra_chapter_repeats``
     （章内碎片）。单章内 46% 重复 → D9 不再是满分。
  2. D9 的 ``raw`` 分别给出 ``cross_chapter`` / ``intra_chapter`` 两个整数计数，
     并保留 ``source`` 键说明来源函数。
  3. issue 严重度**沿用检测器给出的值**，扣分仍走 ``_severity_to_deduct``
     （critical 20 / high 10 / medium 5 / low 2）——权重表与 ``_judge`` 判定
     规则零改动，本文件用断言锁死字面值。
  4. D10「章节重复」行为**逐项不变**（仍只消费 check_duplicate_chapters +
     check_duplicate_paragraphs，粒度是整章/整段）。
  5. 跨章重复句（第二轮已生效）**不得回退**。

测试全部使用临时目录，不触碰真实 ``assets/``、``gui_state/``、``reports/``。

用法：
  python -B -m unittest tests.test_qc_intra_repeat -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

import book_quality  # noqa: E402
import qc  # noqa: E402

# --- 夹具：12~40 字、以句末标点结尾的句子（命中跨章正则 [^。！？\n]{12,40}[。！？]） ---
SENT_A = "他缓缓推开了那扇沉重的木门。"
SENT_B = "她把那封信折好放进了口袋。"
SENT_C = "窗外的雨声一直下个不停歇。"

# 短句（< 12 字）不参与跨章句子检测，用作不干扰断言的填充
FILL_1 = "天亮了。"
FILL_2 = "风停了。"
FILL_3 = "夜深了。"
FILL_4 = "雨住了。"

# 跨章同段回归用：> 30 字、**不含句末标点**的整段（只命中段落级检测）
SHARED_PARA = "这一段超过三十个字的重复段落内容用于验证段落检测的口径没有发生任何漂移"


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


def _write_chapters(root: Path, mapping: dict):
    """把 {章号: 文本} 写入临时目录（chapter-NNN.txt，命中 chapter_loader 发现规则）。"""
    for num, text in mapping.items():
        (root / f"chapter-{num:03d}.txt").write_text(text, encoding="utf-8")


def _dim(report, key):
    """从 QCReport 里取指定 key 的维度。"""
    for layer in report.layers:
        for d in layer.dimensions:
            if d.key == key:
                return d
    raise AssertionError(f"报告中找不到维度 {key!r}")


def _run(root: Path):
    """在临时章节目录上跑一次 run_qc（不传 voice/asset/book，纯离线）。"""
    return qc.run_qc(str(root))


class TestD9ConsumesIntraChapterRepeats(unittest.TestCase):
    """D9 并列消费跨章句 + 章内碎片（Task 3.2 验收 1）。"""

    def test_intra_chapter_46_percent_lowers_d9_score(self):
        """单章内 46% 句子重复 → D9 < 100，且 raw 计数为 cross=0 / intra>=1。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: _high_repeat_text()})
            dim = _dim(_run(root), "sentence_dup")

            self.assertLess(dim.score, 100.0,
                            "章内 46% 重复必须让 D9 掉分（修复前恒为 100.0）")
            self.assertEqual(dim.raw["cross_chapter"], 0,
                             "单章不构成跨章重复，cross_chapter 必须是 0")
            self.assertGreaterEqual(dim.raw["intra_chapter"], 1,
                                    "章内重复必须计入 intra_chapter")
            self.assertEqual(len(dim.issues), 1, f"实得: {dim.issues}")
            self.assertEqual(dim.issues[0]["type"], "intra_chapter_repeat")
            self.assertEqual(dim.issues[0]["severity"], "high")
            self.assertEqual(dim.issues[0]["chapter"], 1,
                             "_wrap_issues 必须把章号归一为 chapter 字段")
            # high 扣 10 分 → 90.0（沿用 _severity_to_deduct 权重表）
            self.assertEqual(dim.score, 90.0)

    def test_both_detectors_feed_d9_together(self):
        """跨章句与章内碎片**并列**消费：两类 issue 同现，扣分叠加。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {
                1: _high_repeat_text(),                      # 章内 high
                2: _chapter(SENT_A, FILL_2),                 # SENT_A 跨 1/2/3 章 → medium
                3: _chapter(SENT_A, FILL_4),
            })
            dim = _dim(_run(root), "sentence_dup")
            types = sorted(i["type"] for i in dim.issues)
            self.assertEqual(types, ["duplicate_sentence", "intra_chapter_repeat"],
                             f"实得: {dim.issues}")
            self.assertEqual(dim.raw["cross_chapter"], 1)
            self.assertEqual(dim.raw["intra_chapter"], 1)
            # medium(5) + high(10) = 15 → 85.0
            self.assertEqual(dim.score, 85.0)

    def test_severity_from_detector_maps_to_deduct_weight(self):
        """严重度沿用检测器输出：medium 扣 5、low 扣 2（权重表未改）。"""
        medium_text = "".join(
            _unique_sentences("重复句", 4) * 2 + _unique_sentences("独有句", 12))
        low_text = "".join([SENT_A, SENT_A] + _unique_sentences("独有句", 18))
        for text, severity, expected in (
            (medium_text, "medium", 95.0),
            (low_text, "low", 98.0),
        ):
            with self.subTest(severity=severity):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _write_chapters(root, {1: text})
                    dim = _dim(_run(root), "sentence_dup")
                    self.assertEqual(dim.issues[0]["severity"], severity)
                    self.assertEqual(dim.score, expected)
                    self.assertEqual(dim.raw["intra_chapter"], 1)

    def test_intra_issue_fields_pass_through(self):
        """检测器的 low_sample / detail 原样透传，便于消费方判断可信度。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: _high_repeat_text()})
            issue = _dim(_run(root), "sentence_dup").issues[0]
            self.assertIn("low_sample", issue)
            self.assertFalse(issue["low_sample"])
            self.assertIn("46%", issue["detail"])


class TestCrossChapterNotRegressed(unittest.TestCase):
    """跨章重复句（第二轮 Task A 已生效）不得回退（验收 2）。"""

    def test_two_adjacent_chapters_lowers_d9(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {
                1: _chapter(SENT_A, FILL_1),
                2: _chapter(SENT_A, FILL_3),
            })
            dim = _dim(_run(root), "sentence_dup")
            self.assertLess(dim.score, 100.0, "相邻两章共享一句必须让 D9 掉分")
            self.assertEqual(dim.raw["cross_chapter"], 1)
            self.assertEqual(dim.raw["intra_chapter"], 0)
            self.assertEqual(dim.score, 98.0)  # 2 章档 low → 扣 2

    def test_three_chapters_still_medium_deduction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {
                1: _chapter(SENT_A, FILL_1),
                2: _chapter(SENT_A, FILL_2),
                3: _chapter(SENT_A, FILL_3),
            })
            dim = _dim(_run(root), "sentence_dup")
            self.assertEqual(dim.issues[0]["severity"], "medium")
            self.assertEqual(dim.score, 95.0)  # ≥3 章档 medium → 扣 5


class TestNoDuplicateFullScore(unittest.TestCase):
    """无重复文本 → D9 == 100.0，两个计数均为 0（验收 3）。"""

    def test_clean_text_full_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {
                1: _chapter(SENT_A, FILL_1),
                2: _chapter(SENT_B, FILL_2),
                3: _chapter(SENT_C, FILL_3),
            })
            dim = _dim(_run(root), "sentence_dup")
            self.assertEqual(dim.score, 100.0)
            self.assertEqual(dim.raw["cross_chapter"], 0)
            self.assertEqual(dim.raw["intra_chapter"], 0)
            self.assertEqual(dim.issues, [])


class TestRawCountsContract(unittest.TestCase):
    """raw 结构契约：两个整数计数 + source 说明来源函数（验收 3 的设计项 a）。"""

    def test_raw_keys_and_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: _high_repeat_text()})
            raw = _dim(_run(root), "sentence_dup").raw
            self.assertEqual(raw["cross_chapter"], int(raw["cross_chapter"]))
            self.assertEqual(raw["intra_chapter"], int(raw["intra_chapter"]))
            self.assertIsInstance(raw["cross_chapter"], int)
            self.assertIsInstance(raw["intra_chapter"], int)
            self.assertNotIsInstance(raw["cross_chapter"], bool)
            self.assertNotIsInstance(raw["intra_chapter"], bool)
            self.assertIn("source", raw)

    def test_raw_counts_equal_detector_lengths(self):
        """计数必须等于两个检测器的真实返回条数（不是估算）。"""
        texts = {
            1: _high_repeat_text(),
            2: _chapter(SENT_A, FILL_2),
            3: _chapter(SENT_A, FILL_4),
        }
        raw = qc._dim_sentence_dup(texts).raw
        self.assertEqual(raw["cross_chapter"],
                         len(book_quality.check_duplicate_sentences(texts)))
        self.assertEqual(raw["intra_chapter"],
                         len(book_quality.check_intra_chapter_repeats(texts)))

    def test_source_names_both_functions(self):
        raw = qc._dim_sentence_dup({1: _high_repeat_text()}).raw
        self.assertIn("check_duplicate_sentences", raw["source"])
        self.assertIn("check_intra_chapter_repeats", raw["source"])

    def test_dimension_metadata_unchanged(self):
        """D9 的 key/label/layer/weight 与满分口径不变（验收：不改 12 维权重）。"""
        dim = qc._dim_sentence_dup({1: _high_repeat_text()})
        self.assertEqual(dim.key, "sentence_dup")
        self.assertEqual(dim.label, "句子重复")
        self.assertEqual(dim.layer, "L4")
        self.assertEqual(dim.weight, 1.0)
        self.assertGreaterEqual(dim.score, 0.0)
        self.assertLessEqual(dim.score, 100.0)


class TestD10Unchanged(unittest.TestCase):
    """D10「章节重复」逐项不变：仍只消费整章/整段粒度检测器（验收 4）。"""

    def _cross_chapter_paragraph_texts(self):
        """两章共享一段 > 30 字整段；正文其余部分互不相同（压低中段相似度）。"""
        ch1 = "\n".join(
            [SHARED_PARA]
            + [f"他沿着潮湿的街道走了很久才停下脚步，这是第{i}次回头张望。"
               for i in range(18)])
        ch2 = "\n".join(
            [SHARED_PARA]
            + [f"她翻动手中的旧书，纸页发出干燥的轻响，读到第{i}行才抬眼。"
               for i in range(18)])
        return {1: ch1, 2: ch2}

    def test_cross_chapter_paragraph_lowers_d10(self):
        texts = self._cross_chapter_paragraph_texts()
        dim = qc._dim_chapter_dup(texts)
        self.assertLess(dim.score, 100.0, "跨章同段必须让 D10 掉分")
        self.assertIn("duplicate_paragraph", [i["type"] for i in dim.issues])

    def test_d10_issues_equal_direct_detector_calls(self):
        """D10 的输出必须严格等于两个检测器直调结果（零行为漂移）。"""
        texts = self._cross_chapter_paragraph_texts()
        expected = (book_quality.check_duplicate_chapters(texts)
                    + book_quality.check_duplicate_paragraphs(texts))
        dim = qc._dim_chapter_dup(texts)
        self.assertEqual(len(dim.issues), len(expected))
        self.assertEqual([i["type"] for i in dim.issues],
                         [i["type"] for i in expected])
        self.assertEqual(dim.score,
                         qc._score_from_issues(qc._wrap_issues(expected)))
        self.assertEqual(dim.raw["source"],
                         "book_quality.check_duplicate_chapters+paragraphs")

    def test_d10_ignores_intra_chapter_repeats(self):
        """章内碎片**不**进 D10（粒度分工：章内 → D9，整章/整段 → D10）。"""
        texts = {1: _high_repeat_text()}
        dim = qc._dim_chapter_dup(texts)
        self.assertEqual(dim.issues, [])
        self.assertEqual(dim.score, 100.0)
        self.assertEqual(book_quality.check_intra_chapter_repeats(texts) != [], True,
                         "夹具本身必须能触发章内检测，否则本断言无意义")

    def test_d10_metadata_unchanged(self):
        dim = qc._dim_chapter_dup({1: "文本。", 2: "另一段文本。"})
        self.assertEqual(dim.key, "chapter_dup")
        self.assertEqual(dim.label, "章节重复")
        self.assertEqual(dim.layer, "L4")
        self.assertEqual(dim.weight, 1.0)


class TestJudgeAndWeightsUnchanged(unittest.TestCase):
    """_severity_to_deduct 权重表与 _judge 判定规则零改动（验收 5）。"""

    def test_weight_table_literal_values(self):
        for severity, expected in (("critical", 20), ("high", 10),
                                   ("medium", 5), ("low", 2)):
            with self.subTest(severity=severity):
                self.assertEqual(
                    qc._severity_to_deduct([{"severity": severity}]), float(expected))

    def test_unknown_severity_falls_back_to_low(self):
        self.assertEqual(qc._severity_to_deduct([{"severity": "unknown"}]), 2.0)
        self.assertEqual(qc._severity_to_deduct([{}]), 2.0)

    def test_deduct_capped_at_100(self):
        issues = [{"severity": "critical"}] * 6   # 120 → 封顶 100
        self.assertEqual(qc._severity_to_deduct(issues), 100.0)

    def test_judge_rules(self):
        self.assertEqual(qc._judge([]), "PASS")
        self.assertEqual(qc._judge([{"severity": "medium"}] * 9), "PASS")
        self.assertEqual(qc._judge([{"severity": "high"}]), "WARN")
        self.assertEqual(qc._judge([{"severity": "high"}] * 4), "WARN")
        self.assertEqual(qc._judge([{"severity": "high"}] * 5), "FAIL")
        self.assertEqual(qc._judge([{"severity": "critical"}]), "FAIL")
        self.assertEqual(
            qc._judge([{"severity": "critical"}, {"severity": "high"}] * 3), "FAIL")

    def test_intra_high_does_not_change_judge_semantics(self):
        """章内 high 只经既有规则生效（1 条 high → WARN，不是 FAIL）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: _high_repeat_text()})
            report = _run(root)
            highs = [i for i in report.issues if i.get("severity") == "high"]
            self.assertEqual(len(highs), 1, f"实得: {highs}")
            self.assertEqual(report.verdict, "WARN")


class TestDocstringMappingUpdated(unittest.TestCase):
    """模块 docstring 的四层十二维映射表把 D9 写成两个来源函数（设计项 c）。"""

    def test_module_docstring_lists_both_sources(self):
        doc = qc.__doc__ or ""
        self.assertIn("D9", doc)
        self.assertIn("check_duplicate_sentences", doc)
        self.assertIn("check_intra_chapter_repeats", doc)

    def test_dim_docstring_lists_both_sources(self):
        doc = qc._dim_sentence_dup.__doc__ or ""
        self.assertIn("check_duplicate_sentences", doc)
        self.assertIn("check_intra_chapter_repeats", doc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
