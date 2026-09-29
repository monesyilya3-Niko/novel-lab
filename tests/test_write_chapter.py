#!/usr/bin/env python3
"""write.py 章节落盘纯函数覆盖测试（出版级补强）。

ensure_novel_structure / save_chapter 只碰磁盘（tmp 目录隔离），不依赖 LLM。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import write as write_mod


class TestEnsureNovelStructure(unittest.TestCase):
    def test_creates_layout_and_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel_dir = Path(tmp) / "book1"
            state_file = write_mod.ensure_novel_structure(novel_dir, "测试书")
            for sub in ("settings", "chapters", "tracker"):
                self.assertTrue((novel_dir / sub).is_dir())
            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["name"], "测试书")
            self.assertEqual(state["current_chapter"], 1)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel_dir = Path(tmp) / "book1"
            write_mod.ensure_novel_structure(novel_dir)
            (novel_dir / "state.json").write_text('{"name": "keep"}', encoding="utf-8")
            write_mod.ensure_novel_structure(novel_dir)
            # 已存在的 state.json 不被覆盖
            self.assertEqual(json.loads((novel_dir / "state.json").read_text(encoding="utf-8"))["name"], "keep")


class TestSaveChapter(unittest.TestCase):
    def _novel(self, tmp: Path) -> Path:
        novel_dir = tmp / "book1"
        write_mod.ensure_novel_structure(novel_dir)
        return novel_dir

    def test_file_layout_and_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel_dir = self._novel(Path(tmp))
            ch = write_mod.save_chapter(novel_dir, 1, "第一章内容")
            self.assertEqual(ch, novel_dir / "chapters" / "arc-1" / "chapter-001.txt")
            self.assertEqual(ch.read_text(encoding="utf-8"), "第一章内容")
            state = json.loads((novel_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["current_chapter"], 1)
            self.assertEqual(state["current_arc"], 1)
            self.assertEqual(state["word_count_today"], len("第一章内容"))

    def test_arc_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel_dir = self._novel(Path(tmp))
            ch31 = write_mod.save_chapter(novel_dir, 31, "x")
            self.assertEqual(ch31.parent.name, "arc-2")
            state = json.loads((novel_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["current_arc"], 2)

    def test_same_day_accumulates(self):
        with tempfile.TemporaryDirectory() as tmp:
            novel_dir = self._novel(Path(tmp))
            write_mod.save_chapter(novel_dir, 1, "ab")
            write_mod.save_chapter(novel_dir, 2, "cdef")
            state = json.loads((novel_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["word_count_today"], 6)

    def test_cross_day_resets(self):
        # 跨日清零分支：预置昨天的 last_write_date 与旧计数
        with tempfile.TemporaryDirectory() as tmp:
            novel_dir = self._novel(Path(tmp))
            state_file = novel_dir / "state.json"
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state["last_write_date"] = "2000-01-01"
            state["word_count_today"] = 9999
            state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            write_mod.save_chapter(novel_dir, 1, "ab")
            new_state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(new_state["word_count_today"], 2)


if __name__ == "__main__":
    unittest.main()
