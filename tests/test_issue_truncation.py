#!/usr/bin/env python3
"""质检问题截断上报专项测试（终审 M-5）

背景（问题实证）：
  ``book_quality_check`` 返回 ``total_issues = len(all_issues)``，但 ``issues`` 只给
  前 50 条。当问题数 > 50 时，CLI/GUI 显示「61 个问题」却只列出 50 条（``novel 质检``
  更只列 20 条），读者无法得知被截断，会误以为列表就是全部。第二轮提升重复检测召回后
  更易触发。

本文件锁定以下契约：
  1. 返回 dict **追加** ``issues_truncated: bool``（= ``len(all_issues) > 50``）与
     ``issues_limit: int``（= 50）；既有键语义不变。
  2. 截断上限提为模块级常量 ``book_quality.MAX_REPORTED_ISSUES``，两处共用。
  3. ``book_quality.py`` 与 ``novel.py 质检`` 的非 JSON 输出在截断时追加一行提示。

测试全部使用临时目录 + 内存构造的章节文本，不触碰真实 ``assets/``、``gui_state/``。

用法：
  python -m unittest tests.test_issue_truncation -v
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

import book_quality  # noqa: E402

# 12~40 字、以句末标点结尾（命中跨章句子重复正则）
SENT_A = "他缓缓推开了那扇沉重的木门。"
SENT_B = "她把那封信折好放进了口袋。"

# 契约里写死的截断上限（与 MAX_REPORTED_ISSUES 交叉校验）
EXPECTED_LIMIT = 50

# 制造 > 50 条问题所需的章数（每章至少 1 条 intra_chapter_repeat）
OVERFLOW_CHAPTERS = 60


def _write_chapters(root: Path, texts: dict) -> None:
    for ch, text in texts.items():
        (root / f"第{ch:03d}章.txt").write_text(text, encoding="utf-8")


def _overflow_texts(count: int) -> dict:
    """构造 count 章、每章含章内重复句 → 每章 1 条 intra_chapter_repeat。

    每章的填充句带章号，互不相同，避免额外触发跨章句子重复导致计数漂移。
    """
    texts = {}
    for ch in range(1, count + 1):
        filler = f"第{ch}章用于填充的独有句子内容。"
        texts[ch] = "\n".join([SENT_A] * 3 + [filler] * 6) + "\n"
    return texts


def _small_texts() -> dict:
    """2 章共享 1 句 → 恰好 1 条 duplicate_sentence，远低于截断上限。"""
    return {
        1: SENT_A + "\n天亮了。\n",
        2: SENT_A + "\n风停了。\n",
    }


class TestIssueTruncationContract(unittest.TestCase):
    """返回值的截断标记契约（M-5）。"""

    def test_overflow_marks_truncated_and_caps_list(self):
        """>50 条问题：必须标记截断，且 issues 恰好被截到 50 条。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, _overflow_texts(OVERFLOW_CHAPTERS))
            result = book_quality.book_quality_check(str(root))

            self.assertNotIn("error", result)
            self.assertGreater(result["total_issues"], EXPECTED_LIMIT,
                               "夹具必须真的超过截断上限，否则测不到截断分支")
            self.assertTrue(result["issues_truncated"], "超过上限必须标记 issues_truncated=True")
            self.assertGreater(result["total_issues"], len(result["issues"]),
                               "截断时 total_issues 必须大于 issues 长度")
            self.assertEqual(len(result["issues"]), EXPECTED_LIMIT,
                             f"issues 应被截到 {EXPECTED_LIMIT} 条")
            self.assertEqual(result["issues_limit"], EXPECTED_LIMIT)

    def test_below_limit_not_marked_truncated(self):
        """≤50 条问题：不得标记截断，且 total_issues 与列表长度精确相等。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, _small_texts())
            result = book_quality.book_quality_check(str(root))

            self.assertNotIn("error", result)
            self.assertLessEqual(result["total_issues"], EXPECTED_LIMIT)
            self.assertFalse(result["issues_truncated"])
            self.assertEqual(result["total_issues"], len(result["issues"]),
                             "未截断时 total_issues 必须等于列表长度")
            self.assertEqual(result["issues_limit"], EXPECTED_LIMIT)

    def test_truncated_flag_matches_definition(self):
        """issues_truncated 恒等于 total_issues > issues_limit（两个夹具都验一遍）。"""
        for name, texts in (("overflow", _overflow_texts(OVERFLOW_CHAPTERS)),
                            ("small", _small_texts())):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _write_chapters(root, texts)
                result = book_quality.book_quality_check(str(root))
                self.assertEqual(result["issues_truncated"],
                                 result["total_issues"] > result["issues_limit"])

    def test_limit_constant_used_for_cap(self):
        """截断上限必须来自模块级常量，便于消费方引用。"""
        self.assertEqual(book_quality.MAX_REPORTED_ISSUES, EXPECTED_LIMIT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, _overflow_texts(OVERFLOW_CHAPTERS))
            result = book_quality.book_quality_check(str(root))
            self.assertEqual(result["issues_limit"], book_quality.MAX_REPORTED_ISSUES)
            self.assertEqual(len(result["issues"]), book_quality.MAX_REPORTED_ISSUES)


class TestTruncationHintInCli(unittest.TestCase):
    """非 JSON 输出必须让读者看见「被截断」这件事（M-5）。"""

    def _run_main(self, argv: list, module) -> str:
        buf = io.StringIO()
        old_argv = sys.argv
        sys.argv = argv
        try:
            with contextlib.redirect_stdout(buf):
                with self.assertRaises(SystemExit) as _ctx:
                    module.main()
        finally:
            sys.argv = old_argv
        return buf.getvalue()

    def test_book_quality_cli_prints_hint_when_truncated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, _overflow_texts(OVERFLOW_CHAPTERS))
            out = self._run_main(["book_quality.py", str(root)], book_quality)

        self.assertIn("⚠", out, "截断时必须有提示行")
        self.assertIn("仅显示前", out, "提示行需说明列表被截断")
        self.assertIn(str(EXPECTED_LIMIT), out, "提示行需给出截断上限")

    def test_book_quality_cli_silent_when_not_truncated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, _small_texts())
            out = self._run_main(["book_quality.py", str(root)], book_quality)

        self.assertNotIn("仅显示前", out, "未截断时不得出现截断提示")

    def test_novel_qc_subcommand_prints_hint_when_truncated(self):
        import novel  # 延迟导入：仅在需要时加载 CLI 入口
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, _overflow_texts(OVERFLOW_CHAPTERS))
            buf = io.StringIO()
            old_argv = sys.argv
            sys.argv = ["novel.py", "质检", str(root)]
            try:
                with contextlib.redirect_stdout(buf):
                    rc = novel.main()
            finally:
                sys.argv = old_argv

        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("⚠", out, "截断时必须有提示行")
        self.assertIn(str(EXPECTED_LIMIT), out)

    def test_novel_qc_subcommand_silent_when_not_truncated(self):
        import novel
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, _small_texts())
            buf = io.StringIO()
            old_argv = sys.argv
            sys.argv = ["novel.py", "质检", str(root)]
            try:
                with contextlib.redirect_stdout(buf):
                    rc = novel.main()
            finally:
                sys.argv = old_argv

        self.assertEqual(rc, 0)
        self.assertNotIn("仅显示前", buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
