#!/usr/bin/env python3
"""
对话占比题材适配（评估报告 P1-4）+ setting_check 检测行为回归。

P1-4：campus-redemption 语料 dialogue_ratio 实测
0.0737 / 0.1469 / 0.2562 / 0.3016，默认满分区 15%–40% 会惩罚慢热抒情声线。
题材包 commercial.quality_thresholds.dialogue_optimal 可覆盖满分区。

用法：python run_tests.py
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
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_load("metrics")
CC = _load("chapter_check")
SC = _load("setting_check")


def _pack_dialogue(min_v, max_v, pass_v=75, warn_v=60):
    return {"commercial": {"quality_thresholds": {
        "pass": pass_v, "warn": warn_v,
        "dialogue_optimal": {"min": min_v, "max": max_v},
    }}}


def _quoted_ratio_text(target: float, cn: int = 1000) -> str:
    dialogue = max(0, int(round(target * cn)))
    quoted = f"「{'乙' * dialogue}」"
    quoted_cn = sum(1 for ch in quoted if "一" <= ch <= "鿿")
    return quoted + "甲" * max(0, cn - quoted_cn)


class TestResolveDialogueBand(unittest.TestCase):
    def test_default_when_missing(self):
        self.assertEqual(CC.resolve_dialogue_band(None), CC.DEFAULT_DIALOGUE_BAND)
        self.assertEqual(CC.resolve_dialogue_band({}), CC.DEFAULT_DIALOGUE_BAND)
        self.assertEqual(
            CC.resolve_dialogue_band({"commercial": {"quality_thresholds": {"pass": 75, "warn": 60}}}),
            CC.DEFAULT_DIALOGUE_BAND)

    def test_valid_override(self):
        self.assertEqual(CC.resolve_dialogue_band(_pack_dialogue(0.07, 0.35)), (0.07, 0.35))

    def test_invalid_falls_back(self):
        for pack in (
            _pack_dialogue(0.35, 0.07),   # min>max
            _pack_dialogue(-0.1, 0.3),    # out of range
            _pack_dialogue(0.2, 0.2),     # equal
            _pack_dialogue("0.07", 0.35), # non-number
            _pack_dialogue(True, 0.35),   # bool
        ):
            self.assertEqual(CC.resolve_dialogue_band(pack), CC.DEFAULT_DIALOGUE_BAND, pack)

    def test_campus_redemption_pack_on_disk(self):
        pack_path = ROOT / "assets" / "campus-redemption-genre-pack.json"
        import json
        data = json.loads(pack_path.read_text(encoding="utf-8"))
        band = CC.resolve_dialogue_band(data)
        self.assertEqual(band, (0.07, 0.35))

    def test_commercial_nested_also_works(self):
        self.assertEqual(
            CC.resolve_dialogue_band(_pack_dialogue(0.07, 0.35)), (0.07, 0.35))
        # 顶层 quality_thresholds 轻量挂载（题材包未写满 commercial 时）
        top = {"quality_thresholds": {"dialogue_optimal": {"min": 0.08, "max": 0.3}}}
        self.assertEqual(CC.resolve_dialogue_band(top), (0.08, 0.3))


class TestCustomBandScoring(unittest.TestCase):
    def test_qingning_like_ratio_full_score_with_genre_band(self):
        """qingning dialogue_ratio=7.37%：题材带下应满分，默认带下不应满分。"""
        text = _quoted_ratio_text(0.0737)
        s_genre, d_genre = CC.check_dialogue_ratio(text, (0.07, 0.35))
        s_default, d_default = CC.check_dialogue_ratio(text, CC.DEFAULT_DIALOGUE_BAND)
        self.assertEqual(s_genre, 12, d_genre)
        self.assertLess(float(s_default), 12, d_default)

    def test_default_band_behavior_unchanged_without_pack(self):
        text = _quoted_ratio_text(0.25)
        self.assertEqual(CC.check_dialogue_ratio(text)[0], 12)
        self.assertEqual(CC.check_dialogue_ratio(text, None)[0], 12)

    def test_chapter_check_uses_genre_pack_band(self):
        # 7.4% 对白 + 疲劳词极少的长文：仅对话维度差异即可观察 verdict 不必钉死
        text = _quoted_ratio_text(0.074, cn=2000)
        r_genre = CC.chapter_check(text, _pack_dialogue(0.07, 0.35))
        r_default = CC.chapter_check(text)
        # details[1] 是对话占比行
        self.assertIn("✓", r_genre["details"][1], r_genre["details"][1])
        self.assertNotIn("✓", r_default["details"][1], r_default["details"][1])
        self.assertGreater(float(r_genre["score"]), float(r_default["score"]))


class TestSettingCheckDetection(unittest.TestCase):
    """P2-2：setting_check 检测行为本身（此前仅有 coverage 结构测试）。"""

    def test_world_rule_violation_detected(self):
        # 关键词必须与 _extract_banned_keywords 输出一致（「枪械」而非「枪声」）
        texts = {1: "他们走进教室。储物柜里藏着一把枪械，众人愣住。"}
        entities = {"world_rules": ["校园题材，禁止出现枪械"]}
        issues = SC.check_setting(texts, entities)
        hits = [i for i in issues if i["type"] == "world_rule_violation"]
        self.assertTrue(hits, issues)
        self.assertEqual(hits[0]["chapter"], 1)
        self.assertEqual(hits[0]["severity"], "high")
        self.assertIn("枪械", hits[0]["detail"])

    def test_world_rule_clean_text_no_issue(self):
        texts = {1: "他们走进教室，开始自习。"}
        entities = {"world_rules": ["校园题材，禁止出现枪械"]}
        issues = SC.check_setting(texts, entities)
        self.assertEqual([i for i in issues if i["type"] == "world_rule_violation"], [])

    def test_attribute_contradiction_detected(self):
        # 属性正则要求「名字(2-4字)+数字+岁」紧邻；「今年」会抢走名字位
        texts = {1: "唐雨20岁，背着书包走进考场。"}
        entities = {"characters": [{"name": "唐雨", "attributes": {"年龄": 18}}]}
        issues = SC.check_setting(texts, entities)
        hits = [i for i in issues if i["type"] == "attribute_contradiction"]
        self.assertTrue(hits, issues)
        self.assertIn("18", hits[0]["detail"])
        self.assertIn("20", hits[0]["detail"])

    def test_attribute_match_no_issue(self):
        texts = {1: "唐雨18岁，背着书包走进考场。"}
        entities = {"characters": [{"name": "唐雨", "attributes": {"年龄": 18}}]}
        issues = SC.check_setting(texts, entities)
        self.assertEqual([i for i in issues if i["type"] == "attribute_contradiction"], [])

    def test_alias_only_appearance_reported(self):
        texts = {1: "小雨站在走廊尽头，没有说话。"}
        entities = {"characters": [{"name": "唐雨", "aliases": ["小雨"]}]}
        issues = SC.check_setting(texts, entities)
        hits = [i for i in issues if i["type"] == "alias_consistency"]
        self.assertTrue(hits, issues)
        self.assertEqual(hits[0]["severity"], "medium")
        self.assertIn("小雨", hits[0]["detail"])

    def test_full_name_present_no_alias_issue(self):
        texts = {1: "唐雨（小雨）站在走廊尽头。"}
        entities = {"characters": [{"name": "唐雨", "aliases": ["小雨"]}]}
        issues = SC.check_setting(texts, entities)
        self.assertEqual([i for i in issues if i["type"] == "alias_consistency"], [])

    def test_empty_texts_and_missing_entities(self):
        self.assertEqual(SC.check_setting({}, {"world_rules": ["禁止枪械"]}), [])
        self.assertEqual(SC.check_setting({1: "有枪械出现"}, None), [])


class TestLlmDegradationMessage(unittest.TestCase):
    def test_insufficient_balance_mentions_features(self):
        llm = _load("llm_client")
        msg = llm.describe_llm_degradation("HTTP 403: INSUFFICIENT_BALANCE")
        self.assertIn("LLM 降级", msg)
        self.assertIn("额度", msg)
        self.assertIn("拆书分析", msg)
        self.assertIn("仍然可用", msg)
        self.assertIn("纯算法质检", msg)

    def test_unconfigured_mentions_add_command(self):
        llm = sys.modules.get("llm_client") or _load("llm_client")
        msg = llm.describe_llm_degradation("尚未配置任何模型。运行: python model_config.py add")
        self.assertIn("尚未配置", msg)
        self.assertIn("model_config.py add", msg)


if __name__ == "__main__":
    unittest.main()
