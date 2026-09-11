"""阶段二 API 集成测试（W15 spec 要求）。

覆盖：13 个新端点走 router.dispatch + 错误包裹。
延迟 import router 避免模块级副作用。
"""
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

_TMP = None
_SAVED = {}


def setUpModule():
    global _TMP, _SAVED
    from gui import config
    _TMP = tempfile.mkdtemp(prefix="phase2_api_")
    _SAVED["ROOT_DIR"] = config.ROOT_DIR
    config.ROOT_DIR = Path(_TMP)
    for name in ("STATE_ROOT", "STATE_JSON_DIR", "ASSETS_ROOT", "NOVEL_DIR",
                 "CORPUS_DIR", "PROMPTS_DIR", "REPORTS_DIR"):
        _SAVED[name] = getattr(config, name)
        setattr(config, name, config.ROOT_DIR / name.lower())
    config.ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
    config.NOVEL_DIR.mkdir(parents=True, exist_ok=True)
    config.CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    config.PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
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
    from gui import config
    for name, value in _SAVED.items():
        setattr(config, name, value)
    if _TMP:
        shutil.rmtree(_TMP, ignore_errors=True)


def _dispatch(method, path, body=None, query=None):
    from gui import router
    from gui.services import ServiceError
    try:
        resp, _ct = router.dispatch(method, path, body or {}, query or {})
        return resp
    except ServiceError as exc:
        return {"code": exc.code, "message": str(exc), "data": None}


class TestRouteRegistration(unittest.TestCase):
    def test_13_new_routes_registered(self):
        from gui import router
        new_routes = [r for r in router.ROUTES
                      if '/api/writing/' in r[1].pattern or '/api/quality/' in r[1].pattern]
        self.assertEqual(len(new_routes), 13, f"Expected 13 routes, got {len(new_routes)}")


class TestWritingEndpoints(unittest.TestCase):
    def test_projects(self):
        resp = _dispatch('GET', '/api/writing/projects')
        self.assertEqual(resp['code'], 0)
        self.assertIsInstance(resp['data'], list)

    def test_inject(self):
        resp = _dispatch('POST', '/api/writing/inject',
                         {'voice': 'voice:testbook-voice-card'})
        self.assertEqual(resp['code'], 0)
        self.assertIn('prompt', resp['data'])
        self.assertGreater(resp['data']['char_count'], 0)

    def test_inject_missing_voice_400(self):
        resp = _dispatch('POST', '/api/writing/inject', {})
        self.assertEqual(resp['code'], 400)

    def test_generate_missing_voice_400(self):
        resp = _dispatch('POST', '/api/writing/generate', {
            'project': 'apitest', 'chapter_no': 1, 'task': '测试',
        })
        self.assertEqual(resp['code'], 400)

    def test_score(self):
        resp = _dispatch('POST', '/api/writing/score', {
            'voice': 'voice:testbook-voice-card',
            'text': '测试内容。' * 30,
        })
        self.assertEqual(resp['code'], 0)
        self.assertIn('consistency', resp['data'])
        self.assertIn('quality', resp['data'])

    def test_assemble_empty_genre_400(self):
        resp = _dispatch('POST', '/api/writing/assemble', {'name': 'x', 'genre': ''})
        self.assertEqual(resp['code'], 400)

    def test_assemble_candidates(self):
        resp = _dispatch('GET', '/api/writing/assemble-candidates')
        self.assertEqual(resp['code'], 0)
        self.assertIsInstance(resp['data'], list)

    def test_task_not_found_404(self):
        resp = _dispatch('GET', '/api/writing/tasks/nonexistent')
        self.assertEqual(resp['code'], 404)


class TestQualityEndpoints(unittest.TestCase):
    def test_check(self):
        resp = _dispatch('POST', '/api/quality/check', {
            'text': '测试内容。' * 30,
            'voice': 'voice:testbook-voice-card',
        })
        self.assertEqual(resp['code'], 0)

    def test_check_no_input_400(self):
        resp = _dispatch('POST', '/api/quality/check', {})
        self.assertEqual(resp['code'], 400)

    def test_reports(self):
        resp = _dispatch('GET', '/api/quality/reports')
        self.assertEqual(resp['code'], 0)
        self.assertIsInstance(resp['data'], list)

    def test_task_not_found_404(self):
        resp = _dispatch('GET', '/api/quality/tasks/nonexistent')
        self.assertEqual(resp['code'], 404)
