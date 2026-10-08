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
from datetime import datetime, timedelta, timezone
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
    def tearDown(self):
        from gui import services
        services._BOOKS.clear()
        super().tearDown()

    def _make_book(self, book_id="book1", status="idle"):
        state = {"book_id": book_id, "title": "T", "status": status,
                 "source_path": str(config.CORPUS_DIR / f"{book_id}.txt")}
        config.STATE_JSON_DIR.mkdir(parents=True, exist_ok=True)
        (config.STATE_JSON_DIR / f"gui_state_{book_id}.json").write_text(
            json.dumps(state), encoding="utf-8")
        config.CORPUS_DIR.mkdir(parents=True, exist_ok=True)
        (config.CORPUS_DIR / f"{book_id}.txt").write_text("正文", encoding="utf-8")

    def _seed_db(self, book_id):
        """往四张表各插一条该书记录（init_schema 幂等）。"""
        from gui import db
        db.init_schema()
        with db.tx() as conn:
            conn.execute("INSERT INTO books(book_id, title, status) VALUES (?, 'T', 'idle')",
                         (book_id,))
            conn.execute("INSERT INTO assets(asset_key, kind, name, path, book_id)"
                         " VALUES (?, 'doc', 'a', ?, ?)",
                         (f"k-{book_id}", f"/tmp/{book_id}", book_id))
            conn.execute("INSERT INTO reports(report_key, type, book_id, path)"
                         " VALUES (?, 'r', ?, ?)",
                         (f"rk-{book_id}", book_id, f"/tmp/r-{book_id}"))
            conn.execute("INSERT INTO analysis_tasks(book_id, status) VALUES (?, 'idle')",
                         (book_id,))

    def _db_row_count(self, book_id):
        from gui import db
        conn = db.get_conn()
        total = 0
        for table in ("books", "assets", "reports", "analysis_tasks"):
            total += conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE book_id = ?",
                (book_id,)).fetchone()[0]
        return total

    def test_delete_book_ok(self):
        self._init()
        self._make_book()
        self._seed_db("book1")
        (config.ASSETS_ROOT / "book1").mkdir(parents=True, exist_ok=True)
        (config.ASSETS_ROOT / "book1" / "a.txt").write_text("x", encoding="utf-8")
        from gui import services
        services._BOOKS["book1"] = {"title": "T"}
        res = admin.delete_book("book1", "admin", "127.0.0.1")
        self.assertEqual(res["bookId"], "book1")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["warnings"], [])
        self.assertFalse((config.CORPUS_DIR / "book1.txt").exists())
        self.assertFalse((config.STATE_JSON_DIR / "gui_state_book1.json").exists())
        self.assertFalse((config.ASSETS_ROOT / "book1").exists())
        self.assertEqual(self._db_row_count("book1"), 0, "四表记录应全部删除")
        self.assertNotIn("book1", services._BOOKS, "内存缓存应清除")
        self.assertTrue(any("sqlite:4行" in r for r in res["removed"]), res["removed"])

    def test_delete_book_legacy_state_location(self):
        """旧位置 gui_state/gui_state_<id>.json 的状态文件也要清掉。"""
        self._init()
        config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
        (config.STATE_ROOT / "gui_state_leg1.json").write_text(
            json.dumps({"book_id": "leg1", "title": "T", "status": "idle"}),
            encoding="utf-8")
        res = admin.delete_book("leg1", "admin", "127.0.0.1")
        self.assertEqual(res["status"], "ok")
        self.assertFalse((config.STATE_ROOT / "gui_state_leg1.json").exists())
        self.assertIn("gui_state_leg1.json", res["removed"])

    def test_delete_book_db_failure_rolls_back(self):
        """DB 事务失败 → 500，文件原样不动（不出现半删状态）。"""
        from unittest import mock

        from gui import db
        self._init()
        self._make_book("dbf1")
        self._seed_db("dbf1")
        with mock.patch.object(db, "tx", side_effect=RuntimeError("boom")):
            with self.assertRaises(ServiceError) as cm:
                admin.delete_book("dbf1", "admin", "127.0.0.1")
        self.assertEqual(cm.exception.code, 500)
        self.assertEqual(self._db_row_count("dbf1"), 4, "事务应回滚，DB 行保留")
        self.assertTrue((config.CORPUS_DIR / "dbf1.txt").is_file(), "文件不得动")
        self.assertTrue((config.STATE_JSON_DIR / "gui_state_dbf1.json").is_file())

    def test_delete_book_partial_on_assets_failure(self):
        """assets 目录删失败 → partial：DB 已清、其余文件已删，残留被逐项报告。"""
        import shutil
        from unittest import mock
        self._init()
        self._make_book("pb1")
        self._seed_db("pb1")
        adir = config.ASSETS_ROOT / "pb1"
        adir.mkdir(parents=True, exist_ok=True)
        (adir / "x.txt").write_text("x", encoding="utf-8")
        with mock.patch.object(shutil, "rmtree", side_effect=OSError("denied")):
            res = admin.delete_book("pb1", "admin", "127.0.0.1")
        self.assertEqual(res["status"], "partial")
        self.assertTrue(any("资产目录" in w for w in res["warnings"]), res["warnings"])
        self.assertEqual(self._db_row_count("pb1"), 0, "DB 事务已提交")
        self.assertFalse((config.CORPUS_DIR / "pb1.txt").exists())
        self.assertFalse((config.STATE_JSON_DIR / "gui_state_pb1.json").exists())
        self.assertTrue(adir.is_dir(), "删失败的资产目录必须残留并被报告，而非静默丢失")
        entries = admin.read_audit(10, action="admin.book.delete")
        self.assertTrue(entries and "partial" in entries[0]["detail"], "审计应记录 partial")

    def test_delete_book_partial_on_corpus_failure(self):
        """corpus 原文删失败 → partial，原文残留并被报告。"""
        from unittest import mock
        self._init()
        self._make_book("pc1")
        with mock.patch.object(admin, "_remove_guarded",
                               return_value=("failed", "denied")):
            res = admin.delete_book("pc1", "admin", "127.0.0.1")
        self.assertEqual(res["status"], "partial")
        self.assertTrue((config.CORPUS_DIR / "pc1.txt").is_file(), "删失败的原文必须残留")
        self.assertTrue(any("corpus" in w for w in res["warnings"]), res["warnings"])
        self.assertFalse((config.STATE_JSON_DIR / "gui_state_pc1.json").exists(),
                         "其余部分应继续清理，不因一项失败中断")

    def test_delete_book_outside_corpus_is_skipped_not_warning(self):
        """corpus 外原文 → skipped（有意保留），不算失败，status 仍为 ok。"""
        self._init()
        outside = Path(self._tmp.name) / "outside2.txt"
        outside.write_text("外部文件", encoding="utf-8")
        config.STATE_JSON_DIR.mkdir(parents=True, exist_ok=True)
        (config.STATE_JSON_DIR / "gui_state_ext2.json").write_text(
            json.dumps({"book_id": "ext2", "title": "T", "status": "idle",
                        "source_path": str(outside)}), encoding="utf-8")
        res = admin.delete_book("ext2", "admin", "127.0.0.1")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["warnings"], [])
        self.assertTrue(any("目录外" in s for s in res["skipped"]), res["skipped"])
        self.assertTrue(outside.is_file(), "corpus 外文件必须保留")

    def test_delete_book_concurrent(self):
        """并发删除同一本书：恰好一个成功，其余 404，不允许裸异常。"""
        import threading
        self._init()
        self._make_book("race1")
        self._seed_db("race1")
        n = 8
        barrier = threading.Barrier(n)
        results = []
        results_lock = threading.Lock()

        def worker():
            barrier.wait()  # 尽量同时冲进删除
            try:
                r = admin.delete_book("race1", "admin", "127.0.0.1")
                outcome = ("ok", r["status"])
            except ServiceError as e:
                outcome = ("err", e.code)
            except Exception as e:  # noqa: BLE001 - 任何裸异常都是 bug
                outcome = ("raw", type(e).__name__)
            with results_lock:
                results.append(outcome)

        threads = [threading.Thread(target=worker) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        oks = [r for r in results if r[0] == "ok"]
        errs = [r for r in results if r[0] == "err"]
        raws = [r for r in results if r[0] == "raw"]
        self.assertEqual(len(oks), 1, f"必须恰好一个成功: {results}")
        self.assertEqual(len(errs), n - 1)
        self.assertTrue(all(code == 404 for _, code in errs),
                        f"后来者应看到书已不存在(404): {results}")
        self.assertEqual(raws, [], f"不允许裸异常: {raws}")
        self.assertEqual(self._db_row_count("race1"), 0)
        self.assertFalse((config.STATE_JSON_DIR / "gui_state_race1.json").exists())
        self.assertFalse((config.CORPUS_DIR / "race1.txt").exists())

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

    def _write_audit_entries(self, entries):
        fp = config.STATE_ROOT / "admin_audit.jsonl"
        fp.parent.mkdir(parents=True, exist_ok=True)
        with fp.open("a", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    @staticmethod
    def _entry(ts, action, username="u"):
        return {"ts": ts, "username": username, "ip": "1.1.1.1",
                "action": action, "detail": ""}

    def test_read_audit_beyond_old_window(self):
        """回归：旧实现只取最近 2000 行再过滤，稀有 action 的旧记录会被漏掉。"""
        base = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)
        entries = [self._entry((base - timedelta(minutes=3000 - i)).isoformat(),
                               "rare.action")
                   for i in range(100)]
        entries += [self._entry((base - timedelta(minutes=2900 - i)).isoformat(), "noise")
                    for i in range(2500)]
        self._write_audit_entries(entries)
        got = admin.read_audit(500, action="rare.action")
        self.assertEqual(len(got), 100, "窗口外的旧记录必须被找到")
        self.assertTrue(all(e["action"] == "rare.action" for e in got))
        # 最新的在前
        self.assertGreater(got[0]["ts"], got[-1]["ts"])

    def test_read_audit_time_range(self):
        base = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)
        self._write_audit_entries([
            self._entry((base - timedelta(minutes=30)).isoformat(), "old"),
            self._entry((base - timedelta(minutes=10)).isoformat(), "mid"),
            self._entry(base.isoformat(), "new"),
        ])
        mid = (base - timedelta(minutes=15)).isoformat()
        got = admin.read_audit(100, since=mid)
        self.assertEqual([e["action"] for e in got], ["new", "mid"])
        got = admin.read_audit(100, until=mid)
        self.assertEqual([e["action"] for e in got], ["old"])
        got = admin.read_audit(100, since=(base - timedelta(minutes=15)).isoformat(),
                               until=(base - timedelta(minutes=5)).isoformat())
        self.assertEqual([e["action"] for e in got], ["mid"])
        # datetime 入参亦可；naive 视为 UTC
        got = admin.read_audit(100, since=datetime(2026, 9, 28, 11, 50))
        self.assertEqual([e["action"] for e in got], ["new", "mid"])
        # 非法时间 → 400
        with self.assertRaises(ServiceError) as cm:
            admin.read_audit(10, since="not-a-time")
        self.assertEqual(cm.exception.code, 400)

    def test_read_audit_reverse_scan_is_bounded(self):
        """since 设为未来时，读到第一条即提前终止，不扫描整个大文件。"""
        fp = config.STATE_ROOT / "admin_audit.jsonl"
        fp.parent.mkdir(parents=True, exist_ok=True)
        with fp.open("w", encoding="utf-8") as f:
            for i in range(200000):
                f.write(json.dumps({"ts": "2020-01-01T00:00:00+00:00",
                                    "username": "u", "ip": "x",
                                    "action": "a", "detail": str(i)}) + "\n")
        consumed = []
        orig = admin._iter_lines_reverse

        def counting(fp_, block_size=8192):
            for line in orig(fp_, block_size):
                consumed.append(1)
                yield line

        admin._iter_lines_reverse = counting
        try:
            got = admin.read_audit(100, since="2030-01-01T00:00:00+00:00")
        finally:
            admin._iter_lines_reverse = orig
        self.assertEqual(got, [])
        self.assertLess(len(consumed), 1000,
                        f"应提前终止，实际消费了 {len(consumed)} 行")

    def test_read_audit_limit_and_newest_first(self):
        for i in range(10):
            admin.audit("admin", "1.1.1.1", f"act.{i}", "")
        got = admin.read_audit(3)
        self.assertEqual([e["action"] for e in got], ["act.9", "act.8", "act.7"])

    def test_tail_lines(self):
        import tempfile
        from pathlib import Path
        # 小文件：全量返回
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
            f.write("a\nb\nc\n")
            fp = Path(f.name)
        try:
            self.assertEqual(admin._tail_lines(fp, 10), ["a", "b", "c"])
            self.assertEqual(admin._tail_lines(fp, 2), ["b", "c"])
            # 大文件：只取尾部（构造超过 8KB 的文件验证块倒读）
            with fp.open("w", encoding="utf-8") as f:
                for i in range(3000):
                    f.write(f"line-{i:05d}\n")
            tail = admin._tail_lines(fp, 100)
            self.assertEqual(len(tail), 100)
            self.assertEqual(tail[0], "line-02900")
            self.assertEqual(tail[-1], "line-02999")
            # 坏字节不崩（errors=replace）
            with fp.open("ab") as f:
                f.write(b"\xff\xfe-bad\n")
            tail2 = admin._tail_lines(fp, 3)
            self.assertEqual(len(tail2), 3)
        finally:
            fp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()


