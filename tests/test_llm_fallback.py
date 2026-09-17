#!/usr/bin/env python3
"""
llm_client 备用模型路由（fallback）单元测试 — 纯标准库 unittest，零第三方依赖

背景（Task 3.4）：
  `llm_client.py` 模块 docstring 第 4 条写着「失败可回退到备用模型」，
  但代码里从未实现——`chat()` 只对同一模型重试 `retries` 次，失败即抛 `LLMError`。
  本文件守住新增的 `resolve_fallback_chain` / `chat(allow_fallback=...)` /
  `_is_retryable_error` 与 `model_config.py fallback` 子命令。

铁律：全部用 monkeypatch 打桩协议 handler，**不联网**；不改 config/models.json。

用法：
  python run_tests.py
  python -m unittest tests.test_llm_fallback -v
"""
import collections
import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    """按文件名从 scripts/ 动态加载模块（与其它测试保持一致的加载方式）。"""
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


llm_client = _load("llm_client")
model_config = _load("model_config")


def _cfg(specs, default_role=None, routes=None):
    """构造模型配置。

    specs: [(model_id, fallback)]，fallback 为 None / str / list。
    """
    models = {}
    for mid, fb in specs:
        m = {
            "protocol": "openai",
            "base_url": f"http://{mid}/v1",
            "model_name": f"{mid}-model",
            "api_key_env": "",
            "timeout": 5,
        }
        if fb is not None:
            m["fallback"] = fb
        models[mid] = m
    first = next(iter(models), None)
    return {
        "version": 1,
        "models": models,
        "roles": {"default": default_role or first},
        "routes": routes or dict(llm_client.DEFAULT_ROUTES),
    }


def _mid_of(model: dict) -> str:
    """从打桩用的 base_url 反推模型 id（handler 只拿得到 model dict）。"""
    return model["base_url"].split("//", 1)[1].split("/", 1)[0]


class _FakeHandler:
    """协议 handler 打桩：按模型 id 决定成功（返回文本）或抛异常。"""

    def __init__(self, behavior: dict):
        self.behavior = behavior
        self.calls = collections.Counter()

    def __call__(self, model, api_key, system, user, max_tokens, temperature):
        mid = _mid_of(model)
        self.calls[mid] += 1
        spec = self.behavior[mid]
        if isinstance(spec, BaseException):
            raise spec
        if isinstance(spec, type) and issubclass(spec, BaseException):
            raise spec("stub failure")
        return {"text": spec, "prompt_tokens": 10, "completion_tokens": 5}


class _FallbackTestBase(unittest.TestCase):
    """统一打桩：load_models / resolve_api_key / PROTOCOL_HANDLERS / time.sleep。"""

    def setUp(self):
        self._orig = {
            "load_models": llm_client.load_models,
            "resolve_api_key": llm_client.resolve_api_key,
            "handlers": dict(llm_client.PROTOCOL_HANDLERS),
        }
        llm_client.resolve_api_key = lambda mid, model: "test-key"
        self._sleep = mock.patch("time.sleep")
        self._sleep.start()

    def tearDown(self):
        self._sleep.stop()
        llm_client.load_models = self._orig["load_models"]
        llm_client.resolve_api_key = self._orig["resolve_api_key"]
        llm_client.PROTOCOL_HANDLERS = self._orig["handlers"]

    def _install(self, cfg, behavior):
        handler = _FakeHandler(behavior)
        llm_client.load_models = lambda: cfg
        llm_client.PROTOCOL_HANDLERS = {"openai": handler}
        return handler


class TestIsRetryableError(unittest.TestCase):
    """失败原因分类：不可重试错误不应浪费重试次数。"""

    def test_http_401_not_retryable(self):
        self.assertFalse(llm_client._is_retryable_error(
            llm_client.LLMError("HTTP 401: unauthorized")))

    def test_http_403_not_retryable(self):
        self.assertFalse(llm_client._is_retryable_error(
            llm_client.LLMError('HTTP 403: {"error": {"code": "INSUFFICIENT_BALANCE"}}')))

    def test_insufficient_balance_not_retryable(self):
        self.assertFalse(llm_client._is_retryable_error(
            llm_client.LLMError("HTTP 402: INSUFFICIENT_BALANCE")))
        self.assertFalse(llm_client._is_retryable_error(
            llm_client.LLMError("insufficient balance")))

    def test_other_llm_error_retryable(self):
        self.assertTrue(llm_client._is_retryable_error(llm_client.LLMError("HTTP 500: boom")))
        self.assertTrue(llm_client._is_retryable_error(llm_client.LLMError("响应格式异常: {}")))

    def test_network_exception_retryable(self):
        self.assertTrue(llm_client._is_retryable_error(ConnectionResetError("reset")))
        self.assertTrue(llm_client._is_retryable_error(TimeoutError("timeout")))


