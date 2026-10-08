"""P2 企业级加固测试：logging 体系 / token 认证 / DPAPI 密钥存储 / 自动备份。

隔离纪律：
- 日志：patch ``logging_setup.LOG_DIR/LOG_FILE`` 到临时目录
- 认证：patch ``config.API_TOKEN`` 与 ``config.LOCK_PATH``；真实 GuiServer 绑临时端口
- 密钥：全部写入临时目录（绝不触碰真实 ``config/.secrets.*``）
- 备份：fake ``migrate.backup`` 计数，不产生真实备份文件
"""

from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _isolation  # noqa: E402

from gui import (
    config,  # noqa: E402
    logging_setup,  # noqa: E402
)


class TestLoggingSetup(unittest.TestCase):
    """logging_setup：幂等初始化 / 落盘 / 命名约定。"""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="log_qa_"))
        self._orig = (logging_setup.LOG_DIR, logging_setup.LOG_FILE)
        logging_setup.LOG_DIR = self._tmp / "logs"
        logging_setup.LOG_FILE = self._tmp / "logs" / "gui.log"

    def tearDown(self):
        logging_setup.LOG_DIR, logging_setup.LOG_FILE = self._orig
        root = logging.getLogger(logging_setup.LOGGER_NAME)
        for h in list(root.handlers):
            root.removeHandler(h)
            h.close()
        _isolation.remove_tree(self._tmp)

    def test_setup_creates_file_and_writes(self):
        log = logging_setup.setup_logging()
        self.assertTrue(Path(log).parent.exists(), "日志目录未创建")
        logging_setup.get_logger("server").info("写一行测试日志")
        for h in logging.getLogger(logging_setup.LOGGER_NAME).handlers:
            h.flush()
        content = logging_setup.LOG_FILE.read_text(encoding="utf-8")
        self.assertIn("写一行测试日志", content)
        self.assertIn("novellab.server", content)

    def test_setup_is_idempotent(self):
        logging_setup.setup_logging()
        logging_setup.setup_logging()
        n = len(logging.getLogger(logging_setup.LOGGER_NAME).handlers)
        self.assertLessEqual(n, 2, "重复 setup 应幂等（file+console 两个 handler）")

    def test_get_logger_naming(self):
        self.assertEqual(logging_setup.get_logger("x").name, "novellab.x")


class TestTokenAuth(unittest.TestCase):
    """NOVEL_LAB_TOKEN 认证：未启用零影响；启用后 /api 全拦截，SSE 走 ?auth=。"""

    PORT = 8775
    TOKEN = "qa-token-123"

    @classmethod
    def setUpClass(cls):
        from gui import server as server_mod
        cls._orig_lock = config.LOCK_PATH
        cls._orig_token = config.API_TOKEN
        cls._orig_state_root = config.STATE_ROOT
        cls._orig_state_json_dir = config.STATE_JSON_DIR
        cls._tmp = Path(tempfile.mkdtemp(prefix="auth_qa_"))
        config.LOCK_PATH = cls._tmp / ".lock"
        config.API_TOKEN = cls.TOKEN
        # 隔离：真实 GuiServer.start() 会调 db.init_schema() 在 config.STATE_ROOT
        # 建库（gui_state/index.db）。2026-09-28 干净安装复测发现此前未隔离，
        # 真实 gui_state/ 落下 index.db。STATE_JSON_DIR 成对隔离（R1）。
        config.STATE_ROOT = cls._tmp / "gui_state"
        config.STATE_JSON_DIR = cls._tmp / "gui" / "state"
        # 隔离：起真实服务会触发 auto_backup（真实 gui_state 备份+剪枝），替换为 no-op
        cls._orig_bk = (server_mod.auto_backup.startup_backup,
                        server_mod.auto_backup.daily_backup_if_due)
        server_mod.auto_backup.startup_backup = lambda: None
        server_mod.auto_backup.daily_backup_if_due = lambda: None
        cls._srv = server_mod.GuiServer(preferred_port=cls.PORT)
        try:
            host, port = cls._srv.start()
        except RuntimeError:
            cls._srv = None  # 端口被占则跳过本用例类
            host, port = None, None
        cls.host, cls.port = host, port

    @classmethod
    def tearDownClass(cls):
        if cls._srv is not None:
            cls._srv.shutdown()
        from gui import server as server_mod
        server_mod.auto_backup.startup_backup, server_mod.auto_backup.daily_backup_if_due = cls._orig_bk
        config.LOCK_PATH = cls._orig_lock
        config.API_TOKEN = cls._orig_token
        config.STATE_ROOT = cls._orig_state_root
        config.STATE_JSON_DIR = cls._orig_state_json_dir
        _isolation.remove_tree(cls._tmp)

    def _get(self, path: str, headers: dict | None = None) -> int:
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers=headers or {})
        try:
            urllib.request.urlopen(req, timeout=5)
            return 200
        except urllib.error.HTTPError as e:
            return e.code

    def test_api_blocked_without_token(self):
        if self._srv is None:
            self.skipTest("测试端口被占")
        self.assertEqual(self._get("/api/overview"), 401)

    def test_api_blocked_with_wrong_token(self):
        if self._srv is None:
            self.skipTest("测试端口被占")
        self.assertEqual(self._get("/api/overview", {"X-Auth-Token": "wrong"}), 401)

    def test_api_passes_with_header(self):
        if self._srv is None:
            self.skipTest("测试端口被占")
        self.assertEqual(self._get("/api/overview", {"X-Auth-Token": self.TOKEN}), 200)

    def test_sse_passes_with_query_param(self):
        if self._srv is None:
            self.skipTest("测试端口被占")
        # SSE 长连接：拿到 200 即认证通过（连接随 urlopen 返回头结束）
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/events?auth={self.TOKEN}")
        try:
            urllib.request.urlopen(req, timeout=5)
            code = 200
        except urllib.error.HTTPError as e:
            code = e.code
        self.assertEqual(code, 200)

    def test_static_shell_unprotected(self):
        if self._srv is None:
            self.skipTest("测试端口被占")
        self.assertEqual(self._get("/"), 200)


