"""SQLite 持久化层单元测试（W06）。

覆盖：
1. init_schema() 建 6 表（schema_migrations/books/assets/reports/analysis_tasks/genres）。
2. apply_migrations() 幂等（重复执行不重复登记版本）。
3. tx() 事务提交 / 回滚。
4. close() 刷盘（wal_checkpoint）。

纯标准库 unittest，隔离到临时目录（monkeypatch config.STATE_ROOT → 重建 db 连接）。
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _isolation  # noqa: E402

from gui import config, db  # noqa: E402

EXPECTED_TABLES = {
    "schema_migrations", "books", "assets", "reports", "analysis_tasks", "genres",
}


class TestDb(unittest.TestCase):
    """db 连接 / schema / 迁移 / 事务。"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="db_qa_"))
        cls._orig_state_root = config.STATE_ROOT
        # DB_PATH / LOCK_PATH 是 STATE_ROOT 的导入期快照，不一起重定向就会指向真实数据目录。
        cls._orig_derived = {"DB_PATH": config.DB_PATH, "LOCK_PATH": config.LOCK_PATH}
        config.STATE_ROOT = cls._tmp / "gui_state"
        config.DB_PATH = config.STATE_ROOT / "index.db"
        config.LOCK_PATH = config.STATE_ROOT / ".lock"
        config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
        db._reset_conn()

    @classmethod
    def tearDownClass(cls):
        db.close()
        config.STATE_ROOT = cls._orig_state_root
        for name, value in cls._orig_derived.items():
            setattr(config, name, value)
        db._reset_conn()
        _isolation.remove_tree(cls._tmp)

    def tearDown(self):
        # 每测清空表，保证独立性。
        try:
            db.reset_all()
        except sqlite3.Error:
            pass

    def _table_names(self) -> set[str]:
        conn = db.get_conn()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return {r["name"] for r in rows}

    def test_init_schema_creates_all_tables(self):
        db.init_schema()
        tables = self._table_names()
        self.assertTrue(EXPECTED_TABLES.issubset(tables),
                        f"缺表: {EXPECTED_TABLES - tables}")

    def test_init_schema_idempotent(self):
        db.init_schema()
        db.init_schema()  # 再执行一次不抛异常。
        tables = self._table_names()
        self.assertTrue(EXPECTED_TABLES.issubset(tables))

    def test_apply_migrations_records_version(self):
        db.init_schema()
        applied = db.apply_migrations()
        self.assertEqual(applied, [1, 2, 3, 4], "应执行 0001、0002、0003、0004 迁移并返回版本 [1, 2, 3, 4]")
        conn = db.get_conn()
        row = conn.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()
        self.assertEqual(row["n"], 4)

    def test_apply_migrations_idempotent(self):
        db.init_schema()
        db.apply_migrations()
        # 再跑一次：不应重复执行、不应重复登记。
        applied_again = db.apply_migrations()
        self.assertEqual(applied_again, [], "已执行迁移不应再次执行")
        conn = db.get_conn()
        row = conn.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()
        self.assertEqual(row["n"], 4)

    def test_tx_commit(self):
        db.init_schema()
        with db.tx() as conn:
            conn.execute(
                "INSERT INTO books (book_id, title) VALUES (?, ?)",
                ("bk-tx", "事务书"),
            )
        row = db.get_conn().execute(
            "SELECT title FROM books WHERE book_id = ?", ("bk-tx",)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], "事务书")

    def test_tx_rollback(self):
        db.init_schema()
        with self.assertRaises(RuntimeError):
            with db.tx() as conn:
                conn.execute(
                    "INSERT INTO books (book_id, title) VALUES (?, ?)",
                    ("bk-rollback", "回滚书"),
                )
                raise RuntimeError("故意失败")
        row = db.get_conn().execute(
            "SELECT 1 FROM books WHERE book_id = ?", ("bk-rollback",)
        ).fetchone()
        self.assertIsNone(row, "事务失败应回滚，不留半成品")

    def test_close_flushes_and_resets(self):
        db.init_schema()
        db.apply_migrations()
        # 写一条数据后 close。
        with db.tx() as conn:
            conn.execute(
                "INSERT INTO books (book_id, title) VALUES (?, ?)",
                ("bk-close", "刷盘书"),
            )
        db.close()
        # 重新打开连接，数据仍在（已刷盘）。
        row = db.get_conn().execute(
            "SELECT title FROM books WHERE book_id = ?", ("bk-close",)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], "刷盘书")

    def test_get_books_filter_by_book_id_and_genre(self):
        """get_books 支持 book_id / genre 过滤（book 种类筛选不泄漏，回归 QA bug）。"""
        db.init_schema()
        with db.tx() as conn:
            conn.execute(
                "INSERT INTO books (book_id, title, genre, status) VALUES (?, ?, ?, ?)",
                ("bk-a", "书A", "xianxia", "done"),
            )
            conn.execute(
                "INSERT INTO books (book_id, title, genre, status) VALUES (?, ?, ?, ?)",
                ("bk-b", "书B", "gongdou", "done"),
            )
            conn.execute(
                "INSERT INTO books (book_id, title, genre, status) VALUES (?, ?, ?, ?)",
                ("bk-c", "书C", "xianxia", "idle"),
            )
        # book_id 精确过滤。
        rows = db.get_books(book_id="bk-a")
        self.assertEqual([r["book_id"] for r in rows], ["bk-a"])
        # genre 精确过滤。
        rows = db.get_books(genre="xianxia")
        self.assertEqual({r["book_id"] for r in rows}, {"bk-a", "bk-c"})
        # status + book_id 组合。
        rows = db.get_books(status="done", book_id="bk-b")
        self.assertEqual([r["book_id"] for r in rows], ["bk-b"])
        # 无匹配返回空列表。
        self.assertEqual(db.get_books(book_id="nonexistent"), [])
        self.assertEqual(db.get_books(genre="nonexistent"), [])

    def test_get_books_no_injection(self):
        """get_books 参数化查询防注入：恶意输入不改变结果集语义。"""
        db.init_schema()
        with db.tx() as conn:
            conn.execute(
                "INSERT INTO books (book_id, title, genre) VALUES (?, ?, ?)",
                ("bk-safe", "安全书", "xianxia"),
            )
        # 注入片段应被当作字面量，匹配不到任何行。
        rows = db.get_books(book_id="' OR '1'='1")
        self.assertEqual(rows, [])
        rows = db.get_books(genre="xianxia' OR '1'='1")
        self.assertEqual(rows, [])

    def test_table_exists(self):
        """table_exists 准确判断表是否存在。"""
        db.init_schema()
        self.assertTrue(db.table_exists("assets"))
        self.assertTrue(db.table_exists("analysis_tasks"))
        self.assertFalse(db.table_exists("nonexistent_table_xyz"))

    def test_backup_captures_wal_writes(self):
        """备份必须包含 WAL 中未 checkpoint 的写入（2026-10-12 修）。

        缺陷背景：backup_to 的**回退分支**原本是裸 ``shutil.copy2(src, dst)``。
        WAL 模式下，刚建的表与数据可能整个还在 ``-wal`` 文件里——实测
        只复制主库得到的"备份"打开后报 ``no such table``，即备份无效。

        本用例验证正常路径（Connection.backup）确实包含最新写入。
        """
        db.init_schema()
        db.apply_migrations()
        conn = db.get_conn()
        with db.tx() as c:
            c.execute("INSERT INTO assets (asset_key,kind,name,path) "
                      "VALUES ('wal_probe','voice','探针','p')")

        dst = self._tmp / "wal_backup.db"
        db.backup_to(dst)

        import sqlite3 as _sq
        chk = _sq.connect(str(dst))
        try:
            n = chk.execute(
                "SELECT COUNT(*) FROM assets WHERE asset_key='wal_probe'").fetchone()[0]
            self.assertEqual(n, 1, "备份未包含 WAL 中的最新写入")
        finally:
            chk.close()

    def test_naive_copy_without_wal_is_incomplete(self):
        """反向守卫：证明"只复制主库"在 WAL 未合并时确实丢数据。

        这不是在测产品代码，而是把**缺陷的成因**固化成可执行证据：
        若将来有人"简化"回退分支为裸 copy2，本用例会说明为什么不行。

        注意：本用例必须用一个**全新的库连接**，确保 WAL 里有未合并内容。
        若沿用 setUpClass 的共享连接，前序测试的 checkpoint 会让 WAL 变空，
        断言就失去意义（实测踩过：该守卫一度假红）。
        """
        import sqlite3 as _sq

        fresh = self._tmp / "fresh_wal.db"
        conn = _sq.connect(str(fresh))
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE t (v TEXT)")
            conn.execute("INSERT INTO t VALUES ('还在WAL里')")
            conn.commit()
            # 此时表结构与数据都在 -wal 中（主库仅 4KB 空壳）

            naive = self._tmp / "fresh_naive.db"
            import shutil as _sh
            _sh.copy2(fresh, naive)      # 只复制主库，不带 -wal

            chk = _sq.connect(str(naive))
            try:
                tables = {r[0] for r in chk.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertNotIn(
                    "t", tables,
                    "裸 copy2 竟拿到了完整表——该缺陷的前提不成立，"
                    "应重新评估回退分支的实现方式",
                )
            finally:
                chk.close()
        finally:
            conn.close()


class TestSchemaInitTransactionSafety(unittest.TestCase):
    """init_schema 不得吞掉调用方事务（2026-10-13 审计修复 D13）。

    缺陷背景：init_schema 经 _exec_sql_file 调 ``conn.executescript()``，
    而 executescript **先隐式提交当前事务**再执行脚本。若调用方已在
    ``with db.tx()`` 里，一次 init_schema() 就把那个事务提交掉——
    后续抛错时回滚失效，半成品数据留在库里。

    实测（修复前）：事务内 INSERT → init_schema() → in_transaction
    由 True 变 False → raise 触发 rollback 后该行仍残留。

    修法两步（第一步单独做不够）：
      1. 改逐条 execute（复用 split_sql_statements）
      2. **末尾的 commit 只在没有活动事务时执行** —— 显式 commit 同样会
         提交调用方的事务，实测仅去掉 executescript 仍不生效
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="schematx_"))
        cls._orig = {
            "STATE_ROOT": config.STATE_ROOT,
            "DB_PATH": config.DB_PATH,
            "LOCK_PATH": config.LOCK_PATH,
        }
        config.STATE_ROOT = cls._tmp / "gui_state"
        config.DB_PATH = config.STATE_ROOT / "index.db"
        config.LOCK_PATH = config.STATE_ROOT / ".lock"
        config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
        db._reset_conn()
        db.init_schema()
        db.apply_migrations()

    @classmethod
    def tearDownClass(cls):
        db.close()
        for k, v in cls._orig.items():
            setattr(config, k, v)
        db._reset_conn()
        _isolation.remove_tree(cls._tmp)

    def test_init_schema_preserves_caller_transaction(self):
        """核心守卫：事务内调 init_schema 后，回滚必须仍然有效。"""
        conn = db.get_conn()
        marker = "tx_marker_001"
        try:
            with db.tx() as c:
                c.execute("INSERT INTO books (book_id, title, status) VALUES (?, '书', 'idle')",
                          (marker,))
                self.assertTrue(conn.in_transaction, "进入事务后应处于事务中")
                db.init_schema()          # 关键调用
                self.assertTrue(conn.in_transaction,
                                "init_schema 提交了调用方的事务——回滚将失效")
                raise RuntimeError("模拟业务失败")
        except RuntimeError:
            pass
        n = conn.execute("SELECT COUNT(*) FROM books WHERE book_id = ?",
                         (marker,)).fetchone()[0]
        self.assertEqual(n, 0, "事务未被回滚——init_schema 吞掉了调用方事务")

    def test_init_schema_works_outside_transaction(self):
        """反向守卫：事务外调用仍应正常建表（幂等）。"""
        db.init_schema()
        db.init_schema()          # 幂等
        tables = [r[0] for r in db.get_conn().execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        self.assertIn("books", tables)
        self.assertIn("schema_migrations", tables)


class TestMigrationUsesImmediateTransaction(unittest.TestCase):
    """迁移事务必须用 BEGIN IMMEDIATE（2026-10-13 审计修复 D18）。

    缺陷背景：apply_migrations 用裸 ``BEGIN``（DEFERRED）——它**不立即取写锁**，
    等到第一条写语句才尝试升级。两个进程并发迁移时（桌面版 + CLI 同时启动
    是真实场景），双方都可能先读到旧快照，随后一条升级锁失败 →
    ``database is locked``，迁移中断。

    修法：BEGIN IMMEDIATE 在起点就取写锁，把冲突前移——后来者直接等锁
    （受 busy_timeout 约束），而不是走到一半才失败。

    用静态断言而非多进程实测：后者在 Windows 上启动开销大且不稳定
    （实测跑 multiprocessing 会挂住），而该行为是 SQLite 的确定性语义。
    """

    def test_apply_migrations_uses_begin_immediate(self):
        src_text = (ROOT / "gui" / "db.py").read_text(encoding="utf-8")
        start = src_text.index("def apply_migrations()")
        end = src_text.index("def ", start + 10)
        block = src_text[start:end]
        self.assertIn('conn.execute("BEGIN IMMEDIATE")', block,
                      "迁移事务退回裸 BEGIN 了——并发迁移会撞锁失败")
        self.assertNotIn('conn.execute("BEGIN")', block,
                         "仍有裸 BEGIN（DEFERRED）——迁移必须用 IMMEDIATE")


class TestResetAllCoversAllTables(unittest.TestCase):
    """reset_all 必须清空全部业务表（2026-10-13 审计修复 D20）。

    缺陷背景：表清单硬编码 6 张（assets/reports/books/analysis_tasks/
    genres/schema_migrations），而迁移 0002~0004 又加了 9 张
    （essence_* ×4、writing_* ×5）。实测：往各表插数据后 reset_all，
    6 张老表归零、**9 张新表各残留 1 行**——测试隔离不彻底。

    修法：从 sqlite_master 动态发现表，新增迁移时自动覆盖。
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = Path(tempfile.mkdtemp(prefix="resetall_"))
        cls._orig = {
            "STATE_ROOT": config.STATE_ROOT,
            "DB_PATH": config.DB_PATH,
            "LOCK_PATH": config.LOCK_PATH,
        }
        config.STATE_ROOT = cls._tmp / "gui_state"
        config.DB_PATH = config.STATE_ROOT / "index.db"
        config.LOCK_PATH = config.STATE_ROOT / ".lock"
        config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
        db._reset_conn()
        db.init_schema()
        db.apply_migrations()

    @classmethod
    def tearDownClass(cls):
        db.close()
        for k, v in cls._orig.items():
            setattr(config, k, v)
        db._reset_conn()
        _isolation.remove_tree(cls._tmp)

    def test_all_business_tables_emptied(self):
        """核心守卫：所有业务表（含 0002~0004 新表）都必须被清空。"""
        conn = db.get_conn()
        # 往新表插数据（老表由 db.init_schema 保证存在）
        conn.execute("INSERT INTO essence_books (book_id, title, genre)"
                     " VALUES ('rb', '书', 'xuanhuan')")
        conn.execute("INSERT INTO essence_assets (book_id, category, title, content)"
                     " VALUES ('rb', 'hook', 'a', 'c')")
        conn.execute("INSERT INTO books (book_id, title, status) VALUES ('rb', '书', 'idle')")
        conn.commit()

        db.reset_all()

        for table in ("essence_books", "essence_assets", "books"):
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            self.assertEqual(n, 0, f"{table} 未被 reset_all 清空（表清单漏了它）")

    def test_table_list_is_discovered_dynamically(self):
        """结构守卫：表清单不得退回硬编码——否则将来加表又会漏。"""
        src_text = (ROOT / "gui" / "db.py").read_text(encoding="utf-8")
        start = src_text.index("def reset_all()")
        block = src_text[start:start + 1200]
        self.assertIn("sqlite_master", block,
                      "reset_all 又变成硬编码表清单了——新增迁移会再次漏清")


if __name__ == "__main__":
    unittest.main(verbosity=2)
