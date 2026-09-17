#!/usr/bin/env python3
"""检测覆盖率字段专项测试（优化第二轮 Task B / 报告 P2-1）

背景（问题实证）：
  缺 ``entities.json`` 时「称呼矛盾 / 状态矛盾」直接跳过；数值类检测读不到数据；
  声线卡无角色——输出统统是「0 问题」，**与「没检查」在输出里无法区分**。
  这是最容易误导使用者的设计缺陷：读者看到 PASS 会以为查过了。

本文件锁定 Task B 的加性契约：
  1. ``logic_check.logic_coverage(texts, entities)`` 返回「各检测项是否可评估」；
  2. ``setting_check.setting_coverage(texts, entities)`` 同上（三项）；
  3. ``book_quality.book_quality_check()`` 返回 dict **追加** ``coverage`` 键，
     既有 6 键一个不少（不修改既有键、不修改函数签名）；
  4. ``logic_check.main()`` / ``setting_check.main()``：``--json`` 追加 ``coverage``；
     非 JSON 输出时若 ``skipped`` 非空，追加打印一行 ``⚠ 未评估: …``。

fix round 1（审查裁决）：
  - **I1**：``style_consistency`` 曾与跨章三项一起按「仅 len(texts) >= 2 才执行」门控，但
    ``check_style_consistency`` 是**无条件调用**的，其情绪分支（``emotion_mode_drift``）
    逐章执行、单章即可产出问题 → 曾出现「issues 里有 emotion_mode_drift，coverage.skipped
    里却有 style_consistency」的自相矛盾（与本任务目标方向相反）。
    修正后的门控：``len(texts) >= 2`` **或** voice_card 提供非空
    ``emotion_handling.mode``；并新增 ``voice_card_loaded`` 字段。
  - **I2**：键集合断言由「子集」收紧为**精确集合**
    ``set(result.keys()) == BQ_RESULT_KEYS | {"coverage"}``（防意外新增键/调试键泄漏）。

终审修复波（2026-09-17）：
  - **M-1**：``check_style_consistency`` 原按真值直取 ``emotion_handling.mode``，而
    coverage 走 ``_voice_card_mode()``（非 str 归一为 ``""``）→ 畸形卡片（如 ``mode=5``）
    仍产生「coverage 判未评估、issues 却产出 emotion_mode_drift」的窄化矛盾。
    修复后两侧同口径，见 ``TestVoiceCardModeConsistency``。

测试全部使用内存 dict 或临时目录，不触碰真实 ``assets/``、``gui_state/``。

用法：
  python -m unittest discover -s tests -p "test_coverage_fields.py" -v
"""
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

# 用常规 import（而非 importlib 动态加载）：book_quality 在模块级 import chapter_loader，
# 动态加载会产生第二个模块实例，导致异常类身份不一致。
import book_quality  # noqa: E402
import logic_check  # noqa: E402
import qc  # noqa: E402
import setting_check  # noqa: E402

# --- 夹具 ---------------------------------------------------------------

TEXTS_2 = {
    1: "唐雨十八岁。她今天去了图书馆。",
    2: "唐雨十八岁。她明天要去学校。",
}

FULL_ENTITIES = {
    "characters": [
        {"name": "唐雨", "aliases": ["小雨"], "attributes": {"年龄": 18}},
        {"name": "江春屿", "aliases": ["春屿"], "attributes": {"年龄": 20}},
    ],
    "world_rules": ["校园题材，无超自然", "禁止出现枪械"],
}

# 有 characters 但缺 world_rules / attributes
PARTIAL_ENTITIES = {"characters": [{"name": "唐雨", "aliases": ["小雨"]}]}

# book_quality_check 既有返回键（Task B 不得删除其中任何一个）
BQ_RESULT_KEYS = {"total_chapters", "total_issues", "severity", "types", "verdict", "issues"}

# Task B 追加键后的**精确**返回键集合（fix round 1 / I2：收紧自「子集」断言）
BQ_RESULT_KEYS_WITH_COVERAGE = BQ_RESULT_KEYS | {"coverage"}

