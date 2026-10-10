"""离线工具引擎与资产端点单元测试（起名工坊、毒点避雷、实操资产库）。

覆盖：
1. gui.name_generator: 角色、势力、功法、法宝生成，去重与数量边界。
2. gui.poison_checker: 7 大核心毒点检测及干净文本置信度。
3. gui.services: generate_names, scan_poison, get_goldfingers, get_hooks, get_taboos。
4. gui.router: /api/tools/* 路由分发、参数校验与响应包裹。

纯标准库，遵循铁红线与测试隔离。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import name_generator, poison_checker, services  # noqa: E402


class TestNameGenerator(unittest.TestCase):
    """起名工坊纯本地算法测试。"""

    def test_character_names_basic(self):
        names = name_generator.generate_character_names(style="xianxia", gender="male", count=10)
        self.assertEqual(len(names), 10)
        self.assertEqual(len(set(names)), 10)
        for n in names:
            self.assertGreaterEqual(len(n), 2)

    def test_character_names_gender_and_genre_variants(self):
        styles = ["xianxia", "dushi", "kehuan", "lishi", "wuxia"]
        for s in styles:
            female = name_generator.generate_character_names(style=s, gender="female", count=5)
            self.assertEqual(len(female), 5)
            neutral = name_generator.generate_character_names(style=s, gender="neutral", count=5)
            self.assertEqual(len(neutral), 5)

    def test_character_names_count_bounds(self):
        names_1 = name_generator.generate_character_names(style="xianxia", count=1)
        self.assertEqual(len(names_1), 1)
        names_50 = name_generator.generate_character_names(style="xianxia", count=50)
        self.assertEqual(len(names_50), 50)
        names_over = name_generator.generate_character_names(style="xianxia", count=100)
        self.assertEqual(len(names_over), 50)

    def test_sect_names(self):
        sects = name_generator.generate_sect_names(kind="sect", count=8)
        self.assertEqual(len(sects), 8)
        self.assertEqual(len(set(sects)), 8)

    def test_martial_art_names(self):
        skills = name_generator.generate_skill_names(count=8)
        self.assertEqual(len(skills), 8)
        self.assertEqual(len(set(skills)), 8)

    def test_artifact_names(self):
        artifacts = name_generator.generate_artifact_names(count=8)
        self.assertEqual(len(artifacts), 8)
        self.assertEqual(len(set(artifacts)), 8)

    def test_generate_unified(self):
        res = name_generator.generate(kind="character", style="xianxia", gender="all", count=5)
        self.assertEqual(res["count"], 5)
        self.assertEqual(len(res["names"]), 5)


class TestPoisonChecker(unittest.TestCase):
    """毒点避雷检测器纯本地算法测试。"""

    def test_clean_text(self):
        clean_text = "林轩运转九天玄雷诀，周身雷光炽盛，抬手一指便将挑衅的仇敌镇压在山门之下，群雄震颤。"
        res = poison_checker.check_poison(clean_text)
        self.assertEqual(res["score"], 0)
        self.assertEqual(res["total_issues"], 0)
        self.assertEqual(len(res["findings"]), 0)
        self.assertIn("安全", res["verdict"])

    def test_detect_suffering(self):
        text = "林轩任凭对方羞辱，低头不敢出声，受尽了百般刁难。"
        res = poison_checker.check_poison(text)
        self.assertGreater(res["score"], 0)
        types = [i["type"] for i in res["findings"]]
        self.assertIn("excessive_suffering", types)

    def test_detect_enemy_mercy(self):
        text = "林轩叹了口气：得饶人处且饶人，这次就放你一马，你走吧。"
        res = poison_checker.check_poison(text)
        self.assertGreater(res["score"], 0)
        types = [i["type"] for i in res["findings"]]
        self.assertIn("enemy_mercy", types)

    def test_detect_simp_behavior(self):
        text = "他甘愿做牛做马，只求你不要离开我，哪怕你多看我一眼。"
        res = poison_checker.check_poison(text)
        self.assertGreater(res["score"], 0)
        types = [i["type"] for i in res["findings"]]
        self.assertIn("simp_behavior", types)

    def test_detect_power_inconsistency(self):
        text = "刚入上界，林轩震惊地发现，元婴遍地走，曾经以为无敌的大帝如今只能守门。"
        res = poison_checker.check_poison(text)
        self.assertGreater(res["score"], 0)
        types = [i["type"] for i in res["findings"]]
        self.assertIn("power_inconsistency", types)

    def test_detect_preachy_monologue(self):
        text = "其实人生就是这样，大道理人人都懂，在这个物欲横流的社会里我们每个人都应该明白。"
        res = poison_checker.check_poison(text)
        self.assertGreater(res["score"], 0)
        types = [i["type"] for i in res["findings"]]
        self.assertIn("preachy_monologue", types)

    def test_detect_distress_trope(self):
        text = "反派冷笑道：不听劝告偷偷溜出，拿你的女人来换你的性命！"
        res = poison_checker.check_poison(text)
        self.assertGreater(res["score"], 0)
        types = [i["type"] for i in res["findings"]]
        self.assertIn("distress_trope", types)

    def test_detect_ntr_ambiguity(self):
        text = "她依偎在另一个男人怀里，眼神迷离地拉扯，毫无顾忌。"
        res = poison_checker.check_poison(text)
        self.assertGreater(res["score"], 0)
        types = [i["type"] for i in res["findings"]]
        self.assertIn("ntr_ambiguity", types)


class TestToolsServicesAndRoutes(unittest.TestCase):
    """服务层及 API 路由分发测试。"""

    def test_generate_names_service(self):
        data = services.generate_names(kind="character", style="xianxia", gender="all", count=5)
        self.assertIn("names", data)
        self.assertEqual(len(data["names"]), 5)

        sect_data = services.generate_names(kind="sect", count=3)
        self.assertEqual(len(sect_data["names"]), 3)

        skill_data = services.generate_names(kind="skill", count=3)
        self.assertEqual(len(skill_data["names"]), 3)

        artifact_data = services.generate_names(kind="artifact", count=3)
        self.assertEqual(len(artifact_data["names"]), 3)

    def test_scan_poison_service(self):
        data = services.scan_poison("林轩运转神功，一剑破万法！")
        self.assertIn("score", data)
        self.assertIn("verdict", data)
        self.assertIn("findings", data)
        self.assertEqual(data["score"], 0)

    def test_get_goldfingers_service(self):
        data = services.get_goldfingers()
        self.assertIn("goldfingers", data)
        self.assertGreaterEqual(len(data["goldfingers"]), 10)

    def test_get_hooks_service(self):
        data = services.get_hooks()
        self.assertIn("hooks", data)
        self.assertGreaterEqual(len(data["hooks"]), 8)

    def test_get_taboos_service(self):
        data = services.get_taboos()
        self.assertIn("taboos", data)
        self.assertGreaterEqual(len(data["taboos"]), 8)

    def test_router_dispatch_tools_routes(self):
        from gui import router

        # 1. GET /api/tools/names
        resp, _ = router.dispatch("GET", "/api/tools/names", {}, {"kind": "character", "style": "dushi", "count": 4})
        self.assertEqual(resp["code"], 0)
        self.assertEqual(len(resp["data"]["names"]), 4)

        # 2. POST /api/tools/poison-check
        resp, _ = router.dispatch("POST", "/api/tools/poison-check", {"text": "主角毫不留情镇压仇敌。"}, {})
        self.assertEqual(resp["code"], 0)
        self.assertIn("score", resp["data"])
        self.assertIn("verdict", resp["data"])

        # 3. GET /api/tools/goldfingers
        resp, _ = router.dispatch("GET", "/api/tools/goldfingers", {}, {})
        self.assertEqual(resp["code"], 0)
        self.assertIn("goldfingers", resp["data"])

        # 4. GET /api/tools/hooks
        resp, _ = router.dispatch("GET", "/api/tools/hooks", {}, {})
        self.assertEqual(resp["code"], 0)
        self.assertIn("hooks", resp["data"])

        # 5. GET /api/tools/taboos
        resp, _ = router.dispatch("GET", "/api/tools/taboos", {}, {})
        self.assertEqual(resp["code"], 0)
        self.assertIn("taboos", resp["data"])


if __name__ == "__main__":
    unittest.main()
