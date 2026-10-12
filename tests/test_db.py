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


if __name__ == "__main__":
    unittest.main(verbosity=2)
