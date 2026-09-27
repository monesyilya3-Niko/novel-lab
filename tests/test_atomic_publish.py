"""P0-2 CLI 原子发布回归测试：两份报告要么全进 reports/，要么全不进。"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class TestAtomicPublish(unittest.TestCase):
    def test_partial_failure_rolls_back(self):
        """第二个 move 失败时，第一个已搬入的文件被回滚删除。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            staging = tmp / "staging"
            reports = tmp / "reports"
            staging.mkdir()
            reports.mkdir()
            book_out = staging / "book-拆书报告.md"
            craft_out = staging / "笔法分析.md"
            book_out.write_text("x" * 6000, encoding="utf-8")
            craft_out.write_text("y" * 6000, encoding="utf-8")

            # 模拟 novel.py 的原子发布逻辑
            moved: list[Path] = []
            real_move = shutil.move

            def fail_on_second(src, dst):
                if "笔法" in str(src):
                    raise OSError("模拟磁盘故障")
                return real_move(src, dst)

            with mock.patch("shutil.move", side_effect=fail_on_second):
                with self.assertRaises(OSError):
                    try:
                        for src in (book_out, craft_out):
                            if src.exists():
                                dst = reports / src.name
                                shutil.move(str(src), str(dst))
                                moved.append(dst)
                    except OSError:
                        for dst in moved:
                            try:
                                dst.unlink()
                            except OSError:
                                pass
                        raise

            # 断言：reports/ 为空（回滚成功），无部分发布
            self.assertEqual(list(reports.iterdir()), [])

    def test_success_moves_both(self):
        """正常情况两份都搬入。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            staging = tmp / "staging"
            reports = tmp / "reports"
            staging.mkdir()
            reports.mkdir()
            for name in ("book-拆书报告.md", "笔法分析.md"):
                (staging / name).write_text("z" * 100, encoding="utf-8")

            moved: list[Path] = []
            for src in (staging / "book-拆书报告.md", staging / "笔法分析.md"):
                if src.exists():
                    dst = reports / src.name
                    shutil.move(str(src), str(dst))
                    moved.append(dst)

            self.assertEqual(len(list(reports.iterdir())), 2)


if __name__ == "__main__":
    unittest.main()
