#!/usr/bin/env python3
"""bugbear（B 规则）修复的回归守卫（2026-09-27 企业级整改 P0-4 第二批）。

只守「修复本身不被回退」，不复述规则文档：
  1. B904：except 内 raise 必须保留异常链（__cause__），否则线上栈信息断裂。
  2. B023：extract_dialogue 的句子定位由闭包提为模块级函数，须证明是纯重构。
  3. B007/B905：launch 自检不再维护与模块列表平行的手抄名字列表。

用法：python run_tests.py
"""
import importlib.util
import io
import re
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


SAMPLER = _load("sampler")


def _reference_sentence_at(body, boundaries, k):
    """逐字复刻重构前的循环内闭包实现。

    刻意不断言具体句子内容，而是与旧实现逐点对比：既有取值方式（切片从
    分隔符起始位开始，故返回串可能以「。」开头）是否为期望行为属于另一个
    议题，本测试只保证「提取为模块级函数」这一步没有改变任何行为。
    """
    if k < 0 or k >= len(boundaries) - 1:
        return ""
    return body[boundaries[k]:boundaries[k + 1]].strip()


class TestSentenceAtIsPureRefactor(unittest.TestCase):
    SAMPLES = [
        "他走进殿中。师父说：“跪下。”他照做了。",
        "第一句！第二句？第三句……第四句；第五句",
        "没有标点的长句",
        "。",
        "",
    ]

    def test_matches_pre_refactor_closure_for_every_k(self):
        for body in self.SAMPLES:
            boundaries = [m.start() for m in SAMPLER.SENT_RE.finditer(body)] + [len(body)]
            for k in range(-3, len(boundaries) + 3):
                self.assertEqual(
                    SAMPLER._sentence_at(body, boundaries, k),
                    _reference_sentence_at(body, boundaries, k),
                    f"k={k} 时行为与重构前不一致: {body!r}",
                )

    def test_out_of_range_returns_empty_string(self):
        body = "甲。乙。丙。"
        boundaries = [m.start() for m in SAMPLER.SENT_RE.finditer(body)] + [len(body)]
        self.assertEqual(SAMPLER._sentence_at(body, boundaries, -1), "")
        self.assertEqual(SAMPLER._sentence_at(body, boundaries, len(boundaries) - 1), "")

    def test_extract_dialogue_shape_unchanged(self):
        chapters = [("第一章", "他进殿。师父说：“跪下。”他照做了。")]
        out = SAMPLER.extract_dialogue(chapters, [0])
        self.assertEqual(len(out), 1, f"应抽到 1 条对话: {out}")
        self.assertEqual(set(out[0]), {"chapter", "title", "before", "line", "after"})
        self.assertEqual(out[0]["chapter"], 1)
        self.assertEqual(out[0]["title"], "第一章")


class TestLaunchCheckHasNoParallelLists(unittest.TestCase):
    def test_import_check_lines_match_module_count(self):
        """自检逐行打印每个模块；名字派生自模块对象，故不可能与模块清单漂移。

        回退成「模块列表 + 手抄名字列表 zip」的写法时，漏配名字会让自检
        少打一行而整体看起来仍是绿的——这条断言把该退化钉死。
        """
        import gui.launch as launch

        buf = io.StringIO()
        with redirect_stdout(buf):
            launch.run_check()
        lines = [ln for ln in buf.getvalue().splitlines() if ln.startswith("[check] import gui.")]
        self.assertEqual(len(lines), 6, f"自检应覆盖 6 个后端模块: {lines}")
        names = {re.search(r"import gui\.(\w+)", ln).group(1) for ln in lines}
        self.assertEqual(
            names,
            {"engine_adapter", "router", "server", "services", "sse", "state_store"},
        )


class TestExceptionChainPreserved(unittest.TestCase):
    """B904：except 内的 raise 必须 `from exc`。

    少了 from，原始异常只会以 __context__ 隐式串接，排查时无法区分
    「底层原始错误」与「异常处理自身出的错」——本项目这些位置全部是
    400/500 业务异常的入口，栈信息断裂会直接拉长定位时间。
    若将来有人删掉 from，__cause__ 变为 None，本类断言即失败。
    """

    def test_asset_handler_keeps_cause_for_non_integer_index(self):
        from gui import router

        with self.assertRaises(router.ServiceError) as cm:
            router._h_asset({"book_id": "b", "chapter": "abc", "pass": "p1"}, {})
        self.assertIsInstance(cm.exception.__cause__, ValueError,
                              "chapter 解析失败必须把原始 ValueError 链进 __cause__")

    def test_list_assets_handler_keeps_cause_for_non_integer_offset(self):
        from gui import router

        with self.assertRaises(router.ServiceError) as cm:
            router._h_list_assets({"offset": "x"}, {})
        self.assertIsInstance(cm.exception.__cause__, ValueError,
                              "offset 解析失败必须把原始 ValueError 链进 __cause__")


if __name__ == "__main__":
    unittest.main(verbosity=2)
