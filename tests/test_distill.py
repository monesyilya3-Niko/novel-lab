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
  7. distill_genre 编排产出符合 schema（distilled 走 Task 1 的专用校验契约，
     不按 voice-card 顶层字段断言）
  8. render_distilled 渲染（必守/建议/分歧/盲区）

用法：
  python run_tests.py            # 运行全部测试（含本文件）
"""
import importlib.util
import sys
import unittest
from collections import Counter
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
RETRIEVE = _load("retrieve")
INJECT = _load("inject")
VALIDATE = _load("validate")


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
    """distill_genre 编排产出 schema 正确（distilled 专用契约，非 voice-card）。"""

    def _distill(self):
        """用真实平铺资产（assets/*.json）采集 campus-redemption；无资产则跳过。"""
        assets_dir = ROOT / "assets"
        if not any(assets_dir.glob("*-voice-card.json")):
            self.skipTest("无资产目录")
        return CORE.distill_genre("campus-redemption")

    def test_schema(self):
        result = self._distill()
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

    def test_each_dimension_passes_distilled_validation(self):
        """每个维度都必须通过 distilled 专用校验（Task 1 契约，rules=[] 亦合法）。"""
        result = self._distill()
        for dim in CORE.DIMENSIONS:
            errors, warns = VALIDATE.validate_asset_data("distilled", result[dim])
            self.assertEqual(errors, [], f"{dim} distilled 硬错误: {errors}")
            self.assertEqual(warns, [], f"{dim} distilled 警告: {warns}")

    def test_distilled_is_not_voice_card_shape(self):
        """蒸馏产物判为 distilled，且不含 voice-card 顶层字段（勿再按 voice-card 断言）。"""
        result = self._distill()
        for dim in CORE.DIMENSIONS:
            d = result[dim]
            self.assertEqual(VALIDATE.auto_kind(d), "distilled",
                             f"{dim} 蒸馏产物应判为 distilled")
            for field in ("narration", "dialogue", "emotion_handling", "banned"):
                self.assertNotIn(field, d, f"{dim} 不应含 voice-card 顶层字段 '{field}'")


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


class TestBug1PayoffTypes(unittest.TestCase):
    """Bug1 回归：sangshi 比例式 ratio 不应误解析为类型清单。"""

    def test_ratio_with_equals_not_parsed(self):
        # 「铺垫:爆发 = 10:1」是配比描述，不应被当成「类型:数字」清单。
        result = CORE._parse_payoff_types("铺垫:爆发 = 10:1 (按章计算...)")
        self.assertIsNone(result)

    def test_type_list_downgrades_directly(self):
        # type 是 list 时应直接降级为 [{'type':t,'ratio':None}]，保留 3 个真实类型。
        asset = {
            "payoff_density": {
                "type": ["情感回应", "身份揭露", "他人认可"],
                "ratio": "铺垫:爆发 = 10:1 (按章计算...)",
            }
        }
        result = CORE._extract_payoff_types_from_asset(asset)
        self.assertEqual(len(result), 3)
        self.assertEqual(
            [r["type"] for r in result],
            ["情感回应", "身份揭露", "他人认可"],
        )
        # ratio 全部为 None（比例式不参与「类型:数字」解析）。
        self.assertTrue(all(r["ratio"] is None for r in result))

    def test_plain_type_ratio_still_parses(self):
        # qingning 的普通「类型:数字」字符串仍应正常解析。
        result = CORE._parse_payoff_types("情感回应:7，他人认可:2，反杀:1")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["type"], "情感回应")
        self.assertEqual(result[0]["ratio"], 7.0)

    def test_payoff_types_cross_book_union_dedup_by_type(self):
        # P3-a 收口回归：跨书并集后同一 payoff type 出现不同 ratio（如
        # 「情感回应」ratio=20 / 7.0 / None），_list_union 只按整项相等去重、
        # 不去重 type。本次修复在 list-union 分支对 payoff_types 追加一次
        # _dedup_payoff_types，按 type 去重、保留首个出现的 ratio。
        rule = CORE._aggregate_field(
            dimension="commercial-obs",
            field="payoff_types",
            book_vals={
                "a": [{"type": "情感回应", "ratio": 20}, {"type": "打脸", "ratio": 40}],
                "b": [{"type": "情感回应", "ratio": 7.0}, {"type": "反杀", "ratio": 1.0}],
                "c": [{"type": "情感回应", "ratio": None}, {"type": "身份揭露", "ratio": None}],
            },
            books=["a", "b", "c"],
            aggregator="list-union",
        )
        types = [x["type"] for x in rule.value]
        # 每个 type 只出现一次（「情感回应」三条去重为一条）。
        self.assertEqual(len(types), len(set(types)))
        self.assertEqual(set(types), {"情感回应", "打脸", "反杀", "身份揭露"})
        # 「情感回应」保留首个出现的 ratio=20（来自 book a）。
        huiying = next(x for x in rule.value if x["type"] == "情感回应")
        self.assertEqual(huiying["ratio"], 20)
        # sources 仍保留各书原始（不去重）列表，供溯源。
        self.assertEqual(len(rule.sources), 3)


class TestBug2FreqDivergence(unittest.TestCase):
    """Bug2 回归：string-freq 众数占比 <100% 时应标记分歧。"""

    def test_freq_full_marks_divergence(self):
        value, has_div = CORE._freq_aggregate_strings_full(["混合式", "直陈式", "混合式"])
        # 众数「混合式」占 2/3，仍返回众数，但必须标记分歧。
        self.assertEqual(value, "混合式")
        self.assertTrue(has_div)

    def test_freq_full_all_same_no_divergence(self):
        value, has_div = CORE._freq_aggregate_strings_full(["混合式", "混合式", "混合式"])
        self.assertEqual(value, "混合式")
        self.assertFalse(has_div)

    def test_aggregate_field_median_string_conflict(self):
        # emotion_handling.mode 三本「混合式/直陈式/混合式」经 median(非数值)分支
        # 聚合后应标 conflict=True（不再静默丢弃「直陈式」）。
        rule = CORE._aggregate_field(
            dimension="voice-card",
            field="emotion_handling.mode",
            book_vals={"a": "混合式", "b": "直陈式", "c": "混合式"},
            books=["a", "b", "c"],
            aggregator="median",
        )
        self.assertEqual(rule.value, "混合式")
        self.assertTrue(rule.conflict)


class TestBug3ListUnionNoIntersection(unittest.TestCase):
    """Bug3 回归：list-union 无交集（三本各说各话）不应标 hard。"""

    def test_list_union_no_intersection_downgrades(self):
        rule = CORE._aggregate_field(
            dimension="craft-card",
            field="craft_summary.top_3_strengths",
            book_vals={
                "a": ["甲技能", "乙技能"],
                "b": ["丙技能", "丁技能"],
                "c": ["戊技能", "己技能"],
            },
            books=["a", "b", "c"],
            aggregator="list-union",
        )
        # 三本零交集 → 降级为 soft 并标记 conflict。
        self.assertEqual(rule.kind, "soft")
        self.assertTrue(rule.conflict)
        # 并集仍保留全部来源。
        self.assertEqual(len(rule.value), 6)

    def test_list_union_with_intersection_stays_hard(self):
        rule = CORE._aggregate_field(
            dimension="craft-card",
            field="craft_summary.top_3_strengths",
            book_vals={
                "a": ["共技", "甲"],
                "b": ["共技", "乙"],
                "c": ["共技", "丙"],
            },
            books=["a", "b", "c"],
            aggregator="list-union",
        )
        # 有交集「共技」→ 仍标 hard，不标 conflict。
        self.assertEqual(rule.kind, "hard")
        self.assertFalse(rule.conflict)


class TestTechniqueNormalization(unittest.TestCase):
    """二期 · 任务 A：技法归一化纯函数。"""

    def test_normalize_removes_space_and_punct(self):
        self.assertEqual(CORE._normalize_technique("三段式 钩子"), "三段式钩子")
        self.assertEqual(CORE._normalize_technique("三段式钩子"), "三段式钩子")

    def test_normalize_strips_stopwords(self):
        # 「的」作为停用词应被剥离（整词，不误伤「目的」内部同形字需另测）。
        self.assertEqual(CORE._normalize_technique("反转式 悬念"), "反转式悬念")

    def test_normalize_empty(self):
        self.assertEqual(CORE._normalize_technique(""), "")
        self.assertEqual(CORE._normalize_technique(None), "")

    def test_char_ngram_similarity_identical(self):
        self.assertEqual(CORE._char_ngram_similarity("abc", "abc"), 1.0)

    def test_char_ngram_similarity_disjoint(self):
        self.assertEqual(CORE._char_ngram_similarity("abc", "xyz"), 0.0)

    def test_cluster_synonym_merge(self):
        techs = [
            {"name": "三段式钩子", "skeleton": "X", "book": "a"},
            {"name": "三段式 钩子", "skeleton": "X", "book": "b"},
            {"name": "三段式悬念钩子", "skeleton": "X", "book": "c"},
            {"name": "三段式钩子法", "skeleton": "X", "book": "d"},
        ]
        clusters = CORE._cluster_techniques(techs)
        # 同义词表把四个别名归到「三段式钩子」一个簇。
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].count, 4)
        self.assertEqual(set(clusters[0].books), {"a", "b", "c", "d"})

    def test_cluster_single_condition_high_threshold(self):
        # skeleton 缺失时退化为单条件 name Jaccard ≥ 0.7 才合并。
        techs = [
            {"name": "生理反应外化情绪张力", "skeleton": "", "book": "a"},
            {"name": "生理反应外化情绪张力", "skeleton": "", "book": "b"},
        ]
        clusters = CORE._cluster_techniques(techs)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].count, 2)

    def test_cluster_distinct_names_stay_separate(self):
        techs = [
            {"name": "以身体距离变化推动关系张力", "skeleton": "S1", "book": "a"},
            {"name": "迟到者的动态切入", "skeleton": "S2", "book": "b"},
        ]
        clusters = CORE._cluster_techniques(techs)
        # 两个完全不同的技法名不应合并。
        self.assertEqual(len(clusters), 2)


class TestRetrieval(unittest.TestCase):
    """二期 · 任务 B：倒排索引 + BM25 检索 + 意图映射 + 渲染。"""

    def _assets(self):
        return {
            "craft-card": {
                "book_a": {
                    "meta": {"id": "craft-card-book_a", "dimension": "craft-card"},
                    "craft_analysis": {
                        "foreshadowing": {
                            "techniques": [
                                {"name": "三段式钩子", "skeleton": "先抛悬念再揭晓"}
                            ]
                        }
                    },
                },
                "book_b": {
                    "meta": {"id": "craft-card-book_b", "dimension": "craft-card"},
                    "craft_analysis": {
                        "foreshadowing": {
                            "techniques": [
                                {"name": "反转式悬念", "skeleton": "结尾反转"}
                            ]
                        }
                    },
                },
            },
            "structure-obs": {
                "book_a": {
                    "meta": {"id": "structure-obs-book_a", "dimension": "structure-obs"},
                    "chapter_analyses": [{"hook": {"skeleton": "钩子骨架A"}}],
                },
            },
        }

    def test_build_index_docs_count(self):
        idx = RETRIEVE.build_index(self._assets())
        self.assertEqual(len(idx.docs), 3)

    def test_build_index_inverted_populated(self):
        idx = RETRIEVE.build_index(self._assets())
        # 倒排表与文档频率表应非空，且词项数 == 文档频率条目数。
        self.assertTrue(len(idx.inverted) > 0)
        self.assertEqual(len(idx.inverted), len(idx.doc_freq))

    def test_retrieve_returns_hits_sorted(self):
        idx = RETRIEVE.build_index(self._assets())
        hits = RETRIEVE.retrieve_for_intent("钩子", idx)
        self.assertTrue(len(hits) > 0)
        scores = [h.score for h in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_retrieve_top_k_limit(self):
        idx = RETRIEVE.build_index(self._assets())
        hits = RETRIEVE.retrieve_for_intent("钩子", idx, top_k=1)
        self.assertLessEqual(len(hits), 1)

    def test_retrieve_empty_intent(self):
        idx = RETRIEVE.build_index(self._assets())
        self.assertEqual(RETRIEVE.retrieve_for_intent("", idx), [])

    def test_render_retrieval_markers(self):
        hits = [
            RETRIEVE.HitEntry(
                asset_id="x", dimension="craft-card", score=1.0, snippet="片段A"
            )
        ]
        text = RETRIEVE.render_retrieval(hits)
        self.assertIn("针对性注入", text)
        self.assertIn("片段A", text)

    def test_render_retrieval_empty(self):
        self.assertEqual(RETRIEVE.render_retrieval([]), "")

    def test_snippet_truncation(self):
        long_body = {"rules": [{"field": "f", "value": "长" * 300}]}
        snippet = RETRIEVE._build_snippet(long_body)
        self.assertLessEqual(len(snippet), RETRIEVE.SNIPPET_LEN)

    # ---- 边界测试：零文档 / 无命中 / 子串去重 / 意图注入 / ImportError 兜底 ----

    def test_empty_index_returns_empty(self):
        idx = RETRIEVE.build_index({})
        self.assertEqual(RETRIEVE.retrieve_for_intent("钩子", idx), [])

    def test_no_hit_intent_returns_empty(self):
        idx = RETRIEVE.build_index(self._assets())
        self.assertEqual(RETRIEVE.retrieve_for_intent("不存在的词xyz", idx), [])

    def test_substring_no_duplicate_accumulation(self):
        # 构造文档：terms 含两个都包含查询词「钩子」的 token。
        # 修复后应只累加「最佳匹配 dt」一次，得分不高于该最佳单次贡献值。
        from collections import Counter
        idx = RETRIEVE.Index()
        doc = RETRIEVE.DocEntry(
            asset_id="d1", dimension="craft-card", terms=Counter({"钩子手法": 1, "小钩子": 1})
        )
        idx.docs.append(doc)
        # 手动补齐 doc_freq/idf_cache，使 _idf 可正常计算（词项 df=1）。
        for term in ("钩子手法", "小钩子"):
            idx.doc_freq[term] = 1
        idx.idf_cache = {}

        score = RETRIEVE._bm25_score(["钩子"], doc, idx)

        # 期望：最佳匹配贡献 = max(idf(t) * tf * (k1+1)/(tf+k1))，tf=1。
        k1 = RETRIEVE.BM25_K1
        contrib_a = RETRIEVE._idf("钩子手法", idx) * 1 * (k1 + 1.0) / (1 + k1)
        contrib_b = RETRIEVE._idf("小钩子", idx) * 1 * (k1 + 1.0) / (1 + k1)
        expected = max(contrib_a, contrib_b)
        self.assertEqual(score, expected)

    def test_intent_map_injects_terms(self):
        idx = RETRIEVE.build_index(self._assets())
        hits = RETRIEVE.retrieve_for_intent("悬念", idx)
        self.assertTrue(len(hits) > 0)
        dimensions = {h.dimension for h in hits}
        self.assertIn("craft-card", dimensions)

    def test_build_index_from_genre_returns_index(self):
        # 正常导入 distill_core 时返回 Index 实例；无 genre 资产时至少不 crash。
        idx = RETRIEVE.build_index_from_genre("nonexistent-genre-xyz")
        self.assertIsInstance(idx, RETRIEVE.Index)

    # ---- 健壮性收尾：非字符串 intent / None index / 空输入防御 ----

    def test_retrieve_non_str_intent_returns_empty(self):
        idx = RETRIEVE.build_index(self._assets())
        self.assertEqual(RETRIEVE.retrieve_for_intent(["钩子"], idx), [])
        self.assertEqual(RETRIEVE.retrieve_for_intent(12345, idx), [])
        self.assertEqual(RETRIEVE.retrieve_for_intent(None, idx), [])

    def test_retrieve_none_index_returns_empty(self):
        self.assertEqual(RETRIEVE.retrieve_for_intent("钩子", None), [])

    def test_build_index_none_returns_empty(self):
        idx = RETRIEVE.build_index(None)
        self.assertIsInstance(idx, RETRIEVE.Index)
        self.assertEqual(idx.docs, [])

    def test_build_index_non_dict_value_skipped(self):
        # 非 dict 值（None 与字符串）应被跳过，不 crash，索引为空。
        idx = RETRIEVE.build_index({"craft-card": None})
        self.assertIsInstance(idx, RETRIEVE.Index)
        self.assertEqual(idx.docs, [])
        idx2 = RETRIEVE.build_index({"craft-card": "notadict"})
        self.assertEqual(idx2.docs, [])

    def test_build_index_non_dict_meta_skipped(self):
        # meta 字段为非 dict 真值（str/list/int）时不应 crash，asset_id 走
        # 兜底分支（meta 视为空 dict，无 id/source_title → "<dimension>-distilled"），
        # docs 非空且无异常。
        for bad_meta in ("notadict", [1, 2], 5):
            idx = RETRIEVE.build_index(
                {"craft-card": {"b": {"meta": bad_meta, "craft_analysis": {"x": "y"}}}}
            )
            self.assertIsInstance(idx, RETRIEVE.Index)
            self.assertEqual(len(idx.docs), 1)
            self.assertEqual(idx.docs[0].asset_id, "craft-card-distilled")


class TestVectorRetrieval(unittest.TestCase):
    """二期 · P0：字符 n-gram 向量 + 余弦 + 融合检索（纯标准库）。"""

    def _assets(self):
        """构造含「悬疑」语义但无「悬念」字面的文档，验证向量近义召回。"""
        return {
            "craft-card": {
                "book_a": {
                    "meta": {"id": "craft-card-book_a", "dimension": "craft-card"},
                    "craft_analysis": {
                        "foreshadowing": {
                            "techniques": [
                                {"name": "悬疑铺垫", "skeleton": "逐步埋下疑点"}
                            ]
                        }
                    },
                },
            },
            "structure-obs": {
                "book_a": {
                    "meta": {"id": "structure-obs-book_a", "dimension": "structure-obs"},
                    "chapter_analyses": [{"hook": {"skeleton": "章末悬疑钩子"}}],
                },
            },
        }

    def test_ngram_counter_has_123_grams_with_prefix(self):
        c = RETRIEVE._ngram_counter("钩子")
        # 1-gram / 2-gram 存在，键带 "n:" 前缀。
        self.assertGreaterEqual(c["1:钩"], 1)
        self.assertGreaterEqual(c["2:钩子"], 1)

    def test_ngram_counter_trigram(self):
        c = RETRIEVE._ngram_counter("三段式")
        self.assertGreaterEqual(c["3:三段式"], 1)

    def test_ngram_counter_empty(self):
        self.assertEqual(RETRIEVE._ngram_counter(""), Counter())

    def test_cosine_identical_is_one(self):
        self.assertEqual(
            RETRIEVE._cosine_sim(Counter({"2:钩子": 1}), 1.0, Counter({"2:钩子": 1}), 1.0),
            1.0,
        )

    def test_cosine_orthogonal_is_zero(self):
        self.assertEqual(
            RETRIEVE._cosine_sim(Counter({"1:a": 1}), 1.0, Counter({"1:b": 1}), 1.0),
            0.0,
        )

    def test_cosine_zero_vector_is_zero(self):
        # 任一范数为 0 → 返回 0（防除零）。
        self.assertEqual(RETRIEVE._cosine_sim(Counter(), 0.0, Counter({"1:a": 1}), 1.0), 0.0)
        self.assertEqual(RETRIEVE._cosine_sim(Counter({"1:a": 1}), 1.0, Counter(), 0.0), 0.0)

    def test_norm(self):
        self.assertEqual(RETRIEVE._norm(Counter({"a": 3, "b": 4})), 5.0)
        self.assertEqual(RETRIEVE._norm(Counter()), 0.0)

    def test_fused_score_weight_boundaries(self):
        # alpha=0 → 纯向量；alpha=1 → 纯 BM25；alpha=0.5 → 各半。
        self.assertEqual(RETRIEVE._fused_score(1.0, 1.0, 0.0, 0.0), 0.0)
        self.assertEqual(RETRIEVE._fused_score(0.0, 1.0, 1.0, 0.0), 1.0)
        self.assertEqual(RETRIEVE._fused_score(1.0, 1.0, 0.0, 1.0), 1.0)
        self.assertEqual(RETRIEVE._fused_score(1.0, 1.0, 1.0, 1.0), 1.0)
        self.assertEqual(RETRIEVE._fused_score(1.0, 1.0, 0.0, 0.5), 0.5)
        self.assertEqual(RETRIEVE._fused_score(0.0, 1.0, 1.0, 0.5), 0.5)

    def test_build_index_norms_length(self):
        idx = RETRIEVE.build_index(self._assets())
        self.assertEqual(len(idx.norms), len(idx.docs))
        # 每篇文档 ngrams 非空且含 "n:" 前缀键。
        for doc in idx.docs:
            self.assertTrue(doc.ngrams)
            self.assertTrue(any(k.startswith("2:") for k in doc.ngrams))

    def test_synonym_recall_suspense_vs_xuanyi(self):
        # 文档用「悬疑」字面，查询「悬念」——BM25 子串补偿召回不了，但向量应能召回。
        idx = RETRIEVE.build_index(self._assets())
        hits = RETRIEVE.retrieve_for_intent("悬念", idx)
        self.assertTrue(len(hits) > 0)
        dimensions = {h.dimension for h in hits}
        self.assertIn("craft-card", dimensions)

    def test_deterministic_two_runs_identical(self):
        idx = RETRIEVE.build_index(self._assets())
        first = RETRIEVE.retrieve_for_intent("想要章末反转", idx)
        second = RETRIEVE.retrieve_for_intent("想要章末反转", idx)
        self.assertEqual(
            [(h.asset_id, h.score) for h in first],
            [(h.asset_id, h.score) for h in second],
        )


class TestInjectRegression(unittest.TestCase):
    """二期 · 注入回归：未传 context_intent 时与一期字节级一致。"""

    def _voice(self):
        return {
            "meta": {"source_title": "chireng_chosen", "genre": "campus-redemption"},
            "narration": {"pov": "第三人称"},
            "dialogue": {"character_voices": []},
            "emotion_handling": {},
            "imagery": {},
            "banned": {},
        }

    def test_build_prompt_no_intent_unchanged(self):
        voice = self._voice()
        base = INJECT.build_prompt(voice, None, None)
        again = INJECT.build_prompt(voice, None, None)
        self.assertEqual(base, again)

    def test_build_prompt_signature_has_context_intent(self):
        import inspect
        sig = inspect.signature(INJECT.build_prompt)
        self.assertIn("context_intent", sig.parameters)


if __name__ == "__main__":
    unittest.main()
