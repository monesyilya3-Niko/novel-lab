"""迁移 CLI 集成测试（W07）。

覆盖：
1. run_migrate() 迁移 55 资产 + 8 报告 + 4 书（构造样例，不硬编码生产数字，验证
   与磁盘扫描一致）。
2. 幂等：重复 run_migrate 不重复插行。
3. infer_kind：trope-library（tropes 键）→ trope；genre-prose-card-index（cards 键）
   → prose_card_index；genre-prose-card-* → prose_card；*-distilled → distilled；
   基础书卡后缀 → voice/structure/commercial/craft/genre_pack。
4. infer_book_id：书卡前缀提取；蒸馏卡与题材索引一律返回 None。
5. check() 只读对账：迁移后一致；删除文件后 missing 被检出。
6. backup()/rollback()：备份存在、回滚可恢复。

纯标准库 unittest，隔离临时目录（monkeypatch config 路径 + 重建 db 连接）。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import config, db, migrate, asset_index  # noqa: E402


class TestMigrateInfer(unittest.TestCase):
    """推断规则单元测试（无需建目录）。"""

    def test_infer_kind_trope_library(self):
        self.assertEqual(
            migrate.infer_kind("trope-library.json", {"tropes": {"x": 1}}), "trope")

    def test_infer_kind_prose_card_index(self):
        # 题材文风卡索引是「题材寻址表」，不再与 trope 混用同一 kind。
        self.assertEqual(
            migrate.infer_kind("genre-prose-card-index.json", {"cards": {"a": 1}}),
            "prose_card_index")

    def test_infer_kind_distilled(self):
        self.assertEqual(
            migrate.infer_kind("campus-redemption-voice-card-distilled.json", {"meta": {}}),
            "distilled",
        )

    def test_infer_kind_distilled_all_dimensions(self):
        """四个维度后缀都必须判为 distilled，而非冒充对应基础卡。"""
        for suffix in ("-voice-card", "-structure-obs", "-commercial-obs", "-craft-card"):
            name = f"campus-redemption{suffix}-distilled.json"
            self.assertEqual(migrate.infer_kind(name, {"meta": {}}), "distilled", name)

    def test_infer_kind_prose_card(self):
        self.assertEqual(
            migrate.infer_kind("genre-prose-card-genre-xuanhuan.json",
                               {"meta": {"kind": "genre-prose-card"}}),
            "prose_card")

    def test_infer_kind_book_cards(self):
        cases = {
            "chireng_chosen-voice-card.json": "voice",
            "chireng_chosen-structure-obs.json": "structure",
            "chireng_chosen-commercial-obs.json": "commercial",
            "chireng_chosen-craft-card.json": "craft",
            "campus-redemption-genre-pack.json": "genre_pack",
        }
        for name, expected in cases.items():
            self.assertEqual(migrate.infer_kind(name, {}), expected, name)

    def test_infer_kind_fallback_trope(self):
        # 未命中任何规则 → trope 兜底（宁多勿丢）。
        self.assertEqual(migrate.infer_kind("unknown-thing.json", {}), "trope")

    def test_infer_book_id_card(self):
        self.assertEqual(
            migrate.infer_book_id("chireng_chosen-voice-card"), "chireng_chosen")

    def test_infer_book_id_distilled_none(self):
        # 蒸馏卡无 _chosen 前缀 → None（跨书蒸馏，无单书归属）。
        self.assertIsNone(migrate.infer_book_id("campus-redemption-voice-card-distilled"))

    def test_index_has_no_book_id(self):
        self.assertIsNone(migrate.infer_book_id("genre-prose-card-index"))

    def test_infer_book_id_trope_none(self):
        self.assertIsNone(migrate.infer_book_id("trope-library"))
        self.assertIsNone(migrate.infer_book_id("genre-prose-card-index"))
        self.assertIsNone(migrate.infer_book_id("genre-prose-card-genre-xuanhuan"))

    def test_infer_genre_from_meta(self):
        self.assertEqual(
            migrate.infer_genre("x.json", {"meta": {"genre": "campus-redemption"}}),
            "campus-redemption")

    def test_infer_genre_from_filename(self):
        self.assertEqual(
            migrate.infer_genre("genre-prose-card-genre-xuanhuan.json", {}), "xuanhuan")

    def test_infer_genre_from_meta_id_prefix(self):
        """FIX-2：题材包无 meta.genre，靠 meta.id 的 genre- 前缀推断。"""
        self.assertEqual(
            migrate.infer_genre(
                "campus-redemption-genre-pack.json",
                {"meta": {"id": "genre-campus-redemption", "name": "校园救赎"}}),
            "campus-redemption")

    def test_infer_genre_priority_meta_over_id(self):
        """meta.genre 优先于 meta.id 前缀（既有优先级不变）。"""
        self.assertEqual(
            migrate.infer_genre(
                "genre-prose-card-genre-xuanhuan.json",
                {"meta": {"genre": "kehuan", "id": "genre-xuanhuan"}}),
            "kehuan")

    def test_infer_genre_filename_over_meta_id(self):
        """文件名 genre-xxx 段优先于 meta.id 前缀（既有优先级不变）。"""
        self.assertEqual(
            migrate.infer_genre(
                "genre-prose-card-genre-xuanhuan.json",
                {"meta": {"id": "genre-foo"}}),
            "xuanhuan")

    def test_infer_genre_id_not_genre_prefix_none(self):
        """meta.id 不以 genre- 开头时不产生题材（不误判）。"""
        self.assertIsNone(
            migrate.infer_genre("weird.json", {"meta": {"id": "campus-redemption-pack"}}))


class TestMigrateFlow(unittest.TestCase):
    """迁移主流程 + 幂等 + 对账 + 回滚（隔离临时目录）。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="migrate_qa_"))
        cls._orig = {
            "ASSETS_ROOT": config.ASSETS_ROOT,
            "REPORTS_DIR": config.REPORTS_DIR,
            "CORPUS_DIR": config.CORPUS_DIR,
            "STATE_ROOT": config.STATE_ROOT,
            # R1：STATE_JSON_DIR 与 STATE_ROOT 必须成对隔离，避免夹具落到真实 gui/state/。
            "STATE_JSON_DIR": config.STATE_JSON_DIR,
        }
        config.ASSETS_ROOT = cls._tmp / "assets"
        config.REPORTS_DIR = cls._tmp / "reports"
        config.CORPUS_DIR = cls._tmp / "corpus"
        config.STATE_ROOT = cls._tmp / "gui_state"
        config.STATE_JSON_DIR = cls._tmp / "gui_state"
        for d in (config.ASSETS_ROOT, config.REPORTS_DIR, config.CORPUS_DIR,
                  config.STATE_ROOT, config.STATE_JSON_DIR):
            d.mkdir(parents=True, exist_ok=True)

        # 构造样例数据（覆盖全部 kind + 已拆/未拆书）。
        # 2 本已拆书（各 4 张书卡）+ 1 题材包 + 1 题材文风卡 + trope-library + index。
        cls.book_ids = ["chireng_chosen", "qingning_chosen"]
        for bid in cls.book_ids:
            for suffix in ("-voice-card", "-structure-obs", "-commercial-obs", "-craft-card"):
                (config.ASSETS_ROOT / f"{bid}{suffix}.json").write_text(
                    json.dumps({"meta": {"genre": "campus-redemption"}}), encoding="utf-8")
        # 题材包：无 meta.genre，靠 meta.id 前缀 + meta.name（FIX-2 覆盖场景）。
        (config.ASSETS_ROOT / "campus-redemption-genre-pack.json").write_text(
            '{"meta":{"id":"genre-campus-redemption","name":"校园救赎"}}',
            encoding="utf-8")
        (config.ASSETS_ROOT / "genre-prose-card-genre-xuanhuan.json").write_text(
            '{"meta":{"kind":"genre-prose-card"}}', encoding="utf-8")
        (config.ASSETS_ROOT / "trope-library.json").write_text(
            '{"tropes":{"a":1}}', encoding="utf-8")
        (config.ASSETS_ROOT / "genre-prose-card-index.json").write_text(
            '{"cards":{"x":1}}', encoding="utf-8")
        # 跨书蒸馏卡（book_id=NULL）。
        (config.ASSETS_ROOT / "campus-redemption-voice-card-distilled.json").write_text(
            '{"meta":{}}', encoding="utf-8")

        # 报告：2 本已拆书各 2 份。
        for bid in cls.book_ids:
            (config.REPORTS_DIR / f"{bid}-拆书报告.md").write_text("# 拆书报告", encoding="utf-8")
            (config.REPORTS_DIR / f"{bid}-笔法分析.md").write_text("# 笔法分析", encoding="utf-8")

        # 语料：2 已拆 + 1 未拆（autumn_chosen）。
        for bid in cls.book_ids + ["autumn_chosen"]:
            (config.CORPUS_DIR / f"{bid}.txt").write_text("正文", encoding="utf-8")

        # 重置 db 连接指向新 STATE_ROOT。
        db._reset_conn()

    @classmethod
    def tearDownClass(cls):
        db.close()
        for k, v in cls._orig.items():
            setattr(config, k, v)
        db._reset_conn()

    def _n(self, table: str) -> int:
        return db.get_conn().execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]

    def test_run_migrate_counts(self):
        result = migrate.run_migrate()
        # 资产：2书×4卡 + genre_pack + prose_card + trope-library + index + 1蒸馏 = 13。
        self.assertEqual(result["assets"], 13, f"资产数不符: {result}")
        self.assertEqual(result["assets_on_disk"], 13)
        # 报告：2书×2 = 4。
        self.assertEqual(result["reports"], 4)
        self.assertEqual(result["reports_on_disk"], 4)
        # 书：2 已拆 + 1 未拆（idle）= 3；已拆 = 2。
        self.assertEqual(result["books"], 3)
        self.assertEqual(result["books_done"], 2)
        self.assertEqual(result["corpus_on_disk"], 3)

    def test_run_migrate_idempotent(self):
        migrate.run_migrate()
        before = (self._n("assets"), self._n("reports"), self._n("books"))
        migrate.run_migrate()  # 再跑一次。
        after = (self._n("assets"), self._n("reports"), self._n("books"))
        self.assertEqual(before, after, "重复迁移不应重复插行")

    def test_distilled_book_id_null(self):
        migrate.run_migrate()
        rows = db.get_conn().execute(
            "SELECT book_id FROM assets WHERE name LIKE 'campus-redemption-voice-card-distilled%'"
        ).fetchall()
        # 蒸馏卡 book_id 应为 NULL（或不存在 book_id）。
        for r in rows:
            self.assertIsNone(r["book_id"])

    def test_distilled_and_index_kinds_in_db(self):
        """distilled / prose_card_index 落入 assets.kind 且 book_id=NULL（不再冒充基础卡）。"""
        migrate.run_migrate()
        rows = {r["name"]: r for r in db.list_asset_rows(limit=100000)}

        dis = rows["campus-redemption-voice-card-distilled"]
        self.assertEqual(dis["kind"], "distilled")
        self.assertIsNone(dis["book_id"], "蒸馏卡无单书归属")

        index = rows["genre-prose-card-index"]
        self.assertEqual(index["kind"], "prose_card_index")
        self.assertIsNone(index["book_id"], "题材索引无单书归属")

    def test_genre_pack_registers_genre_and_display_name(self):
        """FIX-2：题材包靠 meta.id 推断，genres 表应出现 campus-redemption + 中文名。"""
        migrate.run_migrate()
        cmap = {r["name"]: r for r in db.get_genres()}
        self.assertIn("campus-redemption", cmap, f"genres 缺 campus-redemption: {cmap}")
        self.assertEqual(cmap["campus-redemption"]["display_name"], "校园救赎")

    def test_genre_registration_matches_distilled_cards(self):
        """FIX-2：题材包口径与 4 张 campus-redemption 蒸馏卡一致（同一 genre key）。"""
        migrate.run_migrate()
        conn = db.get_conn()
        # 题材包含 genre 的资产（题材包 + 4 蒸馏卡 + 2 本书×4 书卡）应统一为 campus-redemption。
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM assets WHERE genre = 'campus-redemption'"
        ).fetchone()["n"]
        self.assertGreaterEqual(n, 5, "campus-redemption 题材下应有题材包与蒸馏卡等资产")

    def test_check_consistent_after_migrate(self):
        migrate.run_migrate()
        result = migrate.check()
        self.assertTrue(result["ok"], f"迁移后对账应一致: {result}")

    def test_check_detects_missing(self):
        migrate.run_migrate()
        # 删除一个资产文件 → check 应检出 missing。
        victim = config.ASSETS_ROOT / "chireng_chosen-voice-card.json"
        victim.unlink(missing_ok=True)
        try:
            result = migrate.check()
            self.assertFalse(result["ok"])
            self.assertTrue(any("chireng_chosen-voice-card" in p for p in result["assets"]["extra"]))
        finally:
            # 恢复文件，避免污染后续测试（run_migrate_counts 依赖完整 13 资产）。
            victim.write_text(
                json.dumps({"meta": {"genre": "campus-redemption"}}), encoding="utf-8")

    def test_backup_and_rollback(self):
        migrate.run_migrate()
        n_before = self._n("assets")
        self.assertGreater(n_before, 0)

        backup_path = migrate.backup()
        self.assertIsNotNone(backup_path)
        self.assertTrue(backup_path.is_file())

        # 清空 assets 后回滚，应恢复。
        with db.tx() as conn:
            conn.execute("DELETE FROM assets")
        self.assertEqual(self._n("assets"), 0)

        restored = migrate.rollback()
        self.assertIsNotNone(restored)
        self.assertEqual(self._n("assets"), n_before, "回滚后应恢复资产行")

    def test_list_assets_book_id_filter_no_leak(self):
        """回归 QA bug：list_assets(book_id=...) 不应泄漏其他书的 book 实体。

        book 种类应随 book_id 过滤，只返回指定书 1 条 book（而非全量 3 书）。
        """
        migrate.run_migrate()
        idx = asset_index.AssetIndex(ttl_seconds=5)
        idx.invalidate()
        res = idx.list_assets(book_id="chireng_chosen", limit=500)
        # 期望：4 资产卡 + 2 报告 + 1 book（chireng_chosen）= 7。
        self.assertEqual(res["total"], 7, f"book_id 筛选应不泄漏: {res['total']}")
        books = [it for it in res["items"] if it["kind"] == "book"]
        self.assertEqual(len(books), 1, "book 种类应只剩 chireng_chosen 1 条")
        self.assertEqual(books[0]["book_id"], "chireng_chosen")
        # 所有非蒸馏实体均归属 chireng_chosen。
        for it in res["items"]:
            if it["kind"] != "trope":
                self.assertEqual(it.get("book_id"), "chireng_chosen",
                                 f"实体 {it['id']} 泄漏了其他书")

    def test_list_assets_genre_filter_book_no_leak(self):
        """回归 QA bug：book 实体无 genre 时，genre 筛选应返回空（而非全量泄漏）。"""
        migrate.run_migrate()
        idx = asset_index.AssetIndex(ttl_seconds=5)
        idx.invalidate()
        # book 实体在 migrate 中未设置 genre（_upsert_book genre=None），
        # 故按 genre 过滤时 book 种类应为 0，不泄漏全量书。
        res = idx.list_assets(genre="campus-redemption", limit=500)
        books = [it for it in res["items"] if it["kind"] == "book"]
        self.assertEqual(books, [], "book 实体无 genre，按 genre 筛选应返回空而非泄漏全量")


