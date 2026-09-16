#!/usr/bin/env python3
"""
model_config 导入回归测试

背景（2026-09-16 修复）：
  `scripts/model_config.py` 曾写 `from llm_client import (..., secret_store)`，
  但 `llm_client.py` 里的 secret_store 是**函数内延迟 import**（`load_secrets`
  /`save_secrets` 各自 `import secret_store`），并非模块级属性。因此
  `from llm_client import secret_store` 必然抛
  `ImportError: cannot import name 'secret_store' from 'llm_client'`，
  导致 `novel 模型`（以及 `model_config.py` 的任何调用）**完全不可用**——
  连 `list` 都进不去，配置阶段就被拦死。

本文件守住「模块可导入」这条底线。

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


class TestModelConfigImport(unittest.TestCase):
    """model_config 必须可导入（否则 `novel 模型` 全线不可用）。"""

    def test_imports_without_error(self):
        mod = _load("model_config")
        self.assertTrue(callable(mod.main))

    def test_secret_store_available_at_module_level(self):
        """secret_store 必须在模块级可见——它被 storage_mode() 直接调用。"""
        mod = _load("model_config")
        self.assertTrue(hasattr(mod, "secret_store"))
        self.assertTrue(callable(mod.secret_store.storage_mode))

    def test_llm_client_symbols_still_imported(self):
        """重构 import 时不得顺手丢掉原有符号。"""
        mod = _load("model_config")
        for sym in ("load_models", "save_models", "load_secrets", "save_secrets",
                    "test_model", "DEFAULT_ROUTES", "MODELS_FILE", "SECRETS_FILE"):
            with self.subTest(sym=sym):
                self.assertTrue(hasattr(mod, sym))

    def test_presets_present(self):
        mod = _load("model_config")
        self.assertIn("deepseek", mod.PRESETS)


if __name__ == "__main__":
    unittest.main()