# coverage dict 的固定结构（fix round 1 / I1 新增 voice_card_loaded）
BQ_COVERAGE_KEYS = {"entities_loaded", "chapters", "checks", "skipped",
                    "skipped_reason", "voice_card_loaded"}

# logic_coverage / setting_coverage 的固定结构（各 6 键，brief 写明「结构固定」）
LOGIC_COVERAGE_KEYS = {"entities_loaded", "chapters", "checks",
                       "evaluable", "skipped", "skipped_reason"}
SETTING_COVERAGE_KEYS = {"entities_loaded", "chapters", "checks",
                         "evaluable", "skipped", "skipped_reason"}

SENT_A = "他缓缓推开了那扇沉重的木门。"
SENT_B = "她把那封信折好放进了口袋。"

# 单章即可触发 emotion_mode_drift 的正文（3 处直陈式情绪词，见 check_style_consistency）
DIRECT_EMOTION_TEXT = "她很愤怒。他很生气。她感到难过。"

# 声线卡：提供非空 emotion_handling.mode（非「直陈式」）
VOICE_CARD_WITH_MODE = {
    "emotion_handling": {"mode": "间接式"},
    "dialogue": {"character_voices": []},
}

# 声线卡存在但没有 mode（不得据此认为风格一致性可评估）
VOICE_CARD_WITHOUT_MODE = {
    "emotion_handling": {},
    "dialogue": {"character_voices": []},
}

# 畸形声线卡：mode 为**非字符串**（终审 M-1）——两侧口径必须一致地判为「无 mode」
VOICE_CARD_WITH_MALFORMED_MODE = {
    "emotion_handling": {"mode": 5},
    "dialogue": {"character_voices": []},
}

# mode 的全部取值形态：畸形（非 str）+ 既有合法字符串 + 空/缺失
MODE_VALUES = [
    ("int", 5),
    ("float", 3.14),
    ("bool_true", True),
    ("bool_false", False),
    ("list", []),
    ("dict", {}),
    ("null", None),
    ("empty_str", ""),
    ("normal_str", "间接式"),
    ("other_str", "体感"),
    ("direct_str", "直陈式"),
]


def _write_chapters(root: Path, mapping: dict):
    for num, text in mapping.items():
        (root / f"chapter-{num:03d}.txt").write_text(text, encoding="utf-8")


def _write_entities(root: Path, entities: dict):
    settings = root / "settings"
    settings.mkdir(parents=True, exist_ok=True)
    (settings / "entities.json").write_text(
        json.dumps(entities, ensure_ascii=False), encoding="utf-8")


def _write_voice_card(root: Path, voice_card: dict) -> str:
    """把声线卡写到临时目录，返回其路径（不触碰真实 assets/）。"""
    path = root / "voice-card.json"
    path.write_text(json.dumps(voice_card, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _run_cli(script: str, args: list) -> subprocess.CompletedProcess:
    """以子进程运行 scripts/<script>（纯标准库，无网络/无 LLM）。"""
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPTS / script)] + args,
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT), timeout=60)


# ---------------------------------------------------------------------------
# 1. logic_coverage
# ---------------------------------------------------------------------------

