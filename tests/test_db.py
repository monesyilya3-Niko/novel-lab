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
        config.STATE_ROOT = cls._tmp / "gui_state"
        config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
        db._reset_conn()

    @classmethod
    def tearDownClass(cls):
        db.close()
        config.STATE_ROOT = cls._orig_state_root
        db._reset_conn()

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
        self.assertEqual(applied, [1], "应执行 0001 迁移并返回版本 [1]")
        conn = db.get_conn()
        row = conn.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()
        self.assertEqual(row["n"], 1)

    def test_apply_migrations_idempotent(self):
        db.init_schema()
        db.apply_migrations()
        # 再跑一次：不应重复执行、不应重复登记。
        applied_again = db.apply_migrations()
        self.assertEqual(applied_again, [], "已执行迁移不应再次执行")
        conn = db.get_conn()
        row = conn.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()
        self.assertEqual(row["n"], 1)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
