"""测试：多语言 / 跨语种自适应字数与阅读时长统计引擎 (count_words_i18n)。

针对 Exoscribe 国际版与双语写作场景：
- CJK 汉字与西文分词的独立抽取与精准计数
- 纯中文、纯英文、中英混合文本的自适应行为
- 模式切换 ("auto", "zh", "cjk", "en")
- 预估阅读耗时（WPM 算法：中文 400 字/分，英文 220 词/分）
- 主导语种判定 ("zh", "en", "unknown")
- 保持 count_words 既有契约 100% 向后兼容
- 纯 Python 3.13 标准库实现
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_ROOT = _TESTS_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gui import writing_extra


class TestWritingI18nWords(unittest.TestCase):
    def test_empty_and_whitespace(self):
        for val in ("", "   \n\t  ", None):
            res = writing_extra.count_words_i18n(val)
            self.assertEqual(res["total"], 0)
            self.assertEqual(res["cjk_chars"], 0)
            self.assertEqual(res["en_words"], 0)
            self.assertEqual(res["reading_time_minutes"], 0.0)
            self.assertEqual(res["primary_language"], "unknown")

    def test_pure_chinese(self):
        text = "他在雪地里走了一整夜，皮靴踩碎冰壳发出沉闷的脆响。"
        # auto 模式：仅计 CJK 字符数
        res_auto = writing_extra.count_words_i18n(text, mode="auto")
        self.assertEqual(res_auto["cjk_chars"], 23)
        self.assertEqual(res_auto["en_words"], 0)
        self.assertEqual(res_auto["total"], 23)
        self.assertEqual(res_auto["primary_language"], "zh")
        self.assertGreater(res_auto["reading_time_minutes"], 0.0)

        # zh 模式：网文传统口径，含标点但去空白字符
        res_zh = writing_extra.count_words_i18n(text, mode="zh")
        self.assertEqual(res_zh["total"], writing_extra.count_words(text))
        self.assertEqual(res_zh["total"], 25)  # 23 汉字 + 2 个中文逗号句号

        # en 模式：不含英文词
        res_en = writing_extra.count_words_i18n(text, mode="en")
        self.assertEqual(res_en["total"], 0)

    def test_pure_english(self):
        text = "Hello world! It's a state-of-the-art narrative engine."
        # words: "Hello", "world", "It's", "a", "state-of-the-art", "narrative", "engine" -> 7 words
        res_auto = writing_extra.count_words_i18n(text, mode="auto")
        self.assertEqual(res_auto["cjk_chars"], 0)
        self.assertEqual(res_auto["en_words"], 7)
        self.assertEqual(res_auto["total"], 7)
        self.assertEqual(res_auto["primary_language"], "en")
        self.assertGreater(res_auto["reading_time_minutes"], 0.0)

        # en 模式
        res_en = writing_extra.count_words_i18n(text, mode="en")
        self.assertEqual(res_en["total"], 7)

        # zh 传统口径：去空白字符长度（与旧版 count_words 完全一致）
        res_zh = writing_extra.count_words_i18n(text, mode="zh")
        self.assertEqual(res_zh["total"], writing_extra.count_words(text))

    def test_mixed_chinese_and_english(self):
        # 汉字 10 个："第章暮冬念春正式发布"
        # 英文词 3 个："1", "Exoscribe", "v2.0" -> "v2", "0" (or hyphenated)
        text = "第 1 章：暮冬念春 Exoscribe v2.0 正式发布！"
        res = writing_extra.count_words_i18n(text, mode="auto")
        self.assertEqual(res["cjk_chars"], 10)
        self.assertGreater(res["en_words"], 0)
        self.assertEqual(res["total"], res["cjk_chars"] + res["en_words"])
        self.assertEqual(res["primary_language"], "zh")

        # 英文为主导的混合文本
        en_heavy = "Chapter 1: The dawn of Exoscribe is finally here for everyone! 暮冬念春"
        res_en_heavy = writing_extra.count_words_i18n(en_heavy, mode="auto")
        self.assertEqual(res_en_heavy["cjk_chars"], 4)
        self.assertEqual(res_en_heavy["primary_language"], "en")

    def test_reading_time_calculation(self):
        # 800 字中文 -> 800 / 400 = 2.0 分钟
        cn_text = "字" * 800
        res_cn = writing_extra.count_words_i18n(cn_text, mode="auto")
        self.assertEqual(res_cn["reading_time_minutes"], 2.0)

        # 440 词英文 -> 440 / 220 = 2.0 分钟
        en_text = "word " * 440
        res_en = writing_extra.count_words_i18n(en_text, mode="auto")
        self.assertEqual(res_en["reading_time_minutes"], 2.0)

        # 超短文本至少预估 0.1 分钟（约 6 秒），不显示 0.0
        short_text = "一句话。"
        res_short = writing_extra.count_words_i18n(short_text, mode="auto")
        self.assertEqual(res_short["reading_time_minutes"], 0.1)

    def test_count_words_backwards_compatibility(self):
        """确保既有 count_words 函数完全不受任何影响。"""
        self.assertEqual(writing_extra.count_words(""), 0)
        self.assertEqual(writing_extra.count_words("你好，世界！"), 6)
        self.assertEqual(writing_extra.count_words("你好 \n 世界 123"), 7)
        self.assertEqual(writing_extra.count_words("Hello world"), 10)

    def test_count_words_router_api(self):
        """验证 /api/writing/count-words 路由与参数校验。"""
        from gui import router
        from gui.services import ServiceError

        resp, _ = router.dispatch("POST", "/api/writing/count-words", {"text": "Hello world", "mode": "auto"}, {})
        self.assertEqual(resp["code"], 0)
        self.assertEqual(resp["data"]["en_words"], 2)
        self.assertEqual(resp["data"]["primary_language"], "en")

        # 脏参数校验抛出 400 ServiceError
        with self.assertRaises(ServiceError):
            router.dispatch("POST", "/api/writing/count-words", {"text": 123}, {})
        with self.assertRaises(ServiceError):
            router.dispatch("POST", "/api/writing/count-words", {"text": "ok", "mode": 123}, {})


if __name__ == "__main__":
    unittest.main()