class TestLogicCoverageNoEntities(unittest.TestCase):
    """无 entities.json：称呼/状态必须显式标记为「未评估」。"""

    def setUp(self):
        self.cov = logic_check.logic_coverage(TEXTS_2, None)

    def test_entities_not_loaded(self):
        self.assertFalse(self.cov["entities_loaded"])

    def test_chapters_count(self):
        self.assertEqual(self.cov["chapters"], 2)

    def test_number_and_timeline_evaluable(self):
        self.assertTrue(self.cov["checks"]["number"])
        self.assertTrue(self.cov["checks"]["timeline"])

    def test_appellation_and_state_skipped(self):
        self.assertFalse(self.cov["checks"]["appellation"])
        self.assertFalse(self.cov["checks"]["state"])
        self.assertEqual(self.cov["skipped"], ["appellation", "state"],
                         "skipped 必须按固定顺序给出")
        self.assertEqual(self.cov["evaluable"], ["number", "timeline"])

    def test_skipped_reason_non_empty(self):
        self.assertNotEqual(self.cov["skipped_reason"], "")
        self.assertIn("entities.json", self.cov["skipped_reason"])

    def test_entities_without_characters_is_not_loaded(self):
        cov = logic_check.logic_coverage(TEXTS_2, {"world_rules": ["无超自然"]})
        self.assertFalse(cov["entities_loaded"])
        self.assertEqual(cov["skipped"], ["appellation", "state"])

    def test_empty_characters_list_is_not_loaded(self):
        cov = logic_check.logic_coverage(TEXTS_2, {"characters": []})
        self.assertFalse(cov["entities_loaded"])

    def test_coverage_key_set_exact(self):
        """结构固定为 6 键（防意外新增键/调试键泄漏）。"""
        self.assertEqual(set(self.cov.keys()), LOGIC_COVERAGE_KEYS,
                         f"实得: {sorted(self.cov.keys())}")


class TestLogicCoverageFullEntities(unittest.TestCase):
    """有 entities.json（含 characters）：四项全部可评估。"""

    def setUp(self):
        self.cov = logic_check.logic_coverage(TEXTS_2, FULL_ENTITIES)

    def test_all_evaluable(self):
        self.assertTrue(self.cov["entities_loaded"])
        self.assertEqual(self.cov["skipped"], [])
        self.assertEqual(self.cov["skipped_reason"], "")
        self.assertEqual(self.cov["evaluable"],
                         ["number", "timeline", "appellation", "state"])

    def test_checks_all_true(self):
        for key in ("number", "timeline", "appellation", "state"):
            with self.subTest(key=key):
                self.assertTrue(self.cov["checks"][key])


class TestLogicCoverageEmptyTexts(unittest.TestCase):
    """texts 为空：chapters=0，四项全 False。"""

    def test_empty_dict(self):
        for texts in ({}, None):
            with self.subTest(texts=texts):
                cov = logic_check.logic_coverage(texts, FULL_ENTITIES)
                self.assertEqual(cov["chapters"], 0)
                self.assertEqual(cov["evaluable"], [])
                self.assertEqual(cov["skipped"],
                                 ["number", "timeline", "appellation", "state"])
                self.assertFalse(any(cov["checks"].values()))
                self.assertEqual(cov["skipped_reason"], "无章节文本")

    def test_blank_text_values_do_not_count(self):
        cov = logic_check.logic_coverage({1: "", 2: ""}, FULL_ENTITIES)
        self.assertEqual(cov["chapters"], 0)
        self.assertFalse(any(cov["checks"].values()))


# ---------------------------------------------------------------------------
# 2. setting_coverage
# ---------------------------------------------------------------------------

