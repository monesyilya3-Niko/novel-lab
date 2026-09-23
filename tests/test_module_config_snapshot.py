"""防线：禁止「模块级 `X = config.<路径常量>`」形式的导入期路径快照。

背景（2026-09-23 隔离事故，总工排查发现）
----------------------------------------
``gui/system_service.py`` 曾写：

    _SETTINGS_FILE = config.STATE_ROOT / "settings.json"

该赋值在**模块导入期**执行，路径被固化。测试用
``setattr(config, "STATE_ROOT", tmp)`` 重定向时它**不会跟随**，于是
``tests/test_system_service.py`` 实际写进了**真实** ``gui_state/settings.json``。

受控实验（写入哨兵值 → 跑全量测试 → 复查）证实：哨兵被完全抹掉，文件内容变成
测试入参值（consistency_target=85 / default_words=3000）。

为什么既有防线拦不住
--------------------
``tests/_isolation.py`` 的登记表机制只保证「**通过 config 属性访问**路径」的代码
被重定向；对导入期快照完全无效。``test_zz_state_dir_leak_guard`` 又只覆盖
``gui/state/``。因此需要本条**静态**防线，在问题进入运行前就拦住。

白名单
------
``gui/logging_setup.py`` 的 ``LOG_DIR`` / ``LOG_FILE`` 是既有测试契约：
``tests/test_p2_hardening.py`` 直接 patch 这两个模块属性，且 ``setup_logging()``
在**调用期**读取它们（因此不存在「patch 无效」的问题）。改为函数会破坏该契约，
故白名单保留。**新增白名单必须说明为什么无法改成实时求值。**

纯标准库（铁律三）。
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 允许保留模块级快照的文件（相对项目根，POSIX 分隔符）。
# 每条都必须有理由；无理由不得新增。
ALLOWLIST = {
    # 测试契约直接 patch 这两个模块属性，且 setup_logging() 调用期才读取。
    "gui/logging_setup.py",
}

# 扫描范围：gui/ 与 scripts/ 的顶层 .py（web 前端不适用）。
SCAN_DIRS = ("gui", "scripts")
SKIP_PARTS = {"web", "__pycache__", "build", "dist", "node_modules", "migrations"}


def _iter_target_files() -> list[Path]:
    out: list[Path] = []
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            if SKIP_PARTS & set(p.parts):
                continue
            out.append(p)
    return sorted(out)


def _mentions_config_path(node: ast.AST) -> bool:
    """该表达式是否引用了 ``config.<大写路径常量>``。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name):
            if sub.value.id == "config" and sub.attr.isupper():
                return True
    return False


def find_module_level_config_snapshots(path: Path) -> list[tuple[int, str]]:
    """返回 ``[(lineno, 源码文本), ...]``：模块级（含 if 块内）的 config 路径快照。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[tuple[int, str]] = []

    def scan_body(body: list[ast.stmt]) -> None:
        for stmt in body:
            if isinstance(stmt, ast.Assign):
                if _mentions_config_path(stmt.value):
                    hits.append((stmt.lineno, ast.unparse(stmt)))
            elif isinstance(stmt, ast.AnnAssign):
                if stmt.value is not None and _mentions_config_path(stmt.value):
                    hits.append((stmt.lineno, ast.unparse(stmt)))
            elif isinstance(stmt, ast.If):
                # 模块级 if（如 `if TYPE_CHECKING:` / 平台分支）内部同样算导入期。
                scan_body(stmt.body)
                scan_body(stmt.orelse)

    scan_body(tree.body)
    return hits


class TestNoModuleLevelConfigSnapshot(unittest.TestCase):
    """任何模块级 config 路径快照都必须被消除或显式白名单化。"""

    def test_no_unallowlisted_module_level_config_path_snapshot(self):
        offenders: list[str] = []
        scanned = 0
        for path in _iter_target_files():
            rel = path.relative_to(ROOT).as_posix()
            scanned += 1
            for lineno, src in find_module_level_config_snapshots(path):
                if rel in ALLOWLIST:
                    continue
                offenders.append(f"{rel}:{lineno}  {src}")
        self.assertGreater(scanned, 0, "扫描文件数为 0，说明扫描范围配置失效")
        self.assertEqual(
            offenders,
            [],
            "检测到模块级 config 路径快照（导入期固化，config patch 无法重定向，"
            "会让测试写进真实运行态）。请改成函数内实时求值，例如：\n"
            "    def _path() -> Path:\n"
            "        return config.SOME_ROOT / \"x.json\"\n"
            "若确需保留，请加入本文件 ALLOWLIST 并写明理由。\n"
            f"违规点：{offenders}",
        )

    def test_allowlist_entries_actually_exist_and_still_match(self):
        """白名单必须仍指向真实存在、且确实含快照的文件（防止名单腐化）。"""
        for rel in ALLOWLIST:
            p = ROOT / rel
            self.assertTrue(p.is_file(), f"白名单条目不存在: {rel}")
            self.assertTrue(
                find_module_level_config_snapshots(p),
                f"白名单条目已无模块级快照，应从 ALLOWLIST 移除: {rel}",
            )

    def test_detector_actually_detects(self):
        """反向验证：探测器对已知形态必须报出（防止守卫变成永远通过的假测试）。"""
        sample = ast.parse(
            "import config\n"
            "_FOO = config.STATE_ROOT / 'a.json'\n"
            "_BAR = config.ASSETS_ROOT\n"
            "BAZ = 1\n"
        )
        hits: list[str] = []
        for stmt in sample.body:
            if isinstance(stmt, ast.Assign) and _mentions_config_path(stmt.value):
                hits.append(ast.unparse(stmt))
        self.assertEqual(len(hits), 2, f"探测器漏报，实际命中 {hits}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
