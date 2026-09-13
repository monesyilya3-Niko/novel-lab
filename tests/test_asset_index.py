"""资产索引服务单元测试（阶段一 W02）。

覆盖：
1. 扫描 assets/reports/corpus/config 分类计数正确。
2. 缓存 TTL 生效（force / invalidate）。
3. 分页 offset/limit 正确。
4. path 相对化 + kind 白名单防路径穿越。
5. list_books_summary 扫 gui_state。

纯标准库 unittest，隔离临时目录（monkeypatch config 路径）。
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import config, asset_index, state_store  # noqa: E402


class TestAssetIndex(unittest.TestCase):
    """asset_index 扫描 / 分类 / 分页 / 缓存 / 安全。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="asset_index_qa_"))
        # 保存原始路径，指向临时目录。
        cls._orig = {
            "ASSETS_ROOT": config.ASSETS_ROOT,
            "REPORTS_DIR": config.REPORTS_DIR,
            "CORPUS_DIR": config.CORPUS_DIR,
            "CONFIG_DIR": config.CONFIG_DIR,
            "STATE_ROOT": config.STATE_ROOT,
        }
        config.ASSETS_ROOT = cls._tmp / "assets"
        config.REPORTS_DIR = cls._tmp / "reports"
        config.CORPUS_DIR = cls._tmp / "corpus"
        config.CONFIG_DIR = cls._tmp / "config"
        config.STATE_ROOT = cls._tmp / "gui_state"

        # 造数据。
        (config.ASSETS_ROOT).mkdir(parents=True)
        (config.REPORTS_DIR).mkdir(parents=True)
        (config.CORPUS_DIR).mkdir(parents=True)
        (config.CONFIG_DIR).mkdir(parents=True)
        (config.STATE_ROOT).mkdir(parents=True)

        # assets：voice / structure / commercial / craft / genre_pack / prose_card。
        (config.ASSETS_ROOT / "bookA-voice-card.json").write_text('{"meta":{"source_title":"A"}}', encoding="utf-8")
        (config.ASSETS_ROOT / "bookA-structure-obs.json").write_text('{"meta":{}}', encoding="utf-8")
        (config.ASSETS_ROOT / "bookA-commercial-obs.json").write_text('{"meta":{}}', encoding="utf-8")
        (config.ASSETS_ROOT / "bookA-craft-card.json").write_text('{"meta":{}}', encoding="utf-8")
        (config.ASSETS_ROOT / "bookA-genre-pack.json").write_text('{"meta":{}}', encoding="utf-8")
        (config.ASSETS_ROOT / "genre-prose-card-genre-xianxia.json").write_text('{"meta":{}}', encoding="utf-8")
        (config.ASSETS_ROOT / "trope-library.json").write_text('{"meta":{}}', encoding="utf-8")  # 不归类

        # reports：拆书报告 + 笔法分析。
        (config.REPORTS_DIR / "bookA-拆书报告.md").write_text("# 拆书报告", encoding="utf-8")
        (config.REPORTS_DIR / "bookA-笔法分析.md").write_text("# 笔法分析", encoding="utf-8")

        # corpus：根目录 txt（+ 排除子目录内的 txt 不扫）。
        (config.CORPUS_DIR / "bookA.txt").write_text("正文", encoding="utf-8")
        (config.CORPUS_DIR / "bookB.txt").write_text("正文", encoding="utf-8")
        (config.CORPUS_DIR / "sampled").mkdir(exist_ok=True)
        (config.CORPUS_DIR / "sampled" / "ignore.txt").write_text("排除", encoding="utf-8")

        # config：models.json（已配置）。
        (config.CONFIG_DIR / "models.json").write_text('{"models":{"m1":{"model_name":"x"}}}', encoding="utf-8")

        # 强制新建一个独立 index 实例（TTL 用环境变量覆盖为较短值便于测试）。
        cls.idx = asset_index.AssetIndex(ttl_seconds=5)

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._orig.items():
            setattr(config, k, v)

    def test_scan_counts(self):
        data = self.idx.scan(force=True)
        counts = data["counts"]
        self.assertEqual(counts.get("voice"), 1)
        self.assertEqual(counts.get("structure"), 1)
        self.assertEqual(counts.get("commercial"), 1)
        self.assertEqual(counts.get("craft"), 1)
        self.assertEqual(counts.get("genre_pack"), 1)
        self.assertEqual(counts.get("prose_card"), 1)
        self.assertEqual(counts.get("report"), 2)
        self.assertEqual(counts.get("book"), 2)

    def test_path_relative(self):
        for it in self.idx.scan(force=True)["items"]:
            self.assertFalse(Path(it["path"]).is_absolute(), f"path 应为相对路径: {it['path']}")
            self.assertNotIn("..", it["path"])

    def test_pagination(self):
        res = self.idx.list_assets(None, offset=0, limit=3)
        self.assertEqual(res["total"], 10)  # 6 asset + 2 report + 2 book = 10（未归类 trope 不计入）
        self.assertEqual(len(res["items"]), 3)
        res2 = self.idx.list_assets(None, offset=3, limit=3)
        self.assertEqual(len(res2["items"]), 3)
        self.assertNotEqual(res["items"][0]["id"], res2["items"][0]["id"])

    def test_filter_by_kind(self):
        res = self.idx.list_assets("report", 0, 50)
        self.assertEqual(res["total"], 2)
        self.assertTrue(all(it["kind"] == "report" for it in res["items"]))

    def test_invalid_kind_rejected(self):
        with self.assertRaises(ValueError):
            self.idx.list_assets("../../etc", 0, 50)
        with self.assertRaises(ValueError):
            self.idx.get_asset_detail("../../etc", "x")

    def test_cache_ttl_and_invalidate(self):
        self.idx.invalidate()
        d1 = self.idx.scan()
        self.assertTrue(self.idx._cache)
        # 未过期直接命中缓存。
        self.assertIs(self.idx.scan(), d1)
        # invalidate 后重扫。
        self.idx.invalidate()
        self.assertFalse(self.idx._cache)

    def test_get_asset_detail_json(self):
        detail = self.idx.get_asset_detail("voice", "voice:bookA-voice-card")
        self.assertEqual(detail["kind"], "voice")
        self.assertIn("content", detail)

    def test_get_asset_detail_report_markdown(self):
        detail = self.idx.get_asset_detail("report", "report:bookA-拆书报告")
        self.assertEqual(detail["markdown"], "# 拆书报告")

    def test_path_traversal_blocked(self):
        for bad_id in ("voice:../etc/passwd", "voice:../../secrets", "voice:a/b", "voice:"):
            with self.assertRaises((KeyError, ValueError)):
                self.idx.get_asset_detail("voice", bad_id)

    def test_get_overview(self):
        ov = self.idx.get_overview()
        self.assertEqual(ov["total_reports"], 2)
        self.assertEqual(ov["total_genre_packs"], 1)
        self.assertIn("book", ov["assets_by_kind"])
        # total_assets 只统计真资产（ASSET_KINDS），report/book 是虚拟 kind，
        # 已由 total_reports/total_books 单独展示——计入会虚报（首页曾显示 69 而实际 55）。
        expected_assets = sum(
            v for k, v in ov["assets_by_kind"].items() if k not in ("report", "book")
        )
        self.assertEqual(ov["total_assets"], expected_assets)


