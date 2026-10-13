#!/usr/bin/env python3
"""write.py 章节落盘纯函数覆盖测试（出版级补强）。

ensure_novel_structure / save_chapter 只碰磁盘（tmp 目录隔离），不依赖 LLM。
"""
import json
import subprocess
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


class TestWriteCliGuards(unittest.TestCase):
    """「写作」子命令的章号下限与 dry-run 零副作用（2026-10-13 审计 CLI-15/18）。

    CLI-15：--chapter 无下限 → 负数章号静默写出 chapters/arc-0/chapter--01.txt
    （arc = (chapter_no-1)//30+1 对负数得 0），并把 state.json 的
    current_chapter 记成 -1。用户改用 --chapter 1 后两文件共存，
    此后该书的质检/检查（按章号排序与去重）全部不可用。

    CLI-18：ensure_novel_structure 在 --dry-run 检查**之前**调用 →
    "只打印将调用的内容"的预演动作凭空多出 novel/ 目录与 state.json。
    若该目录恰与既有项目同名（默认值就是裸相对串 novel），还会静默污染。
    """

    def _run(self, *extra: str, cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "write.py"),
             "--prompt", str(cwd / "prompt.md"), "--task", "测试要点", *extra],
            cwd=str(cwd), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60,
        )

    def _prep(self, tmp: str) -> Path:
        d = Path(tmp)
        (d / "prompt.md").write_text("# system\n你是写手\n", encoding="utf-8")
        return d

    def test_negative_chapter_rejected_before_any_write(self):
        """核心守卫：负数章号必须拒绝，且不得创建任何目录/文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            d = self._prep(tmp)
            novel_dir = d / "novel"
            p = self._run("--chapter", "-1", "--novel-dir", str(novel_dir), cwd=d)
            out = (p.stdout or "") + (p.stderr or "")
            self.assertNotEqual(p.returncode, 0, "负数章号却返回成功")
            self.assertIn("≥ 1", out, f"未给出可读的章号下限提示:\n{out}")
            self.assertFalse(novel_dir.exists(),
                             "拒绝后仍创建了 novel 目录（校验未先于副作用）")

    def test_oversized_chapter_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._prep(tmp)
            p = self._run("--chapter", "999999", "--novel-dir", str(d / "novel"), cwd=d)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("过大", (p.stdout or "") + (p.stderr or ""))

    def test_dry_run_has_no_side_effects(self):
        """核心守卫：--dry-run 不得创建 novel 目录或 state.json。"""
        with tempfile.TemporaryDirectory() as tmp:
            d = self._prep(tmp)
            novel_dir = d / "novel"
            p = self._run("--chapter", "1", "--novel-dir", str(novel_dir),
                          "--dry-run", cwd=d)
            out = (p.stdout or "") + (p.stderr or "")
            self.assertEqual(p.returncode, 0, f"dry-run 失败:\n{out}")
            self.assertFalse(novel_dir.exists(),
                             "dry-run 创建了 novel 目录（应有零副作用）")
            self.assertFalse((novel_dir / "state.json").exists(),
                             "dry-run 写了 state.json")

    def test_dry_run_does_not_touch_existing_project(self):
        """反向守卫：dry-run 不得覆盖既有项目状态。"""
        with tempfile.TemporaryDirectory() as tmp:
            d = self._prep(tmp)
            novel_dir = d / "novel"
            novel_dir.mkdir()
            state = novel_dir / "state.json"
            sentinel = {"name": "既有项目", "current_chapter": 42}
            state.write_text(json.dumps(sentinel, ensure_ascii=False), encoding="utf-8")

            self._run("--chapter", "1", "--novel-dir", str(novel_dir),
                      "--dry-run", cwd=d)

            after = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(after, sentinel, "dry-run 改动了既有项目的 state.json")

    def test_normal_run_still_creates_structure(self):
        """反向守卫：非 dry-run 仍须正常建目录（不得因新校验误伤）。"""
        with tempfile.TemporaryDirectory() as tmp:
            d = self._prep(tmp)
            novel_dir = d / "novel"
            p = self._run("--chapter", "1", "--novel-dir", str(novel_dir), cwd=d)
            # 无外部模型时会生成"AI 接管清单"并退出，但目录结构应先建好
            self.assertTrue(novel_dir.exists(), "正常路径未创建项目目录")
            self.assertTrue((novel_dir / "state.json").is_file(), "未写 state.json")


if __name__ == "__main__":
    unittest.main()
