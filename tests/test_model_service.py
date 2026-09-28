#!/usr/bin/env python3
"""model_service.py 校验函数覆盖测试（出版级补强）。

模型 ID/协议/URL 校验是安全边界，离线可测。
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


if __name__ == "__main__":
    unittest.main()
