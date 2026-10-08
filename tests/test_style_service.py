"""文风服务（``gui/style_service.py``）回归。

2026-10-08 排查到的两处：

1. 对白统计自己写了引号正则，只认 ASCII ``"`` 与直角引号，中文弯引号 ``“…”``
   整段漏计。本仓库正文几乎都用弯引号，于是"对白占 17%"的稿子被读成 4%，
   再经 ``apply_style_prompt`` 的阈值判断，给用户的建议直接反了。
   现在口径统一走引擎的 ``metrics.dialogue_char_count``。
2. 风格卡用 ``write_text`` 直接落盘，进程中途被杀会留下半份 JSON；
   ``list_styles`` 对坏文件只 warn 并跳过，用户看到的是"卡凭空消失"。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import _isolation  # noqa: E402

from gui import style_service  # noqa: E402
from gui.services import ServiceError  # noqa: E402

# 一段对白占比约 17% 的正文（重复 6 遍凑够 100 字下限）
DIALOGUE_HEAVY = (
    "夜色压得很低。他推开门，屋里只剩一盏灯。\n"
    "“你来了。”她说，声音很轻。\n"
    "他点头，把伞收好：“路上堵车。”\n"
    "“我知道。”她笑了一下，眼里却没有笑意。\n"
    "「好久不见」四个字他练了一路，此刻却说不出口。\n"
) * 6


class TestDialogueMetric(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="style_qa_"))
        self._iso = _isolation.isolate_paths(self._tmp)
        self._iso.__enter__()

    def tearDown(self):
        # isolate_paths 退出时会回收它接管的临时根，这里不再自己删第二遍
        self._iso.__exit__(None, None, None)

    def test_curly_quotes_are_counted(self):
        card = style_service.analyze_style(DIALOGUE_HEAVY, "测试文风")
        ratio = card["metrics"]["dialogue_ratio"]
        # 旧正则在这里报 0.041（只数到「好久不见」），弯引号对白全丢
        self.assertGreater(ratio, 0.12, f"对白占比被低估：{ratio}")

    def test_ratio_matches_engine_dialogue_count(self):
        card = style_service.analyze_style(DIALOGUE_HEAVY, "测试文风")
        from gui import engine_adapter
        expected = round(engine_adapter.dialogue_char_count(DIALOGUE_HEAVY)
                         / len(DIALOGUE_HEAVY), 3)
        self.assertEqual(card["metrics"]["dialogue_ratio"], expected)

    def test_prompt_guidance_follows_real_density(self):
        card = style_service.analyze_style(DIALOGUE_HEAVY, "测试文风")
        style_service.save_style("测试文风", card)
        out = style_service.apply_style_prompt("测试文风", "写一章。")
        joined = "\n".join(out["guidance"])
        # 0.1 < ratio < 0.3 → 应判"平衡"，而不是旧口径下的"对话密度较低"
        self.assertNotIn("对话密度较低", joined)
        self.assertIn("对话与叙述平衡", joined)


class TestStylePersistence(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="style_p_"))
        self._iso = _isolation.isolate_paths(self._tmp)
        self._iso.__enter__()

    def tearDown(self):
        self._iso.__exit__(None, None, None)

    def test_save_leaves_no_temp_file(self):
        res = style_service.save_style("留痕测试", {"metrics": {}})
        d = style_service._styles_dir()
        self.assertTrue((d / "留痕测试.json").is_file())
        self.assertEqual(list(d.glob("*.tmp")), [], f"临时文件没清掉: {res}")

    def test_saved_card_is_valid_json_with_name(self):
        style_service.save_style("内容测试", {"metrics": {"avg_sentence_length": 12.0}})
        fp = style_service._styles_dir() / "内容测试.json"
        data = json.loads(fp.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "内容测试")
        self.assertEqual(style_service.get_style("内容测试")["name"], "内容测试")

    def test_duplicate_name_rejected_without_touching_original(self):
        style_service.save_style("同名卡", {"metrics": {"avg_sentence_length": 11.0}})
        before = (style_service._styles_dir() / "同名卡.json").read_text(encoding="utf-8")
        with self.assertRaises(ServiceError) as cm:
            style_service.save_style("同名卡", {"metrics": {"avg_sentence_length": 99.0}})
        self.assertEqual(cm.exception.code, 409)
        after = (style_service._styles_dir() / "同名卡.json").read_text(encoding="utf-8")
        self.assertEqual(after, before, "重复保存把已有卡片覆盖了")



class TestInputTypes(unittest.TestCase):
    """请求体里的类型脏值必须报 400，而不是变成没有信息量的 500。"""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="style_t_"))
        self._iso = _isolation.isolate_paths(self._tmp)
        self._iso.__enter__()

    def tearDown(self):
        self._iso.__exit__(None, None, None)

    def test_analyze_rejects_non_string_text(self):
        for bad in (123, ["一段文本"], {"text": "x"}):
            with self.assertRaises(ServiceError) as cm:
                style_service.analyze_style(bad)  # type: ignore[arg-type]
            self.assertEqual(cm.exception.code, 400, repr(bad))

    def test_save_rejects_non_object_card(self):
        with self.assertRaises(ServiceError) as cm:
            style_service.save_style("坏卡", "不是对象")  # type: ignore[arg-type]
        self.assertEqual(cm.exception.code, 400)

    def test_apply_rejects_non_string_prompt(self):
        style_service.save_style("可查卡", {"metrics": {}})
        with self.assertRaises(ServiceError) as cm:
            style_service.apply_style_prompt("可查卡", 42)  # type: ignore[arg-type]
        self.assertEqual(cm.exception.code, 400)

    def test_tampered_metric_falls_back_instead_of_crashing(self):
        # 风格卡落在磁盘上，用户会手改：某个指标写成字符串不能让功能 500
        style_service.save_style("被改过的卡", {"metrics": {"dialogue_ratio": "很多"}})
        out = style_service.apply_style_prompt("被改过的卡", "写一章。")
        self.assertTrue(out["guidance"])
        joined = chr(10).join(out["guidance"])
        self.assertIn("对话与叙述平衡", joined)  # 回落到默认 0.2 的判断


if __name__ == "__main__":
    unittest.main()