class TestResolveFallbackChain(_FallbackTestBase):
    """候选链构造：去重 / 排除主模型 / 过滤不存在的 id / 两种 fallback 形态。"""

    def test_primary_is_first_and_fallback_list_order_kept(self):
        cfg = _cfg([("a", ["b", "ghost", "b", "a", "c"]), ("b", None), ("c", None), ("d", None)],
                   default_role="c")
        self._install(cfg, {"a": "A"})
        self.assertEqual(llm_client.resolve_fallback_chain(model_id="a"),
                         ["a", "b", "c", "d"])

    def test_fallback_as_string(self):
        cfg = _cfg([("a", "b"), ("b", None), ("c", None)])
        self._install(cfg, {"a": "A"})
        self.assertEqual(llm_client.resolve_fallback_chain(model_id="a"), ["a", "b", "c"])

    def test_unknown_ids_filtered_out(self):
        cfg = _cfg([("a", ["ghost", "b"]), ("b", None)])
        self._install(cfg, {"a": "A"})
        self.assertEqual(llm_client.resolve_fallback_chain(model_id="a"), ["a", "b"])

    def test_primary_excluded_from_chain(self):
        cfg = _cfg([("a", ["b", "a"]), ("b", ["a"])], default_role="a")
        self._install(cfg, {"a": "A"})
        chain = llm_client.resolve_fallback_chain(model_id="a")
        self.assertEqual(chain.count("a"), 1)
        self.assertEqual(chain, ["a", "b"])

    def test_default_role_used_before_remaining_models(self):
        cfg = _cfg([("a", None), ("b", None), ("c", None)], default_role="c")
        self._install(cfg, {"a": "A"})
        self.assertEqual(llm_client.resolve_fallback_chain(model_id="a"), ["a", "c", "b"])

    def test_task_routing_picks_primary(self):
        cfg = _cfg([("cheap-m", None), ("strong-m", None)])
        cfg["roles"] = {"cheap": "cheap-m", "strong": "strong-m", "default": "strong-m"}
        self._install(cfg, {"cheap-m": "C"})
        chain = llm_client.resolve_fallback_chain(task="pass1_structure")
        self.assertEqual(chain[0], "cheap-m")
        self.assertIn("strong-m", chain)

    def test_primary_resolution_failure_returns_other_models(self):
        """主模型解析失败（不存在的 id）→ 返回其余已配置模型，不抛错。"""
        cfg = _cfg([("a", None), ("b", None)])
        self._install(cfg, {"a": "A"})
        self.assertEqual(llm_client.resolve_fallback_chain(model_id="ghost"), ["a", "b"])

    def test_empty_config_returns_empty_chain(self):
        cfg = _cfg([])
        self._install(cfg, {})
        self.assertEqual(llm_client.resolve_fallback_chain(model_id="a"), [])

    def test_single_model_chain_length_one(self):
        cfg = _cfg([("only", None)])
        self._install(cfg, {"only": "OK"})
        self.assertEqual(llm_client.resolve_fallback_chain(model_id="only"), ["only"])


