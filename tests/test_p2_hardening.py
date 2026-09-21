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

from gui import config  # noqa: E402
from gui import logging_setup  # noqa: E402


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
        cls._tmp = Path(tempfile.mkdtemp(prefix="auth_qa_"))
        config.LOCK_PATH = cls._tmp / ".lock"
        config.API_TOKEN = cls.TOKEN
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


if __name__ == "__main__":
    unittest.main()
