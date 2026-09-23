#!/usr/bin/env python3
"""
novel-lab P3 题材隔离回归测试（纯标准库 unittest，零第三方依赖）。

对应架构师设计 system_design_P3_genre_isolation_report.md §4 T07，覆盖四条铁律一的
执行机制（题材隔离）：

  1. pass5_aggregate.collect_books 返回 (books, mismatches) 二元组，
     题材不匹配时被正确识别进 mismatches（不再静默跳过）。
  2. validate.validate_craft_card 对 meta.genre 为空 / 合法 / 非法三种输入，
     分别产出 error / 通过 / warn。
  3. validate.validate_trope_library 对 genre_scope 合法 / 非法 / 缺失的行为。
  4. retrieve.retrieve_tropes：genre=None 只返回 universal；指定 campus-redemption
     时额外可见该题材专属桥段；top_k 生效。

用法：
  python run_tests.py            # 自动 discover 本文件（pattern test_*.py）
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
ASSETS = ROOT / "assets"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    """按文件名从 scripts/ 动态加载模块（与 test_distill/test_trope_library 同模式）。"""
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


VALIDATE = _load("validate")
PASS5_AGGREGATE = _load("pass5_aggregate")
RETRIEVE = _load("retrieve")


# --------------------------------------------------------------------------
# 1. collect_books 题材隔离
# --------------------------------------------------------------------------

class TestCollectBooks(unittest.TestCase):
    """pass5_aggregate.collect_books 的题材隔离行为（铁律一）。"""

    def test_returns_two_tuple(self):
        """collect_books 必须返回 (books, mismatches) 二元组。"""
        result = PASS5_AGGREGATE.collect_books("campus-redemption", None)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2, "collect_books 应返回 (books, mismatches) 二元组")
        books, mismatches = result
        self.assertIsInstance(books, list)
        self.assertIsInstance(mismatches, list)

    def test_books_all_match_genre_mismatches_empty(self):
        """当 assets 下该题材书全部 genre 一致时，mismatches 应为空列表。

        注（2026-09-23）：此处的语义边界需要明确——``collect_books`` 的 mismatch 判定
        **不区分 ``book_names`` 作用域**，只要 ``assets/`` 里存在任何异题材 voice-card
        就会被计入。当前仓库有 3 个题材（campus-redemption / realistic-romance /
        xuanhuan），因此 ``collect_books("campus-redemption", None)`` 的 mismatches
        必然非空（暮冬念春 + Lord_of_the_Mysteries），``聚合`` 命令也随之必然失败。
        本用例只断言「与目标题材一致的书不会被误报为 mismatch」，不依赖 mismatches 为空。
        """
        books, mismatches = PASS5_AGGREGATE.collect_books("campus-redemption", None)
        # 关键契约：返回的是列表（不因题材一致而抛异常或返回 None）
        self.assertIsInstance(mismatches, list)
        # 与目标题材一致的书不得被误判为 mismatch。
        for name, actual_genre in mismatches:
            self.assertNotEqual(
                actual_genre, "campus-redemption",
                f"'{name}' 被误判为 mismatch，但其 genre 与目标一致",
            )

    def test_mismatch_detected_via_monkeypatch(self):
        """构造一个异题材 voice-card，验证 collect_books 能识别 mismatch（不静默跳过）。

        通过 monkeypatch ASSETS 指向临时目录，放置两个 voice-card：
        - 一本 genre == 'campus-redemption'（应被收集进 books）
        - 一本 genre == 'xianxia'（应被识别进 mismatches）
        """
        import tempfile

        target_genre = "campus-redemption"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # 同题材书
            (tmp_path / "book_a-voice-card.json").write_text(
                json.dumps({"meta": {"genre": target_genre}}, ensure_ascii=False),
                encoding="utf-8",
            )
            # 异题材书（题材不匹配 → 应进 mismatches，不再静默跳过）
            (tmp_path / "book_b-voice-card.json").write_text(
                json.dumps({"meta": {"genre": "xianxia"}}, ensure_ascii=False),
                encoding="utf-8",
            )

            orig_assets = PASS5_AGGREGATE.ASSETS
            PASS5_AGGREGATE.ASSETS = tmp_path
            try:
                books, mismatches = PASS5_AGGREGATE.collect_books(target_genre, None)
            finally:
                PASS5_AGGREGATE.ASSETS = orig_assets

            names = [b["name"] for b in books]
            self.assertIn("book_a", names, "同题材书应被收集进 books")
            self.assertNotIn("book_b", names, "异题材书不应被收集进 books")
            self.assertEqual(
                mismatches,
                [("book_b", "xianxia")],
                "异题材书应被识别进 mismatches（铁律一：不再静默跳过）",
            )

    def test_mismatch_genre_missing_detected(self):
        """voice-card 缺少 genre 时，应作为 mismatch（actual_genre 为 None）被识别。"""
        import tempfile

        target_genre = "campus-redemption"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "book_missing-voice-card.json").write_text(
                json.dumps({"meta": {}}, ensure_ascii=False),
                encoding="utf-8",
            )
            orig_assets = PASS5_AGGREGATE.ASSETS
            PASS5_AGGREGATE.ASSETS = tmp_path
            try:
                books, mismatches = PASS5_AGGREGATE.collect_books(target_genre, None)
            finally:
                PASS5_AGGREGATE.ASSETS = orig_assets

            self.assertEqual(books, [])
            self.assertEqual(
                mismatches,
                [("book_missing", None)],
                "缺失 genre 的 voice-card 应被识别为 mismatch（actual_genre=None）",
            )


# --------------------------------------------------------------------------
# 2. validate_craft_card 的 genre 枚举校验
# --------------------------------------------------------------------------

class TestValidateCraftCardGenre(unittest.TestCase):
    """validate_craft_card 对 meta.genre 的三态校验（铁律一）。"""

    def setUp(self):
        VALIDATE.ERRORS.clear()
        VALIDATE.WARNS.clear()

    @staticmethod
    def _craft(genre):
        """构造一张最小合法 craft-card（含 genre 字段，其余必填字段补齐）。"""
        return {
            "meta": {
                "source_title": "测试书",
                "genre": genre,
                "extracted_at": "2026-09-07",
                "sample_chapters": [1, 2, 3],
                "confidence": 0.9,
            },
            "craft_analysis": {
                "foreshadowing": {"techniques": []},
                "information_release": {"techniques": []},
                "pov_control": {"techniques": []},
            },
            "craft_summary": {
                "top_3_strengths": ["a"],
                "unique_techniques": ["b"],
                "reusable_patterns": ["c"],
            },
        }

    def test_genre_valid_passes(self):
        """genre ∈ KNOWN_GENRES 时，不应产生任何 genre 相关 error 或 warn。"""
        VALIDATE.validate_craft_card(self._craft("campus-redemption"))
        genre_errors = [e for e in VALIDATE.ERRORS if "genre" in e]
        genre_warns = [w for w in VALIDATE.WARNS if "genre" in w]
        self.assertEqual(genre_errors, [], f"合法 genre 不应触发 error: {genre_errors}")
        self.assertEqual(genre_warns, [], f"合法 genre 不应触发 warn: {genre_warns}")

    def test_genre_xuanhuan_in_whitelist(self):
        """xuanhuan 已开放：craft-card 使用该 genre 不得触发白名单 warn。"""
        VALIDATE.validate_craft_card(self._craft("xuanhuan"))
        genre_warns = [w for w in VALIDATE.WARNS if "不在已知题材白名单" in w]
        self.assertEqual(genre_warns, [], f"xuanhuan 应在 KNOWN_GENRES: {genre_warns}")

    def test_xuanhuan_genre_pack_on_disk(self):
        """玄幻题材包文件存在且 meta.id / name 正确。"""
        from pathlib import Path
        p = Path(__file__).resolve().parents[1] / "assets" / "xuanhuan-genre-pack.json"
        self.assertTrue(p.is_file(), f"缺少题材包 {p}")
        data = p.read_text(encoding="utf-8")
        self.assertIn("genre-xuanhuan", data)
        self.assertIn("传统玄幻", data)

    def test_genre_empty_triggers_error(self):
        """genre 为空 → err（硬错误，题材缺失必须阻断）。"""
        VALIDATE.validate_craft_card(self._craft(""))
        self.assertTrue(
            any("meta.genre 为空" in e for e in VALIDATE.ERRORS),
            f"空 genre 应触发硬错误，实际 ERRORS={VALIDATE.ERRORS}",
        )
        # 空 genre 不应同时触发 warn（err 已阻断，warn 分支不执行）
        self.assertFalse(
            any("meta.genre" in w and "不在已知题材白名单" in w for w in VALIDATE.WARNS),
            "空 genre 不应额外触发白名单 warn",
        )

    def test_genre_invalid_triggers_warn_not_error(self):
        """genre 非法（不在白名单）→ warn，不 err（扩展题材时白名单可能滞后）。"""
        VALIDATE.validate_craft_card(self._craft("xianxia"))
        self.assertTrue(
            any("meta.genre" in w and "不在已知题材白名单" in w for w in VALIDATE.WARNS),
            f"非法 genre 应触发 warn，实际 WARNS={VALIDATE.WARNS}",
        )
        self.assertFalse(
            any("meta.genre" in e for e in VALIDATE.ERRORS),
            f"非法 genre 不应触发 error（可入库但阻断聚合），实际 ERRORS={VALIDATE.ERRORS}",
        )


# --------------------------------------------------------------------------
# 3. validate_trope_library 的 genre_scope 校验
# --------------------------------------------------------------------------

class TestValidateTropeLibraryGenreScope(unittest.TestCase):
    """validate_trope_library 对 genre_scope 的三态校验（铁律一）。"""

    def setUp(self):
        VALIDATE.ERRORS.clear()
        VALIDATE.WARNS.clear()

    @staticmethod
    def _lib(scope):
        """构造只含一条 trope 的最小库，便于断言单条 genre_scope 行为。"""
        trope = {
            "id": "T-TEST-001",
            "name": "测试桥段",
            "category": "打脸",
            "abstraction_level": "structural",
            "skeleton": {"setup": "s", "escalation": ["e"], "payoff": "p", "aftermath": "a"},
            "contains_verbatim": False,
            "effectiveness": {"payoff_strength": 8},
        }
        if scope is not None:
            trope["genre_scope"] = scope
        return {"tropes": [trope]}

    def test_genre_scope_universal_valid(self):
        VALIDATE.validate_trope_library(self._lib("universal"))
        self.assertEqual(
            VALIDATE.ERRORS, [],
            f"genre_scope='universal' 不应触发 error: {VALIDATE.ERRORS}",
        )

    def test_genre_scope_known_genre_valid(self):
        VALIDATE.validate_trope_library(self._lib("campus-redemption"))
        self.assertEqual(
            VALIDATE.ERRORS, [],
            f"genre_scope='campus-redemption'（已知题材）不应触发 error: {VALIDATE.ERRORS}",
        )

    def test_genre_scope_missing_triggers_error(self):
        VALIDATE.validate_trope_library(self._lib(None))
        self.assertTrue(
            any("缺少 genre_scope" in e for e in VALIDATE.ERRORS),
            f"缺失 genre_scope 应触发硬错误，实际 ERRORS={VALIDATE.ERRORS}",
        )

    def test_genre_scope_invalid_triggers_error(self):
        VALIDATE.validate_trope_library(self._lib("fantasy"))
        self.assertTrue(
            any("genre_scope='fantasy' 非法" in e for e in VALIDATE.ERRORS),
            f"非法 genre_scope 应触发硬错误，实际 ERRORS={VALIDATE.ERRORS}",
        )


# --------------------------------------------------------------------------
# 4. retrieve_tropes 按 genre_scope 过滤
# --------------------------------------------------------------------------

class TestRetrieveTropes(unittest.TestCase):
    """retrieve.retrieve_tropes 的 genre_scope 过滤 + top_k 行为（铁律一）。"""

    def test_genre_none_returns_only_universal(self):
        """genre=None 时只返回 universal 桥段（保守策略，宁缺毋滥）。"""
        results = RETRIEVE.retrieve_tropes("打脸爽点", genre=None, top_k=50)
        self.assertTrue(len(results) > 0, "应返回至少一条 universal 桥段")
        for t in results:
            self.assertEqual(
                t.get("genre_scope"), "universal",
                f"genre=None 时不应返回非 universal 桥段: {t.get('id')}",
            )

    def test_genre_campus_redemption_returns_universal_and_genre_specific(self):
        """指定 campus-redemption 时，返回 universal + 该题材专属（若存在）桥段。

        当前资产 8 条全部为 universal，故此处只验证"指定题材时至少包含 universal"，
        且不混入其它题材专属（如 'xianxia'）的桥段。
        """
        results = RETRIEVE.retrieve_tropes("打脸爽点", genre="campus-redemption", top_k=50)
        self.assertTrue(len(results) > 0)
        for t in results:
            self.assertIn(
                t.get("genre_scope"), ("universal", "campus-redemption"),
                f"指定 campus-redemption 时不应返回其它题材专属桥段: {t.get('id')}",
            )

    def test_genre_other_returns_only_universal(self):
        """指定一个非 campus-redemption 的题材时，只应返回 universal（无该题材专属）。"""
        results = RETRIEVE.retrieve_tropes("打脸爽点", genre="xianxia", top_k=50)
        self.assertTrue(len(results) > 0)
        for t in results:
            self.assertEqual(
                t.get("genre_scope"), "universal",
                f"无 xianxia 专属桥段时不应返回其它专属桥段: {t.get('id')}",
            )

    def test_top_k_limits_results(self):
        """top_k 应限制返回条数。"""
        k = 3
        results = RETRIEVE.retrieve_tropes("桥段", genre=None, top_k=k)
        self.assertLessEqual(len(results), k, f"返回条数 {len(results)} 应 ≤ top_k={k}")

    def test_top_k_zero_or_negative_returns_empty(self):
        self.assertEqual(RETRIEVE.retrieve_tropes("桥段", genre=None, top_k=0), [])
        self.assertEqual(RETRIEVE.retrieve_tropes("桥段", genre=None, top_k=-1), [])

    def test_empty_intent_returns_empty(self):
        self.assertEqual(RETRIEVE.retrieve_tropes("", genre=None, top_k=5), [])
        self.assertEqual(RETRIEVE.retrieve_tropes("   ", genre=None, top_k=5), [])


# --------------------------------------------------------------------------
# 5. main() 的铁律一判定作用域（2026-09-23 修复回归）
# --------------------------------------------------------------------------

class TestAggregateScopeEnforcement(unittest.TestCase):
    """``pass5_aggregate.main()`` 只对「本次聚合的 source_books」做题材一致性判定。

    修复前（2026-09-23 前）：只要 ``assets/`` 下存在**任何**异题材 voice-card 就
    ``sys.exit(1)``，即使用户已用 ``--books`` 显式限定书目。本项目常态就是多题材并存
    （campus-redemption / realistic-romance / xuanhuan），于是 ``聚合`` 命令**完全
    不可用**，``novel.py 状态`` 里那句「拆 ≥3 本同题材后跑 'novel 聚合'」成了死路。

    修复后判定口径与 AGENTS.md §1 对齐（**source_books** 的 genre 必须全部一致）：
      · ``--books`` 显式指定 → 被点名的书必须全部属于目标题材，否则硬失败；
      · 未显式限定 → 异题材书本就在范围之外，列出但不阻断。
    """

    @staticmethod
    def _book(name: str) -> dict:
        return {"name": name, "voice": {"meta": {"genre": "campus-redemption"}},
                "struct": {}, "comm": {}}

    def _run_main(self, argv, books, mismatches):
        """在受控数据下跑 main()，返回 (返回值, stdout)。

        ``main()`` 无参数、直接读 ``sys.argv``（argparse 默认行为），故需临时替换它。
        """
        import contextlib
        import io

        saved = (PASS5_AGGREGATE.collect_books,
                 PASS5_AGGREGATE.extract_features,
                 PASS5_AGGREGATE.summarize_thresholds)
        saved_argv = sys.argv
        PASS5_AGGREGATE.collect_books = lambda genre, names: (books, mismatches)
        PASS5_AGGREGATE.extract_features = lambda bs: {}
        PASS5_AGGREGATE.summarize_thresholds = lambda fr: {
            "iron": [], "suggest": [], "personal": []}
        sys.argv = ["pass5_aggregate.py"] + list(argv)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = PASS5_AGGREGATE.main()
        finally:
            sys.argv = saved_argv
            (PASS5_AGGREGATE.collect_books,
             PASS5_AGGREGATE.extract_features,
             PASS5_AGGREGATE.summarize_thresholds) = saved
        return rc, buf.getvalue()

    def test_unscoped_run_does_not_fail_on_other_genre_books(self):
        """不限定书目时，异题材书属范围之外 → 不阻断，但要明确列出（不静默跳过）。"""
        books = [self._book("a"), self._book("b"), self._book("c")]
        mismatches = [("lotm", "xuanhuan"), ("暮冬念春", "realistic-romance")]
        rc, out = self._run_main(["--genre", "campus-redemption", "--dry-run"],
                                 books, mismatches)
        self.assertIsNone(rc, f"不限定书目时不应阻断（返回 {rc}）")
        self.assertIn("范围", out, "未列出范围外的异题材书（等于静默跳过）")
        self.assertIn("xuanhuan", out)
        self.assertIn("realistic-romance", out)

    def test_explicit_books_all_valid_passes(self):
        """--books 全部属于目标题材 → 正常放行。"""
        books = [self._book("a"), self._book("b")]
        rc, out = self._run_main(
            ["--genre", "campus-redemption", "--books", "a,b", "--dry-run"],
            books, [("lotm", "xuanhuan")])
        self.assertIsNone(rc, "显式指定的书全部合法时不应阻断")
        self.assertIn("聚合样本: 2 本", out)

    def test_explicit_books_with_other_genre_fails(self):
        """--books 点名了异题材书 → 硬失败（防"以为聚合了 A+B，实际 B 被静默丢掉"）。"""
        books = [self._book("a")]
        mismatches = [("b", "realistic-romance")]
        with self.assertRaises(SystemExit) as ctx:
            self._run_main(["--genre", "campus-redemption", "--books", "a,b", "--dry-run"],
                           books, mismatches)
        msg = str(ctx.exception)
        self.assertIn("题材隔离违规", msg)
        self.assertIn("realistic-romance", msg)

    def test_explicit_nonexistent_book_fails(self):
        """--books 点名了根本不存在的书 → 硬失败（同样防静默漏掉）。"""
        books = [self._book("a")]
        with self.assertRaises(SystemExit) as ctx:
            self._run_main(
                ["--genre", "campus-redemption", "--books", "a,___nope___", "--dry-run"],
                books, [])
        self.assertIn("___nope___", str(ctx.exception))

    def test_no_matching_book_fails(self):
        """目标题材下没有任何书 → 报「未找到」。"""
        with self.assertRaises(SystemExit) as ctx:
            self._run_main(["--genre", "campus-redemption", "--dry-run"], [], [])
        self.assertIn("未找到", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
