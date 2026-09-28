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


class TestAdminSessions(unittest.TestCase):
    """会话管理：列表与吊销。"""

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

    def test_list_and_revoke_session(self):
        pw = self._init()
        r1 = admin.authenticate("admin", pw, "127.0.0.1")
        r2 = admin.authenticate("admin", pw, "127.0.0.2")
        sessions = admin.list_sessions()
        self.assertEqual(len(sessions), 2)
        ids = {s["id"] for s in sessions}
        self.assertEqual(len(ids), 2)
        # token 全文不出现在列表中（只给前缀）
        for s in sessions:
            self.assertEqual(len(s["id"]), 8)
            self.assertNotIn(r1["session_id"], s["id"])
            self.assertIn("createdAt", s)
        # current 标记：传入当前会话 ID 则对应条目标记 True，其余 False
        marked = admin.list_sessions(current_sid=r1["session_id"])
        by_id = {s["id"]: s for s in marked}
        self.assertTrue(by_id[r1["session_id"][:8]]["current"])
        self.assertFalse(by_id[r2["session_id"][:8]]["current"])
        # 不传 current_sid 则全部 False（向后兼容）
        for s in admin.list_sessions():
            self.assertFalse(s["current"])
        # 吊销其中一个
        admin.revoke_session(sessions[0]["id"], "admin", "127.0.0.1")
        self.assertEqual(len(admin.list_sessions()), 1)
        # 吊销不存在的 → 404
        with self.assertRaises(ServiceError) as cm:
            admin.revoke_session("deadbeef", "admin", "127.0.0.1")
        self.assertEqual(cm.exception.code, 404)
        # 前缀太短 → 400
        with self.assertRaises(ServiceError) as cm:
            admin.revoke_session("abc", "admin", "127.0.0.1")
        self.assertEqual(cm.exception.code, 400)
        # 审计记录了吊销
        entries = admin.read_audit(50)
        self.assertTrue(any(e["action"] == "admin.session.revoke" for e in entries))


class TestAdminRateLimitCleanup(unittest.TestCase):
    """失败登录记录过期清理：不足 5 次的 IP 不得永久堆积。"""

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

    def test_stale_entries_purged(self):
        import time
        pw = admin.ensure_initialized()
        self.assertTrue(pw)
        # 3 次失败（不足锁定阈值）
        for _ in range(3):
            try:
                admin.authenticate("admin", "wrong", "10.0.0.1")
            except ServiceError:
                pass
        self.assertIn("10.0.0.1", admin._failed_logins)
        # 把记录推到过期
        admin._failed_logins["10.0.0.1"]["updated_at"] = time.time() - 400
        # 下一次任意登录尝试触发清理
        try:
            admin.authenticate("admin", "wrong", "10.0.0.2")
        except ServiceError:
            pass
        self.assertNotIn("10.0.0.1", admin._failed_logins)


class TestAdminResetPassword(unittest.TestCase):
    """本地 CLI 重置密码。"""

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

    def test_reset_password(self):
        old_pw = admin.ensure_initialized()
        self.assertTrue(old_pw)
        # 登录一次，建立会话
        r = admin.authenticate("admin", old_pw, "127.0.0.1")
        self.assertEqual(len(admin.list_sessions()), 1)
        # 重置
        new_pw = admin.reset_password()
        self.assertTrue(new_pw)
        self.assertNotEqual(new_pw, old_pw)
        # 旧密码失效
        with self.assertRaises(ServiceError):
            admin.authenticate("admin", old_pw, "127.0.0.1")
        # 新密码可用，且要求改密
        r2 = admin.authenticate("admin", new_pw, "127.0.0.1")
        self.assertTrue(r2["must_change_password"])
        # 旧会话全部被吊销
        self.assertIsNone(admin.get_session_user(r["session_id"]))
        # 审计记录
        entries = admin.read_audit(50)
        self.assertTrue(any(e["action"] == "admin.password.reset" for e in entries))


class TestAdminAuditFilter(unittest.TestCase):
    """审计日志过滤。"""

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

    def test_audit_filter(self):
        pw = admin.ensure_initialized()
        admin.authenticate("admin", pw, "127.0.0.1")
        try:
            admin.authenticate("admin", "wrong", "127.0.0.1")
        except ServiceError:
            pass
        # 按 action 过滤
        logins = admin.read_audit(100, action="admin.login")
        self.assertTrue(len(logins) >= 1)
        self.assertTrue(all(e["action"] == "admin.login" for e in logins))
        failed = admin.read_audit(100, action="admin.login.failed")
        self.assertTrue(len(failed) >= 1)
        # 按用户过滤
        by_user = admin.read_audit(100, username="admin")
        self.assertTrue(len(by_user) >= 2)
        # 组合过滤
        combo = admin.read_audit(100, action="admin.login", username="admin")
        self.assertTrue(len(combo) >= 1)
        # 不存在的 action → 空
        self.assertEqual(admin.read_audit(100, action="no.such.action"), [])


if __name__ == "__main__":
    unittest.main()
