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
  4. （第二轮收口）提示条件统一为「**实际渲染条数 < total_issues**」，且提示里的
     条数按实际渲染条数计算——只要 CLI 砍短了列表就必须说明，不能只在
     ``total_issues > 50``（响应体截断）时才提示；未砍短时零新增输出。
     公共实现是纯函数 ``book_quality.format_truncation_hint(total, rendered)``。

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

# 第二轮收口用夹具（``_overflow_texts(n)`` 产出 n + 1 条问题）：
#   CLI_CUT_CHAPTERS → 31 条：超过两处 CLI 的渲染条数（15 / 20），但未达 issues_limit，
#                            旧实现（只在 issues_truncated 时提示）在此完全静默。
#   CLI_FIT_CHAPTERS → 13 条：低于两处 CLI 的渲染条数，必须全部列出且不得有任何提示。
CLI_CUT_CHAPTERS = 30
CLI_FIT_CHAPTERS = 12

# 问题行的严重度图标前缀（book_quality.py 与 novel.py 质检 共用同一套）
SEVERITY_ICONS = ("🔴", "🟠", "🟡", "⚪")


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

    def test_truncated_flag_at_fixture_scale_boundary(self):
        """真实上限下的夹具规模边界：恰好 50 条不截断，51 条才截断。

        这里把 50/51 与预期标记写死为字面量，不再引用实现里的表达式，因此能独立
        发现「判定写成 >=」或「上限被写死成别的数」这类回归。
        """
        for chapters, expected_total, expected_truncated in ((49, 50, False), (50, 51, True)):
            with self.subTest(chapters=chapters), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _write_chapters(root, _overflow_texts(chapters))
                result = book_quality.book_quality_check(str(root))

                self.assertEqual(result["total_issues"], expected_total,
                                 f"{chapters} 章应恰好产出 {expected_total} 条问题")
                self.assertEqual(result["issues_limit"], EXPECTED_LIMIT)
                self.assertEqual(result["issues_truncated"], expected_truncated,
                                 f"total={expected_total} / limit={EXPECTED_LIMIT} 时的截断标记不对")
                self.assertEqual(len(result["issues"]), min(expected_total, EXPECTED_LIMIT))

    def test_truncated_flag_follows_patched_limit(self):
        """用非 50 的假上限验证判定只依赖 total > limit，且截断也随常量走。

        把上限改成 3 / 7 后边界必须整体平移（total == limit 不截断、limit + 1 才截断）。
        实现里任何写死的 50 或错误的比较符都会被这条抓住。
        """
        original = book_quality.MAX_REPORTED_ISSUES
        try:
            for limit, chapters, expected_total, expected_truncated in (
                (3, 2, 3, False),   # total == limit → 不截断
                (3, 3, 4, True),    # total == limit + 1 → 截断
                (7, 6, 7, False),
                (7, 7, 8, True),
            ):
                book_quality.MAX_REPORTED_ISSUES = limit
                with self.subTest(limit=limit, chapters=chapters), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _write_chapters(root, _overflow_texts(chapters))
                    result = book_quality.book_quality_check(str(root))

                    self.assertEqual(result["total_issues"], expected_total)
                    self.assertEqual(result["issues_limit"], limit,
                                     "issues_limit 必须跟随模块级常量，而不是写死 50")
                    self.assertEqual(result["issues_truncated"], expected_truncated)
                    self.assertEqual(len(result["issues"]), limit,
                                     "issues 的截断长度必须等于当前上限")
        finally:
            book_quality.MAX_REPORTED_ISSUES = original

    def test_limit_constant_used_for_cap(self):
        """截断上限必须来自模块级常量，便于消费方引用。"""
        self.assertEqual(book_quality.MAX_REPORTED_ISSUES, EXPECTED_LIMIT)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, _overflow_texts(OVERFLOW_CHAPTERS))
            result = book_quality.book_quality_check(str(root))
            self.assertEqual(result["issues_limit"], book_quality.MAX_REPORTED_ISSUES)
            self.assertEqual(len(result["issues"]), book_quality.MAX_REPORTED_ISSUES)


