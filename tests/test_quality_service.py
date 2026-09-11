"""quality_service 单元测试（W13/W14 spec 要求）。

覆盖：check / book / resolve_chapter_target / clean_stale_scratch / 并发上限 / 路径穿越。
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import config, quality_service  # noqa: E402
from gui.services import ServiceError  # noqa: E402

_TMP = None
_SAVED = {}


def setUpModule():
    global _TMP, _SAVED
    _TMP = tempfile.mkdtemp(prefix="quality_qa_")
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
    # 测试章节目录
    ch_dir = config.NOVEL_DIR / "testproj" / "chapters"
    ch_dir.mkdir(parents=True, exist_ok=True)
    (ch_dir / "chapter-001.txt").write_text("这是第一章测试内容。" * 50, encoding="utf-8")


def tearDownModule():
    for name, value in _SAVED.items():
        setattr(config, name, value)
    if _TMP:
        shutil.rmtree(_TMP, ignore_errors=True)


class TestResolveChapterTarget(unittest.TestCase):
    def test_empty_rejected(self):
        with self.assertRaises(ServiceError):
            quality_service.resolve_chapter_target("")

    def test_nonexistent_404(self):
        with self.assertRaises(ServiceError) as cm:
            quality_service.resolve_chapter_target("no/such/path")
        self.assertEqual(cm.exception.code, 404)

    def test_path_traversal_rejected(self):
        # 绝对路径在项目外
        with self.assertRaises(ServiceError):
            quality_service.resolve_chapter_target("C:/Windows/System32")

    def test_valid_relative_path(self):
        fp = quality_service.resolve_chapter_target("testproj/chapters/chapter-001.txt")
        self.assertTrue(fp.is_file())

    def test_valid_dir(self):
        fp = quality_service.resolve_chapter_target("testproj/chapters")
        self.assertTrue(fp.is_dir())


class TestMaterializeText(unittest.TestCase):
    def test_creates_per_task_subdir(self):
        fp = quality_service._materialize_text("测试内容", "test-task-001")
        self.assertTrue(fp.is_file())
        self.assertEqual(fp.parent.name, "test-task-001")
        # 清理
        fp.unlink()
        fp.parent.rmdir()


class TestCleanStaleScratch(unittest.TestCase):
    def test_cleans_files_and_dirs(self):
        scratch = config.STATE_ROOT / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        # 旧格式文件
        (scratch / "old.txt").write_text("stale", encoding="utf-8")
        # 新格式子目录
        sub = scratch / "old-task"
        sub.mkdir(exist_ok=True)
        (sub / "input.txt").write_text("stale", encoding="utf-8")
        n = quality_service.clean_stale_scratch()
        self.assertGreaterEqual(n, 2)
        self.assertFalse((scratch / "old.txt").exists())
        self.assertFalse(sub.exists())

    def test_empty_dir_returns_zero(self):
        # 确保 scratch 目录不存在时返回 0
        scratch = config.STATE_ROOT / "scratch"
        if scratch.exists():
            import shutil
            shutil.rmtree(scratch)
        n = quality_service.clean_stale_scratch()
        self.assertEqual(n, 0)


class TestCheck(unittest.TestCase):
    def test_no_input_rejected(self):
        with self.assertRaises(ServiceError):
            quality_service.check()

    def test_check_with_text(self):
        text = "她站在教室门口。\"你来了。\"他说。她没有回答。" * 20
        r = quality_service.check(text=text, voice="voice:testbook-voice-card")
        self.assertIn("quality", r)
        self.assertIn("consistency", r)
        self.assertIn("score", r["quality"])

    def test_check_without_voice(self):
        text = "测试内容。" * 30
        r = quality_service.check(text=text)
        self.assertIn("quality", r)
        self.assertNotIn("consistency", r)


class TestBook(unittest.TestCase):
    def test_no_input_rejected(self):
        with self.assertRaises(ServiceError):
            quality_service.book()

    def test_book_with_target_dir(self):
        r = quality_service.book(target="testproj/chapters")
        self.assertIsInstance(r, dict)


class TestConcurrencyLimit(unittest.TestCase):
    def test_active_count_starts_zero(self):
        with quality_service._QUALITY_LOCK:
            quality_service._QUALITY_TASKS.clear()
        self.assertEqual(quality_service._active_quality_count(), 0)

    def test_running_task_counted(self):
        with quality_service._QUALITY_LOCK:
            quality_service._QUALITY_TASKS["q-test"] = {"status": "running"}
        self.assertEqual(quality_service._active_quality_count(), 1)
        with quality_service._QUALITY_LOCK:
            quality_service._QUALITY_TASKS.clear()

    def test_done_task_not_counted(self):
        with quality_service._QUALITY_LOCK:
            quality_service._QUALITY_TASKS["q-done"] = {"status": "done"}
        self.assertEqual(quality_service._active_quality_count(), 0)
        with quality_service._QUALITY_LOCK:
            quality_service._QUALITY_TASKS.clear()


class TestListQcReports(unittest.TestCase):
    def test_empty_reports_dir(self):
        reports = quality_service.list_qc_reports()
        self.assertIsInstance(reports, list)


if __name__ == "__main__":
    unittest.main()