class TestSecretStore(unittest.TestCase):
    """DPAPI 密钥存储：回环 / 明文自动迁移 / 密文无明文残留 / 损坏容错。"""

    def setUp(self):
        import secret_store
        self.ss = secret_store
        self._tmp = Path(tempfile.mkdtemp(prefix="secrets_qa_"))

    def tearDown(self):
        # DPAPI 落盘的 .secrets.bin 在这里，以前整个目录从不回收。
        _isolation.remove_tree(self._tmp)

    def test_roundtrip(self):
        data = {"m1": "sk-测试密钥", "m2": "key-2"}
        path = self.ss.save_secrets(data, self._tmp)
        self.assertTrue(path.exists())
        self.assertEqual(self.ss.load_secrets(self._tmp), data)

    @unittest.skipUnless(sys.platform == "win32", "DPAPI 仅 Windows")
    def test_bin_is_not_plaintext(self):
        self.ss.save_secrets({"k": "sk-secret-value"}, self._tmp)
        blob = (self._tmp / ".secrets.bin").read_bytes()
        # 只断言**密钥明文**不在密文中；不断言短字节片段（如 b'"k"'）——
        # DPAPI 密文为随机分布，偶然包含两字节序列不代表未加密。
        self.assertNotIn(b"sk-secret-value", blob)
        self.assertNotIn(b"sk-", blob)

    @unittest.skipUnless(sys.platform == "win32", "明文迁移逻辑仅 Windows 路径")
    def test_plaintext_auto_migration(self):
        (self._tmp / ".secrets.json").write_text(
            json.dumps({"legacy": "sk-old"}), encoding="utf-8")
        self.assertEqual(self.ss.load_secrets(self._tmp), {"legacy": "sk-old"})
        self.assertFalse((self._tmp / ".secrets.json").exists(), "明文未删除")
        self.assertTrue((self._tmp / ".secrets.bin").exists(), "密文未生成")
        self.assertEqual(self.ss.load_secrets(self._tmp), {"legacy": "sk-old"})

    def test_corrupt_storage_returns_empty(self):
        if sys.platform == "win32":
            (self._tmp / ".secrets.bin").write_bytes(b"garbage-not-dpapi")
        else:
            (self._tmp / ".secrets.json").write_text("not-json", encoding="utf-8")
        self.assertEqual(self.ss.load_secrets(self._tmp), {}, "损坏存储应返回空而非抛异常")


