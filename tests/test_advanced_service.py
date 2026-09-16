"""advanced_service 单元测试（M1/M4 spec 要求）。"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock

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


class TestDistillRunGateError(unittest.TestCase):
    """I-1 回归：写盘门禁的 ``ValueError`` 必须转成 400 可读错误，而不是裸 500。

    ``distill.run_distill`` 在门禁失败时抛 ``ValueError``；修复前服务层不捕获，
    异常一路冒到路由层变成 500，用户只看到「服务器内部错误」，看不到门禁诊断文本。
    """

    GENRE = "gate-fail-genre"

    @classmethod
    def setUpClass(cls):
        # 该题材需要 ≥2 本书才会走到 run_distill（否则先被「书数不足」拦下）。
        for book in ("gatebook_a", "gatebook_b"):
            (config.ASSETS_ROOT / f"{book}-voice-card.json").write_text(
                json.dumps({"meta": {"source_title": book, "genre": cls.GENRE}},
                           ensure_ascii=False),
                encoding="utf-8",
            )

    def test_gate_value_error_becomes_service_error_400(self):
        from unittest.mock import patch

        gate_message = (
            "distilled 写盘门禁失败（未写入任何文件）：\n"
            "[craft-card] 数组至少 1 项，实际 0 项 (meta.source_books)"
        )
        # 用桩模块替换 sys.modules["distill"]：服务层函数内的 ``import distill``
        # 会命中它。**不 import 真实的 distill**——否则会把 ``distill`` 与当时那份
        # ``validate`` 绑定死在 sys.modules 里，破坏 test_distill_gate 对
        # 「门禁与断言共享同一个 validate 实例」的前置断言。
        stub = types.ModuleType("distill")
        stub.run_distill = Mock(side_effect=ValueError(gate_message))

        with patch.dict(sys.modules, {"distill": stub}):
            with self.assertRaises(ServiceError) as ctx:
                advanced_service.distill_genre(self.GENRE)

        self.assertEqual(ctx.exception.code, 400, "门禁失败应是客户端可见的 400")
        self.assertIn("写盘门禁失败", str(ctx.exception), "错误文本应保留门禁诊断")
        stub.run_distill.assert_called_once()

    def test_illegal_genre_still_service_error_400(self):
        """既有契约不回退：非法 genre 仍是 400（不因新捕获分支变成 500）。"""
        with self.assertRaises(ServiceError) as ctx:
            advanced_service.distill_genre("../evil")
        self.assertEqual(ctx.exception.code, 400)


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
