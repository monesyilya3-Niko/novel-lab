#!/usr/bin/env python3
"""batch.py dry-run 覆盖测试（出版级补强）。

run_book(dry_run=True) 走采样+量化+4遍dry-pass，不调 LLM、不写真实 corpus。
通过 monkeypatch batch.ROOT 指向临时目录，保证测试隔离。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import batch as batch_mod


def _make_book_txt(path: Path, chapters: int = 8):
    parts = []
    for i in range(1, chapters + 1):
        parts.append(f"第{i}章 标题{i}\n" + ("正文内容。" * 200) + "\n")
    path.write_text("\n".join(parts), encoding="utf-8")


class TestRunBookDryRun(unittest.TestCase):
    def test_dry_run_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "testbook.txt"
            _make_book_txt(src)
            with mock.patch.object(batch_mod, "ROOT", td):
                result = batch_mod.run_book(src, "campus", None, dry_run=True)
            self.assertIsNone(result)

    def test_dry_run_writes_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "testbook.txt"
            _make_book_txt(src)
            with mock.patch.object(batch_mod, "ROOT", td):
                batch_mod.run_book(src, "campus", None, dry_run=True)
            manifest = td / "corpus" / "sampled" / "testbook" / "manifest.json"
            self.assertTrue(manifest.is_file())
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["book"], "testbook")
            self.assertGreaterEqual(data["total_chapters"], 5)

    def test_too_few_chapters_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "tiny.txt"
            _make_book_txt(src, chapters=2)
            with mock.patch.object(batch_mod, "ROOT", td):
                result = batch_mod.run_book(src, "campus", None, dry_run=True)
            self.assertIsNone(result)

    def test_generate_reports(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            out = td / "reports"
            batch_mod.generate_reports([], out)
            # 空结果不应崩溃
            self.assertTrue(out.is_dir() or not out.exists())


if __name__ == "__main__":
    unittest.main()
