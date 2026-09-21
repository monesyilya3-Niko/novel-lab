#!/usr/bin/env python3
"""CLI 退出码传播契约（2026-09-21）。

背景：`novel.py` 通过 `run_script()` 调 `scripts/*.py`，并用返回码判断成败
（例如 `分析` 命令：`rc1 = run_script("pipeline.py", …); if rc1 != 0: return rc1`）。

但 7 个子脚本的入口全是：

    if __name__ == "__main__":
        main()          # ← 返回值被丢弃，进程退出码恒为 0

于是 `main()` 里的 `return 1`（校验失败 / 章号异常 / LLM 中断）**对上层完全不可见**，
`novel.py` 的失败分支永远不会触发。2026-09-21 实测：组装因 schema REJECT 而失败时，
退出码仍为 0。

本测试锁定该契约：凡是 `scripts/*.py` 与 `novel.py` 里有 `__main__` 块的，
其最后一句必须是 `sys.exit(main())`（或至少含 `sys.exit(`）。

用法：
  python -m unittest tests.test_cli_exit_code -v
  python run_tests.py     # 自动 discover
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MAIN_RE = re.compile(
    r'if\s+__name__\s*==\s*["\']__main__["\']\s*:(?P<body>(?:\n[ \t]+.*|\n)*)')


def _main_block_tail(text: str) -> str | None:
    """返回 __main__ 块里最后一条非空语句。"""
    m = MAIN_RE.search(text)
    if not m:
        return None
    lines = [ln.strip() for ln in m.group("body").splitlines() if ln.strip()]
    return lines[-1] if lines else ""


# 明确豁免：这些文件的 __main__ 块不是「返回码语义」的 CLI 入口。
#   - chapter_loader.py: 源码已标 `# pragma: no cover - 诊断入口`，纯打印诊断
#   - llm_client.py    : 末尾是 print 用法提示（连通性测试入口）
#   - secret_store.py  : 末尾是 print 密钥条目数
# （consistency.py 已于 2026-09-21 补上退出码语义，不再豁免）
EXEMPT = {"chapter_loader.py", "llm_client.py", "secret_store.py"}


class TestCliExitCodePropagation(unittest.TestCase):
    """所有 CLI 入口都必须把 main() 的返回值交给 sys.exit()。"""

    def _targets(self):
        files = [ROOT / "novel.py"]
        files += sorted((ROOT / "scripts").glob("*.py"))
        return [f for f in files if f.exists() and f.name not in EXEMPT]

    def test_every_entrypoint_propagates_exit_code(self):
        offenders = []
        for f in self._targets():
            tail = _main_block_tail(f.read_text(encoding="utf-8"))
            if tail is None:          # 无 __main__ 块（纯库模块），跳过
                continue
            if "sys.exit(" not in tail and "SystemExit(" not in tail:
                offenders.append(f"{f.relative_to(ROOT)} → {tail}")
        self.assertEqual(
            offenders, [],
            "以下入口未把 main() 的返回值交给 sys.exit()，失败退出码会丢失：\n  "
            + "\n  ".join(offenders))

    def test_scripts_import_sys_when_needed(self):
        """用了 sys.exit 就必须 import sys，否则运行期 NameError。"""
        offenders = []
        for f in self._targets():
            text = f.read_text(encoding="utf-8")
            tail = _main_block_tail(text)
            if tail and "sys.exit(" in tail and not re.search(r"^\s*import sys\b", text, re.M):
                offenders.append(str(f.relative_to(ROOT)))
        self.assertEqual(offenders, [], f"以下文件用了 sys.exit 但没 import sys：{offenders}")


if __name__ == "__main__":
    sys.exit(unittest.main())
