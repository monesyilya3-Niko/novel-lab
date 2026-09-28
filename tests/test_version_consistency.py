"""版本一致性守卫：所有面向用户的版本号必须与 ``gui.__version__`` 一致。

单一真相源：``gui/__init__.py::__version__``（构建脚本
``build/build_portable.py`` 也从此处解析版本号）。

检查清单：
- ``gui/__init__.py::__version__``（canonical）
- ``gui/web/package.json`` → version
- ``gui/web/src/layout/WorkbenchNav.tsx`` → 侧边栏显示的 vX.Y.Z
- ``build/installer.iss`` → AppVersion
- ``AGENTS.md`` §7「当前实测口径」→ 版本 **X.Y.Z**
  （``tests/test_doc_metrics.py`` 同样断言此处）
- ``packaging/installer_template.sh`` 必须保留 ``__VERSION__`` 占位符
  （禁止把版本号硬编码进模板）
- ``packaging/build_installer.sh`` 必须从命令行参数取版本（禁止硬编码）

有意排除（语义不同的独立版本号，**不得**统一）：
- ``gui/admin.py::VERSION``：管理员子系统的独立版本，随管理员功能演进，
  不是应用版本；
- ``gui/server.py::server_version``：HTTP Server 标识头，不是应用版本。

本测试只读仓库文件，不写任何状态目录，隔离要求天然满足。
纯标准库（铁律三）。
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _canonical_version() -> str:
    text = (ROOT / "gui" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.M)
    assert m, "gui/__init__.py 未找到 __version__ 定义"
    version = m.group(1).strip()
    assert SEMVER_RE.match(version), f"canonical 版本号格式非法: {version!r}"
    return version


class TestVersionConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = _canonical_version()

    def _assert_matches(self, where: str, version: str) -> None:
        self.assertTrue(SEMVER_RE.match(version), f"{where} 版本号格式非法: {version!r}")
        self.assertEqual(
            version,
            self.canonical,
            f"{where} 的版本号 {version} 与 canonical 版本 {self.canonical} 不一致",
        )

    def test_canonical_version_is_semver(self):
        self.assertTrue(SEMVER_RE.match(self.canonical))

    def test_web_package_json(self):
        data = json.loads((ROOT / "gui" / "web" / "package.json").read_text(encoding="utf-8"))
        self._assert_matches("gui/web/package.json", data["version"])

    def test_frontend_display_version(self):
        text = (ROOT / "gui" / "web" / "src" / "layout" / "WorkbenchNav.tsx").read_text(
            encoding="utf-8"
        )
        m = re.search(r"v(\d+\.\d+\.\d+)", text)
        self.assertIsNotNone(m, "WorkbenchNav.tsx 未找到 vX.Y.Z 显示版本号")
        self._assert_matches("WorkbenchNav.tsx 显示版本", m.group(1))

    def test_windows_installer_iss(self):
        text = (ROOT / "build" / "installer.iss").read_text(encoding="utf-8")
        m = re.search(r'#define\s+AppVersion\s+"([^"]+)"', text)
        self.assertIsNotNone(m, "build/installer.iss 未找到 AppVersion 定义")
        self._assert_matches("build/installer.iss AppVersion", m.group(1))

    def test_agents_md_metric_line(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        m = re.search(r"当前实测口径.*$", text, re.M)
        self.assertIsNotNone(m, "AGENTS.md 未找到「当前实测口径」行")
        vm = re.search(r"版本\s*\*\*([0-9]+\.[0-9]+\.[0-9]+)\*\*", m.group(0))
        self.assertIsNotNone(vm, "「当前实测口径」行缺少版本字段")
        self._assert_matches("AGENTS.md 当前实测口径", vm.group(1))

    def test_installer_template_keeps_version_placeholder(self):
        text = (ROOT / "packaging" / "installer_template.sh").read_text(encoding="utf-8")
        self.assertIn(
            "__VERSION__",
            text,
            "installer_template.sh 必须保留 __VERSION__ 占位符，禁止硬编码版本号",
        )
        self.assertIn(
            "__PAYLOAD_SHA256__",
            text,
            "installer_template.sh 必须保留 __PAYLOAD_SHA256__ 占位符",
        )
        # 模板内不得出现 VERSION="<x.y.z>" 形式的硬编码
        hardcoded = re.findall(r'^VERSION="(\d+\.\d+\.\d+)"', text, re.M)
        self.assertEqual(hardcoded, [], f"installer_template.sh 存在硬编码版本号: {hardcoded}")

    def test_build_installer_takes_version_from_arg(self):
        text = (ROOT / "packaging" / "build_installer.sh").read_text(encoding="utf-8")
        self.assertIsNotNone(
            re.search(r'^VERSION="\$2"', text, re.M),
            "build_installer.sh 必须从 $2 参数取版本（禁止硬编码）",
        )

    def test_admin_subsystem_version_is_intentionally_independent(self):
        # 管理员子系统版本独立于应用版本：此处只做存在性断言并锁定语义，
        # 防止有人误将其“统一”到应用版本。
        text = (ROOT / "gui" / "admin.py").read_text(encoding="utf-8")
        m = re.search(r'^VERSION\s*=\s*"([^"]+)"', text, re.M)
        self.assertIsNotNone(m, "gui/admin.py 的 VERSION 定义不应被删除")
        # 它是管理员子系统的独立版本，不要求等于应用版本（语义不同）


if __name__ == "__main__":
    unittest.main()
