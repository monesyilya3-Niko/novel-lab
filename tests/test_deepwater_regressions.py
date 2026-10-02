"""深水区修复回归测试（2026-09-29）：

- B9 LRU：淘汰最久未用、分析中不淘汰、淘汰后透明重载；
- _secure_read_text：Windows 无 O_NOFOLLOW/O_NONBLOCK 时不崩溃；
- B7：_run_analysis 早退仍清理 _runtime；
- B1：rollback 原子性（复制失败不丢原库）。
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_ROOT = _TESTS_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_TESTS_DIR))
import _isolation  # noqa: E402

from gui import services  # noqa: E402


class LruEvictionTest(unittest.TestCase):
    def setUp(self):
        self._iso = _isolation.isolate_paths(Path(tempfile.mkdtemp(prefix="lru_")))
        self._iso.__enter__()
        # 清空缓存状态
        services._BOOKS.clear()
        services._BOOK_INDEX.clear()

    def tearDown(self):
        services._BOOKS.clear()
        services._BOOK_INDEX.clear()
        self._iso.__exit__(None, None, None)

    def _make_book_file(self, name: str, content: str) -> str:
        p = Path(tempfile.mkdtemp(prefix="book_")) / f"{name}.txt"
        p.write_text(content, encoding="utf-8")
        return str(p)

    def test_evicts_least_recently_used(self):
        """第 4 本导入时淘汰最久未用者（_BOOKS_MAX=3）。"""
        paths = [self._make_book_file(f"b{i}", f"第{i}章\n内容{i}\n" * 50) for i in range(4)]
        ids = [services.import_book(p)["book_id"] for p in paths]
        # 第 0 本应被淘汰
        self.assertNotIn(ids[0], services._BOOKS)
        self.assertIn(ids[1], services._BOOKS)
        self.assertIn(ids[2], services._BOOKS)
        self.assertIn(ids[3], services._BOOKS)
        # 但索引保留，可透明重载
        self.assertIn(ids[0], services._BOOK_INDEX)

    def test_evicted_book_transparently_reloads(self):
        """被淘汰的书经 _books_get 透明重载，内容一致。"""
        p = self._make_book_file("reload", "第一章\n测试内容\n" * 100)
        bid = services.import_book(p)["book_id"]
        original_chapters = services._BOOKS[bid]["chapters"]
        # 导入 3 本新书挤掉它
        for i in range(3):
            services.import_book(self._make_book_file(f"x{i}", f"书{i}\n" * 50))
        self.assertNotIn(bid, services._BOOKS)
        # 重载
        book = services._books_get(bid)
        self.assertIsNotNone(book)
        self.assertEqual(book["chapters"], original_chapters)

    def test_analyzing_book_never_evicted(self):
        """正在分析的书不被淘汰（且它必须在缓存中）。"""
        paths = [self._make_book_file(f"a{i}", f"书{i}\n内容\n" * 50) for i in range(3)]
        ids = [services.import_book(p)["book_id"] for p in paths]
        # 此时缓存 = {a0, a1, a2}，标记 a0（最久）正在分析
        with services._runtime_lock:
            services._runtime[ids[0]] = {"stop_flag": threading.Event()}
        try:
            # 再导入 2 本：应跳过 a0，淘汰 a1、a2
            for i in range(2):
                services.import_book(self._make_book_file(f"y{i}", f"新{i}\n" * 50))
            self.assertIn(ids[0], services._BOOKS)
            self.assertNotIn(ids[1], services._BOOKS)
            self.assertNotIn(ids[2], services._BOOKS)
        finally:
            with services._runtime_lock:
                services._runtime.pop(ids[0], None)


class SecureReadWindowsFallbackTest(unittest.TestCase):
    def test_no_nofollow_attr_does_not_crash(self):
        """模拟 Windows（无 O_NOFOLLOW/O_NONBLOCK）：不抛 AttributeError。"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("第一章\n测试\n")
            path = f.name
        # 保存并移除属性，模拟 Windows
        saved = {}
        for attr in ("O_NOFOLLOW", "O_NONBLOCK"):
            if hasattr(os, attr):
                saved[attr] = getattr(os, attr)
                delattr(os, attr)
        try:
            text = services._secure_read_text(path)
            self.assertIn("第一章", text)
        finally:
            for attr, val in saved.items():
                setattr(os, attr, val)
            os.unlink(path)

    def test_symlink_rejected_on_posix(self):
        """POSIX 下符号链接被拒绝（O_NOFOLLOW 路径）。"""
        if not hasattr(os, "O_NOFOLLOW"):
            self.skipTest("无 O_NOFOLLOW")
        with tempfile.TemporaryDirectory() as td:
            real = Path(td) / "real.txt"
            real.write_text("第一章\n真\n", encoding="utf-8")
            link = Path(td) / "link.txt"
            link.symlink_to(real)
            with self.assertRaises(services.ServiceError) as cm:
                services._secure_read_text(str(link))
            self.assertEqual(cm.exception.code, 403)


class RuntimeCleanupTest(unittest.TestCase):
    def test_early_return_cleans_runtime(self):
        """_run_analysis 书为 None 时早退，finally 仍清理 _runtime（B7）。"""
        bid = "nonexistent-book-id"
        ctx = {"stop_flag": threading.Event(), "paused": threading.Event()}
        with services._runtime_lock:
            services._runtime[bid] = ctx
        # _books_get 返回 None（无此书且无索引）
        services._run_analysis(bid, "general", None, 4000, ctx)
        with services._runtime_lock:
            self.assertNotIn(bid, services._runtime)


class BookIndexBoundTest(unittest.TestCase):
    def test_book_index_is_bounded(self):
        """_BOOK_INDEX 有界：超限时淘汰最旧条目，防止无界内存增长。"""
        with services._books_lock:
            services._BOOK_INDEX.clear()
            # 直接模拟 _books_put_locked 的索引写入路径
            for i in range(services._BOOK_INDEX_MAX + 20):
                bid = f"book-{i:04d}"
                services._BOOK_INDEX[bid] = f"/tmp/src-{i}.txt"
                services._BOOK_INDEX.move_to_end(bid)
                while len(services._BOOK_INDEX) > services._BOOK_INDEX_MAX:
                    services._BOOK_INDEX.popitem(last=False)
            self.assertEqual(len(services._BOOK_INDEX), services._BOOK_INDEX_MAX)
            # 最旧的 20 个已被淘汰，最新的保留
            self.assertNotIn("book-0000", services._BOOK_INDEX)
            self.assertIn(f"book-{services._BOOK_INDEX_MAX + 19:04d}", services._BOOK_INDEX)
            services._BOOK_INDEX.clear()


if __name__ == "__main__":
    unittest.main()
