"""P0-3 上传导入回归：multipart 解析 + 文件名安全 + 端到端上传。

纯标准库（铁律三）。上传集成测试用隔离路径（_isolation），不污染真实
gui_state/ 与 corpus/。
"""
from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import _isolation  # noqa: E402

from gui import router  # noqa: E402
from gui import server as gui_server  # noqa: E402
from gui.services import ServiceError  # noqa: E402

BOUNDARY = "----niko-test-boundary-001"


def _multipart(filename: str | None, content: bytes,
               fields: dict[str, str] | None = None) -> tuple[bytes, str]:
    """手工拼 multipart body（模拟浏览器 FormData，不依赖 email 生成端）。"""
    parts: list[bytes] = []
    if filename is not None:
        parts.append(
            f'--{BOUNDARY}\r\n'
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: text/plain\r\n\r\n".encode("latin-1")
            + content + b"\r\n"
        )
    for k, v in (fields or {}).items():
        parts.append(
            f'--{BOUNDARY}\r\n'
            f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("latin-1")
            + v.encode("utf-8") + b"\r\n"
        )
    parts.append(f"--{BOUNDARY}--\r\n".encode("latin-1"))
    return b"".join(parts), f"multipart/form-data; boundary={BOUNDARY}"


BOOK_TXT = "第1章 楔子\n这是第一章正文内容。\n\n第2章 相遇\n这是第二章正文内容。\n".encode("utf-8")


class TestParseMultipartUpload(unittest.TestCase):
    def test_basic(self):
        raw, ctype = _multipart("book.txt", BOOK_TXT, {"batch_size": "2048"})
        fn, data, fields = router.parse_multipart_upload(raw, ctype)
        self.assertEqual(fn, "book.txt")
        self.assertEqual(data, BOOK_TXT)
        self.assertEqual(fields.get("batch_size"), "2048")

    def test_not_multipart_rejected(self):
        with self.assertRaises(ServiceError) as ctx:
            router.parse_multipart_upload(b"{}", "application/json")
        self.assertEqual(ctx.exception.code, 400)

    def test_no_file_part_rejected(self):
        raw, ctype = _multipart(None, b"", {"batch_size": "1"})
        with self.assertRaises(ServiceError) as ctx:
            router.parse_multipart_upload(raw, ctype)
        self.assertEqual(ctx.exception.code, 400)


class TestUploadFilenameSafety(unittest.TestCase):
    def test_txt_ok(self):
        self.assertEqual(gui_server._safe_upload_filename("暮冬念春.txt"), "暮冬念春.txt")

    def test_non_txt_rejected(self):
        with self.assertRaises(ServiceError) as ctx:
            gui_server._safe_upload_filename("evil.pdf")
        self.assertEqual(ctx.exception.code, 400)

    def test_path_traversal_stripped(self):
        # ../../etc/passwd.txt → 取 basename 后仍为 .txt，但不得含目录
        out = gui_server._safe_upload_filename("../../etc/passwd.txt")
        self.assertEqual(out, "passwd.txt")
        self.assertNotIn("/", out)

    def test_batch_size_validation(self):
        self.assertIsNone(gui_server._parse_upload_batch_size(None))
        self.assertIsNone(gui_server._parse_upload_batch_size("  "))
        self.assertEqual(gui_server._parse_upload_batch_size("2048"), 2048)
        for bad in ("abc", "-5", "0", "3.5"):
            with self.assertRaises(ServiceError, msg=bad) as ctx:
                gui_server._parse_upload_batch_size(bad)
            self.assertEqual(ctx.exception.code, 400)


class TestImportUploadEndToEnd(unittest.TestCase):
    """真实 HTTP 服务 + 隔离路径的上传导入。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="upload_e2e_")
        self.addCleanup(self._tmp.cleanup)
        self._iso = _isolation.isolate_paths(Path(self._tmp.name))
        self._iso.__enter__()
        self.addCleanup(lambda: self._iso.__exit__(None, None, None))

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), gui_server._Handler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        self.addCleanup(self._shutdown)
        self.port = self._httpd.server_address[1]

    def _shutdown(self):
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)

    def _post(self, raw: bytes, ctype: str) -> tuple[int, dict]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request("POST", "/api/import-upload", body=raw,
                     headers={"Content-Type": ctype, "Content-Length": str(len(raw))})
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        conn.close()
        return resp.status, data

    def test_upload_import_ok(self):
        from gui import config
        raw, ctype = _multipart("e2e-book.txt", BOOK_TXT)
        status, data = self._post(raw, ctype)
        self.assertEqual(status, 200, data)
        self.assertEqual(data["code"], 0)
        book = data["data"]
        self.assertEqual(book["total_chapters"], 2)
        # 文件落到隔离 corpus/
        saved = list(config.CORPUS_DIR.glob("e2e-book*.txt"))
        self.assertEqual(len(saved), 1)
        self.assertIn("第1章", saved[0].read_text(encoding="utf-8"))

    def test_upload_duplicate_name_dedup(self):
        from gui import config
        raw, ctype = _multipart("dup.txt", BOOK_TXT)
        s1, _ = self._post(raw, ctype)
        s2, _ = self._post(raw, ctype)
        self.assertEqual((s1, s2), (200, 200))
        names = sorted(p.name for p in config.CORPUS_DIR.glob("dup*.txt"))
        self.assertEqual(names, ["dup-1.txt", "dup.txt"])

    def test_upload_non_txt_rejected(self):
        raw, ctype = _multipart("evil.pdf", b"%PDF-1.4")
        status, data = self._post(raw, ctype)
        self.assertEqual(status, 400)
        self.assertNotEqual(data["code"], 0)

    def test_upload_no_file_rejected(self):
        raw, ctype = _multipart(None, b"")
        status, data = self._post(raw, ctype)
        self.assertEqual(status, 400)

    def test_upload_bad_batch_size_rejected(self):
        raw, ctype = _multipart("b.txt", BOOK_TXT, {"batch_size": "abc"})
        status, _ = self._post(raw, ctype)
        self.assertEqual(status, 400)


    def test_status_after_upload_without_batch_size(self):
        """P0-3 附带修复：task 行 batch_size=NULL 时 get_status 不得崩溃。

        必须初始化 SQLite 表结构，否则走 JSON 回退，覆盖不到真实 bug 路径。
        """
        from gui import db, services
        db.init_schema()
        raw, ctype = _multipart("nobs.txt", BOOK_TXT)
        status, data = self._post(raw, ctype)
        self.assertEqual(status, 200, data)
        book_id = data["data"]["book_id"]
        # 确认 SQLite 行 batch_size 为 NULL（复现实场）
        row = db.get_task(book_id)
        self.assertIsNotNone(row)
        self.assertIsNone(row.get("batch_size"))
        st = services.get_status(book_id)
        self.assertEqual(st["book_id"], book_id)
        self.assertGreater(st["total"], 0)


if __name__ == "__main__":
    unittest.main()
