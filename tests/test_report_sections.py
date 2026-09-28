#!/usr/bin/env python3
"""report.py 渲染纯函数覆盖测试（出版级补强）。

build_report / section_* 均为纯函数（dict in → markdown out），
用固定夹具直接调用，不依赖 LLM 与磁盘。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import report as report_mod


def _voice():
    return {
        "meta": {
            "genre": "campus",
            "source_title": "测试书",
            "sample_chapters": [1, 2, 3],
            "total_sample_words": 30000,
            "confidence": 0.85,
        },
        "dialogue": {
            "character_voices": [
                {
                    "name": "主角",
                    "role": "男主",
                    "speech_signature": {
                        "avg_utterance_length": 12,
                        "verbal_tics": ["嗯", "行"],
                        "refusal_pattern": "沉默走开",
                        "never_says": ["我爱你"],
                    },
                    "arc": {"arc_type": "成长型", "start_state": "自卑", "end_state": "自信"},
                }
            ]
        },
        "narration": {"pov": "第三人称"},
        "style": {"tone": "温暖"},
    }


class TestSectionMeta(unittest.TestCase):
    def test_meta_fields(self):
        out = report_mod.section_meta(_voice()["meta"])
        self.assertIn("campus", out)
        self.assertIn("测试书", out)
        self.assertIn("85%", out)

    def test_empty_meta_no_crash(self):
        out = report_mod.section_meta({})
        self.assertIsInstance(out, str)


class TestSectionVoices(unittest.TestCase):
    def test_empty(self):
        out = report_mod.section_voices([])
        self.assertIn("未提取到", out)

    def test_character_rendered(self):
        voices = _voice()["dialogue"]["character_voices"]
        out = report_mod.section_voices(voices)
        self.assertIn("主角", out)
        self.assertIn("男主", out)
        self.assertIn("嗯、行", out)
        self.assertIn("沉默走开", out)
        self.assertIn("我爱你", out)
        self.assertIn("成长型", out)


class TestSectionStyleStructureCommercial(unittest.TestCase):
    def test_empty_dicts_no_crash(self):
        for fn in (report_mod.section_style, report_mod.section_structure,
                   report_mod.section_commercial):
            out = fn({})
            self.assertIsInstance(out, str)

    def test_style_pov(self):
        out = report_mod.section_style(_voice())
        self.assertIn("第三人称", out)


class TestBuildReport(unittest.TestCase):
    def test_full_report_structure(self):
        md = report_mod.build_report(_voice(), {"beats": []}, {"hooks": []})
        for header in ("# 拆书报告：《测试书》", "## 一、作品定位", "## 二、角色声线拆解",
                       "## 三、文风与情绪写法", "## 四、结构规律", "## 五、商业洞察"):
            self.assertIn(header, md)
        self.assertIn("主角", md)

    def test_title_override(self):
        md = report_mod.build_report(_voice(), {}, {}, title_override="覆盖标题")
        self.assertIn("《覆盖标题》", md)

    def test_empty_inputs_no_crash(self):
        md = report_mod.build_report({}, {}, {})
        self.assertIn("# 拆书报告", md)

    def test_no_verbatim_leak_markers(self):
        # 报告头必须声明不含原文摘录（合规要求）
        md = report_mod.build_report(_voice(), {}, {})
        self.assertIn("不含原文摘录", md)


if __name__ == "__main__":
    unittest.main()