class TestMustChangePasswordGate(_AdminBase):
    """强制改密状态机：needs_password_change + 改密后解除。"""

    def test_needs_password_change_lifecycle(self):
        pw = self._init()
        # 首次初始化要求改密
        self.assertTrue(admin.needs_password_change("admin"))
        self.assertFalse(admin.needs_password_change("someone-else"))
        # 登录返回改密标记
        r = admin.authenticate("admin", pw, "127.0.0.1")
        self.assertTrue(r["must_change_password"])
        # 改密后解除
        admin.change_password("admin", pw, "NewPass12345678", "127.0.0.1")
        self.assertFalse(admin.needs_password_change("admin"))
        r2 = admin.authenticate("admin", "NewPass12345678", "127.0.0.1")
        self.assertFalse(r2["must_change_password"])


class TestAuthenticateTimingAndUnicode(_AdminBase):
    """登录时序与 Unicode：错误用户名也执行 PBKDF2；非 ASCII 用户名不抛异常。"""

    def test_unicode_username_no_crash(self):
        self._init()
        # 非 ASCII 用户名不得抛 TypeError，一律 401
        for bad_user in ("管理员", "admin\u00e9", "a" * 500, ""):
            with self.assertRaises(ServiceError, msg=f"user={bad_user!r}"):
                admin.authenticate(bad_user, "whatever", "127.0.0.1")

    def test_wrong_username_still_costly(self):
        """错误用户名也应执行完整 PBKDF2（用时间下界粗验，不做精确等值断言）。"""
        import time
        self._init()
        t0 = time.monotonic()
        with self.assertRaises(ServiceError):
            admin.authenticate("nonexistent-user", "whatever", "127.0.0.1")
        dt = time.monotonic() - t0
        # 200k 轮 PBKDF2-SHA256 通常 > 50ms；若实现退化为直接返回会远小于此
        self.assertGreater(dt, 0.05, f"错误用户名登录过快({dt:.3f}s)，疑似跳过 PBKDF2")
