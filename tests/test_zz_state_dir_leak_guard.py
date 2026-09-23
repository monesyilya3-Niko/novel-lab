"""全局泄漏守卫：整轮测试不得写入任何真实运行时目录。

覆盖两个目标（2026-09-23 扩充）：
- ``gui/state/``：状态 JSON 派生镜像（R1 事故的现场）；
- ``gui_state/``：SQLite 索引 + ``settings.json``（**当日发现的隔离事故现场**）。

文件名前缀 ``zz`` 使其在 unittest discover（按文件名排序）中排在末位执行，
从而能观测其它全部测试模块的累计副作用——直接捕获 R1 类回归
（任何测试把夹具写进真实派生目录 ``gui/state/`` 并跨轮累积）。

对照基线取 ``_isolation`` 的 ``SESSION_START_*_SNAPSHOT``（discover 阶段、
任何测试执行前拍摄）。纯标准库（铁律三）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import _isolation  # noqa: E402


class TestRealStateDirLeakGuard(unittest.TestCase):
    """真实 gui/state/ 零泄漏守卫。"""

    def test_no_new_state_json_in_real_dir(self):
        current = _isolation.snapshot_real_state_json_dir()
        baseline = _isolation.SESSION_START_STATE_JSON_SNAPSHOT
        leaked = sorted(current - baseline)
        self.assertEqual(
            leaked,
            [],
            "检测到测试污染真实 gui/state/（未隔离 STATE_JSON_DIR）："
            f"新增 {leaked}",
        )

    def test_no_tmp_residue_in_real_dir(self):
        real_dir = _isolation.REAL_STATE_JSON_DIR
        if not real_dir.is_dir():
            return
        residue = sorted(p.name for p in real_dir.glob("*.tmp"))
        self.assertEqual(residue, [], f"真实 gui/state/ 存在原子写 .tmp 残留: {residue}")


class TestRealGuiStateLeakGuard(unittest.TestCase):
    """真实 gui_state/ 零泄漏守卫（2026-09-23 新增）。

    背景：``gui/system_service.py`` 曾把 settings.json 路径写成模块级常量
    ``_SETTINGS_FILE = config.STATE_ROOT / "settings.json"``——导入期固化后，
    测试的 ``setattr(config, "STATE_ROOT", tmp)`` 对它无效，于是
    ``tests/test_system_service.py`` 写进了**真实** ``gui_state/settings.json``
    （受控实验证实：写入哨兵值后被测试覆写）。

    既有 ``TestRealStateDirLeakGuard`` 只覆盖 ``gui/state/``（派生镜像），
    所以这条漏网。本类直接比对 settings.json 的内容哈希，补上缺口。
    """

    def test_settings_json_content_untouched(self):
        current = _isolation.snapshot_real_gui_state()
        baseline = _isolation.SESSION_START_GUI_STATE_SNAPSHOT
        self.assertEqual(
            current["settings_exists"],
            baseline["settings_exists"],
            "测试改动了真实 gui_state/settings.json 的**存在性**（应完全隔离："
            f"会话前={baseline['settings_exists']} 现在={current['settings_exists']}）",
        )
        self.assertEqual(
            current["settings_sha256"],
            baseline["settings_sha256"],
            "测试覆写了真实 gui_state/settings.json 的**内容**——说明有路径常量在"
            "导入期固化，config patch 未能生效。请把该常量改成函数内实时求值。",
        )
        # 内容相同也可能是「覆写成同值」；mtime 变化同样说明文件被写过。
        self.assertEqual(
            current["settings_mtime_ns"],
            baseline["settings_mtime_ns"],
            "真实 gui_state/settings.json 的 mtime 在测试期间被改动（内容可能恰好相同）"
            "——测试期间没有任何合法理由写这个文件，请排查路径隔离。",
        )

    def test_no_tmp_residue_in_real_gui_state(self):
        real_dir = _isolation.REAL_GUI_STATE_DIR
        if not real_dir.is_dir():
            return
        residue = sorted(p.name for p in real_dir.glob("*.tmp"))
        self.assertEqual(residue, [], f"真实 gui_state/ 存在原子写 .tmp 残留: {residue}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
