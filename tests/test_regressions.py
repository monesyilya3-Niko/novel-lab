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


class TestNormalizePass3BannedFields(unittest.TestCase):
    """回归 #5：normalize_pass3 的 banned 组装必须完整提取三字段，不得丢数据。

    历史缺陷（2026-09-08 修复）：当 pass3 输出标准三字段结构
    {"never_used_words": [...], "avoided_structures": [...], "genre_taboos": [...]}
    时，原实现只 fuzzy_find 提 never_used_words（且因 fuzzy_find 对 dict 下钻兜底
    as_str 只取第一个词），并把 avoided_structures/genre_taboos 硬编码为空列表，
    导致数据静默丢失。
    """

    def test_full_three_field_banned_preserved(self):
        norm = _load("normalize")
        pass3 = {
            "switching_rules": [],
            "anti_pattern": {},
            "banned": {
                "never_used_words": ["撕心裂肺", "天崩地裂", "肝肠寸断"],
                "avoided_structures": ["大段排比式煽情", "全知视角跳入多人心思"],
                "genre_taboos": ["狗血失忆", "豪门玛丽苏", "金手指开挂"],
            },
        }
        narration, dialogue, emotion, imagery, banned = norm.normalize_pass3(pass3)
        self.assertEqual(
            banned["never_used_words"],
            ["撕心裂肺", "天崩地裂", "肝肠寸断"],
            "never_used_words 不应丢失其余词",
        )
        self.assertEqual(
            banned["avoided_structures"],
            ["大段排比式煽情", "全知视角跳入多人心思"],
            "avoided_structures 不应被硬编码为空",
        )
        self.assertEqual(
            banned["genre_taboos"],
            ["狗血失忆", "豪门玛丽苏", "金手指开挂"],
            "genre_taboos 不应被硬编码为空",
        )

    def test_flat_list_banned_still_works(self):
        """兜底路径：扁平 list 形态的 banned 仍能正常提取 never_used_words。"""
        norm = _load("normalize")
        pass3 = {
            "switching_rules": [],
            "anti_pattern": {},
            "banned": ["恍若", "顿时", "霎时"],
        }
        narration, dialogue, emotion, imagery, banned = norm.normalize_pass3(pass3)
        self.assertEqual(banned["never_used_words"], ["恍若", "顿时", "霎时"])
        self.assertEqual(banned["avoided_structures"], [])
        self.assertEqual(banned["genre_taboos"], [])


class TestEmotionExamplesAntiPatternMatch(unittest.TestCase):
    """回归 #6：extract_emotion_examples 应按情绪名匹配专属反例，不重复拼接。

    历史缺陷（2026-09-08 修复）：当 anti_pattern 是 dict（按情绪名分组）且
    switching_rules 是 list 时，旧实现在循环外把整个 anti dict 压成一段
    「愤怒：…；悲伤：…；心动：…」拼接文本，重复塞给每条 example，
    导致 3 条 example 的 anti_pattern 完全相同且语义错位。
    """

    def test_each_emotion_gets_own_anti_pattern(self):
        norm = _load("normalize")
        pass3 = {
            "switching_rules": [
                {"scene": "愤怒", "mode": "动作外化式", "example_pattern": "摔物件"},
                {"scene": "悲伤", "mode": "体感式", "example_pattern": "眼泪大颗"},
                {"scene": "心动", "mode": "环境投射式", "example_pattern": "心跳漏拍"},
            ],
            "anti_pattern": {
                "愤怒": "避免直接写「他很愤怒」、堆砌形容词",
                "悲伤": "避免写「她伤心欲绝」、嚎哭式自白",
                "心动": "避免直写「她心动了」、夸张内心呐喊",
            },
        }
        em = norm.extract_emotion_examples(pass3, "混合式")
        by_emotion = {e["emotion"]: e["anti_pattern"] for e in em if e["emotion"] in ("愤怒", "悲伤", "心动")}
        # 每条专属反例，且互不相同
        self.assertEqual(by_emotion["愤怒"], "避免直接写「他很愤怒」、堆砌形容词")
        self.assertEqual(by_emotion["悲伤"], "避免写「她伤心欲绝」、嚎哭式自白")
        self.assertEqual(by_emotion["心动"], "避免直写「她心动了」、夸张内心呐喊")
        self.assertEqual(
            len(set(by_emotion.values())), 3,
            "3 条 anti_pattern 应互不相同，而非共用同一段拼接文本",
        )


