"""资产索引服务单元测试（阶段一 W02）。

覆盖：
1. 扫描 assets/reports/corpus/config 分类计数正确（含 distilled / prose_card_index
   与基础卡的 kind 区分）。
2. 缓存 TTL 生效（force / invalidate）。
3. 分页 offset/limit 正确。
4. path 相对化 + kind 白名单防路径穿越。
5. list_books_summary 扫 gui_state。

纯标准库 unittest，隔离临时目录（monkeypatch config 路径）。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _isolation  # noqa: E402

from gui import asset_index, config, state_store  # noqa: E402


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
            # R1：STATE_JSON_DIR 与 STATE_ROOT 必须成对隔离，避免夹具落到真实 gui/state/。
            "STATE_JSON_DIR": config.STATE_JSON_DIR,
        }
        config.ASSETS_ROOT = cls._tmp / "assets"
        config.REPORTS_DIR = cls._tmp / "reports"
        config.CORPUS_DIR = cls._tmp / "corpus"
        config.CONFIG_DIR = cls._tmp / "config"
        config.STATE_ROOT = cls._tmp / "gui_state"
        config.STATE_JSON_DIR = cls._tmp / "gui_state"

        # 造数据。
        (config.ASSETS_ROOT).mkdir(parents=True)
        (config.REPORTS_DIR).mkdir(parents=True)
        (config.CORPUS_DIR).mkdir(parents=True)
        (config.CONFIG_DIR).mkdir(parents=True)
        (config.STATE_ROOT).mkdir(parents=True, exist_ok=True)
        (config.STATE_JSON_DIR).mkdir(parents=True, exist_ok=True)

        # assets：voice / structure / commercial / craft / genre_pack / prose_card。
        (config.ASSETS_ROOT / "bookA-voice-card.json").write_text('{"meta":{"source_title":"A"}}', encoding="utf-8")
        (config.ASSETS_ROOT / "bookA-structure-obs.json").write_text('{"meta":{}}', encoding="utf-8")
        (config.ASSETS_ROOT / "bookA-commercial-obs.json").write_text('{"meta":{}}', encoding="utf-8")
        (config.ASSETS_ROOT / "bookA-craft-card.json").write_text('{"meta":{}}', encoding="utf-8")
        (config.ASSETS_ROOT / "bookA-genre-pack.json").write_text('{"meta":{}}', encoding="utf-8")
        (config.ASSETS_ROOT / "genre-prose-card-genre-xianxia.json").write_text('{"meta":{}}', encoding="utf-8")
        (config.ASSETS_ROOT / "trope-library.json").write_text('{"meta":{}}', encoding="utf-8")  # 不归类
        # 跨书蒸馏卡与题材索引：必须与基础卡区分 kind，且无单书归属。
        (config.ASSETS_ROOT / "campus-redemption-voice-card-distilled.json").write_text(
            '{"meta":{"dimension":"voice-card"}}', encoding="utf-8")
        (config.ASSETS_ROOT / "genre-prose-card-index.json").write_text(
            '{"cards":{"xianxia":{"file":"genre-prose-card-genre-xianxia.json"}}}', encoding="utf-8")

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
        _isolation.remove_tree(cls._tmp)

    def test_scan_counts(self):
        data = self.idx.scan(force=True)
        counts = data["counts"]
        self.assertEqual(counts.get("voice"), 1)
        self.assertEqual(counts.get("structure"), 1)
        self.assertEqual(counts.get("commercial"), 1)
        self.assertEqual(counts.get("craft"), 1)
        self.assertEqual(counts.get("genre_pack"), 1)
        self.assertEqual(counts.get("prose_card"), 1)
        # distilled / prose_card_index 各自独立成 kind（此前分别被算作 voice / trope）。
        self.assertEqual(counts.get("distilled"), 1)
        self.assertEqual(counts.get("prose_card_index"), 1)
        self.assertEqual(counts.get("report"), 2)
        self.assertEqual(counts.get("book"), 2)

    def test_base_distilled_index_kinds_distinct(self):
        """同一目录下基础卡 / distilled / index 三类 kind 必须可区分。"""
        by_name = {it["name"]: it for it in self.idx.scan(force=True)["items"]}

        base = by_name["bookA-voice-card"]
        self.assertEqual(base["kind"], "voice")
        self.assertEqual(base["book_id"], "bookA")

        distilled = by_name["campus-redemption-voice-card-distilled"]
        self.assertEqual(distilled["kind"], "distilled", "蒸馏卡不得冒充 voice 基础卡")
        self.assertIsNone(distilled["book_id"], "跨书蒸馏卡无单书归属")

        index = by_name["genre-prose-card-index"]
        self.assertEqual(index["kind"], "prose_card_index", "题材索引不得与 trope 混用")
        self.assertIsNone(index["book_id"], "题材索引无单书归属")

    def test_classify_and_book_id_boundaries(self):
        """后缀分类顺序与 book_id 边界（长后缀优先，索引优先于通用 prose-card）。"""
        classify = asset_index.AssetIndex._classify_asset_name
        for suffix in ("-voice-card", "-structure-obs", "-commercial-obs", "-craft-card"):
            self.assertEqual(
                classify(f"campus-redemption{suffix}-distilled.json"), "distilled", suffix)
            self.assertEqual(classify(f"bookA{suffix}.json"),
                             {"-voice-card": "voice", "-structure-obs": "structure",
                              "-commercial-obs": "commercial", "-craft-card": "craft"}[suffix])
        self.assertEqual(classify("genre-prose-card-index.json"), "prose_card_index")
        self.assertEqual(classify("genre-prose-card-genre-xianxia.json"), "prose_card")

        book_id = asset_index.AssetIndex._book_id_from_name
        self.assertEqual(book_id("voice", "bookA-voice-card"), "bookA")
        self.assertIsNone(book_id("distilled", "campus-redemption-voice-card-distilled"))
        self.assertIsNone(book_id("prose_card_index", "genre-prose-card-index"))

    def test_path_relative(self):
        for it in self.idx.scan(force=True)["items"]:
            self.assertFalse(Path(it["path"]).is_absolute(), f"path 应为相对路径: {it['path']}")
            self.assertNotIn("..", it["path"])

    def test_pagination(self):
        res = self.idx.list_assets(None, offset=0, limit=3)
        # 8 asset（6 基础/题材 + distilled + index）+ 2 report + 2 book = 12
        # （trope-library 未归类，不计入）。
        self.assertEqual(res["total"], 12)
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
        _isolation.remove_tree(cls._tmp)

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


class TestAssetSummary(unittest.TestCase):
    """资产可读摘要回归（2026-09-29 用户反馈"资产库有很多内容不对"）：
    详情必须带中文 summary；占位 0 与注入一致被省略；标签与 scripts 同步。

    隔离：自建 setUpClass，把 config 路径指向临时目录并写入夹具，
    不读真实 assets（AGENTS.md §4）。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="asset_summary_qa_"))
        cls._orig = {
            "ASSETS_ROOT": config.ASSETS_ROOT,
            "REPORTS_DIR": config.REPORTS_DIR,
            "CORPUS_DIR": config.CORPUS_DIR,
            "CONFIG_DIR": config.CONFIG_DIR,
            "STATE_ROOT": config.STATE_ROOT,
            "STATE_JSON_DIR": config.STATE_JSON_DIR,
        }
        config.ASSETS_ROOT = cls._tmp / "assets"
        config.REPORTS_DIR = cls._tmp / "reports"
        config.CORPUS_DIR = cls._tmp / "corpus"
        config.CONFIG_DIR = cls._tmp / "config"
        config.STATE_ROOT = cls._tmp / "gui_state"
        config.STATE_JSON_DIR = cls._tmp / "gui_state"
        for d in ("ASSETS_ROOT", "REPORTS_DIR", "CORPUS_DIR", "CONFIG_DIR",
                  "STATE_ROOT"):
            getattr(config, d).mkdir(parents=True, exist_ok=True)

        import json as _json
        voice = {
            "meta": {"source_title": "测试书", "genre": "test-genre"},
            "narration": {"pov": "第三人称限知"},
            "dialogue": {"dialogue_ratio": 0.26},
            "banned": {"never_used_words": ["华丽辞藻堆砌", "复杂心理学术语"]},
        }
        distilled = {
            "meta": {
                "id": "t-voice-card-distilled",
                "dimension": "voice-card",
                "genre": "test-genre",
                "source_books": ["bookA", "bookB"],
                "books_count": 2,
            },
            "rules": [
                {"id": "r1", "dimension": "voice-card",
                 "field": "narration.pov", "kind": "hard",
                 "value": "第三人称限知", "sources": [],
                 "confidence": 0.8, "conflict": False,
                 "over_generalized": False, "blindspot_books": []},
                {"id": "r2", "dimension": "voice-card",
                 "field": "narration.sentence_rhythm.avg_length",
                 "kind": "hard", "value": 0, "sources": [],
                 "confidence": 0.8, "conflict": False,
                 "over_generalized": False, "blindspot_books": []},
                {"id": "r3", "dimension": "voice-card",
                 "field": "emotion_handling.mode", "kind": "soft",
                 "value": "混合式", "sources": [
                     {"book": "bookA", "value": "混合式"},
                     {"book": "bookB", "value": "直陈式"}],
                 "confidence": 0.7, "conflict": True,
                 "over_generalized": False, "blindspot_books": []},
            ],
            "blindspots": [],
            "stats": {},
        }
        trope = {
            "meta": {"id": "trope-library"},
            "tropes": [
                {"id": "t1", "name": "公开打脸", "genre_scope": "universal"},
                {"id": "t2", "name": "隐藏身份", "genre_scope": "universal"},
            ],
        }
        (config.ASSETS_ROOT / "test-book-voice-card.json").write_text(
            _json.dumps(voice, ensure_ascii=False), encoding="utf-8")
        (config.ASSETS_ROOT / "test-voice-card-distilled.json").write_text(
            _json.dumps(distilled, ensure_ascii=False), encoding="utf-8")
        (config.ASSETS_ROOT / "trope-library.json").write_text(
            _json.dumps(trope, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._orig.items():
            setattr(config, k, v)
        for child in sorted(cls._tmp.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        cls._tmp.rmdir()

    def test_detail_has_chinese_summary(self):
        idx = asset_index.AssetIndex()
        detail = idx._detail_from_scan(
            "voice", "test-book-voice-card", "test-book-voice-card")
        summary = detail.get("summary", "")
        self.assertIn("## 基本信息", summary)
        self.assertIn("## 用途", summary)
        self.assertIn("## 关键内容", summary)
        self.assertIn("## 适用位置", summary)
        self.assertIn("声线卡", summary)
        self.assertIn("叙述人称", summary)
        self.assertIn("第三人称限知", summary)
        self.assertIn("26%", summary)
        self.assertIn("## 禁止项", summary)
        # 原始 JSON 仍保留（前端收进"高级"折叠区），不是被摘要替换。
        self.assertIn("content", detail)

    def test_distilled_summary_skips_placeholder_zero(self):
        idx = asset_index.AssetIndex()
        detail = idx._detail_from_scan(
            "distilled", "test-voice-card-distilled", "test-voice-card-distilled")
        summary = detail.get("summary", "")
        # 与注入一致：占位 0 不作为有效规则展示，文末注明省略。
        self.assertNotIn("必守 · 平均句长", summary)
        self.assertIn("从未被统计", summary)
        self.assertIn("必守 · 叙述人称", summary)
        # 分歧的建议规则只计数不展开（保持摘要简洁，详情见原始数据）。
        self.assertIn("建议 1 条", summary)

    def test_trope_summary_lists_names(self):
        idx = asset_index.AssetIndex()
        detail = idx._detail_from_scan("trope", "trope-library", "trope-library")
        summary = detail.get("summary", "")
        self.assertIn("桥段库", summary)
        self.assertIn("公开打脸", summary)
        self.assertIn("隐藏身份", summary)

    def test_summary_never_crashes_on_empty(self):
        for kind in asset_index.ASSET_KINDS:
            s = asset_index.describe_asset(kind, "x", {})
            self.assertIn("## 基本信息", s, kind)
            self.assertIn("## 适用位置", s, kind)

    def test_distilled_labels_in_sync_with_scripts(self):
        # gui 镜像的中文标签必须与 scripts/distill_render.py 保持一致。
        scripts_dir = str(ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import distill_render
        for k, v in asset_index._DISTILLED_FIELD_LABELS.items():
            self.assertIn(k, distill_render.FIELD_LABELS)
            self.assertEqual(v, distill_render.FIELD_LABELS[k],
                             f"蒸馏字段标签漂移: {k}")
        self.assertEqual(asset_index._ZERO_MEANS_MISSING,
                         distill_render._ZERO_MEANS_MISSING,
                         "占位零值字段表漂移：摘要与注入将不一致")


class TestGenreFromFile(unittest.TestCase):
    """_genre_from_file / _make_item 的 genre 透出（2026-09-29 题材隔离 UI 预检配套）。

    规则必须与 writing_service._asset_genre 一致：
    meta.genre 优先，否则取 meta.id 的 ``genre-`` 前缀；文件损坏/结构异常 → None。
    纯静态方法 + 临时文件，不碰 config 路径，无需隔离。
    """

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="genre_from_file_"))
        self._n = 0

    def tearDown(self):
        for p in self._tmp.iterdir():
            p.unlink()
        self._tmp.rmdir()

    def _f(self, content: str) -> Path:
        self._n += 1
        p = self._tmp / f"a{self._n}-voice-card.json"
        p.write_text(content, encoding="utf-8")
        return p

    def test_meta_genre_preferred(self):
        p = self._f('{"meta":{"genre":"xianxia","id":"genre-xianxia-abc"}}')
        self.assertEqual(asset_index.AssetIndex._genre_from_file(p), "xianxia")

    def test_falls_back_to_id_prefix(self):
        p = self._f('{"meta":{"id":"genre-dushi-2026"}}')
        self.assertEqual(asset_index.AssetIndex._genre_from_file(p), "dushi-2026")

    def test_no_genre_no_prefix_returns_none(self):
        p = self._f('{"meta":{"id":"bookA-voice"}}')
        self.assertIsNone(asset_index.AssetIndex._genre_from_file(p))

    def test_broken_json_returns_none(self):
        p = self._f('{"meta": {"genre": "xianxia"')
        self.assertIsNone(asset_index.AssetIndex._genre_from_file(p))

    def test_non_dict_json_returns_none(self):
        p = self._f('[1, 2, 3]')
        self.assertIsNone(asset_index.AssetIndex._genre_from_file(p))

    def test_meta_not_dict_returns_none(self):
        p = self._f('{"meta": "xianxia"}')
        self.assertIsNone(asset_index.AssetIndex._genre_from_file(p))

    def test_missing_file_returns_none(self):
        self.assertIsNone(
            asset_index.AssetIndex._genre_from_file(self._tmp / "nope.json"))

    def test_make_item_carries_genre(self):
        """扫描回退路径的 item 必须带 genre，前端预检依赖该字段。"""
        p = self._f('{"meta":{"genre":"xianxia"}}')
        idx = asset_index.AssetIndex(ttl_seconds=5)
        item = idx._make_item("voice", p, self._tmp)
        self.assertEqual(item["genre"], "xianxia")

    def test_make_item_genre_none_when_unknown(self):
        p = self._f('{"meta":{}}')
        idx = asset_index.AssetIndex(ttl_seconds=5)
        item = idx._make_item("voice", p, self._tmp)
        self.assertIsNone(item["genre"])
