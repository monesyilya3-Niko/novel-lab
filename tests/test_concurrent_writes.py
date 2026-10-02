"""并发写压测回归：ThreadingHTTPServer 多线程下 SQLite 无丢写、无锁异常。

背景：GUI 用 ThreadingHTTPServer，每本书一个分析线程 + 若干 HTTP 线程并发写库。
db.py 采用每线程独立连接 + WAL + busy_timeout=5000 + tx() 统一事务。
本测试模拟真实并发写（多线程交错 INSERT），断言：
1. 最终行数精确等于 线程数 × 每线程写入数（无丢写）；
2. 无 "database is locked" 异常逃逸（busy_timeout 应消化写冲突）。

隔离：_isolation.isolate_paths 重定向 STATE_ROOT 到临时目录，不碰真实库。
"""
from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_ROOT = _TESTS_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_TESTS_DIR))
import _isolation  # noqa: E402

from gui import db  # noqa: E402

THREADS = 8
WRITES_PER_THREAD = 50


class ConcurrentWriteTest(unittest.TestCase):
    def setUp(self):
        self._iso = _isolation.isolate_paths(Path(tempfile.mkdtemp(prefix="concw_")))
        self._iso.__enter__()
        db.init_schema()
        with db.tx() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS _concw_probe "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, tid INTEGER, seq INTEGER)"
            )

    def tearDown(self):
        db.close()
        self._iso.__exit__(None, None, None)

    def test_concurrent_writes_no_loss(self):
        errors: list[BaseException] = []
        barrier = threading.Barrier(THREADS)

        def worker(tid: int):
            try:
                barrier.wait(timeout=30)  # 齐跑，最大化写冲突
                for seq in range(WRITES_PER_THREAD):
                    with db.tx() as conn:
                        conn.execute(
                            "INSERT INTO _concw_probe (tid, seq) VALUES (?, ?)",
                            (tid, seq),
                        )
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=120)
        self.assertFalse(
            [t for t in threads if t.is_alive()], "有线程超时未退出"
        )
        self.assertEqual(errors, [], f"并发写出现异常：{errors[:3]}")
        with db.tx() as conn:
            (total,) = conn.execute("SELECT COUNT(*) FROM _concw_probe").fetchone()
            per_thread = conn.execute(
                "SELECT tid, COUNT(*) FROM _concw_probe GROUP BY tid"
            ).fetchall()
        self.assertEqual(total, THREADS * WRITES_PER_THREAD, "丢写：总行数不符")
        self.assertEqual(len(per_thread), THREADS, "有线程的写入完全丢失")
        for tid, cnt in per_thread:
            self.assertEqual(cnt, WRITES_PER_THREAD, f"线程 {tid} 丢写")


if __name__ == "__main__":
    unittest.main()
