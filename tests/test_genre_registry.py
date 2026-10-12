#!/usr/bin/env python3
"""题材注册表与 prose 卡 slug 校验的回归测试（纯标准库 unittest）。

2026-09-27 企业级整改 P0-2（铁律一「题材隔离」由名义变实质）。

覆盖三类不变式：
  1. 注册表派生结果与磁盘资产一致（磁盘是唯一真相源，注册表只是视图）。
  2. validate.validate_genre_prose_card 的 meta.id slug 校验（此前完全缺失）。
  3. CORE_GENRES 与 KNOWN_GENRES 的语义分离不被放宽（防止后来者"顺手"合并）。

用法：python run_tests.py
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
    """按文件名从 scripts/ 动态加载模块（与 test_genre_isolation 同模式）。"""
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


VALIDATE = _load("validate")
REGISTRY = _load("genre_registry")

#: 磁盘上的 prose 卡文件（排除索引文件）
PROSE_FILES = sorted(
    p for p in ASSETS.glob("genre-prose-card-*.json") if p.name != "genre-prose-card-index.json"
)


def _prose_card(card_id, name="测试题材"):
    """构造一张最小合法 genre-prose-card（仅用于喂校验器）。"""
    return {
        "meta": {
            "kind": "genre-prose-card",
            "id": card_id,
            "name": name,
            "confidence": 0.8,
            "provenance": {"source": "unit-test", "license": "MIT", "verified": False},
        },
        "language_rules": {"forbidden_elements": []},
        "prose": {"sections": {"opening": "一段用于兜底的示例正文。"}},
    }


# --------------------------------------------------------------------------
# 1. 注册表派生 vs 磁盘真相源
# --------------------------------------------------------------------------

class TestRegistryDerivation(unittest.TestCase):
    """注册表必须是磁盘的忠实视图，不得自带数字。"""

    def test_prose_count_equals_disk(self):
        """派生的 prose 卡数必须等于磁盘 genre-prose-card 文件数（不含 index）。"""
        self.assertEqual(
            len(REGISTRY.prose_genre_slugs()),
            len(PROSE_FILES),
            "注册表派生的 prose 卡数与磁盘文件数不一致（视图与真相源脱节）",
        )

    def test_core_genres_are_the_full_chain_three(self):
        """完整链题材固定为这 3 个；若业务新增，必须显式改此断言并补资产链。"""
        self.assertEqual(
            set(REGISTRY.core_genres()),
            {"campus-redemption", "realistic-romance", "xuanhuan"},
        )

    def test_known_is_superset_of_core(self):
        core = set(REGISTRY.core_genres())
        known = set(REGISTRY.known_genres())
        self.assertTrue(core <= known, f"KNOWN_GENRES 必须包含全部 CORE_GENRES: {core - known}")

    def test_known_covers_prose_only_genres(self):
        """prose-only 题材必须进入 KNOWN，否则 trope 无法标注这些题材（genre_scope 过严）。"""
        known = set(REGISTRY.known_genres())
        core = set(REGISTRY.core_genres())
        prose_only = set(REGISTRY.prose_genres()) - core
        self.assertGreater(len(prose_only), 0, "应存在 prose-only 题材，否则本测试空转")
        self.assertTrue(prose_only <= known)

    def test_all_disk_slugs_wellformed(self):
        """全部 prose 卡的 meta.id 都符合命名规范（此前无任何校验）。"""
        self.assertEqual(REGISTRY.malformed_prose_ids(), [], "存在不合规的 prose 卡 meta.id")

    def test_filename_matches_meta_id(self):
        """文件名必须与 meta.id 严格对应（实测约定：'genre-prose-card-' + 完整 meta.id）。

        注意前缀重复：磁盘文件名是 genre-prose-card-genre-dushi-gaowu.json（双 genre-），
        因为转换脚本把完整 meta.id 直接拼在 genre-prose-card- 之后。命名冗余但 32/32 自洽，
        属既有契约；错配会让下游按文件名还是按 meta.id 取题材产生分叉。
        """
        mismatched = []
        for path in PROSE_FILES:
            data = json.loads(path.read_text(encoding="utf-8"))
            meta_id = (data.get("meta") or {}).get("id", "")
            if path.stem != f"genre-prose-card-{meta_id}":
                mismatched.append((path.name, meta_id))
        self.assertEqual(mismatched, [], f"文件名与 meta.id 错配: {mismatched}")

    def test_no_duplicate_genre_across_cards(self):
        """一个题材一张卡：重复卡会让题材注入结果取决于文件遍历顺序。"""
        self.assertEqual(REGISTRY.duplicate_prose_genres(), {}, "同一题材存在多张 prose 卡")

    def test_craft_card_genres_all_in_core(self):
        """磁盘上所有 craft-card 的 genre 都必须 ∈ CORE_GENRES（完整链题材）。"""
        metas = REGISTRY._iter_asset_meta()
        genres = {m["genre"] for _, m in metas if m.get("kind") == "craft-card" or
                  (m.get("kind") is None and "genre" in m)}
        self.assertTrue(genres <= set(REGISTRY.core_genres()),
                        f"存在越界 genre: {genres - set(REGISTRY.core_genres())}")

    def test_registry_falls_back_without_assets(self):
        """兜底路径：扫描不到资产时 core 退回内置集合，校验不会整体失效。"""
        self.assertEqual(set(REGISTRY.core_genres(metas=[])),
                         set(REGISTRY.FALLBACK_CORE_GENRES))


# --------------------------------------------------------------------------
# 2. prose 卡 slug 校验（正向放行 + 负向必须报错，双向自证非空转）
# --------------------------------------------------------------------------

class TestProseCardSlugGuard(unittest.TestCase):
    def _slug_errors(self, card_id):
        VALIDATE.validate_genre_prose_card(_prose_card(card_id))
        return [e for e in VALIDATE.ERRORS if "meta.id" in e]

    def test_guard_is_not_vacuous(self):
        """基线：合法 slug 不得产生 meta.id 错误（否则下面五条负向测试全部空转）。"""
        self.assertEqual(self._slug_errors("genre-xianxia"), [],
                         "合法 slug 被误判，校验逻辑有误")

    def test_uppercase_slug_rejected(self):
        self.assertTrue(self._slug_errors("Genre-Xianxia"), "大写 slug 未被拒绝")

    def test_underscore_slug_rejected(self):
        self.assertTrue(self._slug_errors("genre-xianxia_naodong"), "含下划线 slug 未被拒绝")

    def test_chinese_slug_rejected(self):
        self.assertTrue(self._slug_errors("genre-仙侠"), "中文 slug 未被拒绝")

    def test_missing_prefix_rejected(self):
        self.assertTrue(self._slug_errors("xianxia"), "缺少 genre- 前缀未被拒绝")

    def test_prefix_only_rejected(self):
        self.assertTrue(self._slug_errors("genre-"), "只有前缀无 slug 未被拒绝")


# --------------------------------------------------------------------------
# 3. CORE / KNOWN 语义分离不可放宽
# --------------------------------------------------------------------------

class TestCoreKnownSeparation(unittest.TestCase):
    def _craft(self, genre):
        return {
            "meta": {"source_title": "测试书", "genre": genre, "extracted_at": "2026-09-07",
                     "sample_chapters": [1, 2, 3], "confidence": 0.9},
            "craft_analysis": {"foreshadowing": {"techniques": []},
                               "information_release": {"techniques": []},
                               "pov_control": {"techniques": []}},
            "craft_summary": {"top_3_strengths": ["a"], "unique_techniques": ["b"],
                              "reusable_patterns": ["c"]},
        }

    def _whitelist_warns(self, genre):
        VALIDATE.validate_craft_card(self._craft(genre))
        return [w for w in VALIDATE.WARNS if "不在已知题材白名单" in w]

    def test_full_chain_genre_clean(self):
        self.assertEqual(self._whitelist_warns("xuanhuan"), [], "完整链题材被误警告")

    def test_prose_only_genre_still_warns(self):
        """关键防线：prose-only 题材不得因 KNOWN 扩大而通过 craft-card 校验。

        若有人把 craft-card 的白名单从 CORE_GENRES 改成 KNOWN_GENRES，
        32 个只有 prose 卡的题材会被误判为「已有完整资产链」，聚合层随之失真。
        """
        warns = self._whitelist_warns("xianxia")
        self.assertTrue(warns, "xianxia 只有 prose 卡，craft-card 使用它必须警告；"
                              "说明校验被错误放宽到 KNOWN_GENRES")

    def test_unknown_genre_still_warns(self):
        self.assertTrue(self._whitelist_warns("definitely-not-a-genre"))

    def test_genre_scope_accepts_prose_only_genre(self):
        """genre_scope 用 KNOWN_GENRES：prose-only 题材应可标注 trope。"""
        VALIDATE.validate_trope_library({
            "meta": {"id": "trope-test", "name": "测试桥段库"},
            "tropes": [{"id": "t1", "name": "桥段", "genre_scope": "xianxia"}],
        })
        self.assertEqual([e for e in VALIDATE.ERRORS if "genre_scope" in e], [],
                         f"prose-only 题材被 genre_scope 拒绝: {VALIDATE.ERRORS}")


class TestMetaCacheInvalidation(unittest.TestCase):
    """assets 元信息缓存（2026-10-12 性能优化）的正确性守卫。

    背景：``_iter_asset_meta()`` 每次读盘解析 assets/ 全部 105 个 JSON，
    实测 25ms；``known_genres()`` 达 48ms，而 ``/api/genres`` 每次请求都走它。
    加缓存后降到 ~1ms（35x），但**缓存必须能感知磁盘变化**——
    本项目红线是「磁盘是唯一真相源」，读不到新写入的题材就是数据正确性事故。

    关键设计：缓存键用全部文件的 (名, 大小, mtime_ns) 聚合指纹。
    曾用「目录 mtime」做键，实测**改文件内容时目录 mtime 不变**，会读到旧值。
    """

    def setUp(self):
        import shutil
        import tempfile
        self._tmp = Path(tempfile.mkdtemp(prefix="metacache_"))
        self._orig_assets = REGISTRY.ASSETS_DIR
        self._orig_ttl = __import__("os").environ.get("NOVEL_LAB_GENRE_TTL")
        REGISTRY.ASSETS_DIR = self._tmp
        # TTL 置 0 使缓存对每次调用都重新校验指纹——
        # 这些用例测的是「指纹能否感知磁盘变化」，不是 TTL 语义。
        # TTL 本身的行为由 test_ttl_window_serves_stale 覆盖。
        __import__("os").environ["NOVEL_LAB_GENRE_TTL"] = "0"
        REGISTRY.invalidate_meta_cache()
        self._shutil = shutil

    def tearDown(self):
        import os
        REGISTRY.ASSETS_DIR = self._orig_assets
        if self._orig_ttl is None:
            os.environ.pop("NOVEL_LAB_GENRE_TTL", None)
        else:
            os.environ["NOVEL_LAB_GENRE_TTL"] = self._orig_ttl
        REGISTRY.invalidate_meta_cache()
        self._shutil.rmtree(self._tmp, ignore_errors=True)

    def _write_card(self, slug, genre_id=None):
        import time
        time.sleep(0.01)  # 确保 mtime 前进（文件系统时间戳分辨率）
        (self._tmp / f"genre-prose-card-{slug}.json").write_text(
            json.dumps({"meta": {"kind": "genre-prose-card", "id": genre_id or slug}}),
            encoding="utf-8",
        )

    def test_cache_hit_returns_same_result(self):
        """重复调用结果一致（缓存没有引入随机性）。"""
        self._write_card("genre-aaa")
        first = REGISTRY._iter_asset_meta()
        second = REGISTRY._iter_asset_meta()
        self.assertEqual(first, second)

    def test_new_file_invalidates(self):
        """新增资产文件必须被感知（否则拆书产出新题材后列表不更新）。"""
        self._write_card("genre-aaa")
        before = len(REGISTRY._iter_asset_meta())
        self._write_card("genre-bbb")
        after = len(REGISTRY._iter_asset_meta())
        self.assertEqual(after, before + 1, "新增文件后缓存未失效")

    def test_deleted_file_invalidates(self):
        """删除资产文件必须被感知。"""
        self._write_card("genre-aaa")
        self._write_card("genre-bbb")
        before = len(REGISTRY._iter_asset_meta())
        (self._tmp / "genre-prose-card-genre-aaa.json").unlink()
        after = len(REGISTRY._iter_asset_meta())
        self.assertEqual(after, before - 1, "删除文件后缓存未失效")

    def test_modified_content_invalidates(self):
        """**改文件内容**必须被感知——这是「目录 mtime」做键会漏掉的场景。

        注意 prose_genres() 返回的是**去掉 genre- 前缀的 slug**（bbb），
        不是完整 meta.id（genre-bbb）。
        """
        self._write_card("genre-prose-card-genre-bbb", genre_id="genre-bbb")
        self.assertIn("bbb", REGISTRY.prose_genres())
        self._write_card("genre-prose-card-genre-bbb", genre_id="genre-ccc")
        after = REGISTRY.prose_genres()
        self.assertIn("ccc", after, "改内容后缓存未失效（读到旧值）")
        self.assertNotIn("bbb", after)

    def test_explicit_invalidate_forces_rescan(self):
        """显式 invalidate 后必须重扫。"""
        self._write_card("genre-aaa")
        REGISTRY._iter_asset_meta()
        (self._tmp / "genre-prose-card-genre-aaa.json").unlink()
        # 不 invalidate 也能感知（指纹变化）；此处验证显式调用同样有效
        REGISTRY.invalidate_meta_cache()
        self.assertEqual(REGISTRY._iter_asset_meta(), [])

    def test_invalidate_resets_timestamp(self):
        """invalidate 必须同时重置时间戳，否则 TTL 快路径可能读到空缓存。

        单纯清 dict 而留着旧时间戳时，快路径会遍历空 dict 而**返回 None**
        （本实现用 for-return，空 dict 不进循环）——虽不至于报错，但语义上
        "缓存已失效"就该连时间戳一起归零，避免依赖调用顺序的隐性行为。
        """
        REGISTRY._iter_asset_meta()          # 填充缓存与时间戳
        REGISTRY.invalidate_meta_cache()
        self.assertEqual(REGISTRY._META_CACHE_TS, 0.0,
                         "invalidate 未重置时间戳")
        self.assertEqual(REGISTRY._META_CACHE, {}, "invalidate 未清空缓存")

    def test_cache_actually_hits(self):
        """性能守卫：TTL 内重复调用必须完全跳过 stat（否则每次请求都重扫 105 个文件）。

        实测（2026-10-12，105 个资产）：
          - 无缓存：known_genres() ~48ms
          - 仅指纹（每次 stat 全部文件）：~19ms
          - TTL + 指纹：首次 45ms，TTL 内 **0.05ms**

        断言「冷调用比热调用慢 10 倍以上」——用相对倍数而非绝对毫秒，
        避免 CI 机器性能差异导致误红（实测 ~900x，阈值取 10 很保守）。

        注意：本用例需**真实 TTL**（setUp 里设的 0 会让快路径失效），
        故临时恢复默认 TTL。
        """
        import os
        import time
        os.environ.pop("NOVEL_LAB_GENRE_TTL", None)   # 用默认 3 秒 TTL
        REGISTRY.ASSETS_DIR = self._orig_assets
        REGISTRY.invalidate_meta_cache()
        t0 = time.perf_counter()
        REGISTRY._iter_asset_meta()
        cold = time.perf_counter() - t0
        t0 = time.perf_counter()
        for _ in range(20):
            REGISTRY._iter_asset_meta()
        warm = (time.perf_counter() - t0) / 20
        os.environ["NOVEL_LAB_GENRE_TTL"] = "0"       # 还原 setUp 的设定
        self.assertGreater(
            cold, warm * 10,
            f"缓存未生效：冷 {cold*1000:.2f}ms 热 {warm*1000:.3f}ms，倍数仅 "
            f"{cold/max(warm,1e-9):.1f}x（应 >10x）——检查 _META_CACHE 的 "
            "TTL 快路径是否被移除，或指纹是否每次都在重算",
        )

    def test_ttl_window_serves_cached_value(self):
        """TTL 窗口内改磁盘**不**立即生效——这是缓存的设计代价，需明确锁定。

        为什么要锁定这条"看起来不对"的行为：TTL 缓存的价值全在于
        「窗口内不 stat」，若有人为了"更实时"把 TTL 去掉，性能会退回到 19ms。
        写路径（拆书产出资产）会显式 invalidate，不受此窗口约束——
        由 test_explicit_invalidate_forces_rescan 覆盖。
        """
        import os
        import time
        os.environ["NOVEL_LAB_GENRE_TTL"] = "5"
        try:
            self._write_card("genre-prose-card-genre-aaa", genre_id="genre-aaa")
            self.assertIn("aaa", REGISTRY.prose_genres())
            self._write_card("genre-prose-card-genre-bbb", genre_id="genre-bbb")
            # TTL 内：看不到新文件（设计如此）
            self.assertNotIn("bbb", REGISTRY.prose_genres(),
                             "TTL 窗口内不应感知磁盘变化")
            time.sleep(0.01)
            REGISTRY.invalidate_meta_cache()
            self.assertIn("bbb", REGISTRY.prose_genres(),
                          "invalidate 后应立即感知")
        finally:
            os.environ["NOVEL_LAB_GENRE_TTL"] = "0"


if __name__ == "__main__":
    unittest.main(verbosity=2)
