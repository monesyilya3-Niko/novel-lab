"""内置示例语料接口测试（/api/samples, /api/samples/import）。

覆盖：
1. GET /api/samples 列出随包发布的 8 个示例（名称/题材/章节数/大小）。
2. POST /api/samples/import 合法导入 → 生成 book（含 3 章），写入隔离语料目录。
3. 非法文件名（目录遍历/后缀不对）→ 400。
4. 白名单内但不存在的示例 → 404。

隔离：setUpModule/tearDownModule 成对重定向全部数据路径常量到临时目录，
禁止写入真实 gui_state/assets/corpus。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from gui import router, services  # noqa: E402

from _isolation import isolate_paths  # noqa: E402

_TMP = None
_ISOLATION_EXIT = None


def setUpModule():
    global _TMP, _ISOLATION_EXIT
    _TMP = Path(tempfile.mkdtemp(prefix="samples_"))
    _ISOLATION_EXIT = isolate_paths(_TMP)
    _ISOLATION_EXIT.__enter__()  # 进入上下文：重定向全部数据路径常量


def tearDownModule():
    global _TMP
    try:
        _ISOLATION_EXIT.__exit__(None, None, None)
    except Exception:
        pass
    services._BOOKS.clear()
    services._runtime.clear()
    if _TMP:
        import shutil

        shutil.rmtree(_TMP, ignore_errors=True)
        _TMP = None


def _dispatch_post_import(name):
    payload, _ = router.dispatch(
        "POST", "/api/samples/import", {"name": name}, {})
    return payload


class TestSamplesList(unittest.TestCase):
    def test_list_returns_8_samples(self):
        payload, _ = router.dispatch("GET", "/api/samples", {}, {})
        self.assertEqual(payload["code"], 0)
        samples = payload["data"]["samples"]
        self.assertEqual(len(samples), 8)
        for s in samples:
            self.assertTrue(s["name"].startswith("示例-"))
            self.assertTrue(s["name"].endswith(".txt"))
            self.assertEqual(s["chapters"], 3)
            self.assertGreater(s["size"], 8000)
            self.assertEqual(s["genre"], s["name"][3:-4])


class TestSamplesImport(unittest.TestCase):
    def tearDown(self):
        services._BOOKS.clear()
        services._runtime.clear()

    def test_import_valid_sample(self):
        payload = _dispatch_post_import("示例-悬疑.txt")
        self.assertEqual(payload["code"], 0)
        data = payload["data"]
        self.assertIn("book_id", data)
        self.assertEqual(len(data["chapters"]), 3)
        titles = [c["title"] for c in data["chapters"]]
        self.assertTrue(all(t.startswith("第") for t in titles))

    def test_import_duplicate_ok(self):
        """重复导入不报错（防重名复制）。"""
        p1 = _dispatch_post_import("示例-玄幻.txt")
        p2 = _dispatch_post_import("示例-玄幻.txt")
        self.assertEqual(p1["code"], 0)
        self.assertEqual(p2["code"], 0)

    def test_import_traversal_rejected(self):
        for bad in ("../gui/router.py", "..\\gui\\router.py",
                    "示例-a/b.txt", "示例-悬疑.md", "", "示例-.txt"):
            with self.assertRaises(services.ServiceError) as cm:
                _dispatch_post_import(bad)
            self.assertEqual(cm.exception.code, 400, f"name={bad!r}")

    def test_import_missing_sample_404(self):
        with self.assertRaises(services.ServiceError) as cm:
            _dispatch_post_import("示例-不存在.txt")
        self.assertEqual(cm.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
