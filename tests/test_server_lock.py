"""单实例锁（W09）stale lock 自动清理测试（FIX-1）。

覆盖：
1. ``_pid_is_alive``：当前进程存活 / 已退出 pid / 非法 pid。
2. stale（已死 pid）锁文件 → ``_acquire_lock`` 自动清理并成功获取，且内容更新为
   当前 pid、不残留 ``.stale-*`` 临时文件。
3. 存活 pid（当前进程）→ 正确拒绝二次启动，且不破坏原锁。
4. 非法 / 空内容 → 保守视为 stale 并清理。
5. 释放后可重新获取；真·双实例第二个被拒。

注（L4 澄清）：本文件用 ``subprocess.Popen`` 派生进程来模拟「外部实例」。但需注意
**Popen 直接派生的子进程与独立/分离启动的进程行为不同**：``os.kill(pid, 0)`` 对前者
不报错，对后者（句柄已脱离父进程）才在 Windows 抛 ``WinError 87``。锁探测的真实目标
是后者，故 FIX-1 的 ``ctypes`` 存活性判定才是必要修复（详见
``test_pid_is_alive_live_external_process`` docstring）。

纯标准库 unittest；锁文件隔离到临时目录，绝不触碰真实 ``gui_state/``。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import (
    config,  # noqa: E402
    server,  # noqa: E402
)


class TestStaleLock(unittest.TestCase):
    """stale lock 检测与原子清理。"""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="gui_lock_qa_"))
        self._orig_lock = config.LOCK_PATH
        config.LOCK_PATH = self._tmp / ".lock"
        self._servers: list = []

    def tearDown(self):
        for s in self._servers:
            try:
                s._release_lock()
            except Exception:  # noqa: BLE001 — 清理尽力而为。
                pass
        config.LOCK_PATH = self._orig_lock
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _new_server(self) -> server.GuiServer:
        s = server.GuiServer()
        self._servers.append(s)
        return s

    @staticmethod
    def _dead_pid() -> int:
        """产生一个必定已退出的进程 pid（spawn 后立即 wait）。"""
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        return proc.pid

    @staticmethod
    def _spawn_live() -> subprocess.Popen:
        """起一个存活约 30s 的子进程，模拟「真实存活的外部实例」。"""
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        for _ in range(100):  # 轮询确保进程已起来（避免竞态）。
            if server._pid_is_alive(proc.pid):
                break
            time.sleep(0.05)
        return proc

    # ------------------------------------------------------------------
    # _pid_is_alive
    # ------------------------------------------------------------------

    def test_pid_is_alive_current_process(self):
        self.assertTrue(server._pid_is_alive(os.getpid()))

    def test_pid_is_alive_dead_process(self):
        self.assertFalse(server._pid_is_alive(self._dead_pid()))

    def test_pid_is_alive_invalid(self):
        self.assertFalse(server._pid_is_alive(0))
        self.assertFalse(server._pid_is_alive(-1))

    def test_pid_is_alive_live_external_process(self):
        """FIX-1 回归：os.kill 对「独立/分离启动的存活进程」误报（WinError 87）时仍须判存活。

        实测 Windows + CPython 3.13 下，``os.kill(pid, 0)`` 对**独立/分离启动**的存活
        进程会抛 ``OSError[87]``（ERROR_INVALID_PARAMETER），若据此判死会误清真实存活
        实例的锁（单实例失效）。这是**条件性**现象：由本进程 ``subprocess.Popen``
        **直接派生**的子进程（本测试用 ``_spawn_live``）持有可继承的进程句柄，
        ``os.kill`` 对之不报错；只有**独立/分离启动**（句柄已脱离、父进程无法回收）
        的进程才触发 WinError 87——而单实例锁探测的目标恰恰是后者，故该 bug 在真实
        场景（用户直接双击启动的独立实例）**必现**。
        """
        proc = self._spawn_live()
        try:
            self.assertTrue(server._pid_is_alive(proc.pid),
                            "存活的外部进程必须判为存活，绝不误清活锁")
        finally:
            proc.terminate()
            proc.wait()

    def test_pid_is_alive_exited_process_is_dead(self):
        """FIX-1 回归：已退出（僵尸句柄残留）进程必须判为已退出。

        实测 ``os.kill`` 会对残留句柄的僵尸进程误报存活，若据此判活会导致
        stale 锁永久阻塞后续启动（本 FIX 要解决的原始 bug）。
        """
        proc = self._spawn_live()
        pid = proc.pid
        proc.terminate()
        proc.wait()
        self.assertFalse(server._pid_is_alive(pid),
                         "已退出进程不得判为存活，否则 stale 锁永久阻塞启动")

    # ------------------------------------------------------------------
    # _acquire_lock
    # ------------------------------------------------------------------

    def test_acquire_stale_dead_pid_cleans_and_acquires(self):
        lock = config.LOCK_PATH
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(str(self._dead_pid()), encoding="ascii")

        srv = self._new_server()
        self.assertTrue(srv._acquire_lock(), "stale 锁应被自动清理并获取成功")
        # 锁内容应更新为当前进程 pid。
        self.assertEqual(lock.read_text(encoding="ascii").strip(), str(os.getpid()))
        # 原子清理不残留 .stale-* 临时文件。
        self.assertEqual(list(lock.parent.glob("*.stale-*")), [])

    def test_acquire_live_pid_rejected(self):
        lock = config.LOCK_PATH
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(str(os.getpid()), encoding="ascii")  # 当前进程存活
        srv = self._new_server()
        self.assertFalse(srv._acquire_lock(), "存活实例的锁应拒绝二次启动")
        # 原锁内容不被破坏。
        self.assertEqual(lock.read_text(encoding="ascii").strip(), str(os.getpid()))

    def test_acquire_lock_held_by_live_external_process_rejected(self):
        """FIX-1 回归：锁被真实存活的外部实例持有 → 拒绝二次启动且不破坏其锁。

        这是 ``os.kill`` 误判会真实触发的场景：外部实例仍活着（监听端口），
        若误判其 pid 已死，会清掉它的锁并启动第二个实例。
        """
        proc = self._spawn_live()
        try:
            lock = config.LOCK_PATH
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text(str(proc.pid), encoding="ascii")
            srv = self._new_server()
            self.assertFalse(srv._acquire_lock(), "活锁必须拒绝二次启动")
            # 原锁内容与文件均不被破坏，不残留 .stale-* 临时文件。
            self.assertEqual(lock.read_text(encoding="ascii").strip(), str(proc.pid))
            self.assertEqual(list(lock.parent.glob("*.stale-*")), [])
        finally:
            proc.terminate()
            proc.wait()

    def test_acquire_invalid_content_treated_stale(self):
        lock = config.LOCK_PATH
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("not-a-pid", encoding="ascii")
        srv = self._new_server()
        self.assertTrue(srv._acquire_lock(), "非法内容应保守视为 stale 并清理")

    def test_acquire_empty_content_treated_stale(self):
        lock = config.LOCK_PATH
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("", encoding="ascii")
        srv = self._new_server()
        self.assertTrue(srv._acquire_lock(), "空内容应保守视为 stale 并清理")

    def test_double_acquire_second_rejected(self):
        s1 = self._new_server()
        self.assertTrue(s1._acquire_lock())
        s2 = self._new_server()
        self.assertFalse(s2._acquire_lock(), "已存在存活实例，第二个应被拒")

    def test_release_then_reacquire(self):
        s1 = self._new_server()
        self.assertTrue(s1._acquire_lock())
        s1._release_lock()
        self.assertFalse(config.LOCK_PATH.exists(), "释放后锁文件应被删除")
        s2 = self._new_server()
        self.assertTrue(s2._acquire_lock(), "释放后应可重新获取")


class TestParentWatchdog(unittest.TestCase):
    """Electron 模式下的父进程看护（2026-10-13 审计修复 ELE-03）。

    缺陷背景：桌面版主进程被**强杀**（任务管理器结束进程、崩溃、断电）时，
    Electron 的 before-quit / window-all-closed 都不会触发，stopBackend()
    没机会执行 → 后端成孤儿进程，仍持有单实例锁与端口 → 此后每次启动都
    报"后端服务未能启动"，用户既不知原因也无从恢复。

    修法：后端自己探活父进程 pid，父死则 server.shutdown() 自行退出。

    ⚠️ 本组锁定一个**实测得出的关键事实**：Windows 上父进程退出后
    os.getppid() **仍返回原 pid**（不像 Linux 会变成 1）——故看护必须
    用主动探活（server._pid_is_alive），不能用 getppid 比较。
    """

    def setUp(self):
        self.src = (ROOT / "gui" / "launch.py").read_text(encoding="utf-8")

    def test_watchdog_uses_liveness_probe_not_getppid_compare(self):
        """核心守卫：看护必须探活，不得用 getppid 比较。"""
        self.assertIn("_pid_is_alive", self.src,
                      "看护未使用探活——Windows 上 getppid 在父死后不变，比较法无效")
        self.assertNotIn("os.getppid() != parent_pid", self.src,
                         "退回 getppid 比较法了——实测在 Windows 上无效")

    def test_watchdog_only_in_electron_mode(self):
        """看护只在 --no-browser（Electron）下启用。

        浏览器直连模式（用户直接跑 python gui/launch.py）没有"父进程"概念，
        误判会杀掉正常服务。
        """
        # 调用点（带缩进的语句，非函数定义）必须在 if args.no_browser: 之下
        marker = "        _start_parent_watchdog(server)"
        self.assertIn(marker, self.src,
                      "看护未被调用（或缩进变了——应位于 if args.no_browser: 块内）")
        idx_call = self.src.index(marker)
        idx_guard = self.src.rindex("if args.no_browser:", 0, idx_call)
        self.assertLess(idx_guard, idx_call)

    def test_watchdog_shuts_down_server(self):
        """看护检测到父死必须调 server.shutdown()（而非仅打印）。

        断言必须**排除 docstring 与注释**：看护函数的 docstring 里就写着
        ``server.shutdown()`` 这句说明文字——只做子串搜索会被它满足，
        把真正的调用删掉测试仍绿（变异测试实证过两次）。
        这里改为逐行扫描「非注释、非 docstring」的代码行。
        """
        start = self.src.index("def _start_parent_watchdog")
        end = self.src.index("def main(")
        block = self.src[start:end]

        # 剥掉 docstring：找函数体第一个三引号块并移除
        import re as _re
        body_src = _re.sub(r'"""[\s\S]*?"""', "", block, count=1)
        # 剥掉注释行
        code_lines = [l for l in body_src.splitlines()
                      if l.strip() and not l.strip().startswith("#")]
        code = "\n".join(code_lines)

        self.assertIn("if not is_alive(parent_pid):", code,
                      "看护未按探活结果判断")
        self.assertIn("server.shutdown()", code,
                      "看护只打印不关服务——孤儿进程问题未解决")
        self.assertIn("daemon=True", code, "看护线程必须是 daemon")

    def test_watchdog_thread_is_daemon(self):
        """看护线程必须是 daemon，否则会阻止主进程退出。"""
        start = self.src.index("def _start_parent_watchdog")
        end = self.src.index("def main(")
        block = self.src[start:end]
        self.assertIn("daemon=True", block)


if __name__ == "__main__":
    unittest.main(verbosity=2)