class TestAutoBackup(unittest.TestCase):
    """自动备份：启动触发 / 每日幂等 / 故障容忍。"""

    def setUp(self):
        from gui import auto_backup
        self.ab = auto_backup
        self.ab._last_backup_date = None
        self._calls = []

    def tearDown(self):
        self.ab._last_backup_date = None

    def _fake_backup(self, fail: bool = False):
        self._calls.append(1)
        if fail:
            raise RuntimeError("备份爆炸")
        return self._tmp_backup_path

    def setUp_fake(self):
        from gui import migrate
        self._tmp_backup_path = Path(tempfile.mkdtemp(prefix="bk_qa_")) / "fake.bak"
        self._orig = migrate.backup
        migrate.backup = self._fake_backup
        return migrate

    def tearDown_fake(self, migrate):
        migrate.backup = self._orig
        _isolation.remove_tree(self._tmp_backup_path.parent)

    def test_startup_backup_registers_date(self):
        migrate = self.setUp_fake()
        try:
            self.ab.startup_backup()
            self.assertEqual(len(self._calls), 1)
            self.assertIsNotNone(self.ab._last_backup_date)
        finally:
            self.tearDown_fake(migrate)

    def test_daily_trigger_idempotent_same_day(self):
        migrate = self.setUp_fake()
        try:
            self.ab.startup_backup()
            self.ab.daily_backup_if_due()
            self.ab.daily_backup_if_due()
            self.assertEqual(len(self._calls), 1, "同日重复触发不应重复备份")
        finally:
            self.tearDown_fake(migrate)

    def test_failure_does_not_raise(self):
        migrate = self.setUp_fake()
        try:
            migrate.backup = lambda: self._fake_backup(fail=True)
            self.assertIsNone(self.ab.startup_backup(), "失败应返回 None 而非抛异常")
            self.assertIsNone(self.ab._last_backup_date, "失败不应登记日期（次日可重试）")
        finally:
            self.tearDown_fake(migrate)


class TestAccessLogMasking(unittest.TestCase):
    """访问日志脱敏（2026-10-08 实机发现）。

    桌面版把身份握手令牌交给前端走 `/?handshake=`，SSE 只能用 `?handshake_token=`；
    旧脱敏只覆盖 `auth=`，所以真令牌会**明文写进 gui.log**。另外旧替换串里混着一个
    旧脱敏只覆盖 auth=，所以真令牌会**明文写进 gui.log**。另外旧替换串里混着一个 SOH 控制字节
    """

    def test_credential_params_masked_and_others_kept(self):
        from gui import server

        cases = [
            ("GET /api/books?auth=T1&limit=5 HTTP/1.1",
             "GET /api/books?auth=***&limit=5 HTTP/1.1"),
            ("GET /api/events?task_id=q1&handshake_token=HTOK HTTP/1.1",
             "GET /api/events?task_id=q1&handshake_token=*** HTTP/1.1"),
            ("GET /?handshake=H1 HTTP/1.1",
             "GET /?handshake=*** HTTP/1.1"),
            ("GET /api/x?author=Bob HTTP/1.1",
             "GET /api/x?author=Bob HTTP/1.1"),
            ("GET /api/x?Auth=MIX&b=2 HTTP/1.1",
             "GET /api/x?Auth=***&b=2 HTTP/1.1"),
        ]
        for src, want in cases:
            with self.subTest(src=src):
                self.assertEqual(server._mask_sensitive_query(src), want)

    def test_no_control_bytes_in_masked_line(self):
        from gui import server

        out = server._mask_sensitive_query("GET /x?auth=SECRET&y=2 HTTP/1.1")
        bad = [c for c in out if ord(c) < 32 and c != " "]
        self.assertEqual(bad, [], f"日志行混进控制字符：{out!r}")

    def test_handler_path_uses_the_masker(self):
        """走真正的 _Handler.log_message，确认接线没断（只测纯函数会漏掉这一步）。"""
        import logging

        from gui import server

        class _Capturing(logging.Handler):
            def __init__(self):
                super().__init__()
                self.messages = []

            def emit(self, record):
                self.messages.append(record.getMessage())

        class _Stub:
            def address_string(self):
                return "127.0.0.1"

            log_message = server._Handler.log_message

        logger = logging.getLogger("novellab.server")
        cap = _Capturing()
        old_level = logger.level
        logger.setLevel(logging.INFO)
        logger.addHandler(cap)
        try:
            _Stub().log_message("%s %s", "GET /api/books?auth=SECRET&limit=5 HTTP/1.1", "200")
        finally:
            logger.removeHandler(cap)
            logger.setLevel(old_level)
        joined = chr(10).join(cap.messages)
        self.assertIn("auth=***", joined, f"日志里没有脱敏结果：{joined}")
        self.assertNotIn("SECRET", joined, f"令牌明文出现在日志里：{joined}")
if __name__ == "__main__":
    unittest.main()
