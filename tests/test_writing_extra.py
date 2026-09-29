"""写作增值功能回归（v2.0.2）：大纲 / 人物卡 / 便签 / 码字统计 / 导出。

隔离：_isolation.isolate_paths 重定向全部数据路径（含 NOVEL_DIR）到临时目录，
不碰真实库与真实章节文件。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolation  # noqa: E402

from gui import db, writing_extra  # noqa: E402
from gui.services import ServiceError  # noqa: E402

PROJ = "测试项目"


class WritingExtraTest(unittest.TestCase):
    def setUp(self):
        self._iso = _isolation.isolate_paths(Path(tempfile.mkdtemp(prefix="wxextra_")))
        self._iso.__enter__()
        db.init_schema()
        db.apply_migrations()

    def tearDown(self):
        db.close()
        self._iso.__exit__(None, None, None)

    # -- 字数统计 --
    def test_count_words(self):
        self.assertEqual(writing_extra.count_words(""), 0)
        self.assertEqual(writing_extra.count_words("你好，世界！"), 6)
        self.assertEqual(writing_extra.count_words("你好 \n 世界 123"), 7)
        self.assertEqual(writing_extra.count_words("Hello world"), 10)

    def test_project_validation(self):
        with self.assertRaises(ServiceError):
            writing_extra.list_outlines("")
        with self.assertRaises(ServiceError):
            writing_extra.list_outlines("../escape")
        with self.assertRaises(ServiceError):
            writing_extra.list_outlines("a/b")

    # -- 大纲 --
    def test_outline_crud(self):
        o = writing_extra.create_outline(PROJ, kind="volume", title="第一卷",
                                         summary="开篇", sort_order=1)
        self.assertEqual(o["kind"], "volume")
        self.assertEqual(o["status"], "planned")
        o2 = writing_extra.create_outline(PROJ, title="第1章", sort_order=2)
        items = writing_extra.list_outlines(PROJ)
        self.assertEqual([i["title"] for i in items], ["第一卷", "第1章"])
        upd = writing_extra.update_outline(o2["id"], status="writing")
        self.assertEqual(upd["status"], "writing")
        with self.assertRaises(ServiceError):
            writing_extra.update_outline(o2["id"], status="nope")
        with self.assertRaises(ServiceError):
            writing_extra.create_outline(PROJ, title="  ")
        writing_extra.delete_outline(o["id"])
        self.assertEqual(len(writing_extra.list_outlines(PROJ)), 1)
        with self.assertRaises(ServiceError):
            writing_extra.delete_outline(999999)

    # -- 人物卡 --
    def test_character_crud(self):
        c = writing_extra.create_character(PROJ, "温霜禾", role="女主",
                                           description="粉色控", extra={"age": 19})
        self.assertEqual(c["name"], "温霜禾")
        items = writing_extra.list_characters(PROJ)
        self.assertEqual(len(items), 1)
        upd = writing_extra.update_character(c["id"], role="女主角")
        self.assertEqual(upd["role"], "女主角")
        with self.assertRaises(ServiceError):
            writing_extra.create_character(PROJ, "  ")
        writing_extra.delete_character(c["id"])
        self.assertEqual(writing_extra.list_characters(PROJ), [])

    # -- 便签 --
    def test_note_crud(self):
        n = writing_extra.create_note(PROJ, "灵感", "雪夜告白")
        self.assertEqual(n["title"], "灵感")
        upd = writing_extra.update_note(n["id"], content="雪夜告白·改")
        self.assertEqual(upd["content"], "雪夜告白·改")
        with self.assertRaises(ServiceError):
            writing_extra.create_note(PROJ, "", "")
        writing_extra.delete_note(n["id"])
        self.assertEqual(writing_extra.list_notes(PROJ), [])

    # -- 码字统计 --
    def test_record_and_stats(self):
        writing_extra.record_words(PROJ, 3000)
        writing_extra.record_words(PROJ, 2000, chapters=1)
        writing_extra.record_words(PROJ, 0)  # 0 字不记录
        s = writing_extra.get_stats(PROJ, days=7)
        self.assertEqual(s["today_words"], 5000)
        self.assertEqual(s["today_chapters"], 2)
        self.assertEqual(s["streak_days"], 1)
        self.assertEqual(len(s["history"]), 7)
        self.assertEqual(s["history"][-1]["words"], 5000)
        self.assertEqual(s["total_words"], 0)  # 尚无章节文件
        self.assertEqual(s["total_chapters"], 0)

    def test_stats_total_from_files(self):
        from gui import config
        chdir = config.NOVEL_DIR / PROJ / "chapters" / "arc-1"
        chdir.mkdir(parents=True)
        (chdir / "chapter-001.txt").write_text("标题\n\n正文一二三四", encoding="utf-8")
        (chdir / "chapter-002.txt").write_text("第二章\n\nabcdef", encoding="utf-8")
        s = writing_extra.get_stats(PROJ, days=7)
        self.assertEqual(s["total_chapters"], 2)
        # "标题正文一二三四" = 8；"第二章abcdef" = 9
        self.assertEqual(s["total_words"], 17)

    # -- 导出 --
    def test_export_txt(self):
        from gui import config
        chdir = config.NOVEL_DIR / PROJ / "chapters" / "arc-1"
        chdir.mkdir(parents=True)
        (chdir / "chapter-001.txt").write_text(
            "第001章 相遇\n\n雪落下来的时候。", encoding="utf-8")
        (chdir / "chapter-002.txt").write_text("正文无标题开头，直接写内容。", encoding="utf-8")
        r = writing_extra.export_project_txt(PROJ)
        self.assertEqual(r["chapters"], 2)
        self.assertIn("第001章 相遇", r["content"])
        self.assertIn("第2章", r["content"])  # 无标题章节补默认标题
        # 自带标题的章节不应重复输出标题
        self.assertEqual(r["content"].count("第001章 相遇"), 1)
        self.assertTrue(r["filename"].endswith(".txt"))
        with self.assertRaises(ServiceError):
            writing_extra.export_project_txt("空项目")

    # -- 路由 --
    def test_router_endpoints(self):
        from gui import router
        paths = [p.pattern for _m, p, _h in router.ROUTES]
        for want in ("/api/writing/outlines", "/api/writing/characters",
                     "/api/writing/notes", "/api/writing/stats",
                     "/api/writing/export"):
            self.assertTrue(any(want in pat for pat in paths), want)
        payload, _ = router.dispatch("GET", "/api/writing/stats", {},
                                     {"project": PROJ, "days": "7"})
        self.assertEqual(payload["code"], 0)
        self.assertIn("today_words", payload["data"])




class WritingStatsHookIsolationTest(unittest.TestCase):
    """回归：writing_service.py 里所有 record_words 调用必须被 try/except 包裹。

    背景（2026-09-30 实锤）：手动写作流的挂钩有 try/except，但 AI 生成流
    （_run_generate 落盘后）的挂钩没有——统计表一旦异常，章节已落盘但任务
    状态永远到不了 done，用户看到任务卡死。统计失败绝不能阻断写作主流程。
    """

    def test_all_record_words_calls_are_guarded(self):
        import ast
        src = (Path(__file__).resolve().parent.parent
               / "gui" / "writing_service.py").read_text(encoding="utf-8")
        tree = ast.parse(src)

        calls = []  # (lineno, 是否在 Try 内)

        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self._try_depth = 0

            def visit_Try(self, node):
                self._try_depth += 1
                self.generic_visit(node)
                self._try_depth -= 1

            def visit_Call(self, node):
                func = node.func
                name = ""
                if isinstance(func, ast.Attribute):
                    name = func.attr
                elif isinstance(func, ast.Name):
                    name = func.id
                if name == "record_words":
                    calls.append((node.lineno, self._try_depth > 0))
                self.generic_visit(node)

        Visitor().visit(tree)
        self.assertGreater(len(calls), 0, "writing_service.py 里没找到 record_words 调用")
        for lineno, guarded in calls:
            self.assertTrue(
                guarded,
                f"writing_service.py:{lineno} 的 record_words 调用不在 try/except 内，"
                "统计异常会阻断写作主流程",
            )


if __name__ == "__main__":
    unittest.main()
