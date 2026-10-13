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


class TestSaveStateAuthorityFirst(unittest.TestCase):
    """save_state 的权威优先语义（2026-10-13 审计修复 D10）。

    缺陷背景：原实现是「先 _save_state_json（无 try）→ 后 upsert_task（被 try
    吞）」，与设计**正好相反**（upsert_task 的文档写明"先写 SQLite（权威），
    后原子写 JSON（降级副本）"）。实测后果：JSON 副本写失败（磁盘满、权限、
    路径异常）会**抛出并阻断 SQLite 权威写**，权威库丢更新——而 JSON 只是
    可再生的降级副本，让它拖垮权威源是本末倒置。

    修法：直接委托 upsert_task（权威优先的完整实现）；仅当 SQLite 不可用时
    才回退为"只写 JSON"，且副本写失败也不再向上抛。
    """

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="authfirst_"))
        self._iso = _isolation.isolate_paths(self._tmp)
        self._iso.__enter__()
        db.init_schema()
        db.apply_migrations()

    def tearDown(self):
        self._iso.__exit__(None, None, None)

    def test_normal_save_writes_both(self):
        """反向守卫：正常路径两侧都写。"""
        from gui import state_store
        state_store.save_state({"book_id": "b1", "status": "running", "state_revision": 1})
        n = db.get_conn().execute(
            "SELECT COUNT(*) FROM analysis_tasks WHERE book_id='b1'").fetchone()[0]
        self.assertEqual(n, 1, "SQLite 未写入")
        self.assertTrue(state_store.state_path_for("b1").is_file(), "JSON 副本未写入")

    def test_json_failure_does_not_block_authority(self):
        """核心守卫：JSON 副本写失败时，SQLite 权威写必须仍然成功。"""
        from gui import config, state_store

        blocker = self._tmp / "blocker_file"
        blocker.write_text("x", encoding="utf-8")
        orig = config.STATE_JSON_DIR
        config.STATE_JSON_DIR = blocker      # 目录位置是个文件 → mkdir 失败
        try:
            state_store.save_state(
                {"book_id": "b2", "status": "running", "state_revision": 1})
        finally:
            config.STATE_JSON_DIR = orig

        n = db.get_conn().execute(
            "SELECT COUNT(*) FROM analysis_tasks WHERE book_id='b2'").fetchone()[0]
        self.assertEqual(n, 1, "JSON 副本失败阻断了 SQLite 权威写（权威库丢更新）")

    def test_json_failure_does_not_raise(self):
        """副本写失败不得向上抛——权威库可能已更新，抛异常会让调用方误判。"""
        from gui import config, state_store

        blocker = self._tmp / "blocker2"
        blocker.write_text("x", encoding="utf-8")
        orig = config.STATE_JSON_DIR
        config.STATE_JSON_DIR = blocker
        try:
            try:
                state_store.save_state({"book_id": "b3", "status": "running"})
            except Exception as exc:  # noqa: BLE001
                self.fail(f"副本失败却抛出了异常: {type(exc).__name__}: {exc}")
        finally:
            config.STATE_JSON_DIR = orig

    def test_degrades_to_json_only_when_db_unavailable(self):
        """反向守卫：SQLite 不可用时仍须写 JSON（保留原降级能力）。"""
        from gui import db as _db
        from gui import state_store

        orig = _db.upsert_task
        _db.upsert_task = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("库损坏"))
        try:
            state_store.save_state({"book_id": "b4", "status": "running"})
        finally:
            _db.upsert_task = orig

        self.assertTrue(state_store.state_path_for("b4").is_file(),
                        "库不可用时连 JSON 降级副本都没写")

    def test_missing_book_id_still_raises(self):
        """反向守卫：缺 book_id 仍应抛（这是调用方的编程错误，不是可降级场景）。"""
        from gui import state_store
        with self.assertRaises(ValueError):
            state_store.save_state({"status": "running"})


if __name__ == "__main__":
    unittest.main()
