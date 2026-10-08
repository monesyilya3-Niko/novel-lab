"""R1 回归防线：config 路径常量隔离全覆盖。

背景（R1 事故）：``gui/config.py`` 的 L2 修复新增 ``STATE_JSON_DIR`` 后，
``test_gui_backend`` / ``test_asset_index`` / ``test_overview_api`` 只 patch 了
``STATE_ROOT``，漏了它 → 夹具写进真实 ``gui/state/`` 并跨轮累积，2 个测试长期失败。

本模块的防线（非假测试）：
1. 内省 config 得到的「项目内 Path 常量集合」必须与登记表完全一致——
   新增常量未登记即 **FAIL**（逼开发者纳入隔离）。
2. ``isolate_paths`` 必须把全部登记常量重定向出项目根，退出后精确还原。
3. 行为验证：隔离态下 ``state_store.save_state`` 的落盘必须在临时目录，
   真实 ``gui/state/`` 零新增。

纯标准库 unittest（铁律三）。
"""
from __future__ import annotations

import hashlib
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# 同目录的隔离工具模块（discover 场景下 tests/ 已在 sys.path，此处显式兜底）。
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import _isolation  # noqa: E402

from gui import config, db, state_store  # noqa: E402


def _file_fingerprint(path: Path):
    """文件指纹 (存在性, sha256, mtime_ns)；不存在返回 (False, None, None)。"""
    if not path.is_file():
        return (False, None, None)
    st = path.stat()
    return (True, hashlib.sha256(path.read_bytes()).hexdigest(), st.st_mtime_ns)


class TestConfigPathIsolation(unittest.TestCase):
    """config 数据路径常量的隔离覆盖防线。"""

    def test_registry_covers_all_config_path_constants(self):
        """内省发现的项目内 Path 常量必须与登记表逐项一致。

        新增路径常量（如再次出现 STATE_JSON_DIR 类新目录）而未登记 → 失败。
        """
        discovered = set(_isolation.discover_data_path_constants())
        registered = set(_isolation.DATA_PATH_CONSTANTS)
        self.assertEqual(
            discovered,
            registered,
            "gui/config.py 项目内路径常量与测试隔离登记表不一致："
            f"未登记={sorted(discovered - registered)}，"
            f"登记表多余/拼写错={sorted(registered - discovered)}",
        )

    def test_isolate_paths_redirects_all_out_of_project(self):
        """isolate_paths 必须把全部登记常量重定向出项目根，且退出后精确还原。"""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with _isolation.isolate_paths(tmp) as saved:
                for name in _isolation.DATA_PATH_CONSTANTS:
                    value = getattr(config, name)
                    self.assertTrue(
                        value.is_relative_to(tmp),
                        f"{name} 未被重定向到临时目录: {value}",
                    )
                    self.assertFalse(
                        value.is_relative_to(_isolation.ROOT_DIR),
                        f"{name} 仍指向项目根内: {value}",
                    )
            # 退出后必须精确还原。
            for name in _isolation.DATA_PATH_CONSTANTS:
                self.assertEqual(getattr(config, name), saved[name])

    def test_state_store_write_under_isolation_never_touches_real_dir(self):
        """隔离态下 state_store 落盘必须进临时目录，真实 gui/state/ 零新增。"""
        before = _isolation.snapshot_real_state_json_dir()
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            with _isolation.isolate_paths(tmp):
                st = state_store.new_state("iso_probe", "隔离探针")
                state_store.save_state(st)
                written = config.STATE_JSON_DIR / "gui_state_iso_probe.json"
                self.assertTrue(written.is_file(), "隔离态下状态文件未落在 STATE_JSON_DIR")
                # save_state 会尽力打开隔离库（db 由 STATE_ROOT 推导）；显式关闭，
                # 否则 Windows 文件锁会阻止临时目录回收。
                db.close()
        after = _isolation.snapshot_real_state_json_dir()
        self.assertEqual(
            before,
            after,
            f"隔离态写入污染了真实 gui/state/：新增={sorted(after - before)}",
        )


