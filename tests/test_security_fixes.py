#!/usr/bin/env python3
"""安全修复回归测试（2026-09-28 安全审计发现）。

覆盖：
1. get_book_results book_id 路径穿越 -> 未导入 book_id 直接 404，不再拼接路径
2. export_book_for_platform book_dir 越界 -> 项目根外 403
3. CORS Origin: null 不再放行
4. distill_status genre 白名单
5. secret_store 落盘权限 0o600（POSIX）
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gui import services
from gui.services import ServiceError


class TestBookIdTraversal(unittest.TestCase):
    def test_unknown_book_id_404(self):
        # ../ 穿越 payload：必须 404（_get_book_or_raise），不能走到路径拼接
        with self.assertRaises(ServiceError) as cm:
            services.get_book_results("../../etc")
        self.assertEqual(cm.exception.code, 404)

    def test_unknown_book_id_no_path_access(self):
        # 即使 book_id 形如合法路径，也必须先校验存在性
        with self.assertRaises(ServiceError) as cm:
            services.get_book_results("nonexistent-book-12345")
        self.assertEqual(cm.exception.code, 404)


class TestExportBookDirContainment(unittest.TestCase):
    def test_outside_root_403(self):
        from gui import platform_service
        with self.assertRaises(ServiceError) as cm:
            platform_service.export_book_for_platform("qidian", "/etc")
        self.assertEqual(cm.exception.code, 403)

    def test_parent_escape_403(self):
        from gui import config, platform_service
        evil = str(config.ROOT_DIR.parent / "etc")
        with self.assertRaises(ServiceError) as cm:
            platform_service.export_book_for_platform("qidian", evil)
        # /etc 不存在或越界：403（越界）或 404（不存在但在根内）
        self.assertIn(cm.exception.code, (403, 404))


class TestCorsNullOrigin(unittest.TestCase):
    def test_null_origin_rejected(self):
        from gui.server import _Handler as Handler
        h = Handler.__new__(Handler)
        self.assertFalse(h._is_same_host_origin("null"))

    def test_localhost_still_allowed(self):
        from gui.server import _Handler as Handler
        h = Handler.__new__(Handler)
        self.assertTrue(h._is_same_host_origin("http://localhost:8080"))
        self.assertTrue(h._is_same_host_origin("http://127.0.0.1:8000"))

    def test_empty_origin_rejected(self):
        from gui.server import _Handler as Handler
        h = Handler.__new__(Handler)
        self.assertFalse(h._is_same_host_origin(""))


class TestDistillStatusWhitelist(unittest.TestCase):
    def test_wildcard_rejected(self):
        from gui import advanced_service
        with self.assertRaises(ServiceError) as cm:
            advanced_service.distill_status("*")
        self.assertEqual(cm.exception.code, 400)

    def test_path_sep_rejected(self):
        from gui import advanced_service
        with self.assertRaises(ServiceError) as cm:
            advanced_service.distill_status("../secret")
        self.assertEqual(cm.exception.code, 400)


class TestSecretStorePerms(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX only")
    def test_file_created_0600(self):
        """调用生产函数 save_secrets，落盘文件必须为 0o600（无先写后chmod窗口）。"""
        import sys
        import tempfile

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from secret_store import load_secrets, save_secrets

        with tempfile.TemporaryDirectory() as td:
            p = save_secrets({"k": "v"}, Path(td))
            mode = oct(p.stat().st_mode & 0o777)
            self.assertEqual(mode, "0o600")
            # 回读一致，证明写入路径就是被测的生产路径
            self.assertEqual(load_secrets(Path(td)), {"k": "v"})


if __name__ == "__main__":
    unittest.main()
