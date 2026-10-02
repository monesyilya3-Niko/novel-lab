"""P2-B5/B6 回归测试：非法 chapter_num/batch_size 返回 400 而非 500。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import router
from gui.services import ServiceError


class TestP2B5FormatChapter(unittest.TestCase):
    def test_illegal_chapter_num_returns_400(self):
        body = {"platform_id": "x", "chapter_num": "abc", "title": "t", "content": "c"}
        with self.assertRaises(ServiceError) as ctx:
            router._h_format_chapter({}, body)
        self.assertEqual(ctx.exception.code, 400)

    def test_none_chapter_num_uses_default(self):
        # chapter_num=None 应回退默认值 1，不抛异常（由 service 层决定后续行为）
        try:
            router._h_format_chapter(
                {}, {"platform_id": "x", "chapter_num": None, "title": "t", "content": "c"})
        except ServiceError as e:
            # 允许 service 层因其他原因 400，但不应是 chapter_num 解析 500
            self.assertEqual(e.code, 400)


class TestP2B6BatchSize(unittest.TestCase):
    def test_safe_batch_size_none(self):
        self.assertIsNone(router._safe_batch_size(None))

    def test_safe_batch_size_valid(self):
        self.assertEqual(router._safe_batch_size(5), 5)
        self.assertEqual(router._safe_batch_size("10"), 10)

    def test_safe_batch_size_string_illegal(self):
        with self.assertRaises(ServiceError) as ctx:
            router._safe_batch_size("abc")
        self.assertEqual(ctx.exception.code, 400)

    def test_safe_batch_size_zero_negative(self):
        for v in (0, -5, "-3"):
            with self.assertRaises(ServiceError) as ctx:
                router._safe_batch_size(v)
            self.assertEqual(ctx.exception.code, 400, f"value={v!r}")

    def test_safe_batch_size_float_string(self):
        # "3.5" 不能转为 int，应 400
        with self.assertRaises(ServiceError) as ctx:
            router._safe_batch_size("3.5")
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
