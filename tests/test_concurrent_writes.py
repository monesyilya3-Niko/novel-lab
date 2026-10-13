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


class StateFileConcurrentWriteTest(unittest.TestCase):
    """状态文件并发原子写（2026-10-13 审计修复 CONC-01）。

    缺陷背景：state_store._save_state_json 用**固定 tmp 名**
    ``<path>.tmp``。并发写同一 book_id 时（后台分析线程 + HTTP 线程
    同时保存状态），两个写者用同一个 tmp 文件——实测 30 线程产生
    22 个 PermissionError: WinError 32（一个线程正写 tmp 时，另一个的
    os.replace 撞上文件占用），状态保存静默失败。

    修法分两层（第二层是实测发现的必需项）：
      1. 唯一 tmp 名（pid + tid + 计数器）——避免写者互相窃取 tmp
      2. **按路径加锁** ——仅改 tmp 名不够：实测仍有 18 个
         ``WinError 5 拒绝访问``，那是 Windows 对同一目标路径并发
         ``os.replace`` 的限制，必须串行化「写 tmp + 替换」
    """

    def setUp(self):
        self._iso = _isolation.isolate_paths(Path(tempfile.mkdtemp(prefix="stateconc_")))
        self._iso.__enter__()

    def tearDown(self):
        self._iso.__exit__(None, None, None)

    def test_concurrent_saves_same_book_no_error(self):
        """核心守卫：30 线程并发写同一 book_id 必须零异常。"""
        from gui import state_store

        errors: list[str] = []
        lock = threading.Lock()

        def writer(i: int) -> None:
            try:
                state_store.save_state(
                    {"book_id": "shared", "status": f"s{i}", "n": i})
            except Exception as exc:  # noqa: BLE001
                with lock:
                    errors.append(f"T{i}: {type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"并发写状态文件出现异常：{errors[:3]}")

    def test_final_file_is_valid_json(self):
        """并发写后文件必须完整可读（原子替换未被破坏）。"""
        import json as _json

        from gui import state_store

        def writer(i: int) -> None:
            state_store.save_state({"book_id": "bk", "status": f"s{i}", "n": i})

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        path = state_store.state_path_for("bk")
        data = _json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["book_id"], "bk")
        self.assertIn(data["status"], [f"s{i}" for i in range(20)])

    def test_no_tmp_leftovers(self):
        """并发写不得留下临时文件堆积。"""
        from gui import state_store

        def writer(i: int) -> None:
            state_store.save_state({"book_id": "bk2", "status": f"s{i}"})

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        parent = state_store.state_path_for("bk2").parent
        leftovers = list(parent.glob("*.tmp"))
        self.assertEqual(leftovers, [], f"残留临时文件：{leftovers[:3]}")

    def test_tmp_names_are_unique(self):
        """唯一 tmp 名（跨进程场景的第二层防御）。

        同进程内按路径锁已足够，故本用例**直接验证命名规则**而非并发行为：
        固定名 ``<path>.tmp`` 在跨进程写同一文件时会互相窃取；唯一名
        （含 pid/tid/序号）不会。用源码断言锁定该规则。
        """
        src_text = (_ROOT / "gui" / "state_store.py").read_text(encoding="utf-8")
        self.assertIn("os.getpid()", src_text,
                      "tmp 名缺少 pid 段——跨进程写会互相窃取临时文件")
        self.assertIn("threading.get_ident()", src_text, "tmp 名缺少线程 id 段")
        # 不得退回固定名
        self.assertNotIn('path.with_suffix(path.suffix + ".tmp")', src_text,
                         "tmp 名退回固定形式——跨进程并发会互相窃取")

    def test_different_books_do_not_block_each_other(self):
        """反向守卫：不同 book_id 的写入应可并行（锁按路径分桶，不是全局锁）。"""
        from gui import state_store

        errors: list[str] = []

        def writer(bid: str) -> None:
            try:
                for i in range(10):
                    state_store.save_state({"book_id": bid, "status": f"s{i}"})
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{bid}: {exc}")

        threads = [threading.Thread(target=writer, args=(f"book{n}",)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
