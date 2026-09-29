"""P0-2 CLI 原子发布回归测试：两份报告要么全进 reports/，要么全不进。

直接调用 novel.publish_reports_atomically（生产函数），不复制逻辑。
核心要求：同名旧报告存在时，中途失败必须完整恢复旧报告内容，且无备份残留。
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from novel import publish_reports_atomically


class TestAtomicPublish(unittest.TestCase):
    def _stage(self, tmp: Path, old_book="OLD-BOOK", old_craft="OLD-CRAFT"):
        staging = tmp / "staging"
        reports = tmp / "reports"
        staging.mkdir()
        reports.mkdir()
        book_out = staging / "book-拆书报告.md"
        craft_out = staging / "笔法分析.md"
        book_out.write_text("NEW-BOOK" * 1000, encoding="utf-8")
        craft_out.write_text("NEW-CRAFT" * 1000, encoding="utf-8")
        if old_book is not None:
            (reports / "book-拆书报告.md").write_text(old_book, encoding="utf-8")
        if old_craft is not None:
            (reports / "笔法分析.md").write_text(old_craft, encoding="utf-8")
        return staging, reports, book_out, craft_out

    def _fail_on_staging_move(self, staging: Path, target_name: str):
        """仅当从 staging 搬运目标新报告时失败；备份旧报告的 move 不受影响。"""
        real_move = shutil.move

        def _move(src, dst):
            src_p = Path(src)
            if src_p.parent == staging and src_p.name == target_name:
                raise OSError("模拟磁盘故障")
            return real_move(src, dst)

        return mock.patch("shutil.move", side_effect=_move)

    def _snapshot(self, reports: Path):
        return sorted(p.name for p in reports.iterdir())

    def test_failure_restores_preexisting_reports(self):
        """两份旧报告都存在、第二个新报告搬运失败 → 旧报告内容完整恢复，无残留。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            staging, reports, book_out, craft_out = self._stage(tmp)
            with self._fail_on_staging_move(staging, "笔法分析.md"):
                with self.assertRaises(OSError):
                    publish_reports_atomically((book_out, craft_out), reports)
            # 两份旧报告内容完整恢复
            self.assertEqual((reports / "book-拆书报告.md").read_text(encoding="utf-8"), "OLD-BOOK")
            self.assertEqual((reports / "笔法分析.md").read_text(encoding="utf-8"), "OLD-CRAFT")
            # 无备份目录/临时文件残留：reports/ 里只有两个文件
            self.assertEqual(self._snapshot(reports), ["book-拆书报告.md", "笔法分析.md"])
            for p in reports.iterdir():
                self.assertTrue(p.is_file())

    def test_failure_without_preexisting_reports_leaves_empty(self):
        """旧报告不存在、第二个搬运失败 → reports/ 为空，无残留。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            staging, reports, book_out, craft_out = self._stage(tmp, old_book=None, old_craft=None)
            with self._fail_on_staging_move(staging, "笔法分析.md"):
                with self.assertRaises(OSError):
                    publish_reports_atomically((book_out, craft_out), reports)
            self.assertEqual(self._snapshot(reports), [])

    def test_success_replaces_preexisting_reports(self):
        """正常发布：旧报告被新内容替换，返回目标路径，无备份残留。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            staging, reports, book_out, craft_out = self._stage(tmp)
            moved = publish_reports_atomically((book_out, craft_out), reports)
            self.assertEqual(len(moved), 2)
            self.assertEqual((reports / "book-拆书报告.md").read_text(encoding="utf-8"), "NEW-BOOK" * 1000)
            self.assertEqual((reports / "笔法分析.md").read_text(encoding="utf-8"), "NEW-CRAFT" * 1000)
            self.assertEqual(self._snapshot(reports), ["book-拆书报告.md", "笔法分析.md"])
            self.assertEqual(list(staging.iterdir()), [])

    def test_missing_source_skipped(self):
        """不存在的源文件被跳过，不阻断其他文件；另一份旧报告不受影响。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            staging, reports, book_out, craft_out = self._stage(tmp)
            craft_out.unlink()
            moved = publish_reports_atomically((book_out, craft_out), reports)
            self.assertEqual(len(moved), 1)
            self.assertEqual((reports / "book-拆书报告.md").read_text(encoding="utf-8"), "NEW-BOOK" * 1000)
            self.assertEqual((reports / "笔法分析.md").read_text(encoding="utf-8"), "OLD-CRAFT")

    def test_rollback_unlink_failure_still_raises(self):
        """回滚删除失败（OSError）被忽略，原异常仍向上传播。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            staging, reports, book_out, craft_out = self._stage(tmp)
            with self._fail_on_staging_move(staging, "笔法分析.md"), \
                 mock.patch.object(Path, "unlink", side_effect=OSError("删不动")):
                with self.assertRaises(OSError):
                    publish_reports_atomically((book_out, craft_out), reports)


if __name__ == "__main__":
    unittest.main()
