"""测试脚手架约定回归：每个 tests/test_*.py 脱离仓库根目录必须能正常导入。

2026-10-03 实锤 5 例：test_writing_extra 等 4 个文件只把 tests/ 目录加入
sys.path、test_p2_validation 完全没处理 sys.path，直接 `python3 tests/test_xxx.py`
报 ModuleNotFoundError: gui。统一约定：测试文件必须自行把仓库根目录加入
sys.path（参考 test_writing_service.py），保证 run_tests.py 之外也能直跑。

实现：为每个测试文件起子进程执行 `import <模块>`，子进程 cwd 为临时目录
且不继承 PYTHONPATH——只走模块顶层执行（含 sys.path 装配与 import），
不触发 `if __name__ == "__main__"`、不跑测试，快且无副作用。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent


class DirectRunConventionTest(unittest.TestCase):
    def test_every_test_module_imports_without_repo_root_on_path(self):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        failures = []
        for f in sorted(TESTS_DIR.glob("test_*.py")):
            if f.name == Path(__file__).name:
                continue
            # 复刻 `python3 tests/test_xxx.py` 的 sys.path[0]（脚本所在目录），
            # 但不给仓库根目录：能 import 才算直跑合格。
            code = (
                "import sys; "
                f"sys.path.insert(0, {str(TESTS_DIR)!r}); "
                f"import {f.stem}"
            )
            r = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, timeout=60,
                cwd=tempfile.gettempdir(), env=env,
            )
            err = r.stderr or ""
            if (r.returncode != 0 or "ModuleNotFoundError" in err
                    or "ImportError" in err):
                last = err.strip().splitlines()
                failures.append(
                    f"{f.name}: exit={r.returncode} :: "
                    f"{(last[-1] if last else '')[:120]}"
                )
        self.assertEqual(
            failures, [],
            "以下测试文件脱离仓库根目录后无法导入（直接运行会失败），"
            "请按 test_writing_service.py 的约定补 sys.path 装配：\n"
            + "\n".join(failures),
        )


if __name__ == "__main__":
    unittest.main()
