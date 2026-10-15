"""测试章节张力与黄金三章情绪波形动态分析模型（Tension & Emotion Wave Model）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import router, writing_extra
from gui.services import ServiceError


class TestWritingTensionAnalysis(unittest.TestCase):
    def test_empty_and_whitespace(self):
        """空字符串与纯空白文本返回零张力安全结构。"""
        res1 = writing_extra.analyze_tension_curve("")
        self.assertEqual(res1["tension_curve"], [0] * 10)
        self.assertEqual(res1["max_tension"], 0)
        self.assertEqual(res1["benchmark_alignment_score"], 0)
        self.assertEqual(len(res1["segments"]), 10)

        res2 = writing_extra.analyze_tension_curve("   \n\t  ")
        self.assertEqual(res2["tension_curve"], [0] * 10)

    def test_non_string_rejected(self):
        """非字符串输入直接拒绝并抛出 400。"""
        with self.assertRaises(ServiceError) as cm:
            writing_extra.analyze_tension_curve(12345)  # type: ignore[arg-type]
        self.assertEqual(cm.exception.code, 400)

    def test_high_conflict_action_text(self):
        """充满生死、决战、重击与惊叹短句的文本应产生明显高张力。"""
        text = (
            "深夜长街，杀机骤起！\n"
            "黑衣刺客长刀撕裂长空，狠厉劈向少年头颅！“受死吧！”\n"
            "狂暴的刀芒带着刺耳呼啸，鲜血瞬间染红了青石砖。少年目眦欲裂，心脏狂跳，咬牙侧身翻滚！\n"
            "砰！身后的巨石崩裂成无数碎块，剧毒烟雾弥漫四周！生死一线！"
        )
        res = writing_extra.analyze_tension_curve(text, benchmark="fast_hook", segments_count=5)
        self.assertEqual(len(res["tension_curve"]), 5)
        self.assertEqual(len(res["benchmark_curve"]), 5)
        self.assertGreater(res["max_tension"], 50)
        self.assertGreater(res["avg_tension"], 40)
        self.assertIn("黄金", res["pacing_feedback"][0])

    def test_calm_exposition_text(self):
        """舒缓铺垫与风景描写文本张力相对较低且平缓。"""
        text = (
            "清晨的阳光斜斜穿过古旧的窗棂，洒在有些斑驳的木桌上。\n"
            "茶壶里的水慢慢烧开，升腾起一缕缕白色的水雾，空气中弥漫着淡淡的茉莉清香。\n"
            "老书生安静地翻动着泛黄的书页，窗外的微风吹过庭院里的大槐树，落叶随风轻轻盘旋落在青苔上。\n"
            "远处偶尔传来两声清脆的鸟鸣，整座小镇依然沉浸在静谧安宁的清晨时光中。"
        )
        res = writing_extra.analyze_tension_curve(text, benchmark="steady", segments_count=6)
        self.assertEqual(len(res["tension_curve"]), 6)
        self.assertEqual(len(res["benchmark_curve"]), 6)
        # 平静文本平均张力应低于 45
        self.assertLess(res["avg_tension"], 45)

    def test_custom_segments_and_benchmarks(self):
        """测试不同分段数与各标杆曲线（classic/steady/face_slap）重采样。"""
        sample = "长夜漫漫，危机四伏。他拔剑而起，怒斩强敌！" * 20
        for bm in ("classic", "fast_hook", "steady", "face_slap"):
            res = writing_extra.analyze_tension_curve(sample, benchmark=bm, segments_count=7)
            self.assertEqual(len(res["segments"]), 7)
            self.assertEqual(len(res["tension_curve"]), 7)
            self.assertEqual(len(res["benchmark_curve"]), 7)
            self.assertGreaterEqual(res["benchmark_alignment_score"], 0)
            self.assertLessEqual(res["benchmark_alignment_score"], 100)

    def test_router_api(self):
        """验证 /api/writing/tension-analysis 路由与请求体校验。"""
        resp, _ = router.dispatch("POST", "/api/writing/tension-analysis", {
            "text": "刀光乍裂！敌人步步紧逼，生死关头！",
            "benchmark": "fast_hook",
            "segments_count": 8,
        }, {})
        self.assertEqual(resp["code"], 0)
        data = resp["data"]
        self.assertEqual(len(data["tension_curve"]), 8)
        self.assertEqual(len(data["benchmark_curve"]), 8)
        self.assertIn("climax_segment", data)
        self.assertIn("pacing_feedback", data)
