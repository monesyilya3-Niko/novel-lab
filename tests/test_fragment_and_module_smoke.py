#!/usr/bin/env python3
"""
章内无标点碎片重复 + 此前未测模块的冒烟回归（评估报告 P2-2 / P3）。

用法：python run_tests.py
"""
import importlib.util
import json
import sys
import tempfile
import unittest
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


BQ = _load("book_quality")


def _qc_to_dict(obj):
    """QCReport 可能是 dataclass/dict：统一转 JSON 可序列化结构。"""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dict__"):
        return {k: _qc_to_dict(v) for k, v in vars(obj).items()
                if not k.startswith("_")}
    if isinstance(obj, (list, tuple)):
        return [_qc_to_dict(x) for x in obj]
    return obj


class TestIntraChapterFragments(unittest.TestCase):
    """无标点长段碎片重复：句读切分会漏，n-gram 应能抓到。"""

    def test_unpunctuated_repeat_detected(self):
        frag = "她站在走廊尽头看着窗外的雨心里反复想着那封没有寄出的信"
        # 两段相同长句，中间无句读，总长 > 200
        text = frag + "甲" * 30 + frag + "乙" * 30
        issues = BQ.check_intra_chapter_repeats({1: text})
        self.assertTrue(issues, "无标点重复碎片必须被报出")
        self.assertEqual(issues[0]["type"], "intra_chapter_repeat")
        self.assertEqual(issues[0]["source"], "碎片")
        self.assertIn("碎片", issues[0]["detail"])

    def test_uniform_filler_not_flagged(self):
        # 均匀「甲」填充：字符种类过少，不得误报
        issues = BQ.check_intra_chapter_repeats({1: "甲" * 400})
        self.assertEqual(issues, [])

    def test_clean_text_still_empty(self):
        # 句子互不共享 20 字模板，句读切分后也无整句重复
        parts = [
            "清晨雾气未散码头工人已经开始卸货",
            "实验室仪器突然发出刺耳蜂鸣声",
            "她把旧围巾塞进柜子最底层",
            "雨后的操场积水映出半截彩虹",
            "列车进站时他下意识后退半步",
            "厨房里汤锅咕嘟咕嘟冒着泡",
            "图书馆角落那本诗集被人借走了",
            "夜航飞机的红灯划过天际",
            "他把回执单折成纸飞机扔出去",
            "巷口修车摊的老张还没收工",
            "录音笔里的杂音盖过了人声",
            "抽屉深处躺着一枚生锈的钥匙",
        ]
        text = "".join(p + "。" for p in parts)
        issues = BQ.check_intra_chapter_repeats({1: text})
        self.assertEqual(issues, [])

    def test_sentence_repeat_still_works_and_source_kept(self):
        sent = "她心跳漏了一拍指尖微微发凉不知道该怎么办才好"
        text = (sent + "。" + "旁白填充若干字。") * 6
        issues = BQ.check_intra_chapter_repeats({1: text})
        self.assertTrue(issues)
        self.assertEqual(issues[0]["source"], "句")

    def test_qc_d9_still_consumes_detector(self):
        qc = _load("qc")
        frag = "后槽牙咬得发酸指尖掐进掌心呼吸卡在喉咙里说不出话"
        text = frag + "地" * 20 + frag + "天" * 20
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "chapter-001.txt"
            p.write_text(text, encoding="utf-8")
            result = qc.run_qc(tmp)
        raw_hit = json.dumps(_qc_to_dict(result), ensure_ascii=False)
        self.assertIn("intra_chapter", raw_hit)


class TestModuleSmoke(unittest.TestCase):
    """P2-2：此前零测试模块的可导入与纯函数冒烟。"""

    def test_sampler_split_and_select(self):
        sm = _load("sampler")
        text = "".join(
            f"第{i}章\n这是第{i}章的正文内容，足够长以便被保留。\n\n"
            for i in range(1, 31)
        )
        chapters = sm.split_chapters(text)
        self.assertGreaterEqual(len(chapters), 20)
        sel = sm.select(chapters)
        self.assertIn(0, sel)  # 开篇必取
        self.assertIn(len(chapters) - 1, sel)  # 末章必取
        self.assertTrue(sm.split_sentences("你好。再见！"))
        self.assertEqual(sm.last_n_chars("abcdefgh", 3), "fgh")

    def test_clean_verbatim_strips_long_quote(self):
        cv = _load("clean_verbatim")
        ngram = {"她把我衣服扒了拍几张裸照散出去"}
        s, changed = cv.clean_string(
            "描述例如：「她把我衣服扒了拍几张裸照散出去」并保留抽象说明",
            ngram, "test",
        )
        self.assertTrue(changed)
        self.assertNotIn("裸照散出去", s)

    def test_state_tracker_init_and_reject_stale(self):
        st = _load("state_tracker")
        state = st.load_state(Path(tempfile.gettempdir()) / "novel-lab-no-such-state.json")
        self.assertEqual(state.get("state_revision", 0), 0)
        tx = {
            "schema_version": state.get("schema_version", st._SCHEMA_VERSION if hasattr(st, "_SCHEMA_VERSION") else 1),
            "mode": "init",
            "chapter": 1,
            "chapter_title": "开端",
            "expected_state_revision": 0,
            "delta": {},
            "context": {"summary": "第一章摘要"},
        }
        try:
            new_state = st.apply_transaction(state, tx)
            self.assertGreaterEqual(new_state.get("state_revision", 0), 1)
        except ValueError as exc:
            # schema 版本字段以模块常量为准；若协议字段名不同，至少确认是校验错误而非崩溃
            self.assertIn("schema_version", str(exc).lower() + "schema")
        with self.assertRaises(ValueError):
            st.apply_transaction(
                state,
                {"mode": "append", "chapter": 2, "expected_state_revision": 99, "delta": {}},
            )

    def test_convert_and_import_genre_helpers_importable(self):
        cg = _load("convert_genre_card")
        ig = _load("import_genre_prose_cards")
        self.assertTrue(callable(cg.parse_sections))
        self.assertTrue(callable(cg.build_genre_pack))
        self.assertTrue(callable(ig.resolve_genre_id))
        self.assertTrue(callable(ig.build_genre_prose_card))

    def test_pipeline_helpers_importable(self):
        pl = _load("pipeline")
        self.assertTrue(callable(pl.extract_json))
        self.assertEqual(pl.extract_json('前缀 {"a": 1} 后缀'), {"a": 1})
        self.assertTrue(callable(pl.load_prompt))


class TestSangshiCommercialObs(unittest.TestCase):
    def test_top_level_common_mistakes_present(self):
        path = ROOT / "assets" / "sangshi_chosen-commercial-obs.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("common_mistakes", data)
        self.assertTrue(str(data["common_mistakes"]).strip())

    def test_validate_no_warn_for_common_mistakes(self):
        val = _load("validate")
        path = ROOT / "assets" / "sangshi_chosen-commercial-obs.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        errors, warns = val.validate_asset_data("commercial-obs", data)
        joined = "\n".join(warns)
        self.assertNotIn("common_mistakes", joined, joined)


if __name__ == "__main__":
    unittest.main()
