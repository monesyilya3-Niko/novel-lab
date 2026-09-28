"""内置资产增量同步回归（交接文档待办⑥）。

覆盖 gui/builtin_sync：
1. diff() 正确报告 missing / modified / extra。
2. sync() 只复制缺失文件，永不覆盖内容不同的文件，不动用户自有文件。
3. sync() 幂等：第二次跑无复制。
4. 随包目录缺失时优雅 no-op；用户目录不存在时自动创建。
5. sync_at_startup() 永不抛异常（启动流程安全）。

隔离：setUpClass 成对 patch config.ROOT_DIR / config.ASSETS_ROOT
（builtin_sync 仅实时读取这两个常量），tearDownClass 还原。
纯标准库 unittest。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import builtin_sync, config  # noqa: E402


class TestBuiltinSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig = {"ROOT_DIR": config.ROOT_DIR, "ASSETS_ROOT": config.ASSETS_ROOT}
        cls._tmp = Path(tempfile.mkdtemp(prefix="builtin_sync_"))
        cls.shipped = cls._tmp / "repo" / "assets"
        cls.runtime = cls._tmp / "user" / "assets"
        cls.shipped.mkdir(parents=True)
        cls.runtime.mkdir(parents=True)
        config.ROOT_DIR = cls._tmp / "repo"
        config.ASSETS_ROOT = cls.runtime

        # 随包：a.json（用户目录缺失）/ b.json（两边一致）/ c.json（内容不同）。
        (cls.shipped / "a.json").write_text('{"v": 1}', encoding="utf-8")
        (cls.shipped / "b.json").write_text('{"v": 2}', encoding="utf-8")
        (cls.shipped / "c.json").write_text('{"v": "new"}', encoding="utf-8")
        # 用户目录：b.json 一致 / c.json 被用户改过 / d.json 用户自有。
        (cls.runtime / "b.json").write_text('{"v": 2}', encoding="utf-8")
        (cls.runtime / "c.json").write_text('{"v": "user-edited"}', encoding="utf-8")
        (cls.runtime / "d.json").write_text('{"mine": true}', encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._orig.items():
            setattr(config, k, v)

    def _reset_runtime(self):
        """恢复用户目录夹具到初始态（b 一致 / c 被改过 / d 自有，无 a）。"""
        self.runtime.mkdir(parents=True, exist_ok=True)
        for name, content in (("b.json", '{"v": 2}'),
                              ("c.json", '{"v": "user-edited"}'),
                              ("d.json", '{"mine": true}')):
            (self.runtime / name).write_text(content, encoding="utf-8")
        a = self.runtime / "a.json"
        if a.is_file():
            a.unlink()

    def test_diff(self):
        self._reset_runtime()
        r = builtin_sync.diff()
        self.assertEqual(r["missing"], ["a.json"])
        self.assertEqual(r["modified"], ["c.json"])
        self.assertEqual(r["extra"], ["d.json"])
        self.assertEqual(r["shipped_total"], 3)
        self.assertEqual(r["runtime_total"], 3)

    def test_sync_copies_only_missing(self):
        self._reset_runtime()
        r = builtin_sync.sync()
        self.assertEqual(r["copied"], ["a.json"])
        # 缺失的补上了，内容一致。
        self.assertEqual((self.runtime / "a.json").read_text(encoding="utf-8"),
                         '{"v": 1}')
        # 内容不同的不覆盖：用户修改保留。
        self.assertEqual((self.runtime / "c.json").read_text(encoding="utf-8"),
                         '{"v": "user-edited"}')
        # 用户自有文件不动。
        self.assertTrue((self.runtime / "d.json").is_file())

    def test_sync_idempotent(self):
        self._reset_runtime()
        builtin_sync.sync()
        r = builtin_sync.sync()
        self.assertEqual(r["copied"], [])
        self.assertEqual(r["missing"], [])

    def test_noop_when_shipped_missing(self):
        config.ROOT_DIR = self._tmp / "no-such-dir"
        try:
            r = builtin_sync.sync()
            self.assertTrue(r.get("noop"))
            self.assertEqual(r["copied"], [])
        finally:
            config.ROOT_DIR = self._tmp / "repo"

    def test_sync_creates_runtime_dir(self):
        import shutil
        shutil.rmtree(self.runtime)
        try:
            r = builtin_sync.sync()
            self.assertTrue(self.runtime.is_dir())
            self.assertIn("a.json", r["copied"])
        finally:
            self._reset_runtime()

    def test_sync_at_startup_never_raises(self):
        self._reset_runtime()
        config.ROOT_DIR = self._tmp / "no-such-dir"
        try:
            builtin_sync.sync_at_startup()  # 不抛异常。
        finally:
            config.ROOT_DIR = self._tmp / "repo"
        builtin_sync.sync_at_startup()
        self._reset_runtime()


if __name__ == "__main__":
    unittest.main()
