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


BOOK_TXT = "第1章 楔子\n这是第一章正文内容。\n\n第2章 相遇\n这是第二章正文内容。\n".encode()


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

    def test_rfc2231_chinese_filename(self):
        """RFC2231 filename*=utf-8''%XX 形式中文文件名。"""
        from urllib.parse import quote
        enc = quote("暮冬念春.txt", encoding="utf-8")
        raw = (
            f"--{BOUNDARY}\r\n"
            f'Content-Disposition: form-data; name="file"; filename*=utf-8\'\'{enc}\r\n'
            f"Content-Type: text/plain\r\n\r\n".encode("latin-1")
            + BOOK_TXT + b"\r\n"
            + f"--{BOUNDARY}--\r\n".encode("latin-1")
        )
        ctype = f"multipart/form-data; boundary={BOUNDARY}"
        fn, data, _ = router.parse_multipart_upload(raw, ctype)
        self.assertEqual(fn, "暮冬念春.txt")
        self.assertEqual(data, BOOK_TXT)

    def test_raw_utf8_quoted_chinese_filename(self):
        """浏览器直发 raw UTF-8 中文文件名（非 RFC2231）也能恢复。"""
        raw_name = "暮冬念春.txt".encode().decode("latin-1")
        raw = (
            f"--{BOUNDARY}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{raw_name}"\r\n'
            f"Content-Type: text/plain\r\n\r\n".encode("latin-1")
            + BOOK_TXT + b"\r\n"
            + f"--{BOUNDARY}--\r\n".encode("latin-1")
        )
        ctype = f"multipart/form-data; boundary={BOUNDARY}"
        fn, data, _ = router.parse_multipart_upload(raw, ctype)
        self.assertEqual(fn, "暮冬念春.txt")
        self.assertEqual(data, BOOK_TXT)

    def test_file_part_not_first(self):
        """文本字段在前、文件 part 在后时仍能正确解析。"""
        parts = [
            f"--{BOUNDARY}\r\n"
            f'Content-Disposition: form-data; name="batch_size"\r\n\r\n'.encode("latin-1")
            + b"4096" + b"\r\n",
            f"--{BOUNDARY}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="b.txt"\r\n'
            f"Content-Type: text/plain\r\n\r\n".encode("latin-1")
            + BOOK_TXT + b"\r\n",
            f"--{BOUNDARY}--\r\n".encode("latin-1"),
        ]
        raw = b"".join(parts)
        ctype = f'multipart/form-data; boundary="{BOUNDARY}"'
        fn, data, fields = router.parse_multipart_upload(raw, ctype)
        self.assertEqual(fn, "b.txt")
        self.assertEqual(data, BOOK_TXT)
        self.assertEqual(fields.get("batch_size"), "4096")

    def test_truncated_body_rejected(self):
        raw, ctype = _multipart("b.txt", BOOK_TXT)
        with self.assertRaises(ServiceError) as ctx:
            router.parse_multipart_upload(raw[: len(raw) // 2], ctype)
        self.assertEqual(ctx.exception.code, 400)

    def test_missing_boundary_rejected(self):
        raw, _ = _multipart("b.txt", BOOK_TXT)
        with self.assertRaises(ServiceError) as ctx:
            router.parse_multipart_upload(raw, "multipart/form-data")
        self.assertEqual(ctx.exception.code, 400)

    def test_memory_amplification_bounded(self):
        """回归：解析 20MB body 时 tracemalloc 峰值不得超过 body 的 3 倍。

        旧 stdlib email 实现实测约 10 倍瞬时放大（100MB 上传 RSS 峰值 ~3.1GB）；
        手工扫描实现应为切片提取（~2 倍以内），此处取 3 倍为硬上限。
        """
        import tracemalloc
        big = b"x" * (20 * 1024 * 1024)
        raw, ctype = _multipart("big.txt", big)
        tracemalloc.start()
        try:
            fn, data, _ = router.parse_multipart_upload(raw, ctype)
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(fn, "big.txt")
        self.assertEqual(len(data), len(big))
        self.assertLess(peak, 3 * len(raw), f"peak={peak} body={len(raw)}")


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


class TestImportPathEndpoint(unittest.TestCase):
    """POST /api/import（JSON 传路径）的准入（2026-10-08 撤掉项目根墙）。

    M8 曾要求"导入路径必须在项目目录内"，但用户要拆的书本来就放在项目外，
    和质检那句"路径放不进去"是同一条墙。这里钉住新契约：路径随便指，
    能读到的只有正文——非 .txt、目录、不存在一律拒。
    复用 TestImportUploadEndToEnd 的真实 HTTP + 隔离路径骨架。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="import_path_")
        self.addCleanup(self._tmp.cleanup)
        self._iso = _isolation.isolate_paths(Path(self._tmp.name))
        self._iso.__enter__()
        self.addCleanup(lambda: self._iso.__exit__(None, None, None))

        # 稿子放在**另一个**临时目录：确保它既不在项目根、也不在隔离根内
        self._ext = tempfile.TemporaryDirectory(prefix="import_ext_")
        self.addCleanup(self._ext.cleanup)
        self.ext_dir = Path(self._ext.name)

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
        from gui import db
        db.close()

    def _get(self, path: str) -> tuple[int, dict]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request("GET", path)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        conn.close()
        return resp.status, data

    def _chapter_text(self, book_id: str, no: int) -> str:
        # book_id 里有中文，请求行必须是 ASCII（http.client 直接 encode('ascii')）
        from urllib.parse import quote
        status, data = self._get(f"/api/book/{quote(book_id, safe='')}/chapter/{no}")
        self.assertEqual(status, 200, data)
        return json.dumps(data, ensure_ascii=False)

    def _post(self, payload: dict) -> tuple[int, dict]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        body = json.dumps(payload).encode("utf-8")
        conn.request("POST", "/api/import", body=body,
                     headers={"Content-Type": "application/json",
                              "Content-Length": str(len(body))})
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        conn.close()
        return resp.status, data

    def test_import_from_outside_project_root(self):
        from gui import config
        fp = self.ext_dir / "外部稿.txt"
        fp.write_bytes(BOOK_TXT)
        status, data = self._post({"path": str(fp)})
        self.assertEqual(status, 200, data)
        self.assertEqual(data["code"], 0)
        self.assertEqual(data["data"]["total_chapters"], 2)
        # 路径式导入是"就地引用"原文件（上传式才归一化落 corpus/），
        # 所以这里断言的是引用到了项目外的真实路径，而不是副本落在哪。
        self.assertEqual(str(Path(data["data"]["source_path"]).resolve()),
                         str(fp.resolve()))

    def test_gbk_book_imports(self):
        # 拆书导入侧早就 UTF-8→GBK 两段解；这条钉住"GBK 整本也能拆"，
        # 并且章节内容解对了（不是静默替换成乱码再切章）
        fp = self.ext_dir / "gbk整本.txt"
        fp.write_bytes(BOOK_TXT.decode().encode("gbk"))
        status, data = self._post({"path": str(fp)})
        self.assertEqual(status, 200, data)
        self.assertEqual(data["data"]["total_chapters"], 2)
        got = self._chapter_text(data["data"]["book_id"], 1)
        self.assertIn("这是第一章正文内容。", got)

    def test_non_text_suffix_refused(self):
        from gui import config
        secret = config.STATE_ROOT / "index.db"
        secret.parent.mkdir(parents=True, exist_ok=True)
        secret.write_bytes(b"SQLite format 3\x00")
        status, data = self._post({"path": str(secret)})
        self.assertEqual(status, 400, data)
        self.assertIn(".txt", data["message"])

    def test_directory_refused(self):
        status, data = self._post({"path": str(self.ext_dir)})
        self.assertIn(status, (400, 404), data)

    def test_missing_file_404(self):
        status, data = self._post({"path": str(self.ext_dir / "没有这本书.txt")})
        self.assertEqual(status, 404, data)

    def test_non_string_path_is_400_not_500(self):
        status, data = self._post({"path": 12345})
        self.assertEqual(status, 400, data)


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
        # 必须显式清理，否则 Windows 会报 [WinError 32] 无法删除临时目录
        from gui import db
        db.close()

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