class TestRuntimePathFollowsConfig(unittest.TestCase):
    """运行时路径常量必须**跟随 config 的当前值**，不得在导入期固化。

    2026-09-23 事故（总工排查）：``gui/system_service.py`` 曾写

        _SETTINGS_FILE = config.STATE_ROOT / "settings.json"

    该赋值在导入期执行，路径被固化；测试用 ``setattr(config, "STATE_ROOT", tmp)``
    重定向时它不跟随，于是 ``tests/test_system_service.py`` 写进了**真实**
    ``gui_state/settings.json``。

    本测试是**确定性**判定——主动重定向 config 后断言真实文件未被触碰，
    不依赖「真实文件当前内容恰好与测试写入值不同」这种偶然条件
    （仅靠内容哈希的守卫会因覆写成同值而漏报）。
    """

    def test_update_settings_writes_to_patched_state_root_not_real_file(self):
        from gui import system_service

        real_settings = _isolation.REAL_GUI_STATE_DIR / "settings.json"
        before = _file_fingerprint(real_settings)

        with tempfile.TemporaryDirectory() as td:
            with _isolation.isolate_paths(Path(td)):
                system_service.update_settings({"thresholds": {"consistency_target": 91}})
                redirected = config.STATE_ROOT / "settings.json"
                self.assertTrue(
                    redirected.is_file(),
                    f"隔离态下设置未写入被重定向的 STATE_ROOT: {redirected}",
                )
                self.assertIn(
                    "91",
                    redirected.read_text(encoding="utf-8"),
                    "隔离态下写入的设置内容不正确",
                )
                self.assertFalse(
                    str(redirected.resolve()).startswith(str(_isolation.ROOT_DIR)),
                    "重定向后的路径仍落在项目根内",
                )

        after = _file_fingerprint(real_settings)
        self.assertEqual(
            before,
            after,
            "隔离态下 update_settings 污染了**真实** gui_state/settings.json"
            f"（会话前={before}，之后={after}）——说明 settings.json 路径在导入期"
            "被固化，config patch 对它无效。",
        )

    def test_reset_settings_does_not_delete_real_file_under_isolation(self):
        from gui import system_service

        real_settings = _isolation.REAL_GUI_STATE_DIR / "settings.json"
        before = _file_fingerprint(real_settings)

        with tempfile.TemporaryDirectory() as td:
            with _isolation.isolate_paths(Path(td)):
                system_service.reset_settings()
                self.assertFalse(
                    (config.STATE_ROOT / "settings.json").is_file(),
                    "隔离态下 reset_settings 未删除被重定向路径下的文件",
                )

        self.assertEqual(
            before,
            _file_fingerprint(real_settings),
            "隔离态下 reset_settings 误删/改动了**真实** gui_state/settings.json",
        )


class TestTempTreeRemoval(unittest.TestCase):
    """临时目录回收守卫（2026-10-08）。

    背景：`isolate_paths()` 与十余个测试模块建完 `mkdtemp` 就再不管，实测旧代码每跑
    一轮全量在 %TEMP% 留 **72** 个目录，累计已堆到 3400+。现在回收由
    ``_isolation.remove_tree`` 统一负责，这三条用例钉住它的核心承诺。
    """

    def test_isolate_paths_removes_its_tmp_root(self):
        root = Path(tempfile.mkdtemp(prefix="guard_iso_"))
        with _isolation.isolate_paths(root):
            deep = root / "state_root" / "nested"
            deep.mkdir(parents=True, exist_ok=True)
            (deep / "y.txt").write_text("内容", encoding="utf-8")
        self.assertFalse(root.exists(), "isolate_paths 退出后临时根必须整棵回收")

    def test_remove_tree_releases_open_sqlite_handle(self):
        """Windows 上没释放的 SQLite 句柄会让 rmtree 整棵失败——必须先按路径关连接。"""
        root = Path(tempfile.mkdtemp(prefix="guard_db_"))
        saved_root, saved_db = config.STATE_ROOT, config.DB_PATH
        try:
            config.STATE_ROOT = root / "state_root"
            config.DB_PATH = config.STATE_ROOT / "index.db"
            config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
            db.init_schema()
            self.assertTrue(config.DB_PATH.is_file(), "夹具应已在临时根里建库")
            _isolation.remove_tree(root)
        finally:
            config.STATE_ROOT, config.DB_PATH = saved_root, saved_db
            db._reset_conn()
        self.assertFalse(root.exists(), "带着打开连接的临时目录也必须删得掉")

    def test_remove_tree_is_nested_safe_and_idempotent(self):
        root = Path(tempfile.mkdtemp(prefix="guard_nest_"))
        deep = root / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "f.txt").write_text("x", encoding="utf-8")
        _isolation.remove_tree(root)
        self.assertFalse(root.exists())
        _isolation.remove_tree(root)  # 目录已不存在：静默返回，不抛


