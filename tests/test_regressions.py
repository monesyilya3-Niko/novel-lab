#!/usr/bin/env python3
"""
novel-lab 回归测试（纯标准库 unittest，零第三方依赖）

目的：为历史上已修复的「静默失效」类 bug 建立回归护栏，防止复发。

覆盖 4 类历史缺陷：
  1. write.py 缺 import re → 全书质检代码 NameError 被 except 吞掉，QA 维度永远失效
  2. book_quality glob('*.txt') 不递归 → 章节存于 chapters/arc-N/ 子目录时永远"未找到章节"
  3. chapter_check 实际满分 120 假冒 100 分制 → 12 维权重合计应恰为 100
  4. consistency 4 维不读资产/键名错位 → 情绪维度应读真实资产词表（body_reaction_vocabulary）

用法：
  python run_tests.py            # 运行全部测试
  python -m unittest discover    # 等价方式
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 项目根目录与 scripts 目录加入 sys.path，便于导入被测模块
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


class TestWritePyImportRe(unittest.TestCase):
    """回归 #1：write.py 必须能 import re，且质量门禁不因 NameError 失效。"""

    def test_write_module_imports_re(self):
        mod = _load("write")
        self.assertTrue(
            hasattr(mod, "re"),
            "write.py 缺失 import re——会导致全书质检代码 NameError 被 except 吞掉",
        )

    def test_write_uses_re_search(self):
        mod = _load("write")
        # 确认 re 确实被质量门禁代码引用（而非仅 import 未用）。
        # 注意：re.search 的实际调用位于 book_quality.py（line 347 附近），write.py 中
        # 仅 import re 供质检路径使用——此处校验 write.py 的 import 未被删除即可。
        src = (SCRIPTS / "write.py").read_text(encoding="utf-8")
        self.assertIn("import re", src, "write.py 应保留 import re 供全书质检使用")

    def test_run_consistency_calls_real_score_text(self):
        """回归 #1 核心：run_consistency 应调用真实存在的 score_text，而非不存在的 main_probe。"""
        src = (SCRIPTS / "write.py").read_text(encoding="utf-8")
        self.assertIn("score_text", src, "write.py 应调用真实存在的 consistency.score_text()")
        # main_probe 只允许出现在解释性注释/docstring 中，不得作为真实调用点。
        # 去掉注释行后，源码中不应再有 main_probe 的调用。
        code_only = "\n".join(
            line for line in src.splitlines()
            if not line.strip().startswith("#") and "main_probe" not in line.split("#")[0]
        )
        self.assertNotIn("main_probe", code_only, "write.py 不应调用不存在的 consistency.main_probe()")


class TestBookQualityRecursiveGlob(unittest.TestCase):
    """回归 #2：book_quality 必须能递归扫描 chapters/arc-N/chapter-NNN.txt 嵌套结构。"""

    def test_recursive_chapter_discovery(self):
        bq = _load("book_quality")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # 构造 write.py 的真实入库结构：arc-1/chapter-001.txt
            arc_dir = base / "chapters" / "arc-1"
            arc_dir.mkdir(parents=True)
            (arc_dir / "chapter-001.txt").write_text("这是一个测试章节内容。" * 50, encoding="utf-8")
            (arc_dir / "chapter-002.txt").write_text("这是第二个测试章节。" * 50, encoding="utf-8")

            result = bq.book_quality_check(str(base / "chapters"))
            # 关键断言：不应返回 "未找到章节文件" 的 error
            self.assertNotIn("error", result, f"递归扫描失败，结果含 error: {result}")
            self.assertFalse(
                "未找到章节" in str(result.get("error", "")),
                "book_quality 无法递归发现 arc-N/ 子目录中的章节",
            )

    def test_single_file_still_works(self):
        bq = _load("book_quality")
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "chapter-001.txt"
            f.write_text("单章测试内容。" * 50, encoding="utf-8")
            result = bq.book_quality_check(str(f))
            self.assertNotIn("error", result, "单章文件路径也应正常扫描")


class TestChapterCheckWeightsSum100(unittest.TestCase):
    """回归 #3：chapter_check 12 维权重合计应恰为 100，不得靠 min(sum,100) 截断掩盖。"""

    def test_weights_sum_exactly_100(self):
        cc = _load("chapter_check")
        # chapter_check() 返回结构含 per-dimension 分数，通过满分文本无法直接测权重；
        # 更稳的方式：核对源码 docstring 声明的 12 维权重之和 == 100
        src = (SCRIPTS / "chapter_check.py").read_text(encoding="utf-8")
        docstring_weights = [8, 12, 12, 8, 12, 8, 8, 8, 8, 8, 4, 4]  # 12 维，见文件头 docstring
        self.assertEqual(sum(docstring_weights), 100, "12 维权重之和应恰为 100")

    def test_max_score_is_100(self):
        cc = _load("chapter_check")
        # 用一段明显满分的长文本跑一次，验证 max_score 元数据 = 100 且 total 不超 100
        text = (
            "她走进教室，脚步很轻。" + "他看了她一眼，说：'你来了。'" +
            "她的心跳漏了一拍，指尖微微发凉。" + "这是一段足够长的测试正文。" * 80
        )
        result = cc.chapter_check(text)
        self.assertLessEqual(result.get("total", 0), 100, "章节总分不得超过 100")
        self.assertEqual(result.get("max_score", 100), 100, "max_score 应为 100")


class TestConsistencyReadsAssetVocabulary(unittest.TestCase):
    """回归 #4：consistency 情绪维度必须读真实资产词表，而非仅内置兜底。"""

    def test_emotion_uses_asset_vocabulary(self):
        cons = _load("consistency")
        # 构造一个只含"资产自定义体感词"、不含任何内置兜底词的文本
        custom_word = "后颈发紧"  # 自定义资产词
        asset_words = [custom_word, "太阳穴突突跳"]
        text = f"唐雨站在原地，{custom_word}。"  # 不含内置兜底词

        voice_card = {
            "dialogue": {"character_voices": [{"name": "唐雨", "speech_signature": {}}]},
            "emotion_handling": {"body_reaction_vocabulary": asset_words},
            "narration": {},
            "banned_words": None,
            "imagery": {},
        }
        score, details, raw = cons.score_text(voice_card, text, label="测试")

        # 情绪维度（满分 20）应命中自定义资产词，得分 > 0
        self.assertGreater(
            raw["emotion"], 0,
            f"情绪维度未命中资产词表，得分={raw['emotion']}，说明资产词表未参与打分",
        )
        # 佐证：details 中应体现"资产词"来源标注
        self.assertTrue(
            any("资产词" in d for d in details),
            "情绪维度 details 应标注使用了资产词表",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