class TestChatFallback(_FallbackTestBase):
    """chat() 的备用模型路由行为。"""

    def test_403_switches_candidate_without_retry(self):
        """不可重试错误（403 / INSUFFICIENT_BALANCE）→ 主模型只调用 1 次即换候选。"""
        cfg = _cfg([("primary", ["backup"]), ("backup", None)])
        h = self._install(cfg, {
            "primary": llm_client.LLMError(
                'HTTP 403: {"error": {"code": "INSUFFICIENT_BALANCE", "message": "余额不足"}}'),
            "backup": "备用模型回复",
        })
        r = llm_client.chat("你好", model_id="primary", retries=2)
        self.assertEqual(r["text"], "备用模型回复")
        self.assertEqual(r["model_id"], "backup")
        self.assertEqual(h.calls["primary"], 1)
        self.assertEqual(h.calls["backup"], 1)

    def test_network_error_retried_before_switching(self):
        """网络类异常 → 先重试 retries 次，再换候选。"""
        cfg = _cfg([("primary", ["backup"]), ("backup", None)])
        h = self._install(cfg, {
            "primary": ConnectionResetError("connection reset by peer"),
            "backup": "备用模型回复",
        })
        r = llm_client.chat("你好", model_id="primary", retries=2)
        self.assertEqual(r["model_id"], "backup")
        self.assertEqual(h.calls["primary"], 3)  # retries + 1
        self.assertEqual(h.calls["backup"], 1)

    def test_all_candidates_fail_lists_each_reason(self):
        """全链路失败 → 消息逐个列出候选原因。"""
        cfg = _cfg([("a", ["b", "c"]), ("b", None), ("c", None)])
        self._install(cfg, {
            "a": llm_client.LLMError('HTTP 403: {"code": "INSUFFICIENT_BALANCE"}'),
            "b": llm_client.LLMError("HTTP 500: server error"),
            "c": ConnectionResetError("connection reset by peer"),
        })
        with self.assertRaises(llm_client.LLMError) as ctx:
            llm_client.chat("你好", model_id="a", retries=1)
        msg = str(ctx.exception)
        for mid in ("a", "b", "c"):
            self.assertIn(f"候选 {mid}:", msg)
        self.assertIn("INSUFFICIENT_BALANCE", msg)
        self.assertIn("HTTP 500: server error", msg)
        self.assertIn("connection reset by peer", msg)

    def test_single_candidate_failure_mentions_no_fallback(self):
        """链长为 1 → 消息含「无可用备用模型」。"""
        cfg = _cfg([("only", None)])
        self._install(cfg, {"only": llm_client.LLMError("HTTP 500: boom")})
        with self.assertRaises(llm_client.LLMError) as ctx:
            llm_client.chat("你好", model_id="only", retries=1)
        msg = str(ctx.exception)
        self.assertIn("无可用备用模型", msg)
        self.assertIn("HTTP 500: boom", msg)

    def test_allow_fallback_false_does_not_try_others(self):
        """allow_fallback=False → 只对主模型重试，绝不尝试备用模型。"""
        cfg = _cfg([("primary", ["backup"]), ("backup", None)])
        h = self._install(cfg, {
            "primary": ConnectionResetError("connection reset by peer"),
            "backup": "备用模型回复",
        })
        with self.assertRaises(llm_client.LLMError) as ctx:
            llm_client.chat("你好", model_id="primary", retries=2, allow_fallback=False)
        self.assertEqual(h.calls["primary"], 3)
        self.assertEqual(h.calls["backup"], 0)
        msg = str(ctx.exception)
        self.assertIn("模型 'primary' 调用失败（重试 2 次）", msg)
        self.assertIn("connection reset by peer", msg)
        self.assertNotIn("无可用备用模型", msg)

    def test_allow_fallback_false_message_matches_legacy_on_http_error(self):
        """allow_fallback=False 时 403 的异常消息与改造前格式一致。"""
        cfg = _cfg([("primary", ["backup"]), ("backup", None)])
        h = self._install(cfg, {
            "primary": llm_client.LLMError("HTTP 403: forbidden"),
            "backup": "备用模型回复",
        })
        with self.assertRaises(llm_client.LLMError) as ctx:
            llm_client.chat("你好", model_id="primary", retries=0, allow_fallback=False)
        self.assertEqual(str(ctx.exception),
                         "模型 'primary' 调用失败（重试 0 次）: HTTP 403: forbidden")
        self.assertEqual(h.calls["backup"], 0)

    def test_allow_fallback_false_keeps_legacy_retry_semantics(self):
        """allow_fallback=False 时连不可重试错误也照旧重试 retries 次（改造前语义）。"""
        cfg = _cfg([("primary", ["backup"]), ("backup", None)])
        h = self._install(cfg, {
            "primary": llm_client.LLMError("HTTP 403: forbidden"),
            "backup": "备用模型回复",
        })
        with self.assertRaises(llm_client.LLMError):
            llm_client.chat("你好", model_id="primary", retries=2, allow_fallback=False)
        self.assertEqual(h.calls["primary"], 3)
        self.assertEqual(h.calls["backup"], 0)

    def test_default_is_backward_compatible_on_success(self):
        """默认 allow_fallback=True 不影响成功路径，且不调用备用模型。"""
        cfg = _cfg([("primary", ["backup"]), ("backup", None)])
        h = self._install(cfg, {"primary": "主模型回复", "backup": "备用模型回复"})
        r = llm_client.chat("你好", model_id="primary")
        self.assertEqual(r["model_id"], "primary")
        self.assertEqual(r["text"], "主模型回复")
        self.assertEqual(h.calls["primary"], 1)
        self.assertEqual(h.calls["backup"], 0)

    def test_fallback_result_carries_model_metadata(self):
        """回退后的结果结构不变：model_id / model_name / elapsed / cost 齐全。"""
        cfg = _cfg([("primary", ["backup"]), ("backup", None)])
        self._install(cfg, {
            "primary": llm_client.LLMError("HTTP 401: unauthorized"),
            "backup": "备用模型回复",
        })
        r = llm_client.chat("你好", model_id="primary")
        for key in ("text", "model_id", "model_name", "elapsed", "cost",
                    "prompt_tokens", "completion_tokens"):
            self.assertIn(key, r)
        self.assertEqual(r["model_name"], "backup-model")

    def test_missing_api_key_falls_back_to_next_candidate(self):
        """主模型缺 Key（配置层失败）→ 换候选，而不是直接崩。"""
        cfg = _cfg([("primary", ["backup"]), ("backup", None)])
        h = self._install(cfg, {"primary": "主模型回复", "backup": "备用模型回复"})
        llm_client.resolve_api_key = lambda mid, model: "" if mid == "primary" else "k"
        r = llm_client.chat("你好", model_id="primary")
        self.assertEqual(r["model_id"], "backup")
        self.assertEqual(h.calls["primary"], 0)


