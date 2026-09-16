#!/usr/bin/env python3
"""chapter_loader 专项测试 — 确定性发现 / 备份排除 / 同章号冲突 / 双根语义

背景（2026-09-16）：
    book_quality / qc / logic_check 曾各自递归扫 ``*.txt`` 并 ``texts[num] = read_text()``
    直接赋值，造成两处静默失效：

      1. ``_备份/``、``备份/``、``backup/``、``.git/``、``build/``、``dist/`` 下的旧稿
         被当作正文参与质检，污染结论；
      2. 同一章号命中多个文件（``第001章.txt`` 与 ``chapter-001.txt`` 并存）时，按
         ``sorted(rglob)`` 的遍历顺序静默覆盖——加载结果依赖文件名字典序，既不可
         复现也不报错。

    本文件为统一加载器 ``scripts/chapter_loader.py`` 建立回归护栏，并锁定三个后端入口
    （``book_quality`` / ``qc`` / ``logic_check``）的错误映射契约。

用法：
  python -m unittest discover -s tests -p "test_chapter_loader.py" -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

# 用常规 import 而非 importlib 动态加载：logic_check / qc / book_quality 会在模块级
# `import chapter_loader`，动态加载会产生第二个模块实例，导致 `ChapterLoadError`
# 类身份不一致、assertRaises 误判。
import chapter_loader  # noqa: E402
import logic_check  # noqa: E402
import qc  # noqa: E402
import book_quality  # noqa: E402


class TestChapterLoader(unittest.TestCase):
    """loader 本体：排除规则、冲突报错、单文件兼容、诊断结构。"""

    def test_backup_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "第001章.txt").write_text("正文", encoding="utf-8")
            (root / "_备份").mkdir()
            (root / "_备份" / "第001章_改前.txt").write_text("备份", encoding="utf-8")
            loaded = chapter_loader.load_chapter_texts(root)
            self.assertEqual(loaded, {1: "正文"})

    def test_same_number_non_backup_files_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "第001章.txt").write_text("A", encoding="utf-8")
            (root / "chapter-001.txt").write_text("B", encoding="utf-8")
            with self.assertRaises(chapter_loader.ChapterLoadError) as ctx:
                chapter_loader.load_chapter_texts(root)
            self.assertEqual(ctx.exception.chapter_number, 1)
            self.assertIn("第001章.txt", str(ctx.exception))
            self.assertIn("chapter-001.txt", str(ctx.exception))

    def test_conflict_error_exposes_source_and_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "第001章.txt").write_text("A", encoding="utf-8")
            (root / "chapter-001.txt").write_text("B", encoding="utf-8")
            with self.assertRaises(chapter_loader.ChapterLoadError) as ctx:
                chapter_loader.load_chapter_texts(root)
            exc = ctx.exception
            self.assertIsInstance(exc, ValueError, "ChapterLoadError 必须是 ValueError 子类")
            self.assertEqual(exc.source, root)
            self.assertEqual(
                exc.candidates,
                sorted([root / "第001章.txt", root / "chapter-001.txt"]),
            )

    def test_directory_file_without_number_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.txt").write_text("不是章节", encoding="utf-8")
            (root / "chapter-002.txt").write_text("第二章", encoding="utf-8")
            result = chapter_loader.discover_chapter_files(root)
            self.assertEqual(set(result["files"]), {2})
            self.assertIn(root / "notes.txt", result["ignored"])

    def test_novel_dir_and_chapters_are_both_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "chapter-001.txt").write_text("外层", encoding="utf-8")
            (root / "chapters").mkdir()
            (root / "chapters" / "chapter-002.txt").write_text("内层", encoding="utf-8")
            loaded = logic_check._load_texts(root)
            self.assertEqual(loaded, {1: "外层", 2: "内层"})

    def test_all_excluded_dir_names_are_skipped(self):
        """六类排除目录逐一验证（含大小写不敏感变体）。"""
        for dir_name in ("_备份", "备份", "backup", "BACKUP", ".git", "build", "dist", "Build"):
            with self.subTest(dir_name=dir_name):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    (root / "第001章.txt").write_text("正文", encoding="utf-8")
                    excluded = root / dir_name
                    excluded.mkdir()
                    (excluded / "第001章.txt").write_text("旧稿", encoding="utf-8")
                    self.assertEqual(chapter_loader.load_chapter_texts(root), {1: "正文"})

    def test_nested_excluded_dir_is_skipped(self):
        """排除判定作用于相对路径的**每个**父目录，而非只看顶层。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            arc = root / "arc-1"
            arc.mkdir()
            (arc / "chapter-001.txt").write_text("正文", encoding="utf-8")
            (arc / "backup").mkdir()
            (arc / "backup" / "chapter-002.txt").write_text("旧稿", encoding="utf-8")
            self.assertEqual(chapter_loader.load_chapter_texts(root), {1: "正文"})

    def test_nested_arc_chapters_are_discovered(self):
        """write.py 的入库结构 chapters/arc-N/chapter-NNN.txt 必须仍被递归发现。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for arc, num in ((1, "001"), (2, "002")):
                d = root / f"arc-{arc}"
                d.mkdir()
                (d / f"chapter-{num}.txt").write_text(f"第{arc}段", encoding="utf-8")
            self.assertEqual(chapter_loader.load_chapter_texts(root), {1: "第1段", 2: "第2段"})

    def test_single_file_without_number_is_chapter_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "draft.txt"
            f.write_text("草稿正文", encoding="utf-8")
            self.assertEqual(chapter_loader.load_chapter_texts(f), {1: "草稿正文"})

    def test_single_file_with_number_uses_that_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "chapter-007.txt"
            f.write_text("第七章", encoding="utf-8")
            self.assertEqual(chapter_loader.load_chapter_texts(f), {7: "第七章"})

    def test_result_is_sorted_by_chapter_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for num in ("003", "001", "002"):
                (root / f"chapter-{num}.txt").write_text(num, encoding="utf-8")
            self.assertEqual(list(chapter_loader.load_chapter_texts(root)), [1, 2, 3])

    def test_missing_path_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(chapter_loader.load_chapter_texts(Path(tmp) / "不存在"), {})

    def test_discover_records_duplicates_and_keeps_files_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "第001章.txt").write_text("A", encoding="utf-8")
            (root / "chapter-001.txt").write_text("B", encoding="utf-8")
            (root / "chapter-002.txt").write_text("C", encoding="utf-8")
            diag = chapter_loader.discover_chapter_files(root)
            self.assertEqual(set(diag["files"]), {2}, "冲突章号不得出现在 files 中")
            self.assertEqual(list(diag["duplicates"]), [1])
            self.assertEqual(
                diag["duplicates"][1],
                sorted([root / "第001章.txt", root / "chapter-001.txt"]),
            )


class TestBackendIntegration(unittest.TestCase):
    """三个后端入口的错误映射契约（brief 指定：book_quality 返回 error dict、
    qc 保持 ValueError、logic_check 保留双根语义）。"""

    @staticmethod
    def _collision_dir(tmp: str) -> Path:
        root = Path(tmp)
        (root / "第001章.txt").write_text("A" * 200, encoding="utf-8")
        (root / "chapter-001.txt").write_text("B" * 200, encoding="utf-8")
        return root

    def test_book_quality_returns_error_dict_on_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = book_quality.book_quality_check(str(self._collision_dir(tmp)))
            self.assertIn("error", result)
            self.assertEqual(result.get("error_type"), "chapter_load")
            self.assertNotIn("verdict", result, "冲突时不得返回伪造的质检结论")
            self.assertIn("第001章.txt", result["error"])
            self.assertIn("chapter-001.txt", result["error"])

    def test_book_quality_ignores_backup_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "第001章.txt").write_text("正文内容。" * 50, encoding="utf-8")
            (root / "_备份").mkdir()
            # 备份文件用**不同章号**：若备份目录未被排除，章节数会变成 2
            (root / "_备份" / "第002章_改前.txt").write_text("旧稿。" * 50, encoding="utf-8")
            result = book_quality.book_quality_check(str(root))
            self.assertNotIn("error", result)
            self.assertEqual(result["total_chapters"], 1, "备份目录不得计入章节数")

    def test_book_quality_still_recursive_on_arc_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            arc = root / "arc-1"
            arc.mkdir()
            (arc / "chapter-001.txt").write_text("正文内容。" * 50, encoding="utf-8")
            result = book_quality.book_quality_check(str(root))
            self.assertNotIn("error", result)
            self.assertEqual(result["total_chapters"], 1)

    def test_qc_load_texts_raises_value_error_on_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._collision_dir(tmp)
            with self.assertRaises(chapter_loader.ChapterLoadError):
                qc._load_texts(str(root))
            # 服务层按 ValueError 记录错误，因此必须保持 ValueError 兼容
            self.assertTrue(issubclass(chapter_loader.ChapterLoadError, ValueError))

    def test_run_qc_propagates_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._collision_dir(tmp)
            with self.assertRaises(ValueError):
                qc.run_qc(str(root))

    def test_qc_load_texts_ignores_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "chapter-001.txt").write_text("正文", encoding="utf-8")
            (root / "备份").mkdir()
            (root / "备份" / "chapter-001.txt").write_text("旧稿", encoding="utf-8")
            self.assertEqual(qc._load_texts(str(root)), {1: "正文"})

    def test_logic_check_dual_root_with_distinct_numbers(self):
        """novel_dir 与 novel_dir/chapters 同时存在时，两处章节都要加载。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "chapter-001.txt").write_text("外层", encoding="utf-8")
            (root / "chapters").mkdir()
            (root / "chapters" / "chapter-002.txt").write_text("内层", encoding="utf-8")
            self.assertEqual(logic_check._load_texts(root), {1: "外层", 2: "内层"})

    def test_logic_check_missing_path_returns_empty(self):
        """保持既有契约：路径不存在返回空 dict（main() 据此报「未找到章节文件」）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(logic_check._load_texts(Path(tmp) / "不存在"), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
