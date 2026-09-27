#!/usr/bin/env python3
"""第三方许可证归因守卫（2026-09-27 企业级整改 P0-3）。

覆盖：
  1. 上游许可证副本存在且为逐字 MIT 文本（含正确版权行）。
  2. THIRD_PARTY_NOTICES.md 与磁盘资产逐张对应（清单不得漂移）。
  3. 每张 genre-prose-card 的 provenance 三要素齐备且取值一致。
  4. validate.py 的 provenance 硬校验真实生效（正向放行 + 负向报错）。
  5. prose.sections 为指导性文本而非原文片段的实测边界。

用法：python run_tests.py
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
ASSETS = ROOT / "assets"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


VALIDATE = _load("validate")

UPSTREAM = "zenstory-ai/oh-story-claudecode"
COPYRIGHT = "Copyright (c) 2025-2026 oh-story-claudecode"
LICENSE_COPY = ROOT / "LICENSES" / "oh-story-claudecode" / "LICENSE"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"

PROSE_FILES = sorted(
    p for p in ASSETS.glob("genre-prose-card-*.json") if p.name != "genre-prose-card-index.json"
)


def _card(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _prose_card(**overrides):
    """最小合法 prose 卡；overrides 传 None 表示删除该 provenance 字段。"""
    prov = {"source": UPSTREAM, "license": "MIT", "copyright": COPYRIGHT, "verified": False}
    for key, value in overrides.items():
        if value is None:
            prov.pop(key, None)
        else:
            prov[key] = value
    return {
        "meta": {"kind": "genre-prose-card", "id": "genre-xianxia", "name": "测试题材",
                 "confidence": 0.8, "provenance": prov},
        "language_rules": {"forbidden_elements": []},
        "prose": {"sections": {"开场抓手": "从门规压力切入。"}},
    }


def _prov_errors(data):
    VALIDATE.validate_genre_prose_card(data)
    return [e for e in VALIDATE.ERRORS if "provenance" in e]


class TestLicenseCopy(unittest.TestCase):
    def test_upstream_license_present(self):
        self.assertTrue(LICENSE_COPY.is_file(), f"缺少上游许可证副本 {LICENSE_COPY}")

    def test_license_is_verbatim_mit(self):
        text = LICENSE_COPY.read_text(encoding="utf-8")
        self.assertIn("MIT License", text)
        self.assertIn(COPYRIGHT, text)
        # MIT 实质性条款，缺失即说明副本被改写
        self.assertIn("Permission is hereby granted, free of charge", text)
        self.assertIn("THE SOFTWARE IS PROVIDED", text)
        self.assertIn("WITHOUT WARRANTY OF ANY KIND", text)


class TestNoticesDocument(unittest.TestCase):
    def test_notices_file_exists(self):
        self.assertTrue(NOTICES.is_file(), "缺少 THIRD_PARTY_NOTICES.md")

    def test_notices_lists_every_prose_card(self):
        """清单必须逐张覆盖磁盘上的卡——新增卡不登记即失败（防清单漂移）。"""
        text = NOTICES.read_text(encoding="utf-8")
        missing = [p.name for p in PROSE_FILES if f"assets/{p.name}" not in text]
        self.assertEqual(missing, [], f"以下资产未登记进 THIRD_PARTY_NOTICES.md: {missing}")

    def test_notices_declares_upstream_and_copyright(self):
        text = NOTICES.read_text(encoding="utf-8")
        self.assertIn(UPSTREAM, text)
        self.assertIn(COPYRIGHT, text)
        self.assertIn("LICENSES/oh-story-claudecode/LICENSE", text)

    def test_notices_states_verification_evidence(self):
        """归因必须写清核实方式，不能只照抄资产自报字段。"""
        text = NOTICES.read_text(encoding="utf-8")
        self.assertIn("核实方式", text)
        self.assertIn("1081", text)


class TestProvenanceFields(unittest.TestCase):
    def test_all_cards_carry_full_attribution(self):
        bad = []
        for path in PROSE_FILES:
            prov = (_card(path).get("meta") or {}).get("provenance") or {}
            for key in ("source", "license", "copyright"):
                value = prov.get(key)
                if not isinstance(value, str) or not value.strip():
                    bad.append((path.name, key))
        self.assertEqual(bad, [], f"provenance 归因缺失: {bad}")

    def test_attribution_values_are_consistent(self):
        drift = []
        for path in PROSE_FILES:
            prov = (_card(path).get("meta") or {}).get("provenance") or {}
            got = (prov.get("source"), prov.get("license"), prov.get("copyright"))
            if got != (UPSTREAM, "MIT", COPYRIGHT):
                drift.append((path.name, got))
        self.assertEqual(drift, [], f"归因取值不一致: {drift}")

    def test_verified_stays_false_until_content_reviewed(self):
        """verified 语义是内容级核验；许可证已核验不代表内容已核验。"""
        wrong = [p.name for p in PROSE_FILES
                 if (_card(p).get("meta") or {}).get("provenance", {}).get("verified")
                 is not False]
        self.assertEqual(wrong, [], f"以下卡片 verified 非 false，需先完成内容级复核: {wrong}")

    def test_sections_are_guidance_not_verbatim_prose(self):
        """实测各节为 37–84 字指导文本；500 字宽松上限守住「不含原文片段」这一前提。"""
        offenders = []
        for path in PROSE_FILES:
            sections = (_card(path).get("prose") or {}).get("sections") or {}
            for key, value in sections.items():
                if isinstance(value, str) and len(value) > 500:
                    offenders.append((path.name, key, len(value)))
        self.assertEqual(offenders, [],
                         f"出现超长节，需人工复核是否混入第三方原文: {offenders}")


class TestValidateProvenanceGuard(unittest.TestCase):
    def test_guard_is_not_vacuous(self):
        """基线：归因齐备不得报 provenance 错误（否则下面四条负向断言全部空转）。"""
        self.assertEqual(_prov_errors(_prose_card()), [],
                         f"归因齐备却被报错，校验逻辑有误: {VALIDATE.ERRORS}")

    def test_missing_provenance_is_error(self):
        data = _prose_card()
        del data["meta"]["provenance"]
        self.assertTrue(_prov_errors(data), "provenance 缺失未被拒绝")

    def test_missing_copyright_is_error(self):
        self.assertTrue(_prov_errors(_prose_card(copyright=None)), "copyright 缺失未被拒绝")

    def test_missing_source_is_error(self):
        self.assertTrue(_prov_errors(_prose_card(source=None)), "source 缺失未被拒绝")

    def test_blank_copyright_is_error(self):
        self.assertTrue(_prov_errors(_prose_card(copyright="   ")), "空白 copyright 未被拒绝")


if __name__ == "__main__":
    unittest.main(verbosity=2)