class TestSettingCoverage(unittest.TestCase):
    """setting_coverage：world_rules / attributes / alias 三项。"""

    def test_full_entities_all_true(self):
        cov = setting_check.setting_coverage(TEXTS_2, FULL_ENTITIES)
        self.assertTrue(cov["entities_loaded"])
        self.assertEqual(cov["chapters"], 2)
        self.assertEqual(cov["checks"], {"world_rules": True, "attributes": True,
                                         "alias": True})
        self.assertEqual(cov["skipped"], [])
        self.assertEqual(cov["skipped_reason"], "")

    def test_no_entities_all_false(self):
        cov = setting_check.setting_coverage(TEXTS_2, None)
        self.assertFalse(cov["entities_loaded"])
        self.assertEqual(cov["skipped"], ["world_rules", "attributes", "alias"])
        self.assertFalse(any(cov["checks"].values()))
        self.assertNotEqual(cov["skipped_reason"], "")
        self.assertIn("world_rules", cov["skipped_reason"])

    def test_partial_entities_only_alias_evaluable(self):
        """有 characters + aliases，但无 world_rules / attributes。"""
        cov = setting_check.setting_coverage(TEXTS_2, PARTIAL_ENTITIES)
        self.assertTrue(cov["entities_loaded"], "characters 非空即视为已加载")
        self.assertEqual(cov["checks"], {"world_rules": False, "attributes": False,
                                         "alias": True})
        self.assertEqual(cov["evaluable"], ["alias"])
        self.assertEqual(cov["skipped"], ["world_rules", "attributes"])
        # 多项缺失时用「；」拼接
        self.assertIn("；", cov["skipped_reason"])
        self.assertIn("world_rules", cov["skipped_reason"])
        self.assertIn("attributes", cov["skipped_reason"])

    def test_characters_without_optional_fields_all_false(self):
        cov = setting_check.setting_coverage(TEXTS_2, {"characters": [{"name": "唐雨"}]})
        self.assertTrue(cov["entities_loaded"])
        self.assertEqual(cov["skipped"], ["world_rules", "attributes", "alias"])

    def test_empty_texts_all_false(self):
        cov = setting_check.setting_coverage({}, FULL_ENTITIES)
        self.assertEqual(cov["chapters"], 0)
        self.assertEqual(cov["skipped"], ["world_rules", "attributes", "alias"])
        self.assertEqual(cov["skipped_reason"], "无章节文本")

    def test_coverage_key_set_exact(self):
        """结构固定为 6 键（防意外新增键/调试键泄漏）。"""
        cov = setting_check.setting_coverage(TEXTS_2, FULL_ENTITIES)
        self.assertEqual(set(cov.keys()), SETTING_COVERAGE_KEYS,
                         f"实得: {sorted(cov.keys())}")


# ---------------------------------------------------------------------------
# 3. book_quality_check 的 coverage 键
# ---------------------------------------------------------------------------

class TestBookQualityCoverage(unittest.TestCase):
    """book_quality_check 追加 coverage，既有 6 键一个不少。"""

    def test_no_entities_coverage_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: SENT_A + SENT_B, 2: SENT_A + SENT_B})
            result = book_quality.book_quality_check(str(root))

            self.assertNotIn("error", result)
            self.assertIn("coverage", result, "必须追加 coverage 键")
            # fix round 1 / I2：精确集合断言（防意外新增键/调试键泄漏），
            # 不再用「子集」——子集断言漏掉任何多余键。
            self.assertEqual(set(result.keys()), BQ_RESULT_KEYS_WITH_COVERAGE,
                             f"返回键必须精确为既有 6 键 + coverage，实得: {sorted(result.keys())}")

            cov = result["coverage"]
            self.assertFalse(cov["entities_loaded"])
            self.assertEqual(cov["chapters"], 2)
            self.assertIn("fabrication_name", cov["skipped"])
            self.assertNotEqual(cov["skipped_reason"], "")

    def test_entities_loaded_makes_fabrication_evaluable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: SENT_A, 2: SENT_B})
            _write_entities(root, FULL_ENTITIES)
            result = book_quality.book_quality_check(str(root))

            cov = result["coverage"]
            self.assertTrue(cov["entities_loaded"])
            self.assertTrue(cov["checks"]["fabrication_name"])
            self.assertNotIn("fabrication_name", cov["skipped"])

    def test_single_chapter_cross_chapter_checks_false(self):
        """len(texts) < 2：跨章三项 + style_consistency 为 False 并说明原因。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: SENT_A})
            result = book_quality.book_quality_check(str(root))

            cov = result["coverage"]
            self.assertEqual(cov["chapters"], 1)
            for key in ("duplicate_chapters", "duplicate_paragraphs",
                        "duplicate_sentences", "style_consistency"):
                with self.subTest(key=key):
                    self.assertFalse(cov["checks"][key])
                    self.assertIn(key, cov["skipped"])
            self.assertIn("仅 1 章", cov["skipped_reason"])

    def test_two_chapters_cross_chapter_checks_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: SENT_A, 2: SENT_B})
            cov = book_quality.book_quality_check(str(root))["coverage"]
            for key in ("duplicate_chapters", "duplicate_paragraphs",
                        "duplicate_sentences", "style_consistency"):
                with self.subTest(key=key):
                    self.assertTrue(cov["checks"][key])

    def test_coverage_checks_fixed_key_set_and_order(self):
        """checks 九项固定；skipped 按 checks 定义顺序给出。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: SENT_A})
            cov = book_quality.book_quality_check(str(root))["coverage"]
            self.assertEqual(list(cov["checks"].keys()),
                             ["duplicate_chapters", "duplicate_paragraphs",
                              "duplicate_sentences", "intra_chapter_repeats",
                              "plot_continuity", "word_padding",
                              "fabrication_name", "ai_flavor",
                              "style_consistency"])
            self.assertEqual(cov["skipped"],
                             [k for k, v in cov["checks"].items() if not v])

    def test_coverage_dict_key_set_exact(self):
        """coverage 自身结构固定为 6 键（fix round 1 / I1 新增 voice_card_loaded）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: SENT_A})
            cov = book_quality.book_quality_check(str(root))["coverage"]
            self.assertEqual(set(cov.keys()), BQ_COVERAGE_KEYS,
                             f"coverage 结构必须精确，实得: {sorted(cov.keys())}")

    def test_error_dict_unchanged(self):
        """未找到章节时仍返回既有 error dict，不附加 coverage（既有契约不变）。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = book_quality.book_quality_check(str(Path(tmp)))
            self.assertEqual(result, {"error": "未找到章节文件"})


