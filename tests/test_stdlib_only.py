"""铁律三守护：scripts/ 与 gui/ 后端只准依赖 Python 标准库。

两层校验（用 sys.stdlib_module_names 作标准库白名单，3.10+）：
1. 第三方依赖：任何层级（模块级/函数级）出现非标准库、非本仓模块的
   import 即违规——这是本测试的核心保护。
2. 依赖方向（任务书 v2__1.md §4.3.1 架构硬约束）：
   只有 gui/engine_adapter.py 可以 import scripts/；
   其他任何 gui 模块不得直接 import——**含函数级延迟 import**。
   gui 服务层触碰 scripts/ 一律走 engine_adapter 的薄封装。

gui.web 是前端（Vite/React），不受铁律三约束。
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 运行时源码范围（相对 ROOT）。新增顶层目录时在此登记。
RUNTIME_DIRS = ("scripts", "gui")

# 铁律三豁免：前端工具链与构建产物。
EXEMPT_PREFIXES = ("gui/web/",)

# scripts/ 下被 gui 层函数级延迟 import 的本仓模块名（既有设计，允许）。
SCRIPTS_LOCAL_MODULES = "scripts"


def _iter_py_files() -> list[Path]:
    files: list[Path] = []
    for rel in RUNTIME_DIRS:
        base = ROOT / rel
        if not base.is_dir():
            continue
        files.extend(base.rglob("*.py"))
    out = []
    for f in files:
        if "__pycache__" in f.parts:
            continue
        rel = f.relative_to(ROOT).as_posix()
        if any(rel.startswith(p) for p in EXEMPT_PREFIXES):
            continue
        out.append(f)
    return out


def _top_level_names(node: ast.AST) -> set[str]:
    mods: set[str] = set()
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Import):
            mods.update(alias.name.split(".")[0] for alias in child.names)
        elif isinstance(child, ast.ImportFrom) and child.level == 0 and child.module:
            mods.add(child.module.split(".")[0])
    return mods


def _all_imports(node: ast.AST) -> set[str]:
    mods: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Import):
            mods.update(alias.name.split(".")[0] for alias in sub.names)
        elif isinstance(sub, ast.ImportFrom) and sub.level == 0 and sub.module:
            mods.add(sub.module.split(".")[0])
    return mods


def _is_local_repo_module(mod: str) -> bool:
    return (
        (ROOT / mod).is_dir()
        or (ROOT / f"{mod}.py").is_file()
        or (ROOT / "scripts" / f"{mod}.py").is_file()  # scripts/ 兄弟模块互引合法
    )


class StdlibOnlyGuard(unittest.TestCase):
    """铁律三：运行时源码零第三方依赖 + scripts/ 依赖方向。"""

    def test_no_third_party_imports_any_level(self) -> None:
        stdlib = set(sys.stdlib_module_names)
        offenders: list[str] = []
        for path in _iter_py_files():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for mod in _all_imports(tree):
                if mod in stdlib or _is_local_repo_module(mod):
                    continue
                offenders.append(f"{path.relative_to(ROOT).as_posix()}: import {mod}（第三方）")
        self.assertEqual(offenders, [], "铁律三违规（第三方 import）：\n" + "\n".join(offenders))

    def test_gui_layer_imports_scripts_only_via_engine_adapter(self) -> None:
        # 全层级扫描：模块级 import 与函数级延迟 import 同样违规。
        # （曾有盲区：只查模块级，model_service/advanced_service/system_service 的
        # 函数级直连全部漏网。2026-09-28 收紧。）
        stdlib = set(sys.stdlib_module_names)
        offenders: list[str] = []
        for path in _iter_py_files():
            rel = path.relative_to(ROOT).as_posix()
            if not rel.startswith("gui/") or rel == "gui/engine_adapter.py":
                continue  # 依赖方向约束的是 gui 层；engine_adapter 是唯一例外
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for mod in _all_imports(tree) - stdlib:
                if (ROOT / "scripts" / f"{mod}.py").is_file():
                    offenders.append(f"{rel}: import {mod}（应走 engine_adapter 薄封装）")
        self.assertEqual(offenders, [], "依赖方向违规（gui 层 import scripts/ 模块）：\n" + "\n".join(offenders))

    def test_scoped_files_actually_covered(self) -> None:
        files = _iter_py_files()
        self.assertGreater(len(files), 30, f"扫描范围异常（仅 {len(files)} 个文件），检查 RUNTIME_DIRS")


if __name__ == "__main__":
    unittest.main()
