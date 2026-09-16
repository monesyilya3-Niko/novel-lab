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
from unittest.mock import patch

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
                 "CORPUS_DIR", "PROMPTS_DIR", "REPORTS_DIR", "CONFIG_DIR"):
        _SAVED[name] = getattr(config, name)
        setattr(config, name, config.ROOT_DIR / name.lower())
    # 派生常量同样重定向到临时根（保持与 config 中的派生关系一致）。
    for name in ("DB_PATH", "LOCK_PATH"):
        _SAVED[name] = getattr(config, name)
    config.DB_PATH = config.STATE_ROOT / "index.db"
    config.LOCK_PATH = config.STATE_ROOT / ".lock"
    # 建必要目录
    config.ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
    config.NOVEL_DIR.mkdir(parents=True, exist_ok=True)
    config.CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    config.PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
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
    # 跨书题材蒸馏卡（distilled）：meta.dimension + rules/blindspots/stats 自证。
    distilled = {
        "meta": {"dimension": "voice-card", "genre": "campus-redemption",
                 "books_count": 3, "source_books": ["书甲", "书乙", "书丙"]},
        "rules": [{
            "id": "r1", "dimension": "voice-card", "field": "句长",
            "kind": "hard", "books_count": 3, "value": "短句为主",
            "confidence": 1.0, "conflict": False, "over_generalized": False,
            "blindspot_books": [],
        }],
        "blindspots": [], "stats": {},
    }
    (config.ASSETS_ROOT / "campus-redemption-voice-card-distilled.json").write_text(
        json.dumps(distilled, ensure_ascii=False), encoding="utf-8")
    # 题材文风卡寻址索引（prose_card_index）：只有 cards 映射，不是卡片本身。
    index = {
        "_description": "题材文风卡索引：题材中文名 → id / 落库文件名。",
        "_count": 1,
        "cards": {"东方仙侠": {"id": "genre-xianxia",
                              "file": "genre-prose-card-genre-xianxia.json"}},
    }
    (config.ASSETS_ROOT / "genre-prose-card-index.json").write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8")
    # 真正的题材文风卡（prose_card 正向对照）。
    prose = {
        "meta": {"kind": "genre-prose-card", "genre": "东方仙侠"},
        "language_rules": {"sentence": "短句"},
        "prose": {"imagery": ["剑"]},
        "structure": {}, "commercial": {},
    }
    (config.ASSETS_ROOT / "genre-prose-card-genre-xianxia.json").write_text(
        json.dumps(prose, ensure_ascii=False), encoding="utf-8")


def tearDownModule():
    for name, value in _SAVED.items():
        setattr(config, name, value)
    if _TMP:
        shutil.rmtree(_TMP, ignore_errors=True)


def _assert_kind_mismatch(tc: unittest.TestCase, exc: BaseException,
                          expected: str, actual: str) -> None:
    """断言错误表达的是「内容 kind 与参数期望不符」，而非仅仅出现某个关键词。"""
    msg = str(exc)
    tc.assertIn("kind 不匹配", msg)
    tc.assertIn(f"内容自证为 {actual}", msg)
    tc.assertIn(f"不能作为 {expected} 使用", msg)


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


class TestInjectAssetKindContract(unittest.TestCase):
    """Task 6：inject 的每个资产参数只接受对应 kind；distilled 走专门参数。"""

    def test_voice_plus_distilled_param(self):
        """合法 voice + distilled 参数：两者都注入，prompt 含蒸馏规则段。"""
        r = writing_service.inject(
            voice="voice:testbook-voice-card",
            distilled="distilled:campus-redemption-voice-card-distilled")
        self.assertIn("voice", r["injected_kinds"])
        self.assertIn("distilled", r["injected_kinds"])
        self.assertIn("蒸馏规则", r["prompt"])

    def test_distilled_as_voice_rejected_400(self):
        with self.assertRaises(ServiceError) as ctx:
            writing_service.inject(voice="voice:campus-redemption-voice-card-distilled")
        self.assertEqual(ctx.exception.code, 400)
        _assert_kind_mismatch(self, ctx.exception, expected="voice", actual="distilled")

    def test_index_as_prose_card_rejected_400(self):
        with self.assertRaises(ServiceError) as ctx:
            writing_service.inject(voice="voice:testbook-voice-card",
                                   prose_card="prose_card:genre-prose-card-index")
        self.assertEqual(ctx.exception.code, 400)
        _assert_kind_mismatch(self, ctx.exception, expected="prose_card",
                              actual="prose_card_index")

    def test_real_prose_card_accepted(self):
        r = writing_service.inject(voice="voice:testbook-voice-card",
                                   prose_card="prose_card:genre-prose-card-genre-xianxia")
        self.assertIn("prose_card", r["injected_kinds"])


class TestScoringPathsRejectWrongKind(unittest.TestCase):
    """I3：score / generate / import_chapter 的 voice 也必须走 kind 校验路径。

    这三处此前直接用不校验 kind 的 ``_load_asset_json``，distilled 仍可进入
    单书评分与写作；修复后应同步 400。
    """

    DISTILLED = "voice:campus-redemption-voice-card-distilled"

    def test_score_rejects_distilled_as_voice(self):
        with self.assertRaises(ServiceError) as ctx:
            writing_service.score(voice=self.DISTILLED, text="她推门而入。" * 30)
        self.assertEqual(ctx.exception.code, 400)
        _assert_kind_mismatch(self, ctx.exception, expected="voice", actual="distilled")

    def test_generate_rejects_distilled_as_voice(self):
        # 必须 patch 模型判据：本机 config/models.json 已配置模型，未修复前 generate
        # 会带着 distilled 卡走进 LLM 分支起后台线程（联网），故此处强制降级路径。
        with patch.object(writing_service.engine_adapter,
                          "any_model_configured", return_value=False):
            with self.assertRaises(ServiceError) as ctx:
                writing_service.generate(voice=self.DISTILLED, project="kind_gate_proj",
                                         chapter_no=1, task="写一段测试")
        self.assertEqual(ctx.exception.code, 400)
        _assert_kind_mismatch(self, ctx.exception, expected="voice", actual="distilled")

    def test_import_chapter_rejects_distilled_as_voice(self):
        with self.assertRaises(ServiceError) as ctx:
            writing_service.import_chapter(project="kind_gate_proj", chapter_no=2,
                                           content="这是测试章节内容。" * 50,
                                           voice=self.DISTILLED)
        self.assertEqual(ctx.exception.code, 400)
        _assert_kind_mismatch(self, ctx.exception, expected="voice", actual="distilled")

    def test_score_valid_voice_still_works(self):
        r = writing_service.score(voice="voice:testbook-voice-card", text="她推门而入。" * 30)
        self.assertIn("consistency", r)


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
        with writing_service._WRITING_LOCK:
            writing_service._WRITING_TASKS.clear()
        self.assertEqual(writing_service._active_writing_count(), 0)

    def test_running_task_counted(self):
        with writing_service._WRITING_LOCK:
            writing_service._WRITING_TASKS["test-1"] = {"status": "running"}
        self.assertEqual(writing_service._active_writing_count(), 1)
        with writing_service._WRITING_LOCK:
            writing_service._WRITING_TASKS.clear()

    def test_scoring_and_rewriting_counted(self):
        with writing_service._WRITING_LOCK:
            writing_service._WRITING_TASKS["t-scoring"] = {"status": "scoring"}
            writing_service._WRITING_TASKS["t-rewriting"] = {"status": "rewriting"}
        self.assertEqual(writing_service._active_writing_count(), 2)
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