# ---------------------------------------------------------------------------
# 3b. style_consistency 的 voice_card 门控（fix round 1 / I1）
# ---------------------------------------------------------------------------

class TestStyleConsistencyVoiceCardGating(unittest.TestCase):
    """``style_consistency`` 可评估 ⇔ ``len(texts) >= 2`` 或 voice_card 提供非空
    ``emotion_handling.mode``（``check_style_consistency`` 的情绪分支单章即可产出问题）。"""

    def test_single_chapter_with_voice_card_mode_is_evaluable(self):
        """① 单章 + voice_card.mode：检测真的执行了，coverage 必须说 True。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: DIRECT_EMOTION_TEXT})
            voice = _write_voice_card(root, VOICE_CARD_WITH_MODE)
            result = book_quality.book_quality_check(str(root), voice)

            # 先证明检测确实执行（否则 coverage 的 True 毫无意义）
            self.assertIn("emotion_mode_drift", result["types"],
                          f"情绪分支应在单章执行，实得: {result['types']}")

            cov = result["coverage"]
            self.assertTrue(cov["voice_card_loaded"])
            self.assertTrue(cov["checks"]["style_consistency"],
                            "有 voice_card.mode 时单章也必须标记为可评估")
            self.assertNotIn("style_consistency", cov["skipped"])

    def test_single_chapter_without_voice_card_skips_style_consistency(self):
        """② 单章 + 无 voice_card：False、进 skipped、原因非空。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: DIRECT_EMOTION_TEXT})
            result = book_quality.book_quality_check(str(root))

            self.assertNotIn("emotion_mode_drift", result["types"])
            cov = result["coverage"]
            self.assertFalse(cov["voice_card_loaded"])
            self.assertFalse(cov["checks"]["style_consistency"])
            self.assertIn("style_consistency", cov["skipped"])
            self.assertNotEqual(cov["skipped_reason"], "")
            self.assertIn("voice_card", cov["skipped_reason"])

    def test_two_chapters_without_voice_card_is_evaluable(self):
        """③ 多章：无需 voice_card 也可评估（比喻密度分支跨章执行）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: SENT_A, 2: SENT_B})
            cov = book_quality.book_quality_check(str(root))["coverage"]
            self.assertTrue(cov["checks"]["style_consistency"])
            self.assertNotIn("style_consistency", cov["skipped"])
            self.assertFalse(cov["voice_card_loaded"])

    def test_voice_card_without_mode_is_not_loaded(self):
        """声线卡存在但无 emotion_handling.mode：不得据此认为可评估。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: DIRECT_EMOTION_TEXT})
            voice = _write_voice_card(root, VOICE_CARD_WITHOUT_MODE)
            result = book_quality.book_quality_check(str(root), voice)

            self.assertNotIn("emotion_mode_drift", result["types"])
            cov = result["coverage"]
            self.assertFalse(cov["voice_card_loaded"])
            self.assertFalse(cov["checks"]["style_consistency"])
            self.assertIn("style_consistency", cov["skipped"])

    def test_two_chapters_with_voice_card_without_mode_still_evaluable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: SENT_A, 2: SENT_B})
            voice = _write_voice_card(root, VOICE_CARD_WITHOUT_MODE)
            cov = book_quality.book_quality_check(str(root), voice)["coverage"]
            self.assertTrue(cov["checks"]["style_consistency"])
            self.assertFalse(cov["voice_card_loaded"])

    def test_no_contradiction_between_issues_and_skipped(self):
        """回归护栏：报告了 emotion_mode_drift 就不得同时说 style_consistency 未检测。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: DIRECT_EMOTION_TEXT})
            voice = _write_voice_card(root, VOICE_CARD_WITH_MODE)
            result = book_quality.book_quality_check(str(root), voice)
            if "emotion_mode_drift" in result["types"]:
                self.assertNotIn("style_consistency", result["coverage"]["skipped"])


# ---------------------------------------------------------------------------
# 3c. 畸形 mode 下 coverage 与 issues 的口径一致性（终审 M-1）
# ---------------------------------------------------------------------------

class TestVoiceCardModeConsistency(unittest.TestCase):
    """``mode`` 为非字符串时，coverage 与 issues 必须同口径。

    终审 M-1（修复前实证）：``_voice_card_mode()`` 对非 str 的 mode 归一为 ``""``，
    但 ``check_style_consistency`` 按真值直取 ``.get('mode', '')`` → ``mode=5`` 时
    一侧判「未评估」（skipped 含 style_consistency），另一侧却产出
    ``emotion_mode_drift`` —— 正是 Task B 要消除的自相矛盾，被这条窄路径绕过。
    修复：消费侧改用同一入口 ``_voice_card_mode()``。
    """

    # 不变式：产出了 drift 问题 ⇒ 必须同时声明该检测「已评估」。
    # 反向不成立（多章时无 drift 也属已评估），故只断言单向蕴含。
    def _assert_no_contradiction(self, result, ctx):
        drift = "emotion_mode_drift" in result["types"]
        cov = result["coverage"]
        if drift:
            self.assertTrue(cov["checks"]["style_consistency"],
                            f"{ctx}: 产出了 emotion_mode_drift，coverage 却判未评估")
            self.assertNotIn("style_consistency", cov["skipped"],
                             f"{ctx}: 产出了 emotion_mode_drift，却仍在 skipped 中")

    def test_malformed_mode_single_chapter_has_no_contradiction(self):
        """单章 + mode=5：不得再出现「判未评估却产出问题」。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: DIRECT_EMOTION_TEXT})
            voice = _write_voice_card(root, VOICE_CARD_WITH_MALFORMED_MODE)
            result = book_quality.book_quality_check(str(root), voice)

            self.assertNotIn("emotion_mode_drift", result["types"],
                             "非 str 的 mode 不得被当作有效期望模式（与 coverage 同口径）")
            cov = result["coverage"]
            self.assertFalse(cov["voice_card_loaded"])
            self.assertFalse(cov["checks"]["style_consistency"])
            self.assertIn("style_consistency", cov["skipped"])
            self.assertNotEqual(cov["skipped_reason"], "")
            self._assert_no_contradiction(result, "单章 + mode=5")

    def test_consistency_invariant_across_all_mode_values(self):
        """遍历 mode 全部形态：单章下「判未评估」与「产出问题」永不共存。"""
        for label, mode in MODE_VALUES:
            for card in ({"emotion_handling": {"mode": mode}}, {}):
                with self.subTest(mode=label, card=card):
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        _write_chapters(root, {1: DIRECT_EMOTION_TEXT})
                        voice = _write_voice_card(root, card)
                        result = book_quality.book_quality_check(str(root), voice)
                        self._assert_no_contradiction(result, f"{label}/{card}")

    def test_helper_and_consumer_agree_on_mode(self):
        """_voice_card_mode 是唯一口径：消费侧结果必须与它一致。"""
        for label, mode in MODE_VALUES:
            with self.subTest(mode=label):
                card = {"emotion_handling": {"mode": mode}}
                expected = book_quality._voice_card_mode(card)
                # 非 str 一律归一为 ""；str 原样返回
                if isinstance(mode, str):
                    self.assertEqual(expected, mode)
                else:
                    self.assertEqual(expected, "", f"{label} 应归一为空串")

    def test_helper_handles_non_dict_inputs(self):
        """畸形/空卡片不得让 helper 抛异常。"""
        for bad in (None, [], [1, 2], "x", 5, {"emotion_handling": None},
                    {"emotion_handling": []}, {"emotion_handling": {"mode": 5}}):
            with self.subTest(bad=bad):
                self.assertEqual(book_quality._voice_card_mode(bad), "")

    def test_existing_string_mode_behavior_unchanged(self):
        """回归：既有字符串 mode 的行为逐项不变（约束要求）。"""
        cases = [
            # (mode, 是否产出 drift, 是否可评估)
            ("间接式", True, True),
            ("体感", True, True),
            ("直陈式", False, True),   # 期望模式即直陈式 → 不算漂移，但仍属已评估
            ("", False, False),        # 空 mode → 无期望模式 → 未评估
        ]
        for mode, drift, evaluable in cases:
            with self.subTest(mode=mode):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _write_chapters(root, {1: DIRECT_EMOTION_TEXT})
                    voice = _write_voice_card(root, {"emotion_handling": {"mode": mode}})
                    result = book_quality.book_quality_check(str(root), voice)

                    self.assertEqual("emotion_mode_drift" in result["types"], drift,
                                     f"mode={mode!r} 的 drift 判定变了")
                    cov = result["coverage"]
                    self.assertEqual(cov["checks"]["style_consistency"], evaluable,
                                     f"mode={mode!r} 的可评估性变了")
                    self.assertEqual("style_consistency" in cov["skipped"], not evaluable)
                    self.assertEqual(cov["voice_card_loaded"], evaluable)
                    self._assert_no_contradiction(result, f"mode={mode!r}")


