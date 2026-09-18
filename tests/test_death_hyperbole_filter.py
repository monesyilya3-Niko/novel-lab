#!/usr/bin/env python3
"""
logic_check 死亡词夸张用法过滤回归（2026-09-18）。

背景：《暮冬念春》Ch3「我饿死了」与角色名相邻，被误判为角色死亡，
导致 state_contradiction critical 假阳性。
"""
import importlib.util
import sys
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


LC = _load("logic_check")


class TestHyperbolicDeathFilter(unittest.TestCase):
    def test_starving_not_death(self):
        text = "温霜禾接过抹布，“你不去吃饭？”“去啊，我饿死了。”周敏背上书包。"
        self.assertFalse(LC._name_near_death("温霜禾", text))
        self.assertFalse(LC._name_near_death("周敏", text))

    def test_real_death_still_detected(self):
        text = "温霜禾站在雨里。江春屿死了。她没有哭。"
        self.assertTrue(LC._name_near_death("江春屿", text))
        self.assertTrue(LC._name_near_death("温霜禾", text))  # 邻近窗口内真实死亡词

    def test_tired_hyped_not_death(self):
        text = "林悦说：“今天累死了，不想动。”"
        self.assertFalse(LC._name_near_death("林悦", text))

    def test_died_of_laughter_not_death(self):
        text = "周敏笑死了，趴在桌上。"
        self.assertFalse(LC._name_near_death("周敏", text))

    def test_deceased_still_death(self):
        text = "大姨说他父亲去世了。"
        self.assertTrue(LC._name_near_death("大姨", text) or LC._name_near_death("父亲", text))

    def test_grandmother_death_not_male_lead(self):
        """「外婆去世」出现在谈论江春屿的段落，不得判江春屿死亡。"""
        text = "她记得江春屿说过，外婆是他最亲的人。外婆去世以后，他就只剩一个人。"
        self.assertFalse(LC._name_near_death("江春屿", text))


class TestStateCheckNoFalsePositive(unittest.TestCase):
    def test_starving_scene_no_state_issue(self):
        texts = {
            3: "中午教室。温霜禾接过抹布。周敏说：“去啊，我饿死了。”",
            32: "温霜禾走在走廊上，开口和同学说话。",
        }
        entities = {"characters": [{"name": "温霜禾", "aliases": []}]}
        issues = [i for i in LC._check_state_contradictions(texts, entities)
                  if i["type"] == "state_contradiction"]
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
