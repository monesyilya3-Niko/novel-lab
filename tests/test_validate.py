#!/usr/bin/env python3
"""
validate.py 资产契约回归测试（纯标准库 unittest，零第三方依赖）。

覆盖 2026-09-16 高优先级修复 Task 1 引入的专用校验契约：

  1. `auto_kind` 必须把蒸馏资产（meta.dimension 派生的 voice-card/craft-card/
     structure-obs/commercial-obs distilled）判为 `distilled`，把题材文风卡索引判为
     `genre-prose-card-index`，不得再兜底误判为 voice-card（历史 bug 同款）。
  2. `validate_asset_data(kind, data)` 返回**纯数据**的 (硬错误, 警告) 文本列表，
     且不污染调用前的全局 ERRORS/WARNS。
  3. `validate_distilled` 对顶层 meta/rules/blindspots/stats 契约、
     规则必填键与 dimension 一致性、confidence 范围、bool 字段做硬校验。
  4. `validate_genre_prose_card_index` 对 _count/_description/cards 与卡片 id/file 做硬校验。

用法：
  python run_tests.py            # 自动 discover 本文件（pattern test_*.py）
"""
import copy
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
    """按文件名从 scripts/ 动态加载模块（与 test_genre_isolation/test_distill 同模式）。"""
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


validate = _load("validate")

DISTILLED_FILES = sorted(ASSETS.glob("*-distilled.json"))
INDEX_FILE = ASSETS / "genre-prose-card-index.json"

# 最小合法 distilled 资产（结构对齐 assets/*-distilled.json 实测形状）
DISTILLED_SAMPLE = {
    "meta": {
        "id": "campus-redemption-voice-card-distilled",
        "schema_version": "1.0",
        "dimension": "voice-card",
        "genre": "campus-redemption",
        "distilled_at": "2026-09-11T04:59:49",
        "source_books": ["a", "b", "c", "d"],
        "books_count": 4,
    },
    "rules": [
        {
            "id": "voice-card-narration-pov-0001",
            "dimension": "voice-card",
            "field": "narration.pov",
            "kind": "hard",
            "books_count": 4,
            "value": "第三人称限知",
            "sources": [{"book": "a", "value": "第三人称限知"}],
            "confidence": 0.8,
            "conflict": False,
            "over_generalized": False,
            "blindspot_books": [],
        }
    ],
    "blindspots": [],
    "stats": {"total_rules": 1, "hard_rules": 1, "soft_rules": 0},
}