class TestHandPatchedDataPaths(unittest.TestCase):
    """手工 patch ``config.STATE_ROOT`` 的测试模块，必须把派生常量一起 patch。

    ``DB_PATH`` / ``LOCK_PATH`` 在 config.py 里是 ``STATE_ROOT`` 的**导入期快照**
    （`gui/config.py:150,152`），只 patch STATE_ROOT 带不动它们，读这两个常量的代码
    会指向真实用户数据目录。今天已被咬两次：``migrate._server_is_running()`` 读真实
    ``.lock`` 让全量门禁在桌面版开着时误红；``system_service`` 读真实 ``DB_PATH`` 报库大小。
    走 ``_isolation.isolate_paths()`` 的模块按登记表自动覆盖，故豁免。
    """

    DERIVED = ("DB_PATH", "LOCK_PATH")
    # 守卫/泄漏检测模块本身不是"依赖隔离的用例"，它们读登记表与真实目录正是职责所在。
    EXEMPT_WITH_REASON = {
        "test_module_config_snapshot.py": "AST 扫描导入期快照的守卫，提到常量名即其职责",
        "test_zz_state_dir_leak_guard.py": "真实目录泄漏守卫，要读真实路径才能判断有没有被写",
    }
    WINDOW = 8  # 同一 patch 点上下 8 行内必须出现派生常量的 patch
    # 存量债登记（2026-10-08 立规时实测的每文件违规 patch 点数）。
    # 只许减少不许增加：新写的 patch 点必须一次到位；清掉一个点就把数字改小。
    KNOWN_DEBT = {
        "test_asset_index.py": 7,
        "test_builtin_sync.py": 8,
        "test_migrate.py": 8,
    }

    def _is_patch_line(self, line: str) -> bool:
        return bool(re.search(r"config\.STATE_ROOT\s*=", line)) or '"STATE_ROOT"' in line

    def test_state_root_patch_sites_cover_derived_constants(self):
        """每一处改 STATE_ROOT 的地方，邻近必须一起改 DB_PATH / LOCK_PATH。

        按"每一处"而不是"每个文件"判定：一个文件里多个测试类各 patch 各的，
        文件级粒度会放过漏掉的那几个类。存量违规进 KNOWN_DEBT 记账，
        数量只许降不许升（升了就红，等于新增违规）。
        """
        offenders: dict[str, int] = {}
        details = []
        for fp in sorted(_TESTS_DIR.glob("test_*.py")):
            if fp.name in self.EXEMPT_WITH_REASON:
                continue
            text = fp.read_text(encoding="utf-8")
            if "isolate_paths" in text:
                continue
            lines = text.splitlines()
            for n, line in enumerate(lines, start=1):
                if not self._is_patch_line(line):
                    continue
                window = "\n".join(lines[max(0, n - 1 - self.WINDOW):n - 1 + self.WINDOW])
                missing = [name for name in self.DERIVED
                           if not (re.search(rf"config\.{name}\s*=", window)
                                   or f'"{name}"' in window)]
                if missing:
                    offenders[fp.name] = offenders.get(fp.name, 0) + 1
                    details.append(f"{fp.name}:{n} 缺 {missing}")
        grown = {f: c for f, c in offenders.items() if c > self.KNOWN_DEBT.get(f, 0)}
        self.assertEqual(
            grown, {},
            "新增违规：以下 patch 点改了 config.STATE_ROOT 却没在附近一起改派生常量"
            "（DB_PATH / LOCK_PATH 是 STATE_ROOT 的导入期快照，带不动它，读侧会指向真实"
            "用户数据目录）。补法：紧跟一行 "
            "`config.DB_PATH = config.STATE_ROOT / \"index.db\"` 与 "
            "`config.LOCK_PATH = config.STATE_ROOT / \".lock\"`（还原侧同步），"
            "或整体改用 _isolation.isolate_paths()。明细：" + "; ".join(details),
        )
        paid_down = {f: n for f, n in self.KNOWN_DEBT.items() if offenders.get(f, 0) < n}
        self.assertEqual(
            paid_down, {},
            f"存量债已减少，请同步调小 KNOWN_DEBT（鼓励顺手清掉）：{paid_down}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