# ---------------------------------------------------------------------------
# 4. CLI 输出（main）
# ---------------------------------------------------------------------------

class TestCliCoverageOutput(unittest.TestCase):
    """--json 追加 coverage；非 JSON 输出追加「⚠ 未评估」一行。"""

    def _novel_dir(self, tmp, entities=None):
        root = Path(tmp)
        _write_chapters(root, {1: "唐雨今天去了图书馆，她十八岁。",
                               2: "唐雨明天要去学校，她十八岁。"})
        if entities is not None:
            _write_entities(root, entities)
        return root

    def test_logic_check_json_has_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._novel_dir(tmp)
            proc = _run_cli("logic_check.py", [str(root), "--json"])
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["total_chapters"], 2)
            self.assertIn("issues", payload, "既有键不得缺失")
            cov = payload["coverage"]
            self.assertFalse(cov["entities_loaded"])
            self.assertEqual(cov["skipped"], ["appellation", "state"])

    def test_logic_check_text_output_warns_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._novel_dir(tmp)
            proc = _run_cli("logic_check.py", [str(root)])
            self.assertIn("⚠ 未评估", proc.stdout)
            self.assertIn("appellation", proc.stdout)
            self.assertIn("state", proc.stdout)

    def test_logic_check_text_output_silent_when_all_evaluable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._novel_dir(tmp, FULL_ENTITIES)
            proc = _run_cli("logic_check.py", [str(root)])
            self.assertNotIn("⚠ 未评估", proc.stdout)

    def test_setting_check_json_has_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._novel_dir(tmp, PARTIAL_ENTITIES)
            proc = _run_cli("setting_check.py", [str(root), "--json"])
            payload = json.loads(proc.stdout)
            self.assertIn("issues", payload, "既有键不得缺失")
            cov = payload["coverage"]
            self.assertEqual(cov["skipped"], ["world_rules", "attributes"])

    def test_setting_check_text_output_warns_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._novel_dir(tmp)
            proc = _run_cli("setting_check.py", [str(root)])
            self.assertIn("⚠ 未评估", proc.stdout)
            self.assertIn("world_rules", proc.stdout)

    def test_setting_check_text_output_silent_when_all_evaluable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._novel_dir(tmp, FULL_ENTITIES)
            proc = _run_cli("setting_check.py", [str(root)])
            self.assertNotIn("⚠ 未评估", proc.stdout)


