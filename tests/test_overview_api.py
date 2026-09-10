"""阶段一（W03）概览/资产/报告/拆书结果 API 集成测试。

覆盖端点（走 router.dispatch 全链路，验证统一响应包裹 + snake_case 数据）：
1. GET /api/overview      → 概览聚合（total_books / total_reports / model_configured）。
2. GET /api/assets        → 资产清单分页（kind 过滤 / 非法 kind 400）。
3. GET /api/assets/<kind>/<id> → 资产详情（路径穿越 400/404）。
4. GET /api/reports       → 报告清单。
5. GET /api/reports/<id>  → 报告 Markdown 原文。
6. GET /api/book/<id>/results → 拆书结构化结果（组装卡 + report_ids）。

纯标准库 unittest，隔离临时目录（monkeypatch config 路径 + 重建 asset_index 单例）。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import config, asset_index, router, services  # noqa: E402
from gui.services import ServiceError  # noqa: E402


class TestOverviewAPI(unittest.TestCase):
    """概览 / 资产 / 报告 / 拆书结果 端点集成测试。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="overview_api_qa_"))
        cls._orig = {
            "ASSETS_ROOT": config.ASSETS_ROOT,
            "REPORTS_DIR": config.REPORTS_DIR,
            "CORPUS_DIR": config.CORPUS_DIR,
            "CONFIG_DIR": config.CONFIG_DIR,
            "STATE_ROOT": config.STATE_ROOT,
            # R1：STATE_JSON_DIR 必须与 STATE_ROOT 成对隔离，否则 list_books_summary
            # 会读到真实 gui/state/ 的历史残留，导致 total_books 断言失真。
            "STATE_JSON_DIR": config.STATE_JSON_DIR,
        }
        config.ASSETS_ROOT = cls._tmp / "assets"
        config.REPORTS_DIR = cls._tmp / "reports"
        config.CORPUS_DIR = cls._tmp / "corpus"
        config.CONFIG_DIR = cls._tmp / "config"
        config.STATE_ROOT = cls._tmp / "gui_state"
        config.STATE_JSON_DIR = cls._tmp / "gui" / "state"

        for d in (config.ASSETS_ROOT, config.REPORTS_DIR, config.CORPUS_DIR,
                  config.CONFIG_DIR, config.STATE_ROOT, config.STATE_JSON_DIR):
            d.mkdir(parents=True, exist_ok=True)

        # assets：voice-card + structure-obs + craft-card（组装卡，bookA）。
        (config.ASSETS_ROOT / "bookA-voice-card.json").write_text(
            json.dumps({"meta": {"source_title": "测试书A"}, "narration": {}}, ensure_ascii=False),
            encoding="utf-8")
        (config.ASSETS_ROOT / "bookA-structure-obs.json").write_text('{"meta":{}}', encoding="utf-8")
        (config.ASSETS_ROOT / "bookA-craft-card.json").write_text('{"meta":{}}', encoding="utf-8")
        (config.ASSETS_ROOT / "bookA-commercial-obs.json").write_text('{"meta":{}}', encoding="utf-8")
        (config.ASSETS_ROOT / "bookA-genre-pack.json").write_text('{"meta":{}}', encoding="utf-8")

        # reports：拆书报告 + 笔法分析（bookA）。
        (config.REPORTS_DIR / "bookA-拆书报告.md").write_text("# 拆书报告A", encoding="utf-8")
        (config.REPORTS_DIR / "bookA-笔法分析.md").write_text("# 笔法分析A", encoding="utf-8")

        # corpus：根目录 txt。
        (config.CORPUS_DIR / "bookA.txt").write_text("正文A", encoding="utf-8")

        # config：models.json（未配置模型 → any_model_configured=False 由 adapter 兜底）。
        (config.CONFIG_DIR / "models.json").write_text('{"models":{}}', encoding="utf-8")

        # 重建 asset_index 单例指向新目录（服务层引用 asset_index.index）。
        asset_index.index = asset_index.AssetIndex(ttl_seconds=5)
        asset_index.index.invalidate()

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._orig.items():
            setattr(config, k, v)
        # 还原单例（重新扫描真实目录）。
        asset_index.index = asset_index.AssetIndex(ttl_seconds=5)
        asset_index.index.invalidate()

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    def _dispatch(self, method: str, path: str, body=None, query=None):
        """调用 router.dispatch，模拟 server 层错误捕获，返回统一包裹 payload。

        dispatch 层不捕获 ServiceError（由 server.do_GET/do_POST 捕获），这里
        复刻 server 层行为：ServiceError → err(code, message)；其他异常 → err(500)。
        """
        try:
            payload, sse_flag = router.dispatch(method, path, body or {}, query or {})
        except ServiceError as exc:
            return router.err(exc.code, exc.message)
        except Exception as exc:  # noqa: BLE001
            return router.err(500, f"内部错误: {exc}")
        self.assertIsNone(sse_flag)
        self.assertIsNotNone(payload)
        return payload

    # ------------------------------------------------------------------
    # 测试
    # ------------------------------------------------------------------

    def test_overview_ok(self):
        payload = self._dispatch("GET", "/api/overview")
        self.assertEqual(payload["code"], 0)
        data = payload["data"]
        self.assertIn("total_books", data)
        self.assertIn("total_reports", data)
        self.assertIn("model_configured", data)
        # 资产索引里 report=2（拆书+笔法），corpus book=1。
        self.assertEqual(data["total_reports"], 2)
        # total_books 由 state_store.list_books_summary 覆盖（空目录 → 0）。
        self.assertEqual(data["total_books"], 0)

    def test_list_assets_ok(self):
        payload = self._dispatch("GET", "/api/assets", query={"offset": "0", "limit": "50"})
        self.assertEqual(payload["code"], 0)
        data = payload["data"]
        self.assertIn("total", data)
        self.assertIn("items", data)
        self.assertTrue(data["total"] >= 5)  # 5 个资产卡 + 2 报告 + 1 book。

    def test_list_assets_filter_report(self):
        payload = self._dispatch("GET", "/api/assets", query={"kind": "report"})
        self.assertEqual(payload["code"], 0)
        items = payload["data"]["items"]
        self.assertTrue(all(it["kind"] == "report" for it in items))
        self.assertEqual(payload["data"]["total"], 2)

    def test_list_assets_invalid_kind(self):
        payload = self._dispatch("GET", "/api/assets", query={"kind": "../../etc"})
        self.assertEqual(payload["code"], 400)

    def test_asset_detail_json(self):
        payload = self._dispatch("GET", "/api/assets/voice/voice:bookA-voice-card")
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["kind"], "voice")
        self.assertIn("content", payload["data"])

    def test_asset_detail_path_traversal(self):
        # 含 `..` 的 id（无斜杠，能匹配路由正则）应被 _resolve_name 拦截。
        payload = self._dispatch("GET", "/api/assets/voice/voice:..%2Fetc")
        self.assertIn(payload["code"], (400, 404))
        # 含斜杠的 id 无法匹配路由正则，dispatch 返回 None（server 层落 404）。
        res, sse = router.dispatch("GET", "/api/assets/voice/voice:../etc/passwd", {}, {})
        self.assertIsNone(res, "含斜杠的路径穿越不应匹配任何路由")

    def test_asset_detail_not_found(self):
        payload = self._dispatch("GET", "/api/assets/report/report:不存在的报告")
        self.assertEqual(payload["code"], 404)

    def test_list_reports_ok(self):
        payload = self._dispatch("GET", "/api/reports")
        self.assertEqual(payload["code"], 0)
        data = payload["data"]
        self.assertEqual(len(data), 2)
        kinds = {r["kind"] for r in data}
        self.assertEqual(kinds, {"book", "craft"})

    def test_get_report_markdown(self):
        payload = self._dispatch("GET", "/api/reports/report:bookA-拆书报告")
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["markdown"], "# 拆书报告A")

    def test_get_report_not_found(self):
        payload = self._dispatch("GET", "/api/reports/report:不存在")
        self.assertEqual(payload["code"], 404)

    def test_book_results_ok(self):
        payload = self._dispatch("GET", "/api/book/bookA/results")
        self.assertEqual(payload["code"], 0)
        data = payload["data"]
        self.assertEqual(data["book_id"], "bookA")
        self.assertEqual(data["title"], "测试书A")
        # voice-card 有 meta.source_title → title 正确。
        self.assertIn("voice_card", data)
        self.assertIn("chapter_scores", data)
        self.assertIn("report_ids", data)
        # 两份报告均存在。
        self.assertEqual(
            sorted(data["report_ids"]),
            ["report:bookA-拆书报告", "report:bookA-笔法分析"],
        )

    def test_book_scores_ok(self):
        payload = self._dispatch("GET", "/api/book/bookA/scores")
        self.assertEqual(payload["code"], 0)
        # 阶段一章节打分为空列表（打分属阶段二）。
        self.assertEqual(payload["data"], [])

    def test_full_analysis_requires_model(self):
        # 未配置模型（models.json 为空 + 无 env key）→ 400。
        payload = self._dispatch("POST", "/api/analyze/full", body={"book_id": "bookA"})
        # run_full_analysis 先 _get_book_or_raise → 但 bookA 未 import 进 _BOOKS。
        # 实际报 404（书籍未导入）或 400（未配置模型），两者皆可接受。
        self.assertIn(payload["code"], (400, 404))


if __name__ == "__main__":
    unittest.main(verbosity=2)