class TestTestModelNoFallback(_FallbackTestBase):
    """连通性测试不得被备用链路污染（否则「备用通了」会误报为「主模型通了」）。"""

    def test_test_model_passes_allow_fallback_false(self):
        captured = {}

        def spy(user, **kwargs):
            captured.update(kwargs)
            return {"text": "正常", "elapsed": 0.1, "prompt_tokens": 1, "completion_tokens": 1}

        orig_chat = llm_client.chat
        llm_client.chat = spy
        try:
            cfg = _cfg([("primary", ["backup"]), ("backup", None)])
            llm_client.load_models = lambda: cfg
            r = llm_client.test_model("primary")
        finally:
            llm_client.chat = orig_chat
        self.assertTrue(r["ok"])
        self.assertIs(captured.get("allow_fallback"), False)

    def test_test_model_reports_failure_not_backup_success(self):
        """主模型挂、备用模型通 → test_model 必须报 FAIL。"""
        cfg = _cfg([("primary", ["backup"]), ("backup", None)])
        h = self._install(cfg, {
            "primary": llm_client.LLMError("HTTP 403: forbidden"),
            "backup": "正常",
        })
        r = llm_client.test_model("primary")
        self.assertFalse(r["ok"])
        self.assertEqual(h.calls["backup"], 0)


class TestModelConfigFallbackCommand(_FallbackTestBase):
    """`model_config.py fallback` 子命令：写入 / 清空 / 校验。"""

    def setUp(self):
        super().setUp()
        self.cfg = _cfg([("a", None), ("b", None), ("c", None)])
        self.saved = []
        self._orig_mc = (model_config.load_models, model_config.save_models)
        model_config.load_models = lambda: self.cfg
        model_config.save_models = lambda cfg: self.saved.append(cfg)

    def tearDown(self):
        model_config.load_models, model_config.save_models = self._orig_mc
        super().tearDown()

    def _run(self, argv):
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["model_config.py"] + argv):
            with contextlib.redirect_stdout(buf):
                rc = model_config.main()
        self.out = buf.getvalue()
        return rc

    def test_writes_fallback_list(self):
        rc = self._run(["fallback", "a", "b", "c"])
        self.assertEqual(rc, 0)
        self.assertEqual(self.cfg["models"]["a"]["fallback"], ["b", "c"])
        self.assertEqual(len(self.saved), 1)
        self.assertIn("b, c", self.out)

    def test_single_fallback_also_stored_as_list(self):
        rc = self._run(["fallback", "a", "b"])
        self.assertEqual(rc, 0)
        self.assertEqual(self.cfg["models"]["a"]["fallback"], ["b"])

    def test_clears_fallback(self):
        self.cfg["models"]["a"]["fallback"] = ["b"]
        rc = self._run(["fallback", "a"])
        self.assertEqual(rc, 0)
        self.assertNotIn("fallback", self.cfg["models"]["a"])
        self.assertEqual(len(self.saved), 1)
        self.assertIn("已清空", self.out)

    def test_rejects_unknown_model_and_does_not_write(self):
        rc = self._run(["fallback", "ghost", "b"])
        self.assertEqual(rc, 1)
        self.assertEqual(self.saved, [])

    def test_rejects_unknown_fallback_and_does_not_write(self):
        rc = self._run(["fallback", "a", "b", "ghost"])
        self.assertEqual(rc, 1)
        self.assertNotIn("fallback", self.cfg["models"]["a"])
        self.assertEqual(self.saved, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