# ---------------------------------------------------------------------------
# 5. qc.run_qc 的 meta.coverage（brief 第 5 项，纯加性）
# ---------------------------------------------------------------------------

class TestQcMetaCoverage(unittest.TestCase):
    """qc 报告 meta 汇总 D2（logic）/ D5（setting）覆盖率，不触及评分。"""

    def test_meta_coverage_without_entities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: SENT_A, 2: SENT_B})
            report = qc.run_qc(str(root))

            cov = report.meta["coverage"]
            self.assertFalse(cov["logic"]["entities_loaded"])
            self.assertEqual(cov["logic"]["skipped"], ["appellation", "state"])
            self.assertEqual(cov["setting"]["skipped"],
                             ["world_rules", "attributes", "alias"])
            # 既有 meta 键不受影响
            self.assertIn("total_chapters", report.meta)
            self.assertIn("severity_count", report.meta)
            self.assertIn(report.verdict, {"PASS", "WARN", "FAIL"})

    def test_meta_coverage_with_entities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_chapters(root, {1: SENT_A, 2: SENT_B})
            _write_entities(root, FULL_ENTITIES)
            cov = qc.run_qc(str(root)).meta["coverage"]
            self.assertTrue(cov["logic"]["entities_loaded"])
            self.assertEqual(cov["logic"]["skipped"], [])
            self.assertEqual(cov["setting"]["skipped"], [])


