"""桥段库 API 回归（交接文档待办 ④）。

覆盖 ``GET /api/tropes`` 背后的 ``services.list_tropes``：
1. 正常返回 total_count + tropes 数组。
2. 文件缺失 → ServiceError 404。
3. 文件损坏 → ServiceError 500。
4. 缺少 tropes 数组 → ServiceError 500。
5. 路由表确实注册了 /api/tropes（GET）。

只 patch ``config.ASSETS_ROOT``（函数内实时求值，无其他路径依赖），
setUp/tearDown 成对还原；纯标准库 unittest。
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _isolation  # noqa: E402

from gui import config, router, services  # noqa: E402
from gui.services import ServiceError  # noqa: E402


def _trope(i: int) -> dict:
    return {
        "id": f"T-{i:03d}",
        "name": f"桥段{i}",
        "category": "打脸",
        "genre_scope": "universal",
        "applicable_genres": ["xianxia"],
        "skeleton": {"setup": "铺垫", "escalation": ["激化"],
                     "payoff": "引爆", "aftermath": "余波"},
        "abstraction_level": "structural",
        "parameters": [],
        "effectiveness": "",
        "variations": [],
        "common_failures": [],
    }


class TestListTropes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig = config.ASSETS_ROOT
        cls._tmp = Path(tempfile.mkdtemp(prefix="trope_api_"))
        config.ASSETS_ROOT = cls._tmp

    @classmethod
    def tearDownClass(cls):
        config.ASSETS_ROOT = cls._orig
        _isolation.remove_tree(cls._tmp)

    def _write(self, data) -> Path:
        fp = self._tmp / "trope-library.json"
        if isinstance(data, str):
            fp.write_text(data, encoding="utf-8")
        else:
            fp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return fp

    def tearDown(self):
        fp = self._tmp / "trope-library.json"
        if fp.is_file():
            fp.unlink()

    def test_ok(self):
        self._write({"tropes": [_trope(1), _trope(2)]})
        r = services.list_tropes()
        self.assertEqual(r["total_count"], 2)
        self.assertEqual(len(r["tropes"]), 2)
        self.assertEqual(r["tropes"][0]["id"], "T-001")

    def test_missing_file_404(self):
        with self.assertRaises(ServiceError) as cm:
            services.list_tropes()
        self.assertEqual(cm.exception.code, 404)

    def test_broken_json_500(self):
        self._write('{"tropes": [broken')
        with self.assertRaises(ServiceError) as cm:
            services.list_tropes()
        self.assertEqual(cm.exception.code, 500)

    def test_no_tropes_array_500(self):
        self._write({"note": "no tropes here"})
        with self.assertRaises(ServiceError) as cm:
            services.list_tropes()
        self.assertEqual(cm.exception.code, 500)

    def test_route_registered(self):
        hits = [rt for rt in router.ROUTES
                if rt[0] == "GET" and rt[1].pattern == r"^/api/tropes$"]
        self.assertEqual(len(hits), 1)


if __name__ == "__main__":
    unittest.main()
