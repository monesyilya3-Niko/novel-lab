#!/usr/bin/env python3
"""`total_sample_words` 语义回归（2026-09-21）。

背景
----
该字段此前一律填 `metrics.total_chars`（**全书**字数），但字段名与两个消费方都要求
它是**采样**字数：

  - `report.py`   → `**采样范围**：第 X-Y 章 等 N 章（共 {total_sample_words} 字）`
  - `report_craft.py` → `words = meta.get("total_sample_words", 0)`

实测症状：《暮冬念春》报告写着「采样范围：第 1-2 章 等 27 章（共 **328658** 字）」——
27 章采样不可能有 32.8 万字，自相矛盾。修复后为 **61189** 字（采样章实际字数）。

修复方式
--------
`pipeline` 生成 manifest 时算好 `sample_words`；`assemble` / `pipeline` 的
`_sample_words()` 优先取它，老 manifest 无该字段时退回旧行为（向后兼容）。

⚠ `assemble.py` 与 `pipeline.py` 各有一份 `_sample_words`（历史重复实现），
本测试**同时锁定两者**，防止将来只改一处。
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import assemble  # noqa: E402
import pipeline  # noqa: E402


class TestSampleWordsSemantics(unittest.TestCase):
    MODULES = (assemble, pipeline)

    def test_both_modules_expose_helper(self):
        """两份实现都必须存在（否则说明只改了一处）。"""
        for mod in self.MODULES:
            self.assertTrue(hasattr(mod, "_sample_words"),
                            f"{mod.__name__} 缺少 _sample_words")

    def test_prefers_manifest_sample_words(self):
        """manifest 有 sample_words → 用它，不用全书字数。"""
        for mod in self.MODULES:
            with self.subTest(mod=mod.__name__):
                got = mod._sample_words({"sample_words": 61189},
                                        {"total_chars": 328658})
                self.assertEqual(got, 61189)

    def test_falls_back_to_metrics(self):
        """老 manifest 无该字段 → 退回旧行为，不报错。"""
        for mod in self.MODULES:
            with self.subTest(mod=mod.__name__):
                got = mod._sample_words({}, {"total_chars": 328658})
                self.assertEqual(got, 328658)

    def test_invalid_values_fall_back(self):
        """0 / 负数 / None / 字符串 / 浮点 都视为无效，退回 metrics。"""
        for bad in (0, -1, None, "abc", 1.5):
            for mod in self.MODULES:
                with self.subTest(mod=mod.__name__, bad=bad):
                    got = mod._sample_words({"sample_words": bad},
                                            {"total_chars": 100})
                    self.assertEqual(got, 100)

    def test_missing_metrics_returns_zero(self):
        for mod in self.MODULES:
            with self.subTest(mod=mod.__name__):
                self.assertEqual(mod._sample_words({}, {}), 0)


if __name__ == "__main__":
    sys.exit(unittest.main())
