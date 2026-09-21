#!/usr/bin/env python3
"""`backfill_meta` 回填脚本回归（2026-09-21）。

该脚本用于给**已有**资产补 `meta.source_fingerprint`（新增字段之前产出的资产没有），
是「只动 meta 一个字段、不碰任何分析内容」的一次性迁移工具 ——
所以「除该字段外内容零变化」是它最重要的契约，必须锁定。

本测试只碰临时目录，不读不写任何真实资产。

用法：
  python -m unittest tests.test_backfill_meta -v
  python run_tests.py     # 自动 discover
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import backfill_meta as bm  # noqa: E402

PASS_FILE = "pass1_structure.json"
KIND = "structure-obs"


class TestBackfillMeta(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.raw = base / "raw"
        self.assets = base / "assets"
        for d in (self.raw, self.assets):
            d.mkdir(parents=True)
        self._patches = [
            mock.patch.object(bm, "RAW_DIR", self.raw),
            mock.patch.object(bm, "ASSETS_DIR", self.assets),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self.tmp.cleanup()

    # ---- helpers ----

    def _book(self, name="书", *, with_pass=True, meta=None):
        d = self.raw / name
        d.mkdir(parents=True, exist_ok=True)      # 目录总是存在（模拟 LOTM 那种空目录）
        if with_pass:
            (d / PASS_FILE).write_text('{"chapter_analyses": []}', encoding="utf-8")
        payload = {"meta": meta if meta is not None else {"source_title": name},
                   "keep_me": "must not change",
                   "nested": {"a": [1, 2, 3]}}
        (self.assets / f"{name}-{KIND}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.assets / f"{name}-{KIND}.json"

    def _read(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    # ---- cases ----

    def test_dry_run_does_not_write(self):
        """dry-run 只预览，不落盘。"""
        p = self._book()
        before = p.read_text(encoding="utf-8")
        changes, errors, _notes = bm.backfill_one("书", dry_run=True)
        self.assertEqual(errors, [])
        self.assertEqual(len(changes), 1)
        self.assertEqual(p.read_text(encoding="utf-8"), before)

    def test_writes_fingerprint(self):
        """执行后指纹写入 meta。"""
        p = self._book()
        changes, errors, _notes = bm.backfill_one("书", dry_run=False)
        self.assertEqual(errors, [])
        self.assertEqual(len(changes), 1)
        d = self._read(p)
        self.assertIn(PASS_FILE, d["meta"]["source_fingerprint"])

    def test_only_meta_fingerprint_changes(self):
        """**核心契约**：除 source_fingerprint 外，内容零变化。"""
        p = self._book()
        before = self._read(p)
        bm.backfill_one("书", dry_run=False)
        after = self._read(p)
        before["meta"].pop("source_fingerprint", None)
        after["meta"].pop("source_fingerprint", None)
        self.assertEqual(before, after)
        self.assertEqual(after["keep_me"], "must not change")
        self.assertEqual(after["nested"], {"a": [1, 2, 3]})

    def test_skips_when_already_current(self):
        """指纹已匹配 → 不产生变更。"""
        self._book()
        bm.backfill_one("书", dry_run=False)
        changes, errors, _notes = bm.backfill_one("书", dry_run=False)
        self.assertEqual(changes, [])
        self.assertEqual(errors, [])

    def test_no_source_pass_reports_note(self):
        """corpus/raw/<书>/ 为空（纯会话产出）→ 只提示，不算变更。"""
        self._book(with_pass=False)
        changes, errors, notes = bm.backfill_one("书", dry_run=False)
        self.assertEqual(changes, [])
        self.assertEqual(errors, [])
        self.assertTrue(any("无来源 pass 文件" in n for n in notes), notes)

    def test_missing_book_reports_error(self):
        changes, errors, _notes = bm.backfill_one("不存在", dry_run=False)
        self.assertEqual(changes, [])
        self.assertTrue(errors)


if __name__ == "__main__":
    sys.exit(unittest.main())
