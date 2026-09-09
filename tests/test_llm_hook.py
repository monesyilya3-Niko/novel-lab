#!/usr/bin/env python3
"""
llm_hook.py 单元测试 — 纯标准库 unittest，零第三方依赖

覆盖（对应 ARCH_llm_hook_causality.md T01 验收标准）：
  1. 空候选：无候选 issue 时 hook 原样返回、不触发 LLM 调用
  2. 无模型：any_model_configured() 为 False → make_causality_hook() 返回 None（L1 降级）
  3. 解析漂移：LLM 返回纯文本/包裹文字/关键字 → 宽容解析正确判定
  4. 正常判定：正常 JSON 返回 → false_positive 被过滤 / real_contradiction 保留

另覆盖：
  - 保守原则：解析失败 / verdict 缺失 → 默认 real_contradiction（保留）
  - 候选筛选：仅 4 类易误报类型 + severity 截断
  - LLMError 降级：调用抛异常 → 返回原列表（L2 降级）
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    """从 scripts/ 动态加载模块（与 test_regressions 保持一致的加载方式）。"""
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


llm_hook = _load("llm_hook")
llm_client = _load("llm_client")


# llm_hook 内部通过 `import llm_client` 持有对 llm_client 模块的引用；
# 由于 _load 每次创建独立模块实例，测试里 monkeypatch 须直接改 llm_hook.llm_client，
# 才能让 hook 内部的调用命中桩函数。
def _patch_llm(configured, chat=None):
    """返回 (orig_any, orig_chat) 以便恢复；直接改 llm_hook.llm_client。"""
    orig_any = llm_hook.llm_client.any_model_configured
    orig_chat = llm_hook.llm_client.chat
    llm_hook.llm_client.any_model_configured = lambda: configured
    if chat is not None:
        llm_hook.llm_client.chat = chat
    return orig_any, orig_chat


def _restore_llm(orig_any, orig_chat):
    llm_hook.llm_client.any_model_configured = orig_any
    llm_hook.llm_client.chat = orig_chat


def _issue(typ="number_contradiction", severity="high", chapter=3,
           detail="实体「唐雨」的年龄在 Ch1 为 18，Ch3 变为 24，疑似矛盾"):
    return {"type": typ, "severity": severity, "chapter": chapter, "detail": detail}


class TestParseVerdict(unittest.TestCase):
    """判定解析（防格式漂移 + 保守原则）。"""

    def test_parse_normal_json_false_positive(self):
        text = json.dumps({"verdict": "false_positive", "reason": "闪回", "category": "flashback"})
        self.assertEqual(llm_hook._parse_verdict(text), "false_positive")

    def test_parse_normal_json_real_contradiction(self):
        text = json.dumps({"verdict": "real_contradiction", "reason": "确实矛盾", "category": "real"})
        self.assertEqual(llm_hook._parse_verdict(text), "real_contradiction")

    def test_parse_wrapped_text(self):
        """解析漂移：JSON 前后有包裹文字 → 提取首个 {...} 解析。"""
        text = '以下是判定结果：{"verdict": "false_positive", "reason": "倒叙", "category": "flashback"} 谢谢'
        self.assertEqual(llm_hook._parse_verdict(text), "false_positive")

    def test_parse_pure_text_keyword_false_positive(self):
        """解析漂移：纯文本命中「闪回」关键字 → false_positive。"""
        text = "这是一段闪回剧情，不是矛盾。"
        self.assertEqual(llm_hook._parse_verdict(text), "false_positive")

    def test_parse_pure_text_keyword_real(self):
        """纯文本命中「确实矛盾」关键字 → real_contradiction。"""
        text = "这里确实矛盾，是硬伤。"
        self.assertEqual(llm_hook._parse_verdict(text), "real_contradiction")

    def test_parse_garbage_defaults_real(self):
        """解析失败且无关键字 → 默认 real_contradiction（保守，不漏杀）。"""
        self.assertEqual(llm_hook._parse_verdict("。。。"), "real_contradiction")
        self.assertEqual(llm_hook._parse_verdict(""), "real_contradiction")
        self.assertEqual(llm_hook._parse_verdict(None), "real_contradiction")

    def test_parse_missing_verdict_defaults_real(self):
        """JSON 可解析但缺 verdict 字段 → 默认 real_contradiction。"""
        text = json.dumps({"reason": "无判定"})
        self.assertEqual(llm_hook._parse_verdict(text), "real_contradiction")

    def test_parse_boolean_alias(self):
        """等价布尔字段 is_contradiction 的兼容解析。"""
        self.assertEqual(
            llm_hook._parse_verdict(json.dumps({"is_contradiction": False})),
            "false_positive",
        )
        self.assertEqual(
            llm_hook._parse_verdict(json.dumps({"is_contradiction": True})),
            "real_contradiction",
        )


class TestSelectCandidates(unittest.TestCase):
    """候选筛选：仅 4 类 + severity 截断。"""

    def test_only_candidate_types_selected(self):
        issues = [
            _issue(typ="number_contradiction"),
            _issue(typ="timeline_contradiction"),
            _issue(typ="state_contradiction", severity="critical"),
            _issue(typ="appellation_contradiction", severity="medium"),
            _issue(typ="other_unknown_type"),  # 不应被选中
            _issue(typ="structure_incomplete", severity="medium"),  # 不应被选中
        ]
        idxs = llm_hook._select_candidates(issues)
        self.assertEqual(sorted(idxs), [0, 1, 2, 3])

    def test_severity_priority_truncation(self):
        """超限时按 severity 优先截断：critical 排在前面。"""
        issues = []
        # 3 个 low + 1 个 critical，设 max=2，应选中 critical 和 1 个 low
        issues.append(_issue(typ="number_contradiction", severity="low"))
        issues.append(_issue(typ="number_contradiction", severity="low"))
        issues.append(_issue(typ="number_contradiction", severity="critical"))
        idxs = llm_hook._select_candidates(issues, max_candidates=2)
        # critical 的原始下标是 2，应被优先选中
        self.assertIn(2, idxs)
        self.assertEqual(len(idxs), 2)

    def test_empty_returns_empty(self):
        self.assertEqual(llm_hook._select_candidates([]), [])


class TestMakeCausalityHook(unittest.TestCase):
    """L1 降级 + 构造行为。"""

    def test_no_model_returns_none(self):
        """无模型配置 → make_causality_hook 返回 None（不抛异常）。"""
        orig_any, orig_chat = _patch_llm(False)
        try:
            self.assertIsNone(llm_hook.make_causality_hook())
        finally:
            _restore_llm(orig_any, orig_chat)

    def test_any_model_configured_raises_returns_none(self):
        """any_model_configured 抛异常（配置损坏）→ 返回 None 而非崩溃。"""
        orig_any, orig_chat = _patch_llm(False)
        llm_hook.llm_client.any_model_configured = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            self.assertIsNone(llm_hook.make_causality_hook())
        finally:
            _restore_llm(orig_any, orig_chat)

    def test_with_model_returns_callable(self):
        """有模型配置 → 返回 callable，且挂载 llm_hook_meta。"""
        orig_any, orig_chat = _patch_llm(True)
        try:
            hook = llm_hook.make_causality_hook()
            self.assertTrue(callable(hook))
            self.assertIsInstance(getattr(hook, "llm_hook_meta", None), dict)
            self.assertTrue(hook.llm_hook_meta.get("enabled"))
        finally:
            _restore_llm(orig_any, orig_chat)


class TestJudgeCandidates(unittest.TestCase):
    """判定 + 过滤 + 降级（L2/L3）。"""

    def test_empty_candidates_returns_original(self):
        """空候选：无候选 issue 时原样返回、不触发 LLM。"""
        issues = [_issue(typ="structure_incomplete", severity="medium")]
        out = llm_hook._judge_candidates(list(issues), task="consistency_check")
        self.assertEqual(out, issues)

    def test_no_model_returns_original(self):
        """运行时无模型（L1 兜底）→ 原样返回。"""
        orig_any, orig_chat = _patch_llm(False)
        try:
            issues = [_issue()]
            self.assertEqual(llm_hook._judge_candidates(list(issues)), issues)
        finally:
            _restore_llm(orig_any, orig_chat)

    def test_llm_error_returns_original(self):
        """LLM 调用抛异常（L2 降级）→ 原样返回，不冒泡。"""
        orig_any, orig_chat = _patch_llm(True)
        llm_hook.llm_client.chat = lambda *a, **k: (_ for _ in ()).throw(llm_hook.llm_client.LLMError("no key"))
        try:
            issues = [_issue(), _issue(typ="timeline_contradiction", chapter=5)]
            self.assertEqual(llm_hook._judge_candidates(list(issues)), issues)
        finally:
            _restore_llm(orig_any, orig_chat)

    def test_normal_false_positive_filtered(self):
        """正常判定：false_positive 被过滤，real_contradiction 保留。"""
        orig_any, orig_chat = _patch_llm(True)

        def fake_chat(user, **kwargs):
            # 根据 prompt 中的 detail 决定返回
            if "唐雨" in user:
                return {"text": json.dumps({"verdict": "false_positive",
                                            "reason": "闪回", "category": "flashback"}),
                        "cost": 0.0001}
            return {"text": json.dumps({"verdict": "real_contradiction",
                                        "reason": "确实矛盾", "category": "real"}),
                    "cost": 0.0002}

        llm_hook.llm_client.chat = fake_chat
        try:
            issues = [
                _issue(detail="实体「唐雨」的年龄在 Ch1 为 18，Ch3 变为 24，疑似矛盾"),
                _issue(typ="timeline_contradiction", chapter=5,
                       detail="Ch2 相对时间推进，Ch5 回溯，时间线倒退"),
            ]
            out = llm_hook._judge_candidates(list(issues), stats={})
            # 唐雨（false_positive）被过滤，只剩 timeline 那条
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["type"], "timeline_contradiction")
        finally:
            _restore_llm(orig_any, orig_chat)

    def test_parse_failure_defaults_real(self):
        """解析漂移（纯文本垃圾）→ 默认 real_contradiction，保留全部。"""
        orig_any, orig_chat = _patch_llm(True)
        llm_hook.llm_client.chat = lambda *a, **k: {"text": "看不懂的乱码。。。", "cost": 0.0}
        try:
            issues = [_issue()]
            self.assertEqual(llm_hook._judge_candidates(list(issues)), issues)
        finally:
            _restore_llm(orig_any, orig_chat)

    def test_stats_recorded(self):
        """统计信息正确写入 stats（candidates/filtered/retained/undetermined/cost）。"""
        orig_any, orig_chat = _patch_llm(True)
        llm_hook.llm_client.chat = lambda *a, **k: {"text": json.dumps({"verdict": "false_positive"}),
                                                    "cost": 0.0005}
        try:
            issues = [_issue(), _issue(typ="timeline_contradiction", chapter=5)]
            stats = {}
            llm_hook._judge_candidates(list(issues), stats=stats)
            self.assertEqual(stats["candidates"], 2)
            self.assertEqual(stats["filtered"], 2)
            self.assertEqual(stats["retained"], 0)
            self.assertEqual(stats["undetermined"], 0)
            self.assertAlmostEqual(stats["cost"], 0.001, places=4)
        finally:
            _restore_llm(orig_any, orig_chat)


class TestBuildPrompt(unittest.TestCase):
    """prompt 构造（detail + 片段截断）。"""

    def test_build_user_prompt_contains_detail(self):
        issue = _issue(detail="实体「唐雨」的年龄矛盾")
        prompt = llm_hook._build_user_prompt(issue, {})
        self.assertIn("唐雨", prompt)
        self.assertIn("verdict", prompt)

    def test_snippet_truncated(self):
        texts = {3: "唐雨" + "字" * 2000}
        snippet = llm_hook._build_snippets(_issue(chapter=3), texts)
        self.assertLessEqual(len(snippet), llm_hook.SNIPPET_MAX_CHARS + 200)

    def test_build_user_prompt_with_real_texts_includes_snippet(self):
        """带真实原文：prompt 应包含「相关章节原文片段」及章节原文内容。"""
        texts = {3: "这里是第三章的原文，唐雨在回忆自己十八岁的往事。"}
        issue = _issue(chapter=3, detail="实体「唐雨」的年龄矛盾")
        prompt = llm_hook._build_user_prompt(issue, texts)
        self.assertIn("相关章节原文片段", prompt)
        self.assertIn("十八岁", prompt)  # 原文内容确实进入 prompt

    def test_build_user_prompt_empty_texts_no_snippet_header(self):
        """空 texts：prompt 不含「原文片段」标题，仅 detail + 判定指令。"""
        issue = _issue(chapter=3, detail="实体「唐雨」的年龄矛盾")
        prompt = llm_hook._build_user_prompt(issue, {})
        self.assertNotIn("相关章节原文片段", prompt)


class TestJudgeCandidatesWithTexts(unittest.TestCase):
    """「带 texts 的判定」——核心验收：hook 真正拿到章节原文并喂给 LLM。"""

    def _patch(self):
        return _patch_llm(True)

    def test_hook_with_texts_passes_real_snippet_to_llm(self):
        """构造带 texts 的 hook 后调用，LLM 收到的 user prompt 含章节原文。"""
        orig_any, orig_chat = self._patch()
        captured = {}

        def fake_chat(user, **kwargs):
            captured["user"] = user
            return {"text": json.dumps({"verdict": "false_positive",
                                        "reason": "闪回", "category": "flashback"}),
                    "cost": 0.0001}

        llm_hook.llm_client.chat = fake_chat
        try:
            texts = {3: "第三章原文：唐雨站在窗前，回忆起十八岁那年的夏天。"}
            hook = llm_hook.make_causality_hook(texts=texts)
            self.assertTrue(callable(hook))
            issues = [_issue(chapter=3, detail="实体「唐雨」的年龄矛盾")]
            out = hook(issues)
            # 原文片段确实进入了 LLM 的 user prompt
            self.assertIn("相关章节原文片段", captured["user"])
            self.assertIn("十八岁那年的夏天", captured["user"])
            # false_positive 被过滤
            self.assertEqual(out, [])
        finally:
            _restore_llm(orig_any, orig_chat)

    def test_hook_without_texts_gets_only_detail(self):
        """不传 texts：LLM 拿不到原文片段（对照验证空 texts 是缺陷）。"""
        orig_any, orig_chat = self._patch()
        captured = {}

        def fake_chat(user, **kwargs):
            captured["user"] = user
            return {"text": json.dumps({"verdict": "real_contradiction",
                                        "reason": "确实矛盾", "category": "real"}),
                    "cost": 0.0001}

        llm_hook.llm_client.chat = fake_chat
        try:
            hook = llm_hook.make_causality_hook()  # 不传 texts
            issues = [_issue(chapter=3, detail="实体「唐雨」的年龄矛盾")]
            hook(issues)
            self.assertNotIn("相关章节原文片段", captured["user"])
        finally:
            _restore_llm(orig_any, orig_chat)

    def test_make_causality_hook_with_texts_alias(self):
        """make_causality_hook_with_texts 与 make_causality_hook(texts=...) 等价。"""
        orig_any, orig_chat = self._patch()
        captured = {}

        def fake_chat(user, **kwargs):
            captured["user"] = user
            return {"text": json.dumps({"verdict": "real_contradiction"}), "cost": 0.0}

        llm_hook.llm_client.chat = fake_chat
        try:
            texts = {2: "第二章：林晚在回忆。"}
            hook = llm_hook.make_causality_hook_with_texts(texts=texts)
            self.assertTrue(callable(hook))
            hook([_issue(chapter=2, detail="实体「林晚」的状态矛盾")])
            self.assertIn("第二章：林晚在回忆。", captured["user"])
        finally:
            _restore_llm(orig_any, orig_chat)

    def test_undetermined_counts_parse_failure(self):
        """undetermined 统计：LLM 返回垃圾（无法解析）→ 计入 undetermined，非 0。"""
        orig_any, orig_chat = self._patch()
        llm_hook.llm_client.chat = lambda *a, **k: {"text": "看不懂的乱码。。。", "cost": 0.0}
        try:
            issues = [_issue(), _issue(typ="timeline_contradiction", chapter=5)]
            stats = {}
            out = llm_hook._judge_candidates(list(issues), stats=stats)
            # 解析失败 → 默认 real_contradiction 保守保留，全部保留
            self.assertEqual(len(out), 2)
            # undetermined 应为 2（两条都无法解析），不再恒为 0
            self.assertEqual(stats["undetermined"], 2)
            self.assertEqual(stats["candidates"], 2)
            self.assertEqual(stats["filtered"], 0)
            self.assertEqual(stats["retained"], 2)
        finally:
            _restore_llm(orig_any, orig_chat)

    def test_undetermined_counts_llm_exception(self):
        """undetermined 统计：LLM 抛异常 → 计入 undetermined。"""
        orig_any, orig_chat = self._patch()
        llm_hook.llm_client.chat = lambda *a, **k: (_ for _ in ()).throw(
            llm_hook.llm_client.LLMError("no key"))
        try:
            issues = [_issue()]
            stats = {}
            out = llm_hook._judge_candidates(list(issues), stats=stats)
            self.assertEqual(len(out), 1)  # 保守保留
            self.assertEqual(stats["undetermined"], 1)
            self.assertEqual(stats["filtered"], 0)
            self.assertEqual(stats["retained"], 1)
        finally:
            _restore_llm(orig_any, orig_chat)


if __name__ == "__main__":
    unittest.main(verbosity=2)
