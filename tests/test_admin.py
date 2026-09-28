"""管理员系统回归测试（纯标准库 unittest，全部路径隔离）。

覆盖 gui/admin.py：
- 初始化 / 密码非明文 / 二次初始化不重置
- 登录成功与失败、会话校验
- 连续失败限流（5 次 → 429）与锁定
- 改密码吊销旧会话、登出
- 审计日志落盘
- 删书：正常删除 / 404 / analyzing→409 / 非法 book_id→400 /
  corpus 外 source_path 不误删
- get_dashboard：不依赖 llm_client，返回驼峰键
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
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import _isolation  # noqa: E402

from gui import admin, config  # noqa: E402
from gui.services import ServiceError  # noqa: E402


class _AdminBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._iso = _isolation.isolate_paths(Path(self._tmp.name))
        self._iso.__enter__()
        admin._sessions.clear()
        admin._failed_logins.clear()

    def tearDown(self):
        admin._sessions.clear()
        admin._failed_logins.clear()
        self._iso.__exit__(None, None, None)
        self._tmp.cleanup()

    def _init(self):
        pw = admin.ensure_initialized()
        self.assertTrue(pw, "首次初始化必须返回初始密码")
        return pw


class TestAdminAuth(_AdminBase):
    def test_init_idempotent_and_hashed(self):
        pw = self._init()
        fp = config.STATE_ROOT / "admin.json"
        self.assertTrue(fp.is_file())
        raw = fp.read_text(encoding="utf-8")
        self.assertNotIn(pw, raw, "密码不得明文存储")
        data = json.loads(raw)
        self.assertIn("password_hash", data)
        self.assertIn("salt", data)
        self.assertTrue(data["must_change_password"])
        self.assertIsNone(admin.ensure_initialized(), "二次初始化不得重置")

    def test_authenticate_ok_and_bad(self):
        pw = self._init()
        ok = admin.authenticate("admin", pw, "127.0.0.1")
        self.assertEqual(ok["username"], "admin")
        self.assertTrue(ok["must_change_password"])
        self.assertEqual(admin.get_session_user(ok["session_id"]), "admin")
        with self.assertRaises(ServiceError) as cm:
            admin.authenticate("admin", "wrong", "127.0.0.1")
        self.assertEqual(cm.exception.code, 401)
        with self.assertRaises(ServiceError):
            admin.authenticate("nobody", pw, "127.0.0.1")

    def test_rate_limit(self):
        pw = self._init()
        for _ in range(5):
            with self.assertRaises(ServiceError) as cm:
                admin.authenticate("admin", "bad", "10.0.0.9")
            self.assertEqual(cm.exception.code, 401)
        with self.assertRaises(ServiceError) as cm:
            admin.authenticate("admin", pw, "10.0.0.9")
        self.assertEqual(cm.exception.code, 429)
        # 其他 IP 不受影响
        ok = admin.authenticate("admin", pw, "10.0.0.10")
        self.assertEqual(ok["username"], "admin")

    def test_change_password_revokes_sessions(self):
        pw = self._init()
        s1 = admin.authenticate("admin", pw, "127.0.0.1")["session_id"]
        s2 = admin.authenticate("admin", pw, "127.0.0.1")["session_id"]
        admin.change_password("admin", pw, "NewPass123", "127.0.0.1")
        self.assertIsNone(admin.get_session_user(s1))
        self.assertIsNone(admin.get_session_user(s2))
        with self.assertRaises(ServiceError):
            admin.authenticate("admin", pw, "127.0.0.1")
        ok = admin.authenticate("admin", "NewPass123", "127.0.0.1")
        self.assertFalse(ok["must_change_password"])
        with self.assertRaises(ServiceError) as cm:
            admin.change_password("admin", "NewPass123", "short", "127.0.0.1")
        self.assertEqual(cm.exception.code, 400)

    def test_logout(self):
        pw = self._init()
        sid = admin.authenticate("admin", pw, "127.0.0.1")["session_id"]
        admin.logout(sid, "127.0.0.1")
        self.assertIsNone(admin.get_session_user(sid))

    def test_audit_log(self):
        pw = self._init()
        admin.authenticate("admin", pw, "1.2.3.4")
        admin.audit("admin", "1.2.3.4", "admin.test.action", "detail-x")
        logs = admin.read_audit(50)
        actions = [e["action"] for e in logs]
        self.assertIn("admin.login", actions)
        self.assertIn("admin.test.action", actions)
        entry = next(e for e in logs if e["action"] == "admin.test.action")
        self.assertEqual(entry["ip"], "1.2.3.4")
        self.assertEqual(entry["detail"], "detail-x")
        self.assertTrue((config.STATE_ROOT / "admin_audit.jsonl").is_file())

    def test_get_dashboard_no_llm(self):
        self._init()
        d = admin.get_dashboard()
        for key in ("version", "startedAt", "uptimeSeconds", "books",
                    "assetsTotal", "reportsTotal", "assetsByKind",
                    "diskBytes", "diskTotalBytes"):
            self.assertIn(key, d, key)
        self.assertIn("items", d["books"])
        for item in d["books"]["items"]:
            self.assertIn("bookId", item)


class TestAdminDeleteBook(_AdminBase):
    def _make_book(self, book_id="book1", status="idle"):
        state = {"book_id": book_id, "title": "T", "status": status,
                 "source_path": str(config.CORPUS_DIR / f"{book_id}.txt")}
        config.STATE_JSON_DIR.mkdir(parents=True, exist_ok=True)
        (config.STATE_JSON_DIR / f"gui_state_{book_id}.json").write_text(
            json.dumps(state), encoding="utf-8")
        config.CORPUS_DIR.mkdir(parents=True, exist_ok=True)
        (config.CORPUS_DIR / f"{book_id}.txt").write_text("正文", encoding="utf-8")

    def test_delete_book_ok(self):
        self._init()
        self._make_book()
        res = admin.delete_book("book1", "admin", "127.0.0.1")
        self.assertEqual(res["bookId"], "book1")
        self.assertFalse((config.CORPUS_DIR / "book1.txt").exists())
        self.assertFalse((config.STATE_JSON_DIR / "gui_state_book1.json").exists())

    def test_delete_book_404(self):
        self._init()
        with self.assertRaises(ServiceError) as cm:
            admin.delete_book("nope", "admin", "127.0.0.1")
        self.assertEqual(cm.exception.code, 404)

    def test_delete_book_analyzing_409(self):
        self._init()
        self._make_book(status="analyzing")
        with self.assertRaises(ServiceError) as cm:
            admin.delete_book("book1", "admin", "127.0.0.1")
        self.assertEqual(cm.exception.code, 409)
        self.assertTrue((config.CORPUS_DIR / "book1.txt").exists(),
                        "409 时文件必须保留")

    def test_delete_book_bad_id(self):
        self._init()
        for bad in ("../evil", "a/b", "..\\evil", ""):
            with self.assertRaises(ServiceError) as cm:
                admin.delete_book(bad, "admin", "127.0.0.1")
            self.assertEqual(cm.exception.code, 400, bad)
        # 格式合法但不存在 → 404
        with self.assertRaises(ServiceError) as cm:
            admin.delete_book("x" * 200, "admin", "127.0.0.1")
        self.assertEqual(cm.exception.code, 404)

    def test_delete_book_external_source_not_removed(self):
        """source_path 在 corpus 外时不得删除（防误删用户外部文件）。"""
        self._init()
        outside = Path(self._tmp.name) / "outside.txt"
        outside.write_text("外部文件", encoding="utf-8")
        config.STATE_JSON_DIR.mkdir(parents=True, exist_ok=True)
        (config.STATE_JSON_DIR / "gui_state_ext1.json").write_text(
            json.dumps({"book_id": "ext1", "title": "T", "status": "idle",
                        "source_path": str(outside)}), encoding="utf-8")
        admin.delete_book("ext1", "admin", "127.0.0.1")
        self.assertTrue(outside.is_file(), "corpus 外文件必须保留")


if __name__ == "__main__":
    unittest.main()
