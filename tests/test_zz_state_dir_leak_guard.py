"""全局泄漏守卫：整轮测试不得向真实 ``gui/state/`` 写入任何状态 JSON。

文件名前缀 ``zz`` 使其在 unittest discover（按文件名排序）中排在末位执行，
从而能观测其它全部测试模块的累计副作用——直接捕获 R1 类回归
（任何测试把夹具写进真实派生目录 ``gui/state/`` 并跨轮累积）。

对照基线取 ``_isolation.SESSION_START_STATE_JSON_SNAPSHOT``（discover 阶段、
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
