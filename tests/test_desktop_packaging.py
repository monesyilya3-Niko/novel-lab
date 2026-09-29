"""桌面打包回归：assets-manifest.json 必须进安装包（2026-09-29 补齐）。

背景：builtin_sync.load_manifest() 按 ``config.ROOT_DIR / "assets-manifest.json"``
实时读取；安装包内 ROOT_DIR = desktop/backend/。若 sync_backend.py 漏同步该文件，
安装版将静默降级为无 manifest 行为（丢失"官方旧版可升级"分类）。

本测试真跑 desktop/sync_backend.py（desktop/backend/ 是 gitignored 构建产物，
跑完清理），断言 manifest 落位且内容有效。
"""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "desktop") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop"))

BACKEND = ROOT / "desktop" / "backend"


class TestDesktopPackagingManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sync_backend
        rc = sync_backend.main()
        assert rc == 0, f"sync_backend.main() 返回 {rc}"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(BACKEND, ignore_errors=True)

    def test_manifest_packaged(self):
        fp = BACKEND / "assets-manifest.json"
        self.assertTrue(fp.is_file(), "安装包内缺失 assets-manifest.json")
        m = json.loads(fp.read_text(encoding="utf-8"))
        import gui
        self.assertEqual(m["version"], gui.__version__)
        self.assertEqual(len(m["files"]), 72)

    def test_assets_packaged(self):
        self.assertEqual(len(list((BACKEND / "assets").glob("*.json"))), 72)

    def test_dist_packaged(self):
        self.assertTrue((BACKEND / "gui" / "web" / "dist" / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
