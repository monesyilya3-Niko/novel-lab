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


if __name__ == "__main__":
    unittest.main(verbosity=2)
