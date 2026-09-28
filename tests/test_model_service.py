#!/usr/bin/env python3
"""model_service.py 覆盖测试（出版级补强）。

校验函数 + CRUD 全链路（engine_adapter 层全部 mock，不碰真实 LLM 与磁盘）。
test_model 的连通性分支通过 mock engine_adapter.model_test 覆盖成功/失败两种结果；
真实外部模型链路仍未实测（无可用 LLM key）。
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gui import model_service
from gui.services import ServiceError


class TestValidateModelId(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(model_service._validate_model_id("deepseek-v3"), "deepseek-v3")
        self.assertEqual(model_service._validate_model_id("  gpt4  "), "gpt4")

    def test_empty(self):
        with self.assertRaises(ServiceError):
            model_service._validate_model_id("")
        with self.assertRaises(ServiceError):
            model_service._validate_model_id("   ")

    def test_path_traversal(self):
        for bad in ["../etc", "a/b", "a\\b", "a b", "a\nb"]:
            with self.assertRaises(ServiceError, msg=bad):
                model_service._validate_model_id(bad)

    def test_invalid_chars(self):
        with self.assertRaises(ServiceError):
            model_service._validate_model_id("model@x")


class TestValidateProtocol(unittest.TestCase):
    def test_valid(self):
        for p in ("openai", "anthropic", "ollama"):
            self.assertEqual(model_service._validate_protocol(p), p)

    def test_invalid(self):
        with self.assertRaises(ServiceError):
            model_service._validate_protocol("custom")


class TestValidateBaseUrl(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(model_service._validate_base_url("https://api.x.com/"), "https://api.x.com")
        self.assertEqual(model_service._validate_base_url("http://localhost:11434"), "http://localhost:11434")

    def test_empty(self):
        with self.assertRaises(ServiceError):
            model_service._validate_base_url("")

    def test_bad_scheme(self):
        with self.assertRaises(ServiceError):
            model_service._validate_base_url("ftp://x.com")


class TestModelHasKey(unittest.TestCase):
    def test_secret_store_hit(self):
        self.assertTrue(model_service._model_has_key({"m1": "k"}, "m1", {}))

    def test_env_hit(self):
        with mock.patch.dict(os.environ, {"TEST_KEY_XYZ": "v"}):
            self.assertTrue(model_service._model_has_key({}, "m1", {"api_key_env": "TEST_KEY_XYZ"}))

    def test_env_missing(self):
        # P1-B2：只看名称不看是否设置会误报
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(model_service._model_has_key({}, "m1", {"api_key_env": "NO_SUCH_VAR_XYZ"}))

    def test_no_env_name(self):
        self.assertFalse(model_service._model_has_key({}, "m1", {}))


class TestModelCrud(unittest.TestCase):
    """CRUD 全链路：engine_adapter 的 load/save 全部 mock，测服务层逻辑。"""

    def setUp(self):
        self.cfg = {"models": {}, "roles": {}, "routes": {}}
        self.secrets = {}
        self.saved = {}
        patches = [
            mock.patch("gui.model_service.engine_adapter.models_load",
                       side_effect=lambda: self.cfg),
            mock.patch("gui.model_service.engine_adapter.models_save",
                       side_effect=lambda c: self.saved.update(cfg=c)),
            mock.patch("gui.model_service.engine_adapter.secrets_load",
                       side_effect=lambda: self.secrets),
            mock.patch("gui.model_service.engine_adapter.secrets_save",
                       side_effect=lambda s: self.saved.update(secrets=dict(s))),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _body(self, **kw):
        b = {"id": "m1", "protocol": "openai",
             "base_url": "https://api.example.com/v1", "model_name": "gpt-x"}
        b.update(kw)
        return b

    def test_add_and_get(self):
        got = model_service.add_model(self._body())
        self.assertEqual(got["id"], "m1")
        self.assertFalse(got["has_key"])
        self.assertEqual(got["base_url"], "https://api.example.com/v1")
        # 落盘内容一致
        self.assertIn("m1", self.saved["cfg"]["models"])
        # get 走同一份 cfg
        again = model_service.get_model("m1")
        self.assertEqual(again["model_name"], "gpt-x")

    def test_add_with_api_key_sets_secret(self):
        got = model_service.add_model(self._body(api_key="sk-test"))
        self.assertTrue(got["has_key"])
        self.assertEqual(self.saved["secrets"], {"m1": "sk-test"})

    def test_add_duplicate_409(self):
        model_service.add_model(self._body())
        with self.assertRaises(ServiceError) as cm:
            model_service.add_model(self._body())
        self.assertEqual(cm.exception.code, 409)

    def test_add_invalid_inputs_400(self):
        for bad in (None, "x", []):
            with self.assertRaises(ServiceError) as cm:
                model_service.add_model(bad)
            self.assertEqual(cm.exception.code, 400)
        with self.assertRaises(ServiceError) as cm:
            model_service.add_model(self._body(protocol="nope"))
        self.assertEqual(cm.exception.code, 400)
        with self.assertRaises(ServiceError) as cm:
            model_service.add_model(self._body(model_name="  "))
        self.assertEqual(cm.exception.code, 400)
        with self.assertRaises(ServiceError) as cm:
            model_service.add_model(self._body(base_url="ftp://x"))
        self.assertEqual(cm.exception.code, 400)

    def test_get_missing_404(self):
        with self.assertRaises(ServiceError) as cm:
            model_service.get_model("nope")
        self.assertEqual(cm.exception.code, 404)

    def test_list_models_has_key_flags(self):
        model_service.add_model(self._body())
        model_service.add_model(self._body(id="m2", api_key="sk-2"))
        out = model_service.list_models()
        self.assertEqual(out["total"], 2)
        flags = {m["id"]: m["has_key"] for m in out["models"]}
        self.assertEqual(flags, {"m1": False, "m2": True})

    def test_update_model(self):
        model_service.add_model(self._body())
        got = model_service.update_model("m1", {"label": "新名", "timeout": 60,
                                                "base_url": "https://b.example.com/"})
        self.assertEqual(got["label"], "新名")
        self.assertEqual(got["timeout"], 60)
        self.assertEqual(got["base_url"], "https://b.example.com")  # 尾部 / 被剥掉
        # 清空可选字段
        model_service.update_model("m1", {"note": "x"})
        got2 = model_service.update_model("m1", {"note": ""})
        self.assertEqual(got2["note"], "")
        # 非法协议 / 不存在
        with self.assertRaises(ServiceError) as cm:
            model_service.update_model("m1", {"protocol": "nope"})
        self.assertEqual(cm.exception.code, 400)
        with self.assertRaises(ServiceError) as cm:
            model_service.update_model("ghost", {"label": "x"})
        self.assertEqual(cm.exception.code, 404)

    def test_delete_model_clears_role_and_secret(self):
        model_service.add_model(self._body(api_key="sk-test"))
        self.cfg["roles"] = {"writer": "m1", "other": "m2"}
        out = model_service.delete_model("m1")
        self.assertEqual(out, {"deleted": "m1"})
        self.assertNotIn("m1", self.saved["cfg"]["models"])
        self.assertNotIn("writer", self.saved["cfg"]["roles"])
        self.assertIn("other", self.saved["cfg"]["roles"])
        self.assertNotIn("m1", self.saved["secrets"])
        with self.assertRaises(ServiceError) as cm:
            model_service.delete_model("m1")
        self.assertEqual(cm.exception.code, 404)

    def test_set_api_key(self):
        model_service.add_model(self._body())
        out = model_service.set_api_key("m1", "  sk-new  ")
        self.assertEqual(out, {"id": "m1", "has_key": True})
        self.assertEqual(self.saved["secrets"], {"m1": "sk-new"})
        with self.assertRaises(ServiceError) as cm:
            model_service.set_api_key("m1", "   ")
        self.assertEqual(cm.exception.code, 400)
        with self.assertRaises(ServiceError) as cm:
            model_service.set_api_key("ghost", "sk-x")
        self.assertEqual(cm.exception.code, 404)


class TestModelConnectivity(unittest.TestCase):
    """连通性测试：只 mock engine_adapter.model_test，不发起真实网络请求。"""

    def test_success(self):
        with mock.patch("gui.model_service.engine_adapter.model_test",
                        return_value={"ok": True}) as mt:
            out = model_service.test_model("m1")
        mt.assert_called_once_with("m1")
        self.assertEqual(out, {"id": "m1", "success": True, "result": {"ok": True}})

    def test_failure_returns_error_dict(self):
        with mock.patch("gui.model_service.engine_adapter.model_test",
                        side_effect=RuntimeError("连不上")):
            out = model_service.test_model("m1")
        self.assertFalse(out["success"])
        self.assertIn("连不上", out["error"])

    def test_get_presets(self):
        with mock.patch("gui.model_service.engine_adapter.model_presets",
                        return_value={"openai": {}}) as mp:
            self.assertEqual(model_service.get_presets(), {"openai": {}})
        mp.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
