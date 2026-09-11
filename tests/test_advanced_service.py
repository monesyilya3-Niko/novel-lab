"""advanced_service 单元测试（M1/M4 spec 要求）。"""
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

from gui import config, advanced_service  # noqa: E402
from gui.services import ServiceError  # noqa: E402

_TMP = None
_SAVED = {}


def setUpModule():
    global _TMP, _SAVED
    _TMP = tempfile.mkdtemp(prefix="advanced_qa_")
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
    # 测试 pass 目录
    raw_dir = config.CORPUS_DIR / "raw" / "testbook"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "pass1_structure.json").write_text("{}", encoding="utf-8")


def tearDownModule():
    for name, value in _SAVED.items():
        setattr(config, name, value)
    if _TMP:
        shutil.rmtree(_TMP, ignore_errors=True)


class TestDistillStatus(unittest.TestCase):
    def test_returns_expected_keys(self):
        r = advanced_service.distill_status("campus-redemption")
        for key in ("genre", "books", "book_count", "distilled_assets", "can_distill"):
            self.assertIn(key, r)

    def test_empty_genre_rejected(self):
        with self.assertRaises(ServiceError):
            advanced_service.distill_status("")


class TestBatchStatus(unittest.TestCase):
    def test_returns_books(self):
        r = advanced_service.batch_status()
        self.assertIn("books", r)
        self.assertIn("total", r)
        self.assertGreaterEqual(r["total"], 1)

    def test_book_has_passes(self):
        r = advanced_service.batch_status()
        book = r["books"][0]
        self.assertIn("name", book)
        self.assertIn("passes", book)
        self.assertIn("pass_count", book)
        self.assertIn("has_assets", book)


class TestUpdateAsset(unittest.TestCase):
    def test_update_nonexistent_404(self):
        with self.assertRaises(ServiceError) as ctx:
            advanced_service.update_asset("voice", "nonexistent", {"test": True})
        self.assertEqual(ctx.exception.code, 404)

    def test_update_empty_content_400(self):
        with self.assertRaises(ServiceError):
            advanced_service.update_asset("voice", "testbook-voice-card", {})

    def test_path_traversal_rejected(self):
        with self.assertRaises(ServiceError):
            advanced_service.update_asset("voice", "../../etc/passwd", {"test": True})


class TestDeleteAsset(unittest.TestCase):
    def test_delete_nonexistent_404(self):
        with self.assertRaises(ServiceError) as ctx:
            advanced_service.delete_asset("voice", "nonexistent")
        self.assertEqual(ctx.exception.code, 404)

    def test_path_traversal_rejected(self):
        with self.assertRaises(ServiceError):
            advanced_service.delete_asset("voice", "../../etc/passwd")


class TestCreateAsset(unittest.TestCase):
    def test_create_empty_name_400(self):
        with self.assertRaises(ServiceError):
            advanced_service.create_asset("", "voice", {"test": True})

    def test_create_empty_content_400(self):
        with self.assertRaises(ServiceError):
            advanced_service.create_asset("newasset", "voice", {})

    def test_create_and_delete(self):
        from unittest.mock import patch
        with patch.object(advanced_service.migrate, 'sync_asset'):
            r = advanced_service.create_asset("tmp-test-asset", "voice", {"meta": {"kind": "test"}})
            self.assertTrue(r["created"])
            # 清理
            advanced_service.delete_asset("voice", "tmp-test-asset")


class TestAggregateGenre(unittest.TestCase):
    def test_empty_genre_rejected(self):
        with self.assertRaises(ServiceError):
            advanced_service.aggregate_genre("")

    def test_insufficient_books(self):
        with self.assertRaises(ServiceError) as ctx:
            advanced_service.aggregate_genre("campus-redemption")
        # 只有 1 本书，需要 >=3
        self.assertIn("聚合需要", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
