"""内置资产增量同步回归（交接文档待办⑥；2026-09-29 补齐 manifest 版本感知）。

覆盖 gui/builtin_sync：
1. diff() 正确报告 missing / modified / extra。
2. sync() 只复制缺失文件，永不覆盖内容不同的文件，不动用户自有文件。
3. sync() 幂等：第二次跑无复制。
4. 随包目录缺失时优雅 no-op；用户目录不存在时自动创建。
5. sync_at_startup() 永不抛异常（启动流程安全）。
6. manifest 版本感知：官方旧版 hash → upgradable；未知 hash → modified。
7. write_manifest() 生成与增量累积 previous_hashes。
8. sync() 后 SQLite 自动重索引：新资产经 AssetIndex 即刻可见；重复启动幂等。
9. 真实 65→72 扩充场景（随包 72 个真实内置资产）。

隔离：setUpClass 成对 patch config.ROOT_DIR / config.ASSETS_ROOT /
config.STATE_ROOT / config.STATE_JSON_DIR（builtin_sync 与 migrate.sync_asset
仅实时读取这些常量；db 在连接时实时解析 STATE_ROOT），tearDownClass 还原
并关闭连接。纯标准库 unittest。
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _isolation  # noqa: E402

from gui import builtin_sync, config, db  # noqa: E402


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TestBuiltinSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig = {"ROOT_DIR": config.ROOT_DIR, "ASSETS_ROOT": config.ASSETS_ROOT,
                     "STATE_ROOT": config.STATE_ROOT,
                     # 派生常量是 STATE_ROOT 的导入期快照，一起保存才能成对还原。
                     "DB_PATH": config.DB_PATH,
                     "LOCK_PATH": config.LOCK_PATH,
                     "STATE_JSON_DIR": config.STATE_JSON_DIR}
        cls._tmp = Path(tempfile.mkdtemp(prefix="builtin_sync_"))
        cls.shipped = cls._tmp / "repo" / "assets"
        cls.runtime = cls._tmp / "user" / "assets"
        cls.shipped.mkdir(parents=True)
        cls.runtime.mkdir(parents=True)
        config.ROOT_DIR = cls._tmp / "repo"
        config.ASSETS_ROOT = cls.runtime
        # sync() 会把补齐的文件重索引进 SQLite：STATE_ROOT 也隔离到 tmp，
        # 避免污染开发库；db 在连接时实时解析 STATE_ROOT。
        config.STATE_ROOT = cls._tmp / "state"
        config.DB_PATH = config.STATE_ROOT / "index.db"
        config.LOCK_PATH = config.STATE_ROOT / ".lock"
        config.STATE_JSON_DIR = cls._tmp / "state"
        config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
        db._reset_conn()
        db.init_schema()

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
        db.close()
        for k, v in cls._orig.items():
            setattr(config, k, v)
        db._reset_conn()
        _isolation.remove_tree(cls._tmp)

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
        # 无 manifest 时降级为旧行为：无 upgradable 分类。
        self.assertEqual(r["upgradable"], [])
        self.assertIsNone(r["manifest_version"])

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


class _ManifestFixture(unittest.TestCase):
    """manifest 场景夹具基类：shipped 有 a(新)/b(新版)/c(新版)，manifest 登记三者。

    b 的 previous_hashes 含旧版 hash（模拟「桥段库 8→32」这类官方升级）；
    用户目录：b=官方旧版内容 / c=用户改过 / d=用户自有；a 缺失。
    """

    @classmethod
    def setUpClass(cls):
        cls._orig = {"ROOT_DIR": config.ROOT_DIR, "ASSETS_ROOT": config.ASSETS_ROOT,
                     "STATE_ROOT": config.STATE_ROOT,
                     # 派生常量是 STATE_ROOT 的导入期快照，一起保存才能成对还原。
                     "DB_PATH": config.DB_PATH,
                     "LOCK_PATH": config.LOCK_PATH,
                     "STATE_JSON_DIR": config.STATE_JSON_DIR}
        cls._tmp = Path(tempfile.mkdtemp(prefix="builtin_manifest_"))
        cls.repo = cls._tmp / "repo"
        cls.shipped = cls.repo / "assets"
        cls.runtime = cls._tmp / "user" / "assets"
        cls.shipped.mkdir(parents=True)
        cls.runtime.mkdir(parents=True)
        config.ROOT_DIR = cls.repo
        config.ASSETS_ROOT = cls.runtime
        config.STATE_ROOT = cls._tmp / "state"
        config.DB_PATH = config.STATE_ROOT / "index.db"
        config.LOCK_PATH = config.STATE_ROOT / ".lock"
        config.STATE_JSON_DIR = cls._tmp / "state"
        config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
        db._reset_conn()
        db.init_schema()

        cls.a_new = b'{"v": "a-new"}'
        cls.b_old = json.dumps(
            {"meta": {"kind": "trope-library"}, "tropes": [{"id": f"T-{i}"} for i in range(8)]},
            ensure_ascii=False).encode("utf-8")
        cls.b_new = json.dumps(
            {"meta": {"kind": "trope-library"}, "tropes": [{"id": f"T-{i}"} for i in range(32)]},
            ensure_ascii=False).encode("utf-8")
        cls.c_new = b'{"v": "c-new"}'
        (cls.shipped / "a.json").write_bytes(cls.a_new)
        (cls.shipped / "b.json").write_bytes(cls.b_new)
        (cls.shipped / "c.json").write_bytes(cls.c_new)

        manifest = {
            "version": "9.9.9-test",
            "generated_at": "2026-09-29T00:00:00+08:00",
            "files": {
                "a.json": {"sha256": _sha_bytes(cls.a_new), "previous_hashes": []},
                "b.json": {"sha256": _sha_bytes(cls.b_new),
                           "previous_hashes": [_sha_bytes(cls.b_old)]},
                "c.json": {"sha256": _sha_bytes(cls.c_new), "previous_hashes": []},
            },
        }
        (cls.repo / builtin_sync.MANIFEST_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        db.close()
        for k, v in cls._orig.items():
            setattr(config, k, v)
        db._reset_conn()
        _isolation.remove_tree(cls._tmp)

    def _reset_runtime(self):
        self.runtime.mkdir(parents=True, exist_ok=True)
        for p in self.runtime.glob("*.json"):
            p.unlink()
        (self.runtime / "b.json").write_bytes(self.b_old)          # 官方旧版
        (self.runtime / "c.json").write_bytes(b'{"v": "user-edited"}')  # 用户改过
        (self.runtime / "d.json").write_bytes(b'{"mine": true}')    # 用户自有


class TestManifestClassification(_ManifestFixture):
    """manifest 版本感知分类：官方旧版 → upgradable；未知修改 → modified。"""

    def test_diff_classifies_upgradable_vs_modified(self):
        self._reset_runtime()
        r = builtin_sync.diff()
        self.assertEqual(r["missing"], ["a.json"])
        self.assertEqual(r["upgradable"], ["b.json"])   # 桥段库 8→32：官方旧版
        self.assertEqual(r["modified"], ["c.json"])     # 用户改过
        self.assertEqual(r["extra"], ["d.json"])
        self.assertEqual(r["manifest_version"], "9.9.9-test")

    def test_sync_never_overwrites_upgradable_or_modified(self):
        self._reset_runtime()
        r = builtin_sync.sync()
        self.assertEqual(r["copied"], ["a.json"])
        # 官方旧版不自动覆盖：仍是 8 条旧内容。
        self.assertEqual((self.runtime / "b.json").read_bytes(), self.b_old)
        # 用户修改不覆盖。
        self.assertEqual((self.runtime / "c.json").read_text(encoding="utf-8"),
                         '{"v": "user-edited"}')
        # 分类在同步后保持稳定（幂等）。
        r2 = builtin_sync.diff()
        self.assertEqual(r2["upgradable"], ["b.json"])
        self.assertEqual(r2["modified"], ["c.json"])


class TestWriteManifest(unittest.TestCase):
    """write_manifest()：生成覆盖全部随包文件；hash 变化时累积 previous_hashes。"""

    def setUp(self):
        self._orig = {"ROOT_DIR": config.ROOT_DIR}
        self._tmp = Path(tempfile.mkdtemp(prefix="write_manifest_"))
        self.shipped = self._tmp / "repo" / "assets"
        self.shipped.mkdir(parents=True)
        config.ROOT_DIR = self._tmp / "repo"
        (self.shipped / "x.json").write_text('{"v": 1}', encoding="utf-8")
        (self.shipped / "y.json").write_text('{"v": 2}', encoding="utf-8")

    def tearDown(self):
        config.ROOT_DIR = self._orig["ROOT_DIR"]
        _isolation.remove_tree(self._tmp)

    def test_generate_covers_all_files(self):
        m = builtin_sync.write_manifest()
        self.assertEqual(set(m["files"]), {"x.json", "y.json"})
        self.assertEqual(m["version"], __import__("gui").__version__)
        for entry in m["files"].values():
            self.assertEqual(entry["previous_hashes"], [])
            self.assertEqual(len(entry["sha256"]), 64)
        # 落盘可被 load_manifest 读回。
        self.assertEqual(builtin_sync.load_manifest()["files"], m["files"])

    def test_regen_accumulates_previous_hashes(self):
        m1 = builtin_sync.write_manifest()
        old_hash = m1["files"]["x.json"]["sha256"]
        (self.shipped / "x.json").write_text('{"v": 1, "changed": true}', encoding="utf-8")
        m2 = builtin_sync.write_manifest()
        self.assertEqual(m2["files"]["x.json"]["previous_hashes"], [old_hash])
        self.assertNotEqual(m2["files"]["x.json"]["sha256"], old_hash)
        # 未变化的文件不受影响。
        self.assertEqual(m2["files"]["y.json"], m1["files"]["y.json"])
        # 无变化重跑：不重复追加。
        m3 = builtin_sync.write_manifest()
        self.assertEqual(m3["files"]["x.json"]["previous_hashes"], [old_hash])

    def test_regen_without_changes_skips_write(self):
        """无变化重跑：不写文件（字节不变），返回现有 manifest。"""
        from gui import config
        m1 = builtin_sync.write_manifest()
        mp = config.ROOT_DIR / builtin_sync.MANIFEST_NAME
        before = mp.read_bytes()
        m2 = builtin_sync.write_manifest()
        self.assertEqual(mp.read_bytes(), before)  # 文件未被触碰
        self.assertEqual(m2["files"], m1["files"])
        self.assertEqual(m2["generated_at"], m1["generated_at"])

    def test_load_manifest_rejects_broken(self):
        (config.ROOT_DIR / builtin_sync.MANIFEST_NAME).write_text("not json", encoding="utf-8")
        self.assertIsNone(builtin_sync.load_manifest())
        (config.ROOT_DIR / builtin_sync.MANIFEST_NAME).write_text(
            '{"files": {"x.json": {"sha256": 123}}}', encoding="utf-8")
        self.assertIsNone(builtin_sync.load_manifest())


class TestSyncRefreshSqlite(unittest.TestCase):
    """sync() 后 SQLite 自动重索引：新资产经 AssetIndex 即刻可见；重复启动幂等。"""

    def setUp(self):
        self._orig = {"ROOT_DIR": config.ROOT_DIR, "ASSETS_ROOT": config.ASSETS_ROOT,
                      "STATE_ROOT": config.STATE_ROOT,
                      # 派生常量是 STATE_ROOT 的导入期快照，一起保存才能成对还原。
                      "DB_PATH": config.DB_PATH,
                      "LOCK_PATH": config.LOCK_PATH,
                      "STATE_JSON_DIR": config.STATE_JSON_DIR}
        self._tmp = Path(tempfile.mkdtemp(prefix="sync_sqlite_"))
        self.shipped = self._tmp / "repo" / "assets"
        self.shipped.mkdir(parents=True)
        (self.shipped / "demo-voice-card.json").write_text(
            json.dumps({"meta": {"title": "演示文风", "genre": "campus-redemption",
                                 "kind": "voice-card"}}, ensure_ascii=False),
            encoding="utf-8")
        config.ROOT_DIR = self._tmp / "repo"
        config.ASSETS_ROOT = self._tmp / "user" / "assets"
        config.ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
        config.STATE_ROOT = self._tmp / "state"
        config.DB_PATH = config.STATE_ROOT / "index.db"
        config.LOCK_PATH = config.STATE_ROOT / ".lock"
        config.STATE_JSON_DIR = self._tmp / "state"
        config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
        db._reset_conn()
        db.init_schema()

    def tearDown(self):
        db.close()
        for k, v in self._orig.items():
            setattr(config, k, v)
        db._reset_conn()
        _isolation.remove_tree(self._tmp)

    def _asset_rows(self) -> int:
        conn = db.get_conn()
        return int(conn.execute("SELECT COUNT(*) AS n FROM assets").fetchone()["n"])

    def test_synced_asset_visible_in_sqlite(self):
        from gui.asset_index import AssetIndex
        r = builtin_sync.sync()
        self.assertEqual(r["copied"], ["demo-voice-card.json"])
        self.assertEqual(r["reindexed"], ["demo-voice-card.json"])
        # SQLite 里有行，且 AssetIndex（SQLite 权威路径）能查到。
        self.assertEqual(self._asset_rows(), 1)
        items = AssetIndex().list_assets(kind="voice")
        self.assertEqual(items["total"], 1)
        self.assertEqual(items["items"][0]["id"], "voice:demo-voice-card")

    def test_repeated_startup_idempotent(self):
        builtin_sync.sync()
        before = self._asset_rows()
        r = builtin_sync.sync()
        self.assertEqual(r["copied"], [])
        self.assertEqual(r["missing"], [])
        self.assertEqual(self._asset_rows(), before)


class TestRealWorldExpansion(unittest.TestCase):
    """真实 65→102 扩充场景：随包 102 个真实内置资产，用户目录只有前 65 个。"""

    def setUp(self):
        self._orig = {"ROOT_DIR": config.ROOT_DIR, "ASSETS_ROOT": config.ASSETS_ROOT,
                      "STATE_ROOT": config.STATE_ROOT,
                      # 派生常量是 STATE_ROOT 的导入期快照，一起保存才能成对还原。
                      "DB_PATH": config.DB_PATH,
                      "LOCK_PATH": config.LOCK_PATH,
                      "STATE_JSON_DIR": config.STATE_JSON_DIR}
        self._tmp = Path(tempfile.mkdtemp(prefix="real_expand_"))
        config.ROOT_DIR = ROOT  # 真实仓库根：读真实 assets/ 与真实 manifest。
        config.ASSETS_ROOT = self._tmp / "user" / "assets"
        config.ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
        config.STATE_ROOT = self._tmp / "state"
        config.DB_PATH = config.STATE_ROOT / "index.db"
        config.LOCK_PATH = config.STATE_ROOT / ".lock"
        config.STATE_JSON_DIR = self._tmp / "state"
        config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
        db._reset_conn()
        db.init_schema()
        shipped = sorted((ROOT / "assets").glob("*.json"))
        assert len(shipped) == 105, f"随包资产应为 105 个，实测 {len(shipped)}"
        import shutil
        for p in shipped[:65]:
            shutil.copy2(p, config.ASSETS_ROOT / p.name)
        self._expected_missing = sorted(p.name for p in shipped[65:])

    def tearDown(self):
        db.close()
        for k, v in self._orig.items():
            setattr(config, k, v)
        db._reset_conn()
        _isolation.remove_tree(self._tmp)

    def test_65_to_105(self):
        r = builtin_sync.diff()
        self.assertEqual(r["shipped_total"], 105)
        self.assertEqual(r["runtime_total"], 65)
        self.assertEqual(r["missing"], self._expected_missing)
        self.assertEqual(r["modified"], [])
        self.assertEqual(r["upgradable"], [])
        self.assertEqual(r["manifest_version"], __import__("gui").__version__)
        r2 = builtin_sync.sync()
        self.assertEqual(r2["copied"], self._expected_missing)
        # 105 个全部就位。
        self.assertEqual(len(sorted(config.ASSETS_ROOT.glob("*.json"))), 105)
        # SQLite 同步可见：40 个新行。
        conn = db.get_conn()
        n = int(conn.execute("SELECT COUNT(*) AS n FROM assets").fetchone()["n"])
        self.assertEqual(n, 40)


if __name__ == "__main__":
    unittest.main()
