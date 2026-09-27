#!/usr/bin/env python3
"""P0-4 回归：题材必填＋后端以注册表为唯一来源校验。

覆盖：
  1. engine_adapter.known_genres() 与 scripts/genre_registry 同源（非手写副本）。
  2. engine_adapter.is_known_genre：已知/未知/空/非字符串。
  3. services.start_analysis：未知题材 → ServiceError(400)；已知题材才放行
     （用 mock 绕过模型配置检查，只验证题材校验层）。
  4. router GET /api/genres 返回题材列表。

用法：python run_tests.py
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gui import engine_adapter  # noqa: E402
from gui.services import ServiceError  # noqa: E402


class TestGenreAdapter(unittest.TestCase):
    def test_known_genres_matches_registry(self):
        from scripts import genre_registry
        self.assertEqual(
            set(engine_adapter.known_genres()),
            set(genre_registry.known_genres()),
            "engine_adapter.known_genres 必须与 scripts/genre_registry 同源",
        )

    def test_known_genres_nonempty_sorted(self):
        gs = engine_adapter.known_genres()
        self.assertGreater(len(gs), 0)
        self.assertEqual(gs, sorted(gs))

    def test_is_known_genre(self):
        self.assertTrue(engine_adapter.is_known_genre("campus-redemption"))
        self.assertFalse(engine_adapter.is_known_genre("不存在的题材"))
        self.assertFalse(engine_adapter.is_known_genre(""))
        self.assertFalse(engine_adapter.is_known_genre("   "))
        self.assertFalse(engine_adapter.is_known_genre(None))  # type: ignore[arg-type]
        self.assertFalse(engine_adapter.is_known_genre(123))  # type: ignore[arg-type]


class TestStartAnalysisGenreValidation(unittest.TestCase):
    """start_analysis 的题材校验（mock 掉书籍与模型检查，聚焦题材层）。"""

    def _call(self, genre):
        from gui import services
        with mock.patch.object(services, "_get_book_or_raise", return_value={"book_id": "b"}), \
             mock.patch.object(engine_adapter, "any_model_configured", return_value=True), \
             mock.patch.object(services, "state_store") as mock_store, \
             mock.patch.object(services, "_runtime_lock"):
            mock_store.load_state.return_value = {}
            try:
                services.start_analysis("b", genre)
            except ServiceError as e:
                return e.code
            return 200

    def test_unknown_genre_400(self):
        self.assertEqual(self._call("未知"), 400)

    def test_empty_genre_400(self):
        self.assertEqual(self._call(""), 400)

    def test_known_genre_passes_validation(self):
        # 题材校验通过后，会因缺少真实运行时状态而走其他分支，
        # 但绝不应是 400（题材错误）。
        from gui import services
        with mock.patch.object(services, "_get_book_or_raise", return_value={"book_id": "b"}), \
             mock.patch.object(engine_adapter, "any_model_configured", return_value=True):
            try:
                services.start_analysis("b", "campus-redemption")
            except ServiceError as e:
                self.assertNotEqual(e.code, 400, f"已知题材不应 400: {e}")
            except Exception:
                pass  # 其他异常（线程/状态）与题材校验无关


class TestGenresEndpoint(unittest.TestCase):
    def test_get_genres(self):
        from gui.router import _h_genres
        resp = _h_genres({}, {})
        self.assertEqual(resp["code"], 0)
        genres = resp["data"]["genres"]
        self.assertIn("campus-redemption", genres)
        self.assertEqual(genres, sorted(genres))


if __name__ == "__main__":
    unittest.main()
