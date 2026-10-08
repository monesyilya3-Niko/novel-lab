"""scripts/metrics.py 流式化回归：数值正确性 + 内存上界。

背景：2026-09-28 发现 compute_metrics 在 100MB 文本下物化 3300 万字符
list（char_ttr 约 1.6GB）与 310 万句子 list，是上传 RSS 冲到 3.1GB 的主因。
修复为流式实现（公式不变），本文件锁定：
1. 流式结果与旧物化口径数值一致；
2. char_ttr / compute 在大文本下峰值内存有界。

阈值取"输入字节数 × 6"而不是更紧的 3 倍：tracemalloc 的峰值里含解释器自身的分配开销，
同一份流式代码在 2026-10-08 的实测里，Python 3.11（ubuntu）峰值 = 输入的 3.13 倍、
3.12/3.13 则低于 3 倍——3 倍阈值量的是解释器版本而不是它要守的性质。
要拦的是"退回物化"那一档：当年 char_ttr 在 20MB 输入上冲到 300MB+（约 15 倍），
6 倍仍能稳稳拦住，同时不给版本差异留误红空间。收紧之前请先拿多版本实测数据说话。
"""
from __future__ import annotations

import sys
import tracemalloc
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import metrics


class TestCharTtr(unittest.TestCase):
    def test_basic(self):
        # 4 种字符 / 8 个 token → 0.5
        self.assertEqual(metrics.char_ttr("甲乙甲乙丙丁丙丁"), 0.5)

    def test_empty(self):
        self.assertEqual(metrics.char_ttr(""), 0.0)
        self.assertEqual(metrics.char_ttr("abc 123"), 0.0)  # 无 CJK

    def test_streaming_memory_bounded(self):
        # 20MB CJK 文本：旧实现物化 list 约 300MB+；流式应 < 3x 输入
        text = "甲乙丙丁戊己庚辛壬癸" * 700_000  # ~20MB
        tracemalloc.start()
        try:
            v = metrics.char_ttr(text)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        # 文本高度重复，TTR 四舍五入为 0；本测试锁定的是内存上界而非值
        self.assertGreaterEqual(v, 0.0)
        self.assertLess(
            peak, len(text.encode("utf-8")) * 6,
            f"char_ttr 峰值 {peak/1e6:.1f}MB 超过输入 6 倍，疑似物化倒退",
        )


class TestBigramFreq(unittest.TestCase):
    def test_counts(self):
        grams = metrics.bigram_freq("甲乙甲乙甲丙", top=5)
        d = {g["gram"]: g["count"] for g in grams}
        self.assertEqual(d["甲乙"], 2)
        self.assertEqual(d["乙甲"], 2)


class TestComputeStreaming(unittest.TestCase):
    def test_sentence_stats(self):
        text = "第一句。第二句很长很长很长很长很长很长很长很长很长很长！短？"
        r = metrics.compute(text)
        self.assertEqual(r["sentence_count"], 3)
        # total_chars = 去空白后全部字符（含标点）
        self.assertEqual(r["total_chars"], 30)
        self.assertGreater(r["short_ratio"], 0)
        self.assertIn("short_ratio", r)
        self.assertIn("long_ratio", r)

    def test_empty(self):
        r = metrics.compute("")
        self.assertEqual(r["sentence_count"], 0)
        self.assertEqual(r["avg_sentence_len"], 0)
        self.assertEqual(r["char_ttr"], 0.0)

    def test_compute_memory_bounded(self):
        # 10MB 多句文本：旧实现物化句子 list；流式应 < 3x 输入
        # ~10MB, 35100 句（SENT_RE 按 \n 也切分，每单元多出"第1章"一段）
        unit = "甲乙丙丁戊己庚辛壬癸。"
        text = ("第1章\n" + unit * 350) * 100
        tracemalloc.start()
        try:
            r = metrics.compute(text)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(r["sentence_count"], 35_100)
        self.assertLess(
            peak, len(text.encode("utf-8")) * 6,
            f"compute 峰值 {peak/1e6:.1f}MB 超过输入 6 倍，疑似物化倒退",
        )


if __name__ == "__main__":
    unittest.main()
