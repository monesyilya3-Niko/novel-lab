#!/usr/bin/env python3
"""
novel-lab 蒸馏层回归测试（纯标准库 unittest，零第三方依赖）

覆盖蒸馏核心库（distill_core）的关键聚合逻辑：
  1. collect_assets 资产分组
  2. align 字段归一化（buildup_length 抽字数、payoff_types 正则解析、缺失补 None）
  3. aggregate 分层（hard/soft/personal）与数值中位数、列表交集
  4. resolve_conflict 冲突标记与稳定 id
  5. score_confidence 置信度评分与 over_generalized
  6. detect_blindspots 盲区诊断
  7. distill_genre 编排产出符合 schema
  8. render_distilled 渲染（必守/建议/分歧/盲区）

用法：
  python run_tests.py            # 运行全部测试（含本文件）
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    """按文件名从 scripts/ 动态加载模块（与 test_regressions 同模式）。

    额外把模块注册进 sys.modules，确保 dataclass 等依赖 ``sys.modules[__module__]``
    的类型元编程可正常工作。
    """
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


CORE = _load("distill_core")
RENDER = _load("distill_render")


class TestAlign(unittest.TestCase):
    """align 字段归一化。"""

    def test_buildup_length_int(self):
        assets = {
            "a": {"buildup_length": 3000},
            "b": {"buildup_length": {"chapters": 3, "words": 7200}},
            "c": {"buildup_length": 21000},
        }
        aligned = CORE.align("commercial-obs", assets)
        self.assertEqual(aligned["a"]["buildup_length"], 3000.0)
        self.assertEqual(aligned["b"]["buildup_length"], 7200.0)
        self.assertEqual(aligned["c"]["buildup_length"], 21000.0)

    def test_payoff_types_scattered_string(self):
        assets = {
            "a": {"payoff_density": {"payoff_types": [{"type": "反杀", "ratio": 3}]}},
            "b": {"payoff_density": {"type": "情感回应", "ratio": "情感回应:7，他人认可:2，反杀:1"}},
        }
        aligned = CORE.align("commercial-obs", assets)
        self.assertIsInstance(aligned["a"]["payoff_types"], list)
        parsed = aligned["b"]["payoff_types"]
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]["type"], "情感回应")
        self.assertEqual(parsed[0]["ratio"], 7.0)

    def test_missing_field_is_none(self):
        assets = {"a": {}}
        aligned = CORE.align("commercial-obs", assets)
        for field in CORE.COMMERCIAL_FIELDS:
            self.assertIsNone(aligned["a"][field])

    def test_common_mistakes_nested_path(self):
        assets = {
            "a": {
                "opening_analysis": {
                    "chapter_1": {"common_mistakes": ["错误A", "错误B"]}
                }
            }
        }
        aligned = CORE.align("commercial-obs", assets)
        self.assertEqual(aligned["a"]["common_mistakes"], ["错误A", "错误B"])


class TestAggregate(unittest.TestCase):
    """aggregate 分层与聚合策略。"""

    def test_median_numeric(self):
        aligned = {
            "a": {"payoff_density": {"per_thousand_words": 1.5, "per_chapter": 3}},
            "b": {"payoff_density": {"per_thousand_words": 0.8, "per_chapter": 3}},
            "c": {"payoff_density": {"per_thousand_words": 0.8, "per_chapter": 3}},
        }
        rules = CORE.aggregate("commercial-obs", aligned)
        # payoff_density 归一化为 per_thousand_words / per_chapter 子字段。
        rule = next(r for r in rules if r.field == "payoff_density.per_thousand_words")
        self.assertEqual(rule.kind, "hard")
        self.assertEqual(rule.books_count, 3)
        self.assertEqual(rule.value, 0.8)

    def test_kind_layer(self):
        self.assertEqual(CORE._kind_for_count(3), "hard")
        self.assertEqual(CORE._kind_for_count(2), "soft")
        self.assertEqual(CORE._kind_for_count(1), "personal")

    def test_list_intersection(self):
        self.assertEqual(
            CORE._list_intersection([[1, 2, 3], [2, 3, 4], [2, 3, 5]]), [2, 3]
        )

    def test_banned_intersection(self):
        aligned = {
            "a": {"banned": {"never_used_words": ["x", "y", "z"]}},
            "b": {"banned": {"never_used_words": ["y", "z", "w"]}},
            "c": {"banned": {"never_used_words": ["z", "y", "v"]}},
        }
        rules = CORE.aggregate("voice-card", aligned)
        rule = next(r for r in rules if r.field == "banned.never_used_words")
        self.assertEqual(sorted(rule.value), ["y", "z"])


class TestConflictAndId(unittest.TestCase):
    """resolve_conflict 冲突标记与稳定 id。"""

    def test_conflict_flag_and_id(self):
        rule_a = CORE.AggregatedRule(dimension="commercial-obs", field="skeleton", kind="hard", value="A")
        rule_b = CORE.AggregatedRule(dimension="commercial-obs", field="skeleton", kind="hard", value="B")
        resolved = CORE.resolve_conflict([rule_a, rule_b])
        self.assertTrue(all(r.conflict for r in resolved))
        self.assertEqual(len(resolved), 2)
        self.assertTrue(resolved[0].id.startswith("commercial-obs-skeleton-"))
        self.assertNotEqual(resolved[0].id, resolved[1].id)


class TestConfidence(unittest.TestCase):
    """score_confidence 评分。"""

    def test_hard_base(self):
        rule = CORE.AggregatedRule(kind="hard")
        self.assertEqual(CORE.score_confidence(rule), 0.8)

    def test_missing_book_penalty(self):
        rule = CORE.AggregatedRule(kind="hard", blindspot_books=["a", "b", "c"])
        self.assertEqual(CORE.score_confidence(rule), 0.5)

    def test_conflict_penalty(self):
        rule = CORE.AggregatedRule(kind="soft", conflict=True)
        self.assertEqual(CORE.score_confidence(rule), 0.5)

    def test_floor(self):
        rule = CORE.AggregatedRule(kind="personal", blindspot_books=["a", "b", "c"], conflict=True)
        self.assertEqual(CORE.score_confidence(rule), CORE.CONFIDENCE_MIN)


class TestBlindspots(unittest.TestCase):
    """detect_blindspots 诊断。"""

    def test_detect(self):
        raw = {"a": {}, "b": {"skeleton": "s"}}
        aligned = {
            "a": {"skeleton": None},
            "b": {"skeleton": "s"},
        }
        spots = CORE.detect_blindspots("commercial-obs", raw, aligned)
        fields = {(s["book"], s["field"]) for s in spots}
        self.assertIn(("a", "skeleton"), fields)
        self.assertNotIn(("b", "skeleton"), fields)


class TestDistillGenre(unittest.TestCase):
    """distill_genre 编排产出 schema 正确。"""

    def test_schema(self):
        # 用真实平铺资产（assets/*.json），按 meta.genre 采集 campus-redemption。
        assets_dir = ROOT / "assets"
        has_voice = any(assets_dir.glob("*-voice-card.json"))
        if not has_voice:
            self.skipTest("无资产目录")
        result = CORE.distill_genre("campus-redemption")
        for dim in CORE.DIMENSIONS:
            d = result[dim]
            self.assertIn("meta", d)
            self.assertIn("rules", d)
            self.assertIn("blindspots", d)
            self.assertIn("stats", d)
            self.assertEqual(d["meta"]["id"], f"campus-redemption-{dim}-distilled")
            for r in d["rules"]:
                self.assertIn("id", r)
                self.assertIn("confidence", r)
                self.assertTrue(0.0 <= r["confidence"] <= 1.0)


class TestRenderDistilled(unittest.TestCase):
    """render_distilled 渲染。"""

    def _sample(self):
        return {
            "meta": {
                "id": "campus-redemption-voice-card-distilled",
                "dimension": "voice-card",
                "genre": "campus-redemption",
                "source_books": ["a", "b", "c"],
                "books_count": 3,
            },
            "rules": [
                {
                    "id": "voice-card-banned-never_used_words-0001",
                    "dimension": "voice-card",
                    "field": "banned.never_used_words",
                    "kind": "hard",
                    "books_count": 3,
                    "value": ["词A", "词B"],
                    "sources": [],
                    "confidence": 0.8,
                    "conflict": False,
                    "over_generalized": False,
                    "blindspot_books": [],
                },
                {
                    "id": "voice-card-narration-pov-0001",
                    "dimension": "voice-card",
                    "field": "narration.pov",
                    "kind": "soft",
                    "books_count": 2,
                    "value": "第三人称",
                    "sources": [],
                    "confidence": 0.6,
                    "conflict": True,
                    "over_generalized": False,
                    "blindspot_books": ["c"],
                },
            ],
            "blindspots": [
                {"book": "c", "dimension": "voice-card", "field": "narration.pov", "note": "缺失"}
            ],
            "stats": {},
        }

    def test_render_has_markers(self):
        text = RENDER.render_distilled(self._sample())
        self.assertIn("必守", text)
        self.assertIn("建议", text)
        self.assertIn("二选一/分歧", text)
        self.assertIn("注意缺失", text)

    def test_render_empty(self):
        self.assertEqual(RENDER.render_distilled(None), "")
        self.assertEqual(RENDER.render_distilled({"rules": [], "blindspots": []}), "")


if __name__ == "__main__":
    unittest.main()