# ---------------------------------------------------------------------------
# 6. 加性契约：既有签名不变
# ---------------------------------------------------------------------------

class TestExistingSignaturesUnchanged(unittest.TestCase):
    """Task B 只新增函数与新增键，既有函数签名一字不改。"""

    def test_check_logic_signature(self):
        params = list(inspect.signature(logic_check.check_logic).parameters.items())
        self.assertEqual([p[0] for p in params], ["texts", "entities", "llm_hook"])
        self.assertIsNone(params[1][1].default)
        self.assertIsNone(params[2][1].default)

    def test_check_setting_signature(self):
        params = list(inspect.signature(setting_check.check_setting).parameters.items())
        self.assertEqual([p[0] for p in params], ["texts", "entities"])
        self.assertIsNone(params[1][1].default)

    def test_book_quality_check_signature(self):
        params = list(inspect.signature(book_quality.book_quality_check).parameters.items())
        self.assertEqual([p[0] for p in params],
                         ["chapter_dir", "voice_card_path", "prev_chapters_dir"])
        self.assertIsNone(params[1][1].default)
        self.assertIsNone(params[2][1].default)

    def test_coverage_functions_are_additive(self):
        """coverage 函数是新函数，签名与 brief 一致。"""
        self.assertEqual(list(inspect.signature(logic_check.logic_coverage).parameters),
                         ["texts", "entities"])
        self.assertEqual(list(inspect.signature(setting_check.setting_coverage).parameters),
                         ["texts", "entities"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
