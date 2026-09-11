"""system_service 单元测试（M5 spec 要求）。"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import config, system_service  # noqa: E402
from gui.services import ServiceError  # noqa: E402

_TMP = None
_SAVED = {}


def setUpModule():
    global _TMP, _SAVED
    _TMP = tempfile.mkdtemp(prefix="system_qa_")
    _SAVED["ROOT_DIR"] = config.ROOT_DIR
    config.ROOT_DIR = Path(_TMP)
    for name in ("STATE_ROOT", "STATE_JSON_DIR", "ASSETS_ROOT", "NOVEL_DIR",
                 "CORPUS_DIR", "REPORTS_DIR"):
        _SAVED[name] = getattr(config, name)
        setattr(config, name, config.ROOT_DIR / name.lower())
    config.ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
    config.NOVEL_DIR.mkdir(parents=True, exist_ok=True)
    config.CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    # 测试 voice-card
    vc = {
        "meta": {"title": "测试书", "genre": "campus-redemption", "confidence": 0.9},
        "narration": {"pov": "third_limited"},
        "dialogue": {"character_voices": []},
        "emotion_handling": {"mode": "体感"},
        "banned": {"never_used_words": []},
    }
    (config.ASSETS_ROOT / "testbook-voice-card.json").write_text(
        json.dumps(vc, ensure_ascii=False), encoding="utf-8")


def tearDownModule():
    for name, value in _SAVED.items():
        setattr(config, name, value)
    if _TMP:
        shutil.rmtree(_TMP, ignore_errors=True)


class TestSystemStatus(unittest.TestCase):
    def test_returns_expected_keys(self):
        r = system_service.system_status()
        for key in ("disk", "counts", "model", "paths", "python"):
            self.assertIn(key, r)

    def test_counts_assets(self):
        r = system_service.system_status()
        self.assertGreaterEqual(r["counts"]["assets"], 1)


class TestComplianceScan(unittest.TestCase):
    def test_scan_all(self):
        r = system_service.compliance_scan()
        self.assertIn("results", r)
        self.assertIn("summary", r)
        self.assertGreaterEqual(r["summary"]["total"], 1)

    def test_scan_single_asset(self):
        r = system_service.compliance_scan(voice="voice:testbook-voice-card")
        self.assertEqual(len(r["results"]), 1)
        self.assertEqual(r["results"][0]["name"], "testbook-voice-card")

    def test_scan_nonexistent_404(self):
        with self.assertRaises(ServiceError) as ctx:
            system_service.compliance_scan(voice="voice:nonexistent")
        self.assertEqual(ctx.exception.code, 404)

    def test_scan_path_traversal_rejected(self):
        with self.assertRaises(ServiceError):
            system_service.compliance_scan(voice="voice:../../etc/passwd")


class TestModelInfo(unittest.TestCase):
    def test_returns_configured_flag(self):
        r = system_service.model_info()
        self.assertIn("configured", r)
        self.assertIn("models", r)
        self.assertIn("note", r)


class TestSettings(unittest.TestCase):
    def test_get_settings(self):
        r = system_service.get_settings()
        for key in ("port", "batch_size", "thresholds", "writing", "paths", "env_overrides"):
            self.assertIn(key, r)

    def test_update_thresholds(self):
        r = system_service.update_settings({"thresholds": {"consistency_target": 85}})
        self.assertEqual(r["thresholds"]["consistency_target"], 85)

    def test_update_writing(self):
        r = system_service.update_settings({"writing": {"default_words": 3000}})
        self.assertEqual(r["writing"]["default_words"], 3000)

    def test_invalid_threshold_rejected(self):
        with self.assertRaises(ServiceError):
            system_service.update_settings({"thresholds": {"consistency_target": 150}})

    def test_invalid_words_rejected(self):
        with self.assertRaises(ServiceError):
            system_service.update_settings({"writing": {"default_words": 50}})

    def test_reset_settings(self):
        system_service.update_settings({"thresholds": {"consistency_target": 80}})
        r = system_service.reset_settings()
        self.assertEqual(r["thresholds"]["consistency_target"], 90)  # default


if __name__ == "__main__":
    unittest.main()
