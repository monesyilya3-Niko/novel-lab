#!/usr/bin/env python3
"""
logic_check 数字/时间线检测 + qc 空声线卡兜底 测试

背景（2026-09-16 修复）：
  在《暮冬念春》（157 章中文长篇）上跑 `novel qc` 得到 75.8 分 / FAIL，
  逐条取证后发现 FAIL 完全由两处工具缺陷造成，与作品质量无关：

  1. 时间线检测把「昨天/今天/明天」当作绝对位置，并以**全书不回落的最高水位线**
     逐章比较，导致任何不含前瞻时间词的章节都被判「时间线倒退」——33 条误报
     （占 21% 章节）。且不区分对白与比喻。
  2. 数值类矛盾检测的正则只认阿拉伯数字，而中文小说几乎全用汉字数字，
     该检测实际零覆盖（「0 问题」并非一致性的证据）。
  3. `qc` 的 `_dim_character_arc` / `_dim_craft` 在声线卡存在但
     `character_voices` 为空列表时，直接把维度打到 0 分，而卡片为 None 时
     却按「无法评估」记 100——两条分支不一致。

本文件为上述三处建立回归护栏。

用法：
  python run_tests.py
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
    """按文件名从 scripts/ 动态加载模块（模块名与文件名一致）。"""
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


logic_check = _load("logic_check")
qc = _load("qc")


class TestCnToInt(unittest.TestCase):
    """汉字数字解析。"""

    def test_arabic_passthrough(self):
        self.assertEqual(logic_check._cn_to_int("18"), 18)

    def test_single_and_compound(self):
        for token, expect in [("三", 3), ("十", 10), ("十八", 18), ("二十", 20),
                              ("二十三", 23), ("一百二十", 120), ("两", 2)]:
            with self.subTest(token=token):
                self.assertEqual(logic_check._cn_to_int(token), expect)

    def test_invalid_returns_none(self):
        for token in ["", "abc", "岁", "十8"]:
            with self.subTest(token=token):
                self.assertIsNone(logic_check._cn_to_int(token))


class TestLooksLikeName(unittest.TestCase):
    """实体名候选粗筛。"""

    def test_real_names_pass(self):
        for name in ["江春屿", "温霜禾", "大姨", "林悦", "许知夏"]:
            with self.subTest(name=name):
                self.assertTrue(logic_check._looks_like_name(name))

    def test_function_fragments_rejected(self):
        # 汉字数字放开后，这些片段最容易冒充实体名
        for name in ["已经不是", "我那时候", "温霜禾第", "你还不到", "一个刚满", "有点心疼"]:
            with self.subTest(name=name):
                self.assertFalse(logic_check._looks_like_name(name))

    def test_length_bounds(self):
        self.assertFalse(logic_check._looks_like_name("江"))
        self.assertFalse(logic_check._looks_like_name("江春屿和林"))


class TestNumberContradiction(unittest.TestCase):
    """数字/年龄矛盾：汉字数字必须能读到数据。"""

    def test_chinese_numeral_age_detected(self):
        texts = {1: "江春屿十八岁。", 3: "江春屿二十四岁。"}
        issues = logic_check._check_number_contradictions(texts)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["type"], "number_contradiction")
        self.assertIn("18", issues[0]["detail"])
        self.assertIn("24", issues[0]["detail"])

    def test_arabic_and_chinese_unified(self):
        """「十八」与「18」是同一个取值，不得互判矛盾。"""
        texts = {1: "江春屿十八岁。", 3: "江春屿18岁。"}
        self.assertEqual(logic_check._check_number_contradictions(texts), [])

    def test_consistent_age_no_issue(self):
        texts = {85: "江春屿二十岁。", 95: "江春屿，二十岁。", 112: "刚满二十岁的人。"}
        self.assertEqual(logic_check._check_number_contradictions(texts), [])

    def test_non_name_fragment_not_flagged(self):
        """「她已经不是十七八岁」中的片段不得被当成实体。"""
        texts = {1: "她已经不是十七八岁了。", 3: "她已经不是二十岁了。"}
        self.assertEqual(logic_check._check_number_contradictions(texts), [])


class TestTimelineFalsePositives(unittest.TestCase):
    """时间线检测：旧实现的核心误报模式必须全部消失。"""

    def test_plan_word_is_not_anchor(self):
        """「她打算明天再确认一次」是计划，不是叙事推进。"""
        texts = {6: "这个秘密，她打算明天再确认一次。",
                 7: "大姨问她今天怎么回来得早。"}
        self.assertEqual(logic_check._check_timeline_contradictions(texts), [])

    def test_simile_is_not_anchor(self):
        """「好像昨天才见过」是比喻。"""
        texts = {1: "她记得很清楚，清楚到好像昨天才见过。",
                 2: "她今天去了图书馆。"}
        self.assertEqual(logic_check._check_timeline_contradictions(texts), [])

    def test_dialogue_is_not_anchor(self):
        """引号内的时间词不作锚点。"""
        texts = {1: "“大姨昨天寄了酱菜过来。”",
                 2: "“今天复诊怎么样？”"}
        self.assertEqual(logic_check._check_timeline_contradictions(texts), [])

    def test_mid_sentence_next_day_is_idiom(self):
        """「哭完以后，第二天仍要起床」是惯用语，不作锚点。"""
        texts = {1: "可哭完以后，第二天仍要起床。"}
        self.assertEqual(logic_check._check_timeline_contradictions(texts), [])

    def test_no_running_high_water_mark(self):
        """旧实现：先出现「明天」，后续只含「今天」的章节被判倒退。"""
        texts = {1: "明天会怎样，她不知道。",
                 2: "今天，她照常去上课。",
                 3: "今天，她又去了一趟图书馆。"}
        self.assertEqual(logic_check._check_timeline_contradictions(texts), [])


class TestTimelineTruePositives(unittest.TestCase):
    """时间线检测：同场景内的日序编号错误必须报出。"""

    def test_non_monotonic_day_ordinal_flagged(self):
        filler = "她低头写字。" * 60  # 约 360 字，仍在同场景窗口内
        texts = {20: f"第三天，她发现桌洞里多一个纸袋。\n\n{filler}\n\n第二天，桌洞里又有早餐。"}
        issues = logic_check._check_timeline_contradictions(texts)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["type"], "timeline_contradiction")
        self.assertEqual(issues[0]["chapter"], 20)

    def test_cross_scene_regression_ignored(self):
        """相距超过同场景窗口的日序标签互不约束（跨场景不是矛盾）。"""
        filler = "她低头写字。" * 400  # 约 2400 字，超出窗口
        texts = {3: f"第三天中午，她因为值日留在教室。\n\n{filler}\n\n第二天早读前，她到教室。"}
        self.assertEqual(logic_check._check_timeline_contradictions(texts), [])

    def test_monotonic_sequence_clean(self):
        texts = {61: "第二天也没有。第三天，仍然没有。第四天清晨，她醒得很早。"}
        self.assertEqual(logic_check._check_timeline_contradictions(texts), [])

    def test_day_one_resets_enumeration(self):
        """「第一天」开启新枚举，其后不得与前面的日序比较。"""
        filler = "她低头写字。" * 40
        texts = {1: f"第三天，茶几又碎。\n\n{filler}\n\n第一天，她坐在最后一排。"}
        self.assertEqual(logic_check._check_timeline_contradictions(texts), [])


class TestQcEmptyVoiceCard(unittest.TestCase):
    """qc：声线卡无角色时应按「无法评估」处理，而不是打到 0 分。"""

    @staticmethod
    def _card(voices=None):
        return {
            "dialogue": {"character_voices": voices if voices is not None else []},
            "emotion_handling": {},
            "narration": {},
            "banned_words": [],
            "imagery": {},
        }

    def test_character_arc_skipped_when_no_voices(self):
        dim = qc._dim_character_arc({1: "温霜禾看着他。"}, self._card())
        self.assertEqual(dim.score, 100.0)
        self.assertIn("skipped", dim.raw)
        self.assertEqual(dim.issues, [])

    def test_craft_renormalized_when_no_voices(self):
        dim = qc._dim_craft({1: "温霜禾看着他。"}, self._card())
        dims = dim.raw["dims"]
        self.assertIn("renormalized", dims)
        evaluable = dims["emotion"] + dims["narration"] + dims["banned"] + dims["imagery"]
        self.assertEqual(dim.score, round(evaluable / 65 * 100, 1))

    def test_craft_not_renormalized_with_voices(self):
        card = self._card([{"name": "温霜禾", "speech_signature": {"verbal_tics": ["嗯"]}}])
        dim = qc._dim_craft({1: "温霜禾说：“嗯。”"}, card)
        self.assertNotIn("renormalized", dim.raw["dims"])

    def test_character_arc_scored_with_voices(self):
        card = self._card([{"name": "温霜禾", "speech_signature": {"verbal_tics": ["嗯"]}}])
        dim = qc._dim_character_arc({1: "温霜禾说：“嗯。”"}, card)
        self.assertNotIn("skipped", dim.raw)

    def test_no_card_still_skipped(self):
        self.assertEqual(qc._dim_character_arc({1: "文本"}, None).score, 100.0)
        self.assertEqual(qc._dim_craft({1: "文本"}, None).score, 100.0)


if __name__ == "__main__":
    unittest.main()
