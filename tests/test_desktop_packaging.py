"""桌面打包回归：安装包内容完整性（2026-09-29 起）。

背景1：builtin_sync.load_manifest() 按 ``config.ROOT_DIR / "assets-manifest.json"``
实时读取；安装包内 ROOT_DIR = desktop/backend/。若 sync_backend.py 漏同步该文件，
安装版将静默降级为无 manifest 行为（丢失"官方旧版可升级"分类）。

背景2（2026-09-29 深度检查发现）：main.js 打包后 spawn
``resources/backend/python-win/python.exe``，但旧 sync_backend.py 从不复制
python-win/，且 ``npm run dist`` 也不自动跑 sync_backend.py——按文档步骤构建
会产出没有后端/没有 Python 运行时的坏安装包。已修复：
sync_backend.py 复制 python-win（缺失则报错退出），package.json 加 predist 钩子，
新增 fetch-python-win.py 自动准备 embeddable Python。

本测试真跑 desktop/sync_backend.py（desktop/backend/ 是 gitignored 构建产物，
跑完清理），断言安装包内容完整。
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
PYWIN_SRC = ROOT / "desktop" / "build" / "python-win"


class TestDesktopPackagingManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 构建机前置：build/python-win/ 不存在时跳过（跑 fetch-python-win.py 可准备）；
        # 在能构建的机器上必须全量断言。
        if not (PYWIN_SRC / "python.exe").is_file():
            raise unittest.SkipTest(
                "desktop/build/python-win/python.exe 不存在，跳过打包回归；"
                "构建前请跑 python desktop/fetch-python-win.py"
            )
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
        shipped = len(list((ROOT / "assets").glob("*.json")))
        self.assertEqual(len(m["files"]), shipped,
                         "manifest 文件数应与仓库 assets/ 实测一致")

    def test_assets_packaged(self):
        shipped = len(list((ROOT / "assets").glob("*.json")))
        self.assertEqual(len(list((BACKEND / "assets").glob("*.json"))), shipped,
                         "打包资产数应与仓库 assets/ 实测一致")

    def test_dist_packaged(self):
        self.assertTrue((BACKEND / "gui" / "web" / "dist" / "index.html").is_file())

    def test_python_win_packaged(self):
        """背景2：python-win/ 必须进安装包，否则安装版启动即失败。"""
        exe = BACKEND / "python-win" / "python.exe"
        self.assertTrue(exe.is_file(), "安装包内缺失 backend/python-win/python.exe")
        self.assertTrue((BACKEND / "python-win" / "python312.dll").is_file(),
                        "安装包内缺失 backend/python-win/python312.dll")

    def test_predist_hook(self):
        """背景2：npm run dist 必须自动跑后端同步，否则文档步骤产出坏安装包。"""
        pkg = json.loads((ROOT / "desktop" / "package.json").read_text(encoding="utf-8"))
        predist = pkg.get("scripts", {}).get("predist", "")
        self.assertIn("sync_backend.py", predist, "package.json 缺少 predist 同步钩子")
        self.assertIn("fetch-python-win.py", predist, "package.json predist 未准备 python-win")

    def test_dev_files_excluded(self):
        """背景3（2026-09-29 安装包开箱审计）：云端 exe 经解剖发现
        gui/web/src（前端源码）、gui/web/e2e、vite/eslint 等构建配置、
        scripts/*_isolated.sh 曾被打进安装包。安装版运行时只需要
        gui/web/dist，这些开发期文件不得进包（体积 + 源码暴露）。"""
        for rel in [
            "gui/web/src",
            "gui/web/e2e",
            "gui/web/package.json",
            "gui/web/package-lock.json",
            "gui/web/vite.config.ts",
            "gui/web/tsconfig.json",
            "gui/web/eslint.config.js",
            "gui/web/playwright.config.ts",
            "gui/web/index.html",
            "scripts/e2e_isolated.sh",
            "scripts/perf_isolated.sh",
        ]:
            self.assertFalse((BACKEND / rel).exists(),
                             f"开发期文件不应进安装包: {rel}")
        # 运行时真正需要的必须还在
        self.assertTrue((BACKEND / "gui" / "web" / "dist" / "index.html").is_file())
        self.assertTrue((BACKEND / "gui" / "server.py").is_file() or
                        (BACKEND / "gui" / "__init__.py").is_file())


if __name__ == "__main__":
    unittest.main()