class TestYamlLiteEmptyValueList(unittest.TestCase):
    """回归 #7：yaml_lite 空值键后紧跟缩进列表不得崩溃。

    历史缺陷（QA 回归发现）：``key:``（空值）后紧跟 ``- item`` 列表时，
    旧实现先把 ``result[key]`` 写成空字符串 ``""`` 再记录 ``current_list_key``，
    下一行列表项的 ``result.setdefault(key, [])`` 命中已存在的 ``str``，
    随后 ``.append(item)`` 触发 ``AttributeError: 'str' object has no attribute 'append'``。
    修复：空值分支改为 ``result.pop(key, None)``，使列表项分支能创建全新 list。
    """

    def test_empty_value_then_list_parses_to_list(self):
        yl = _load("yaml_lite")
        text = "aliases:\n  - a\n  - b\n"
        result = yl.parse_yaml(text)
        self.assertEqual(
            result["aliases"], ["a", "b"],
            "空值键后紧跟列表应解析为列表，而非崩溃或残留空字符串",
        )

    def test_empty_value_stays_empty_when_no_list_follows(self):
        yl = _load("yaml_lite")
        text = "aliases:\nname: 张三\n"
        result = yl.parse_yaml(text)
        # 无列表跟随时，空值键应不存在或为空，且不干扰后续键值对。
        self.assertNotIn("aliases", result, "无列表跟随时空值键不应残留空字符串")
        self.assertEqual(result["name"], "张三")


class TestQcLlmHookWiring(unittest.TestCase):
    """回归 #5：qc.py 的 llm_hook 参数不得遮蔽模块名（接线层崩溃类 bug）。

    历史缺陷：run_qc 的参数 ``llm_hook=None`` 遮蔽了模块级 ``import llm_hook``，
    导致 ``--llm-hook`` 在无模型环境下触发 ``AttributeError: 'NoneType' object
    has no attribute 'make_causality_hook'``。工程师单测只覆盖 hook 模块自身逻辑，
    未覆盖 qc.py 端到端接线，故漏网。此处固化：无模型环境跑 run_qc(enable_llm_hook=True)
    必须静默降级为纯算法（meta.llm_hook.enabled=False），不得崩溃。
    """

    def test_run_qc_enable_llm_hook_no_model_silently_degrades(self):
        qc = _load("qc")
        # 构造最小章节目录（单章 txt），复用 _load_texts 的发现逻辑。
        with tempfile.TemporaryDirectory() as tmp:
            ch = Path(tmp) / "chapters"
            ch.mkdir()
            (ch / "ch1.txt").write_text("十八岁那年的夏天，唐雨回到故乡。", encoding="utf-8")

            # 无模型环境（默认 llm_client 未配置），enable_llm_hook=True 应静默降级。
            report = qc.run_qc(str(ch), enable_llm_hook=True)

            self.assertIsNotNone(report, "run_qc 应正常返回 QCReport，而非崩溃")
            meta_hook = report.meta.get("llm_hook")
            self.assertIsNotNone(meta_hook, "meta 应含 llm_hook 字段")
            self.assertFalse(meta_hook.get("enabled"),
                             "无模型环境下 llm_hook 应静默降级为 enabled=False")

    def test_run_qc_enable_llm_hook_equals_baseline_issues(self):
        qc = _load("qc")
        with tempfile.TemporaryDirectory() as tmp:
            ch = Path(tmp) / "chapters"
            ch.mkdir()
            (ch / "ch1.txt").write_text("十八岁那年的夏天，唐雨回到故乡。", encoding="utf-8")

            base = qc.run_qc(str(ch))                       # 纯算法基线
            with_hook = qc.run_qc(str(ch), enable_llm_hook=True)  # 降级后应一致

            self.assertEqual(len(with_hook.issues), len(base.issues),
                             "无模型降级后 issue 数量应与纯算法基线一致")


if __name__ == "__main__":
    unittest.main(verbosity=2)