# 最小合法 index 资产（结构对齐 assets/genre-prose-card-index.json 实测形状）
INDEX_SAMPLE = {
    "_description": "题材文风卡索引：题材中文名 → id / 落库文件名。",
    "_count": 1,
    "cards": {"都市": {"id": "genre-dushi", "file": "genre-prose-card-genre-dushi.json"}},
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 1. auto_kind 类型判定
# --------------------------------------------------------------------------

class TestAssetKindDetection(unittest.TestCase):
    """auto_kind 必须区分 distilled / genre-prose-card-index / genre-prose-card。"""

    def test_distilled_is_not_voice_card(self):
        d = {
            "meta": {"dimension": "voice-card", "id": "g-voice-card-distilled",
                     "schema_version": "1.0", "genre": "campus-redemption",
                     "source_books": ["a", "b", "c"], "books_count": 3},
            "rules": [], "blindspots": [], "stats": {},
        }
        self.assertEqual(validate.auto_kind(d, "g-voice-card-distilled.json"), "distilled")

    def test_index_is_distinct_kind(self):
        self.assertEqual(
            validate.auto_kind({"_count": 1, "_description": "x", "cards": {}},
                               "genre-prose-card-index.json"),
            "genre-prose-card-index",
        )

    def test_filename_argument_is_optional(self):
        """旧的单参数调用必须继续有效（向后兼容）。"""
        self.assertEqual(validate.auto_kind({"tropes": [], "abstraction_level": "structural"}),
                         "trope-library")
        self.assertEqual(validate.auto_kind({"meta": {"kind": "genre-prose-card"}}),
                         "genre-prose-card")
        self.assertEqual(validate.auto_kind({}), "voice-card")

    def test_index_requires_filename_hint(self):
        """仅有 cards 键、文件名无 index 线索时不得误判为 index（保守）。"""
        self.assertNotEqual(
            validate.auto_kind({"_count": 1, "_description": "x", "cards": {}}, "unknown.json"),
            "genre-prose-card-index",
        )

    def test_real_assets_keep_their_kind(self):
        """真实资产目录的判定不得被新规则带偏。"""
        self.assertEqual(validate.auto_kind(_load_json(INDEX_FILE), INDEX_FILE.name),
                         "genre-prose-card-index")
        for p in DISTILLED_FILES:
            self.assertEqual(validate.auto_kind(_load_json(p), p.name), "distilled",
                             f"{p.name} 应判为 distilled")
        for p in sorted(ASSETS.glob("genre-prose-card-genre-*.json")):
            self.assertEqual(validate.auto_kind(_load_json(p), p.name), "genre-prose-card",
                             f"{p.name} 应仍判为 genre-prose-card")
        for p in sorted(ASSETS.glob("*-voice-card.json")):
            self.assertEqual(validate.auto_kind(_load_json(p), p.name), "voice-card",
                             f"{p.name} 应仍判为 voice-card")


# --------------------------------------------------------------------------
# 2. validate_asset_data 纯数据接口
# --------------------------------------------------------------------------

class TestValidateAssetData(unittest.TestCase):
    """validate_asset_data 返回纯数据文本，且不污染全局 ERRORS/WARNS。"""

    def setUp(self):
        validate.reset()

    def test_returns_two_lists_of_text(self):
        errors, warns = validate.validate_asset_data("distilled", DISTILLED_SAMPLE)
        self.assertIsInstance(errors, list)
        self.assertIsInstance(warns, list)
        self.assertEqual(errors, [])
        self.assertEqual(warns, [])

    def test_returned_text_has_no_marker_prefix(self):
        """返回文本为纯数据：不带 err()/warn() 的 '✗' / '⚠' 前缀。"""
        errors, warns = validate.validate_asset_data("genre-prose-card-index", {"_count": -1})
        self.assertTrue(errors)
        for line in errors + warns:
            self.assertFalse(line.lstrip().startswith(("✗", "⚠")), f"应去掉前缀标记: {line!r}")

    def test_does_not_pollute_globals(self):
        validate.err("调用前已存在的错误", "pre")
        before_errors = list(validate.ERRORS)
        before_warns = list(validate.WARNS)

        validate.validate_asset_data("distilled", {"meta": {}})

        self.assertEqual(validate.ERRORS, before_errors)
        self.assertEqual(validate.WARNS, before_warns)

    def test_unknown_kind_reports_error(self):
        errors, _ = validate.validate_asset_data("no-such-kind", {})
        self.assertTrue(any("no-such-kind" in e for e in errors))


# --------------------------------------------------------------------------
# 3. distilled 契约
# --------------------------------------------------------------------------

class TestDistilledValidation(unittest.TestCase):
    """validate_distilled / validate_asset_data("distilled", ...) 的契约校验。"""

    def setUp(self):
        self.sample = copy.deepcopy(DISTILLED_SAMPLE)
        validate.reset()

    def test_current_shape_passes(self):
        errors, warns = validate.validate_asset_data("distilled", self.sample)
        self.assertEqual(errors, [])

    def test_all_real_distilled_assets_pass(self):
        """四个现有 distilled 资产必须零硬错误、零警告（CLI 退出码 0 前提）。"""
        self.assertTrue(DISTILLED_FILES, "assets/ 下应存在 *-distilled.json")
        for p in DISTILLED_FILES:
            errors, warns = validate.validate_asset_data("distilled", _load_json(p))
            self.assertEqual(errors, [], f"{p.name} 不应有硬错误: {errors}")
            self.assertEqual(warns, [], f"{p.name} 不应有警告: {warns}")

    def test_empty_rules_allowed(self):
        """rules 允许为空列表（现有 distilled 存在空规则场景）。"""
        d = copy.deepcopy(self.sample)
        d["rules"] = []
        errors, _ = validate.validate_asset_data("distilled", d)
        self.assertEqual(errors, [])

    def test_rule_dimension_mismatch_rejects(self):
        bad = copy.deepcopy(self.sample)
        bad["rules"] = [{"id": "x", "dimension": "craft-card", "field": "x",
                         "kind": "hard", "books_count": 3, "value": None,
                         "confidence": 0.8, "conflict": False,
                         "over_generalized": False, "blindspot_books": []}]
        errors, _ = validate.validate_asset_data("distilled", bad)
        self.assertTrue(any("dimension" in e for e in errors))

    def test_meta_dimension_enum_rejects_unknown(self):
        bad = copy.deepcopy(self.sample)
        bad["meta"]["dimension"] = "no-such-dimension"
        errors, _ = validate.validate_asset_data("distilled", bad)
        self.assertTrue(any("dimension" in e for e in errors))

    def test_missing_meta_dimension_rejects(self):
        bad = copy.deepcopy(self.sample)
        del bad["meta"]["dimension"]
        errors, _ = validate.validate_asset_data("distilled", bad)
        self.assertTrue(any("dimension" in e for e in errors))

    def test_missing_rule_required_key_rejects(self):
        bad = copy.deepcopy(self.sample)
        del bad["rules"][0]["blindspot_books"]
        errors, _ = validate.validate_asset_data("distilled", bad)
        self.assertTrue(any("blindspot_books" in e for e in errors))

    def test_confidence_out_of_range_rejects(self):
        bad = copy.deepcopy(self.sample)
        bad["rules"][0]["confidence"] = 1.5
        errors, _ = validate.validate_asset_data("distilled", bad)
        self.assertTrue(any("confidence" in e for e in errors))

    def test_non_bool_flag_rejects(self):
        bad = copy.deepcopy(self.sample)
        bad["rules"][0]["conflict"] = "false"
        errors, _ = validate.validate_asset_data("distilled", bad)
        self.assertTrue(any("conflict" in e for e in errors))

    def test_missing_top_level_field_rejects(self):
        bad = copy.deepcopy(self.sample)
        del bad["stats"]
        errors, _ = validate.validate_asset_data("distilled", bad)
        self.assertTrue(any("stats" in e for e in errors))


# --------------------------------------------------------------------------
# 4. genre-prose-card-index 契约
# --------------------------------------------------------------------------

class TestGenreProseCardIndexValidation(unittest.TestCase):
    """validate_genre_prose_card_index 的契约校验。"""

    def setUp(self):
        validate.reset()

    def test_index_shape_passes(self):
        errors, _ = validate.validate_asset_data(
            "genre-prose-card-index",
            {"_count": 1, "_description": "x",
             "cards": {"都市": {"id": "genre-dushi", "file": "genre-prose-card-genre-dushi.json"}}},
        )
        self.assertEqual(errors, [])

    def test_real_index_asset_passes(self):
        """真实索引必须零硬错误、零警告，且不触发任何 voice-card 错误。"""
        errors, warns = validate.validate_asset_data("genre-prose-card-index", _load_json(INDEX_FILE))
        self.assertEqual(errors, [], f"索引不应有硬错误: {errors}")
        self.assertEqual(warns, [], f"索引不应有警告: {warns}")
        self.assertFalse([e for e in errors if "voice-card" in e],
                         "索引不得被当作 voice-card 校验")

    def test_index_not_validated_as_voice_card(self):
        """索引经 auto_kind + validate_asset_data 不得产生 voice-card 类错误。"""
        d = _load_json(INDEX_FILE)
        kind = validate.auto_kind(d, INDEX_FILE.name)
        self.assertEqual(kind, "genre-prose-card-index")
        errors, _ = validate.validate_asset_data(kind, d)
        self.assertEqual(errors, [])

    def test_negative_count_rejects(self):
        errors, _ = validate.validate_asset_data("genre-prose-card-index", {"_count": -1})
        self.assertTrue(any("_count" in e for e in errors))

    def test_non_int_count_rejects(self):
        errors, _ = validate.validate_asset_data("genre-prose-card-index", {"_count": "32"})
        self.assertTrue(any("_count" in e for e in errors))

    def test_cards_not_object_rejects(self):
        errors, _ = validate.validate_asset_data(
            "genre-prose-card-index", {"_count": 0, "_description": "x", "cards": []})
        self.assertTrue(any("cards" in e for e in errors))

    def test_card_missing_id_rejects(self):
        errors, _ = validate.validate_asset_data(
            "genre-prose-card-index",
            {"_count": 1, "_description": "x",
             "cards": {"都市": {"file": "genre-prose-card-genre-dushi.json"}}})
        self.assertTrue(any("id" in e for e in errors))

    def test_card_missing_file_rejects(self):
        errors, _ = validate.validate_asset_data(
            "genre-prose-card-index",
            {"_count": 1, "_description": "x", "cards": {"都市": {"id": "genre-dushi"}}})
        self.assertTrue(any("file" in e for e in errors))

    def test_missing_description_rejects(self):
        errors, _ = validate.validate_asset_data(
            "genre-prose-card-index", {"_count": 0, "cards": {}})
        self.assertTrue(any("_description" in e for e in errors))


# --------------------------------------------------------------------------
# 5. DISPATCH / CLI 注册
# --------------------------------------------------------------------------

class TestDispatchRegistration(unittest.TestCase):
    """新 kind 必须注册进 DISPATCH（CLI --kind choices 同源）。"""

    def test_dispatch_contains_new_kinds(self):
        self.assertIn("distilled", validate.DISPATCH)
        self.assertIn("genre-prose-card-index", validate.DISPATCH)
        self.assertIs(validate.DISPATCH["distilled"], validate.validate_distilled)
        self.assertIs(validate.DISPATCH["genre-prose-card-index"],
                      validate.validate_genre_prose_card_index)

    def test_dispatch_keeps_legacy_kinds(self):
        for kind in ("voice-card", "genre-pack", "trope-library", "craft-card",
                     "structure-obs", "commercial-obs", "genre-prose-card"):
            self.assertIn(kind, validate.DISPATCH, f"{kind} 不得从 DISPATCH 移除")


if __name__ == "__main__":
    unittest.main()