class TestFormatTruncationHint(unittest.TestCase):
    """纯函数 ``format_truncation_hint`` 的直接单测（第二轮收口）。

    四处 CLI 共用它，因此这里把「何时提示」与「提示里写哪两个数」钉死在函数上，
    各调用点只负责把**实际渲染条数**传进来。
    """

    def test_returns_hint_with_both_numbers_when_cut_short(self):
        """total > rendered：必须给提示，且两个数字各就各位。"""
        hint = book_quality.format_truncation_hint(30, 15)

        self.assertNotEqual(hint, "", "渲染条数少于总数时必须给提示")
        self.assertRegex(hint, r"共\s*30\s*条，仅显示前\s*15\s*条",
                         "提示必须给出真实总数与实际渲染条数，且顺序不能颠倒")

    def test_empty_when_total_equals_rendered(self):
        """total == rendered：列表完整，必须保持静默。"""
        self.assertEqual(book_quality.format_truncation_hint(12, 12), "",
                         "总数等于渲染条数时不得新增输出")

    def test_empty_when_rendered_exceeds_total(self):
        """total < rendered：渲染比总数还多（不可能砍短），必须保持静默。"""
        self.assertEqual(book_quality.format_truncation_hint(3, 8), "",
                         "渲染条数不少于总数时不得新增输出")

    def test_hint_never_contains_the_response_limit(self):
        """提示只讲「总数 / 实际渲染条数」，不掺入 issues_limit（那是调用点的事）。"""
        hint = book_quality.format_truncation_hint(60, 15)

        self.assertNotIn(str(EXPECTED_LIMIT), hint,
                         "提示里的数字只能是传入的两个数，不得混入写死的上限")


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

    def _count_issue_lines(self, out: str) -> int:
        """数出真正打印出来的问题行数（按严重度图标前缀识别）。"""
        return sum(1 for line in out.splitlines()
                   if line.strip().startswith(SEVERITY_ICONS))

    def _run_novel_qc(self, target) -> tuple:
        import novel  # 延迟导入：仅在需要时加载 CLI 入口
        buf = io.StringIO()
        old_argv = sys.argv
        sys.argv = ["novel.py", "质检", str(target)]
        try:
            with contextlib.redirect_stdout(buf):
                rc = novel.main()
        finally:
            sys.argv = old_argv
        return rc, buf.getvalue()

    def _total_issues(self, root: Path) -> int:
        result = book_quality.book_quality_check(str(root))
        self.assertNotIn("error", result)
        return result["total_issues"]

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

    # ---- 第二轮收口：渲染条数 < total_issues 就必须提示，且条数 == 实际渲染行数 ----

    def test_book_quality_cli_hint_count_equals_rendered_lines(self):
        """31 条问题（未达 50 上限但超过渲染条数）：必须提示，且条数等于实际列出的行数。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, _overflow_texts(CLI_CUT_CHAPTERS))
            total = self._total_issues(root)
            out = self._run_main(["book_quality.py", str(root)], book_quality)

        self.assertGreater(total, 20,
                           "夹具必须超过两处 CLI 的渲染条数（15 / 20），否则测不到「砍短但不截断」")
        self.assertLessEqual(total, EXPECTED_LIMIT,
                             "夹具不得触发响应体截断，否则测的是旧分支")
        rendered = self._count_issue_lines(out)
        self.assertGreater(rendered, 0, "至少要列出一条问题")
        self.assertLess(rendered, total, "夹具必须真的被砍短")
        self.assertRegex(out, rf"共\s*{total}\s*条，仅显示前\s*{rendered}\s*条",
                         "提示条数必须等于实际渲染行数，不得写死")

    def test_book_quality_cli_silent_when_all_issues_rendered(self):
        """13 条问题全部列出：零新增输出。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, _overflow_texts(CLI_FIT_CHAPTERS))
            total = self._total_issues(root)
            out = self._run_main(["book_quality.py", str(root)], book_quality)

        self.assertEqual(self._count_issue_lines(out), total,
                         "13 条问题必须全部列出（否则应给出提示）")
        self.assertNotIn("仅显示前", out, "未砍短时不得出现截断提示")

    def test_novel_qc_hint_count_equals_rendered_lines(self):
        """novel.py 质检 同样按「实际渲染条数 < total_issues」提示。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, _overflow_texts(CLI_CUT_CHAPTERS))
            total = self._total_issues(root)
            rc, out = self._run_novel_qc(root)

        self.assertEqual(rc, 0)
        self.assertGreater(total, 20, "夹具必须超过本命令的渲染条数（20）")
        self.assertLessEqual(total, EXPECTED_LIMIT, "夹具不得触发响应体截断")
        rendered = self._count_issue_lines(out)
        self.assertGreater(rendered, 0, "至少要列出一条问题")
        self.assertLess(rendered, total, "夹具必须真的被砍短")
        self.assertRegex(out, rf"共\s*{total}\s*条，仅显示前\s*{rendered}\s*条",
                         "提示条数必须等于实际渲染行数，不得写死")

    def test_novel_qc_silent_when_all_issues_rendered(self):
        """novel.py 质检 在问题全部列出时零新增输出。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, _overflow_texts(CLI_FIT_CHAPTERS))
            total = self._total_issues(root)
            rc, out = self._run_novel_qc(root)

        self.assertEqual(rc, 0)
        self.assertEqual(self._count_issue_lines(out), total,
                         "13 条问题必须全部列出（否则应给出提示）")
        self.assertNotIn("仅显示前", out, "未砍短时不得出现截断提示")


if __name__ == "__main__":
    unittest.main(verbosity=2)
