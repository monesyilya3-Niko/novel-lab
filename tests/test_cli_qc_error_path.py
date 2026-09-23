"""CLI 错误路径可读性回归：引擎返回 ``{"error": ...}`` 时不得抛裸 KeyError。

背景（2026-09-23 总工排查）
--------------------------
``scripts/book_quality.py::book_quality_check`` 在无法质检时返回
``{"error": "未找到章节文件"}``（或带 ``error_type: "chapter_load"`` 的冲突错误），
这种返回里**没有** ``total_chapters`` / ``total_issues`` / ``verdict`` / ``severity``
/ ``issues`` 等字段。

但 ``novel.py`` 的「质检」分支直接索引 ``result['total_chapters']``，从不检查 ``error``：

    $ python novel.py 质检 <不存在的目录>
    ...
    KeyError: 'total_chapters'

用户看到的是 Python traceback，而不是「目录不存在」。触发条件包括：目录不存在、
空目录、同一章号命中多个物理文件。仓库内 ``error_type`` 契约此前**没有任何调用方
消费**（全仓 grep 只命中定义处）。

本测试锁定修复后的契约：非零退出 + 可读信息 + 不出现 traceback。
纯标准库（铁律三）。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOVEL_PY = ROOT / "novel.py"
TIMEOUT = 120


def _run_qc(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(NOVEL_PY), "质检", *args],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=TIMEOUT,
    )


class TestQcErrorPathReadable(unittest.TestCase):
    """「质检」对无法质检的输入必须给可读错误，不得崩栈。"""

    def test_missing_directory_exits_nonzero_without_traceback(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "definitely_not_here"
            p = _run_qc(str(missing))
            out = (p.stdout or "") + (p.stderr or "")
            self.assertNotEqual(p.returncode, 0, "无法质检却返回 0（失败分支退出码丢失）")
            self.assertNotIn("Traceback", out, f"抛出了未捕获异常回溯:\n{out}")
            self.assertNotIn("KeyError", out, f"仍是 KeyError 崩栈:\n{out}")
            self.assertIn("质检失败", out, f"缺少可读的失败提示:\n{out}")

    def test_empty_directory_exits_nonzero_without_traceback(self):
        with tempfile.TemporaryDirectory() as td:
            p = _run_qc(td)
            out = (p.stdout or "") + (p.stderr or "")
            self.assertNotEqual(p.returncode, 0)
            self.assertNotIn("Traceback", out, f"抛出了未捕获异常回溯:\n{out}")
            self.assertIn("质检失败", out)

    def test_json_mode_still_emits_machine_readable_error(self):
        """--json 模式必须仍输出错误对象（消费者按 error 判定），且非零退出。"""
        with tempfile.TemporaryDirectory() as td:
            p = _run_qc(td, "--json")
            self.assertNotEqual(p.returncode, 0, "--json 失败路径应非零退出")
            self.assertIn('"error"', p.stdout or "",
                          f"--json 未输出机器可读错误对象:\n{p.stdout!r}")
            self.assertNotIn("Traceback", (p.stdout or "") + (p.stderr or ""))


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
