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

from gui import config, state_store, db  # noqa: E402
import _isolation  # noqa: E402


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
