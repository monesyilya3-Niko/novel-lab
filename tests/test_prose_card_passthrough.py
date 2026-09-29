"""prose_card 请求透传独立回归（2026-09-29 补齐）。

锁定链路：POST /api/writing/inject 的 ``prose_card`` 字段必须原样透传给
``writing_service.inject(prose_card=...)``，不得被改名、丢弃或错塞进其他参数。
此前只有「inject 整体可用」测试（test_phase2_api），无 prose_card 专项断言。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestProseCardPassthrough(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gui import config
        cls._saved = {"ROOT_DIR": config.ROOT_DIR, "ASSETS_ROOT": config.ASSETS_ROOT}
        cls._tmp = Path(tempfile.mkdtemp(prefix="prose_passthrough_"))
        config.ROOT_DIR = cls._tmp
        # _load_asset_json 按 config.ASSETS_ROOT 实时解析资产文件。
        config.ASSETS_ROOT = cls._tmp / "assets"

    @classmethod
    def tearDownClass(cls):
        from gui import config
        for k, v in cls._saved.items():
            setattr(config, k, v)

    def _dispatch(self, body):
        from gui import router
        from gui.services import ServiceError
        try:
            resp, _ct = router.dispatch("POST", "/api/writing/inject", body, {})
            return resp
        except ServiceError as exc:
            return {"code": exc.code, "message": str(exc), "data": None}

    def test_prose_card_passed_through_verbatim(self):
        """router 必须把 prose_card 原值交给 writing_service.inject。"""
        from gui import writing_service
        with patch.object(writing_service, "inject",
                          return_value={"ok": True}) as m:
            resp = self._dispatch({"voice": "voice:whatever",
                                   "prose_card": "prose_card:genre-dushi-richang"})
            self.assertEqual(resp["code"], 0)
            m.assert_called_once()
            kwargs = m.call_args.kwargs
            self.assertEqual(kwargs.get("prose_card"),
                             "prose_card:genre-dushi-richang")

    def test_prose_card_absent_stays_none(self):
        """不带 prose_card 的请求透传为 None（不凭空捏造默认值）。"""
        from gui import writing_service
        with patch.object(writing_service, "inject",
                          return_value={"ok": True}) as m:
            resp = self._dispatch({"voice": "voice:whatever"})
            self.assertEqual(resp["code"], 0)
            m.assert_called_once()
            self.assertIsNone(m.call_args.kwargs.get("prose_card"))

    def test_prose_card_reaches_prompt(self):
        """端到端：真实 inject() 下 prose_card 进入 injected_kinds。"""
        import json
        from gui import config, writing_service
        assets = config.ROOT_DIR / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        vc = {"meta": {"title": "T", "genre": "campus-redemption", "confidence": 0.9,
                       "kind": "voice-card"}}
        pc = {"meta": {"title": "P", "genre": "campus-redemption",
                       "kind": "genre-prose-card", "id": "genre-test"}}
        (assets / "t-voice-card.json").write_text(
            json.dumps(vc, ensure_ascii=False), encoding="utf-8")
        (assets / "genre-prose-card-test.json").write_text(
            json.dumps(pc, ensure_ascii=False), encoding="utf-8")
        out = writing_service.inject(
            voice="voice:t-voice-card",
            prose_card="prose_card:genre-prose-card-test")
        self.assertIn("prose_card", out["injected_kinds"])


if __name__ == "__main__":
    unittest.main()