class TestBackupRetention(unittest.TestCase):
    """FIX-3：备份保留策略（只保留最近 N 个 *.bak-*，超出自动清理最旧的）。"""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="migrate_bak_"))
        self._orig_state = config.STATE_ROOT
        config.STATE_ROOT = self._tmp / "gui_state"
        config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
        db._reset_conn()

    def tearDown(self):
        db.close()
        config.STATE_ROOT = self._orig_state
        db._reset_conn()

    def _make_baks(self, stamps) -> None:
        for ts in stamps:
            (config.STATE_ROOT / f"index.db.bak-{ts}").write_bytes(b"x")

    def test_prune_keeps_three_newest(self):
        """造 4 个 bak 跑一次 prune(keep=3) → 只留最近 3 个。"""
        self._make_baks(["20260101-000001", "20260101-000002",
                         "20260101-000003", "20260101-000004"])
        removed = migrate.prune_backups(keep=3)
        remaining = sorted(p.name for p in config.STATE_ROOT.glob("*.bak-*"))
        self.assertEqual(len(removed), 1, f"应只删 1 个最旧: {removed}")
        self.assertEqual(
            remaining,
            ["index.db.bak-20260101-000002", "index.db.bak-20260101-000003",
             "index.db.bak-20260101-000004"],
            "应保留最近 3 个")

    def test_prune_noop_when_within_keep(self):
        self._make_baks(["20260101-000001", "20260101-000002"])
        removed = migrate.prune_backups(keep=3)
        self.assertEqual(removed, [])
        self.assertEqual(len(list(config.STATE_ROOT.glob("*.bak-*"))), 2)

    def test_backup_converges_to_keep(self):
        """连续备份后备份数量不超过 BACKUP_KEEP（backup() 内置保留策略）。"""
        db.init_schema()
        for _ in range(5):
            migrate.backup()
        n = len(list(config.STATE_ROOT.glob("*.bak-*")))
        self.assertLessEqual(n, migrate.BACKUP_KEEP, f"备份数 {n} 超过上限")


if __name__ == "__main__":
    unittest.main(verbosity=2)
