#!/usr/bin/env python3
"""`inject.render_voices` 角色排序回归（2026-09-21）。

背景
----
注入产物是喂给写作 LLM 的 **system prompt**，AI 对靠前内容的注意力更高 ——
主角/配角应当排在工具人之前。此前按 pass2 产出顺序注入，《暮冬念春》13 个角色里
配角「白汐」被排在 4 个工具人之后，主角也可能排在末尾。

修复：`render_voices` 开头按 `_ROLE_ORDER`（主角 0 / 配角 1 / 工具人·龙套 2 / 未知 3）
做**稳定排序**，同权重角色保持原有相对顺序。

用法：
  python -m unittest tests.test_inject_voice_order -v
  python run_tests.py     # 自动 discover
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import inject  # noqa: E402


def _v(name, role):
    return {"name": name, "role": role, "speech_signature": {}}


class TestRenderVoicesOrder(unittest.TestCase):
    @staticmethod
    def _names(text):
        return [ln[4:].split("（")[0] for ln in text.splitlines() if ln.startswith("### ")]

    def test_sorted_by_role_weight(self):
        """主角 → 配角 → 工具人。"""
        voices = [_v("工具A", "工具人"), _v("配A", "配角"), _v("主A", "主角")]
        self.assertEqual(self._names(inject.render_voices(voices)),
                         ["主A", "配A", "工具A"])

    def test_stable_within_same_role(self):
        """同权重保持原有相对顺序（稳定排序）。"""
        voices = [_v("配2", "配角"), _v("配1", "配角"), _v("主1", "主角")]
        self.assertEqual(self._names(inject.render_voices(voices)),
                         ["主1", "配2", "配1"])

    def test_unknown_role_goes_last(self):
        """未识别的 role 排在最后，不被丢弃。"""
        voices = [_v("未知", "路人甲"), _v("主", "主角")]
        self.assertEqual(self._names(inject.render_voices(voices)), ["主", "未知"])

    def test_dragon_set_treated_as_minor(self):
        """龙套与工具人同级。"""
        voices = [_v("龙套", "龙套"), _v("配", "配角")]
        self.assertEqual(self._names(inject.render_voices(voices)), ["配", "龙套"])

    def test_missing_role_field(self):
        """role 字段缺失 → 归入未知组，不报错。"""
        voices = [{"name": "无名", "speech_signature": {}}, _v("主", "主角")]
        self.assertEqual(self._names(inject.render_voices(voices)), ["主", "无名"])

    def test_empty(self):
        self.assertEqual(inject.render_voices([]), "（无声线数据）")


if __name__ == "__main__":
    sys.exit(unittest.main())
