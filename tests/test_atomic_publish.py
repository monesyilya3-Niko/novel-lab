"""P0-2 CLI 原子发布回归测试：两份报告要么全进 reports/，要么全不进。

直接调用 novel.publish_reports_atomically（生产函数），不复制逻辑。
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
    def _stage(self, tmp: Path):
        staging = tmp / "staging"
        reports = tmp / "reports"
        staging.mkdir()
        reports.mkdir()
        book_out = staging / "book-拆书报告.md"
        craft_out = staging / "笔法分析.md"
        book_out.write_text("x" * 6000, encoding="utf-8")
        craft_out.write_text("y" * 6000, encoding="utf-8")
        return staging, reports, book_out, craft_out

    def test_partial_failure_rolls_back(self):
        """第二个 move 失败时，第一个已搬入的文件被回滚删除，异常向上传播。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            staging, reports, book_out, craft_out = self._stage(tmp)
            real_move = shutil.move

            def fail_on_second(src, dst):
                if "笔法" in str(src):
                    raise OSError("模拟磁盘故障")
                return real_move(src, dst)

            with mock.patch("shutil.move", side_effect=fail_on_second):
                with self.assertRaises(OSError):
                    publish_reports_atomically((book_out, craft_out), reports)

            # reports/ 为空（回滚成功），无部分发布；
            # 第一个文件已从 staging 搬走又被回滚删除（生产行为：staging 随后整体清理）
            self.assertEqual(list(reports.iterdir()), [])
            self.assertFalse((staging / "book-拆书报告.md").exists())

    def test_success_moves_both(self):
        """正常情况两份都搬入，返回目标路径。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            staging, reports, book_out, craft_out = self._stage(tmp)
            moved = publish_reports_atomically((book_out, craft_out), reports)
            self.assertEqual(len(moved), 2)
            self.assertEqual(sorted(p.name for p in reports.iterdir()),
                             ["book-拆书报告.md", "笔法分析.md"])
            self.assertEqual(list(staging.iterdir()), [])

    def test_missing_source_skipped(self):
        """不存在的源文件被跳过，不阻断其他文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            staging, reports, book_out, craft_out = self._stage(tmp)
            craft_out.unlink()
            moved = publish_reports_atomically((book_out, craft_out), reports)
            self.assertEqual(len(moved), 1)
            self.assertTrue((reports / "book-拆书报告.md").exists())

    def test_rollback_failure_ignored(self):
        """回滚时目标删除失败（OSError）被忽略，原异常仍传播。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            staging, reports, book_out, craft_out = self._stage(tmp)
            real_move = shutil.move

            def fail_on_second(src, dst):
                if "笔法" in str(src):
                    raise OSError("模拟磁盘故障")
                return real_move(src, dst)

            with mock.patch("shutil.move", side_effect=fail_on_second), \
                 mock.patch.object(Path, "unlink", side_effect=OSError("删不动")):
                with self.assertRaises(OSError):
                    publish_reports_atomically((book_out, craft_out), reports)


if __name__ == "__main__":
    unittest.main()
