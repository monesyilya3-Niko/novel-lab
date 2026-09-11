"""writing_service 单元测试（W11/W12 spec 要求）。

覆盖：inject / score / assemble / list_projects / import_chapter / 降级 / 并发上限 / 路径穿越。
纯标准库 unittest，隔离真实目录。
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import config, writing_service  # noqa: E402
from gui.services import ServiceError  # noqa: E402

_TMP = None
_SAVED = {}


def setUpModule():
    global _TMP, _SAVED
    _TMP = tempfile.mkdtemp(prefix="writing_qa_")
    # ROOT_DIR 是临时根，其它路径必须是 ROOT_DIR 的子目录（代码中 relative_to 依赖此关系）
    _SAVED["ROOT_DIR"] = config.ROOT_DIR
    config.ROOT_DIR = Path(_TMP)
    for name in ("STATE_ROOT", "STATE_JSON_DIR", "ASSETS_ROOT", "NOVEL_DIR",
                 "CORPUS_DIR", "PROMPTS_DIR", "REPORTS_DIR"):
        _SAVED[name] = getattr(config, name)
        setattr(config, name, config.ROOT_DIR / name.lower())
    # 建必要目录
    config.ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
    config.NOVEL_DIR.mkdir(parents=True, exist_ok=True)
    config.CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    config.PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    # 写一个测试 voice-card
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


class TestSanitizeProject(unittest.TestCase):
    def test_empty_rejected(self):
        with self.assertRaises(ServiceError):
            writing_service._sanitize_project("")

    def test_default_rejected(self):
        with self.assertRaises(ServiceError):
            writing_service._sanitize_project("default")

    def test_path_traversal_rejected(self):
        for bad in ("../evil", "a/b", "a\\b", "..", "a\x00b"):
            with self.assertRaises(ServiceError):
                writing_service._sanitize_project(bad)

    def test_valid_name_passes(self):
        self.assertEqual(writing_service._sanitize_project("mybook"), "mybook")


class TestLoadAssetJson(unittest.TestCase):
    def test_missing_colon_rejected(self):
        with self.assertRaises(ServiceError):
            writing_service._load_asset_json("no-colon")

    def test_path_traversal_rejected(self):
        for bad in ("voice:../../etc/passwd", "voice:..\\..\\secret", "voice:a/b"):
            with self.assertRaises(ServiceError):
                writing_service._load_asset_json(bad)

    def test_nonexistent_asset_404(self):
        with self.assertRaises(ServiceError) as cm:
            writing_service._load_asset_json("voice:nonexistent_book")
        self.assertEqual(cm.exception.code, 404)

    def test_valid_asset_loads(self):
        data = writing_service._load_asset_json("voice:testbook-voice-card")
        self.assertIn("meta", data)


class TestListProjects(unittest.TestCase):
    def test_default_always_present(self):
        projects = writing_service.list_projects()
        ids = [p["id"] for p in projects]
        self.assertIn("default", ids)
        # default 必须是只读
        default = next(p for p in projects if p["id"] == "default")
        self.assertTrue(default["read_only"])

    def test_project_dir_detected(self):
        proj = config.NOVEL_DIR / "myproj_ls"
        proj.mkdir(parents=True, exist_ok=True)
        projects = writing_service.list_projects()
        ids = [p["id"] for p in projects]
        self.assertIn("myproj_ls", ids)
        self.assertIn("default", ids)


class TestScore(unittest.TestCase):
    def test_no_input_rejected(self):
        with self.assertRaises(ServiceError):
            writing_service.score(voice="voice:testbook-voice-card")

    def test_score_with_text(self):
        text = "她站在教室门口。\"你来了。\"他说。她没有回答。"
        r = writing_service.score(voice="voice:testbook-voice-card", text=text)
        self.assertIn("consistency", r)
        self.assertIn("quality", r)
        self.assertIn("verdict", r)
        self.assertIn("score", r["consistency"])
        self.assertIn("dims", r["consistency"])

    def test_chapter_path_outside_novel_rejected(self):
        with self.assertRaises(ServiceError):
            writing_service.score(
                voice="voice:testbook-voice-card",
                chapter_path="C:/Windows/System32/drivers/etc/hosts")


class TestImportChapter(unittest.TestCase):
    def test_default_project_rejected(self):
        with self.assertRaises(ServiceError):
            writing_service.import_chapter(project="default", chapter_no=1, content="test")

    def test_empty_content_rejected(self):
        with self.assertRaises(ServiceError):
            writing_service.import_chapter(project="myproj", chapter_no=1, content="")

    def test_valid_import(self):
        r = writing_service.import_chapter(
            project="testproj", chapter_no=1, content="这是测试章节内容。" * 50,
            voice="voice:testbook-voice-card")
        self.assertIn("chapter_path", r)
        self.assertIn("consistency_score", r)
        self.assertIn("quality_score", r)


class TestAssemble(unittest.TestCase):
    def test_empty_genre_rejected(self):
        with self.assertRaises(ServiceError):
            writing_service.assemble(name="any", genre="")

    def test_path_traversal_name_rejected(self):
        with self.assertRaises(ServiceError):
            writing_service.assemble(name="../evil", genre="campus-redemption")

    def test_nonexistent_book_404(self):
        with self.assertRaises(ServiceError) as cm:
            writing_service.assemble(name="no_such_book", genre="campus-redemption")
        self.assertEqual(cm.exception.code, 404)


class TestGenerateDegraded(unittest.TestCase):
    """无模型时 generate 应同步返回降级指引。"""

    def test_no_model_degraded(self):
        with patch.object(writing_service.engine_adapter, "any_model_configured", return_value=False):
            r = writing_service.generate(
                voice="voice:testbook-voice-card", project="degrade_test",
                chapter_no=1, task="写一段测试")
            self.assertEqual(r["status"], "degraded")
            self.assertEqual(r["mode"], "no_model")
            self.assertIn("prompt", r)
            self.assertIn("guide_markdown", r)


class TestConcurrencyLimit(unittest.TestCase):
    def test_active_count_starts_zero(self):
        # 清空任务注册表
        with writing_service._WRITING_LOCK:
            writing_service._WRITING_TASKS.clear()
        self.assertEqual(writing_service._active_writing_count(), 0)

    def test_running_task_counted(self):
        with writing_service._WRITING_LOCK:
            writing_service._WRITING_TASKS["test-1"] = {"status": "running"}
        self.assertEqual(writing_service._active_writing_count(), 1)
        with writing_service._WRITING_LOCK:
            writing_service._WRITING_TASKS.clear()

    def test_done_task_not_counted(self):
        with writing_service._WRITING_LOCK:
            writing_service._WRITING_TASKS["test-2"] = {"status": "done"}
        self.assertEqual(writing_service._active_writing_count(), 0)
        with writing_service._WRITING_LOCK:
            writing_service._WRITING_TASKS.clear()


if __name__ == "__main__":
    unittest.main()
