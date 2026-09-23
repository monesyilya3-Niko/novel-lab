"""铁律二「写盘前校验」回归（2026-09-23 总工修复）。

背景
----
``gui/services.py::_generate_reports`` 原先是「先写盘 → 再校验」：先把两份 Markdown
写进 ``reports/``，再调铁律二校验；校验失败只抑制 ``report_ready`` 事件，
**不删除已落盘的文件**。于是低于门槛的报告永久留在交付目录里冒充合格品。

实测存量后果：6 本书中 4 本的「拆书报告 + 笔法分析」合计仅 5612–7024 字
（门槛 10000），用项目自身的 ``report.check_combined_report_length()`` 判定全部
``ok=False``，且没有任何机制回头复核。

本测试锁定修复后的契约：**校验不通过则一个字节都不写**。

纯标准库（铁律三）。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import _isolation  # noqa: E402
from gui import config, db, services  # noqa: E402


class TestReportWriteGate(unittest.TestCase):
    """低于门槛不得落盘；达到门槛才落盘。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="report_gate_")
        self.addCleanup(self._tmp.cleanup)
        self._iso = _isolation.isolate_paths(Path(self._tmp.name))
        self._iso.__enter__()
        self.addCleanup(lambda: self._iso.__exit__(None, None, None))

        # 报告内容由各用例注入。
        self.book_md = ""
        self.craft_md = ""
        self.events: list[dict] = []

        adapter = services.engine_adapter
        self._orig = {
            "load": services._load_assembled_card,
            "build": adapter.build_report,
            "craft": adapter.render_craft_report,
            "publish": services.broker.publish,
        }
        services._load_assembled_card = lambda book_id, card_type: (
            {"meta": {"source_title": "测试书"}} if card_type in ("voice", "craft") else {}
        )
        adapter.build_report = lambda *a, **k: self.book_md
        adapter.render_craft_report = lambda *a, **k: self.craft_md
        services.broker.publish = lambda ev: self.events.append(ev)

        def _restore():
            services._load_assembled_card = self._orig["load"]
            adapter.build_report = self._orig["build"]
            adapter.render_craft_report = self._orig["craft"]
            services.broker.publish = self._orig["publish"]

        self.addCleanup(_restore)
        # 隔离态下 state_store 会打开临时 index.db；Windows 上不显式关闭会锁住文件，
        # 导致临时目录回收失败（PermissionError WinError 32）。最后注册 → 最先执行。
        self.addCleanup(db.close)

    def _reports_dir(self) -> Path:
        return config.REPORTS_DIR

    def _written(self) -> list[str]:
        d = self._reports_dir()
        if not d.is_dir():
            return []
        return sorted(p.name for p in d.iterdir())

    # ------------------------------------------------------------------

    def test_below_threshold_writes_nothing(self):
        """合计 < 10000 字符：不得产出任何报告文件，且发布 report_error。"""
        self.book_md = "甲" * 2000
        self.craft_md = "乙" * 2000  # 合计 4000 < 10000

        services._generate_reports("book_low", {"title": "测试书"})

        self.assertEqual(self._written(), [], "低于门槛却写出了报告文件（写盘前校验失效）")
        statuses = [e.get("status") for e in self.events]
        self.assertIn("report_error", statuses, f"未发布 report_error，实际事件: {statuses}")
        self.assertNotIn("report_ready", statuses, "低于门槛却发布了 report_ready")
        msg = next(e["message"] for e in self.events if e.get("status") == "report_error")
        self.assertIn("已阻止写盘", msg, f"错误信息未说明已阻止写盘: {msg}")
        self.assertIn("10000", msg, f"错误信息未给出门槛: {msg}")

    def test_at_threshold_writes_both_reports(self):
        """合计 ≥ 10000 字符：两份报告都落盘，且 report_ids 列全。"""
        self.book_md = "甲" * 6000
        self.craft_md = "乙" * 5000  # 合计 11000 ≥ 10000

        services._generate_reports("book_ok", {"title": "测试书"})

        self.assertEqual(
            self._written(),
            ["book_ok-拆书报告.md", "book_ok-笔法分析.md"],
            "达到门槛但报告未按预期落盘",
        )
        ready = [e for e in self.events if e.get("status") == "report_ready"]
        self.assertEqual(len(ready), 1, f"report_ready 事件数异常: {self.events}")
        self.assertEqual(
            sorted(ready[0]["report_ids"]),
            ["report:book_ok-拆书报告", "report:book_ok-笔法分析"],
        )
        self.assertEqual(ready[0]["report_chars"], 11000)

    def test_craft_missing_reports_only_book_and_does_not_fake_craft_id(self):
        """craft-card 缺失时只写拆书报告，report_ids 不得虚报笔法分析。"""
        self.book_md = "甲" * 12000
        self.craft_md = ""  # craft 缺失 → 不生成

        services._generate_reports("book_nocraft", {"title": "测试书"})

        self.assertEqual(self._written(), ["book_nocraft-拆书报告.md"])
        ready = [e for e in self.events if e.get("status") == "report_ready"]
        self.assertEqual(len(ready), 1)
        self.assertEqual(
            ready[0]["report_ids"],
            ["report:book_nocraft-拆书报告"],
            "craft 缺失却把「笔法分析」列进了 report_ids（虚报）",
        )

    def test_below_threshold_does_not_overwrite_existing_reports(self):
        """低于门槛时，此前已存在的合格报告必须原样保留（不得被半成品覆盖）。"""
        reports_dir = self._reports_dir()
        reports_dir.mkdir(parents=True, exist_ok=True)
        existing = reports_dir / "book_keep-拆书报告.md"
        existing.write_text("甲" * 12000, encoding="utf-8")
        before = existing.read_text(encoding="utf-8")

        self.book_md = "甲" * 100
        self.craft_md = "乙" * 100
        services._generate_reports("book_keep", {"title": "测试书"})

        self.assertTrue(existing.is_file(), "已有报告被删除")
        self.assertEqual(existing.read_text(encoding="utf-8"), before, "已有报告被半成品覆盖")


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