class TestListBooksSummary(unittest.TestCase):
    """state_store.list_books_summary 扫 gui_state 目录。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="books_summary_qa_"))
        # R1：STATE_ROOT 与 STATE_JSON_DIR 必须成对隔离——save_state 写后者，
        # list_books_summary 同时扫两者；漏 patch 会把夹具写进真实 gui/state/ 并跨轮累积。
        cls._orig = {
            "STATE_ROOT": config.STATE_ROOT,
            "STATE_JSON_DIR": config.STATE_JSON_DIR,
        }
        config.STATE_ROOT = cls._tmp
        config.STATE_JSON_DIR = cls._tmp

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._orig.items():
            setattr(config, k, v)

    def setUp(self):
        # 造两个状态文件。
        for bid, title, status, done in (
            ("bk1", "书一", "done", 3),
            ("bk2", "书二", "idle", 0),
        ):
            st = state_store.new_state(bid, title)
            st["status"] = status
            for i in range(done):
                st["chapter_states"][f"c1-b{i}"] = {"status": "success", "asset": "a", "ts": 0}
            state_store.save_state(st)

    def tearDown(self):
        for root in (config.STATE_ROOT, config.STATE_JSON_DIR):
            for p in root.glob("gui_state_*.json"):
                p.unlink(missing_ok=True)
            for p in root.glob("*.tmp"):
                p.unlink(missing_ok=True)

    def test_list_books_summary(self):
        books = state_store.list_books_summary()
        self.assertEqual(len(books), 2)
        by_id = {b["book_id"]: b for b in books}
        self.assertEqual(by_id["bk1"]["title"], "书一")
        self.assertEqual(by_id["bk1"]["done"], 3)
        self.assertEqual(by_id["bk2"]["done"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
