"""B3 回归：跨线程关闭 SQLite 连接是否真正释放 FD。

验证 _prune_dead_threads_locked() 从主线程关闭死线程的连接后，
数据库文件的 FD 确实被内核回收（/proc/self/fd 不再含该文件）。
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolation  # noqa: E402

from gui import db  # noqa: E402


def _open_fds_for(path: Path) -> set[int]:
    """返回当前进程中指向 path 的 FD 集合（Linux /proc）。"""
    result = set()
    fd_dir = Path("/proc/self/fd")
    if not fd_dir.is_dir():
        return result
    target = str(path.resolve())
    for fd_name in fd_dir.iterdir():
        try:
            if os.readlink(fd_name) == target:
                result.add(int(fd_name.name))
        except OSError:
            pass
    return result


class CrossThreadCloseTest(unittest.TestCase):
    def setUp(self):
        self._iso = _isolation.isolate_paths(Path(tempfile.mkdtemp(prefix="b3_")))
        self._iso.__enter__()
        db._reset_conn()

    def tearDown(self):
        db._reset_conn()
        self._iso.__exit__(None, None, None)

    def test_prune_dead_thread_releases_fd(self):
        db_path = db.db_path()
        # 工作线程内建连接并执行一次查询（确保 FD 真正打开）
        tid_holder: list[int] = []

        def worker():
            tid_holder.append(threading.get_ident())
            conn = db.get_conn()
            conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
            conn.commit()

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        worker_tid = tid_holder[0]

        # 线程已死，但连接仍在 _conns 中
        with db._conns_lock:
            self.assertIn(worker_tid, db._conns)

        # FD 应处于打开状态
        fds_before = _open_fds_for(db_path)
        self.assertTrue(fds_before, "工作线程的 DB 连接 FD 应已打开")

        # 主线程执行 prune（跨线程 close）
        with db._conns_lock:
            db._prune_dead_threads_locked()
            self.assertNotIn(worker_tid, db._conns)

        # 给内核一点时间回收（通常是同步的）
        time.sleep(0.1)
        fds_after = _open_fds_for(db_path)
        # 主线程自己的连接可能还开着，但工作线程的 FD 必须消失。
        # 由于每线程独立连接，工作线程的 FD 集合应不再出现。
        leaked = fds_before - fds_after
        self.assertTrue(
            leaked,
            f"prune 后工作线程的 FD 应被释放，释放前={fds_before}，释放后={fds_after}",
        )

    def test_close_all_from_main_thread(self):
        """db.close() 从主线程关闭所有连接（含其他线程的）后 FD 清零。"""
        db_path = db.db_path()

        def worker():
            conn = db.get_conn()
            conn.execute("CREATE TABLE IF NOT EXISTS t2 (id INTEGER)")
            conn.commit()

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        with db._conns_lock:
            # 注意：get_conn 每 50 次调用触发一次死线程 prune，3 个工作线程的
            # 连接可能已被部分清理；此处只要求至少残留 1 条待关闭连接。
            n_conns = len(db._conns)
        self.assertGreaterEqual(n_conns, 1)

        db.close()

        with db._conns_lock:
            self.assertEqual(len(db._conns), 0)
        time.sleep(0.1)
        self.assertEqual(
            _open_fds_for(db_path), set(), "close() 后不应残留 DB 文件 FD"
        )


if __name__ == "__main__":
    unittest.main()
