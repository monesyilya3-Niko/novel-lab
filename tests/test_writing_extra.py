"""写作增值功能回归（v2.0.2）：大纲 / 人物卡 / 便签 / 码字统计 / 导出。

隔离：_isolation.isolate_paths 重定向全部数据路径（含 NOVEL_DIR）到临时目录，
不碰真实库与真实章节文件。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TESTS_DIR = Path(__file__).resolve().parent
_ROOT = _TESTS_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_TESTS_DIR))
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

    def test_stats_reads_gbk_chapter(self):
        """用户把稿子按 chapter-NNN.txt 摆进 novel/ 是常见操作，GBK 编码不能算漏。

        旧实现 ``read_text(encoding="utf-8")`` 在这里直接抛 UnicodeDecodeError，
        码字统计/导出/入库记账全变 500，而且不带文件名。
        """
        from gui import config
        chdir = config.NOVEL_DIR / PROJ / "chapters" / "arc-1"
        chdir.mkdir(parents=True)
        (chdir / "chapter-001.txt").write_text("标题\n\n正文一二三四", encoding="utf-8")
        (chdir / "chapter-002.txt").write_bytes("第二章\n\n正文一二三四".encode("gbk"))
        s = writing_extra.get_stats(PROJ, days=7)
        self.assertEqual(s["total_chapters"], 2)
        # "标题正文一二三四"=8 + "第二章正文一二三四"=9；GBK 那章不许算成 0
        self.assertEqual(s["total_words"], 17)

    def test_export_reads_gbk_chapter(self):
        from gui import config
        chdir = config.NOVEL_DIR / PROJ / "chapters" / "arc-1"
        chdir.mkdir(parents=True)
        (chdir / "chapter-001.txt").write_text("第001章 相遇\n\n雪落下来的时候。", encoding="utf-8")
        (chdir / "chapter-002.txt").write_bytes("第002章 离别\n\n他没有回头。".encode("gbk"))
        r = writing_extra.export_project_txt(PROJ)
        self.assertEqual(r["chapters"], 2)
        self.assertIn("他没有回头", r["content"])

    def test_undecodable_chapter_error_names_the_file(self):
        from gui import config
        chdir = config.NOVEL_DIR / PROJ / "chapters" / "arc-1"
        chdir.mkdir(parents=True)
        bad = chdir / "chapter-009.txt"
        bad.write_bytes(b"\xff\xfe\x00\x01\x02")
        with self.assertRaises(ServiceError) as cm:
            writing_extra.get_stats(PROJ, days=7)
        self.assertEqual(cm.exception.code, 400)
        self.assertIn("chapter-009.txt", cm.exception.message)

    # -- 重复入库幂等 --
    def _today(self):
        s = writing_extra.get_stats(PROJ, days=7)
        return s["today_words"], s["today_chapters"]

    def test_reimport_identical_is_noop(self):
        from gui import writing_service
        r1 = writing_service.import_chapter(PROJ, 1, "第一章正文。" * 200)
        self.assertFalse(r1["overwrote"])
        self.assertEqual(self._today(), (1200, 1))
        r2 = writing_service.import_chapter(PROJ, 1, "第一章正文。" * 200)
        self.assertTrue(r2["overwrote"])
        self.assertEqual(self._today(), (1200, 1))  # 完全幂等：字数章节都不变

    def test_reimport_longer_records_delta(self):
        from gui import writing_service
        writing_service.import_chapter(PROJ, 1, "一" * 1000)
        writing_service.import_chapter(PROJ, 1, "一" * 1500)
        self.assertEqual(self._today(), (1500, 1))  # 只记 +500，不重复加章节

    def test_reimport_shorter_deducts(self):
        from gui import writing_service
        writing_service.import_chapter(PROJ, 1, "一" * 1000)
        writing_service.import_chapter(PROJ, 1, "一" * 600)
        self.assertEqual(self._today(), (600, 1))  # 改短扣减

    def test_new_chapters_still_count(self):
        from gui import writing_service
        writing_service.import_chapter(PROJ, 1, "一" * 1000)
        writing_service.import_chapter(PROJ, 2, "二" * 500)
        self.assertEqual(self._today(), (1500, 2))

    def test_get_chapter_words(self):
        from gui import writing_service
        self.assertIsNone(writing_extra.get_chapter_words(PROJ, 1))
        writing_service.import_chapter(PROJ, 1, "一" * 777)
        self.assertEqual(writing_extra.get_chapter_words(PROJ, 1), 777)

    def test_concurrent_reimport_same_chapter(self):
        """并发重复入库同一章节：20 线程同时入库，最终只记一次（防竞态）。"""
        import threading

        from gui import writing_service
        errs: list = []

        def worker():
            try:
                writing_service.import_chapter(PROJ, 1, "一" * 1000)
            except Exception as exc:  # noqa: BLE001
                errs.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errs, [])
        self.assertEqual(self._today(), (1000, 1))

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


class RecordWordsFailureBehaviorTest(unittest.TestCase):
    """行为级回归：record_words 抛异常时，写作任务仍必须进入 done。

    AST 静态测试（WritingStatsHookIsolationTest）只保证"调用被 try/except
    包裹"，本测试真正模拟码字统计表异常，验证 AI 生成流与手动入库流的
    主流程都不受影响：章节已落盘，任务状态必须走到 done，不能卡死。
    """

    def setUp(self):
        self._iso = _isolation.isolate_paths(Path(tempfile.mkdtemp(prefix="wxhook_")))
        self._iso.__enter__()
        db.init_schema()
        db.apply_migrations()
        # 模拟统计表异常：record_words 每次调用都炸
        self._boom = RuntimeError("统计表炸了（测试模拟）")
        self._rec_patcher = patch.object(
            writing_extra, "record_words", side_effect=self._boom)
        self._rec_patcher.start()
        self.addCleanup(self._rec_patcher.stop)

    def tearDown(self):
        from gui import writing_service
        with writing_service._WRITING_LOCK:
            writing_service._WRITING_TASKS.clear()
        db.close()
        self._iso.__exit__(None, None, None)

    def _mock_llm_pipeline(self):
        """打桩整条 AI 生成管线：首稿即达标，只走 1 个 attempt。"""
        from gui import engine_adapter
        p1 = patch.object(engine_adapter, "llm_chat",
                          return_value={"text": "第一章正文。" * 200})
        p2 = patch.object(engine_adapter, "score_text",
                          return_value={"score": 95.0, "details": []})
        p3 = patch.object(engine_adapter, "chapter_check",
                          return_value={"score": 90, "issues": []})
        p4 = patch.object(engine_adapter, "ensure_novel_structure",
                          return_value=Path("novel"))
        fake_chapter = Path("novel") / "chapters" / "chapter-001.txt"
        p5 = patch.object(engine_adapter, "save_chapter",
                          return_value=fake_chapter)
        for p in (p1, p2, p3, p4, p5):
            p.start()
            self.addCleanup(p.stop)

    def test_generate_reaches_done_when_record_words_raises(self):
        from gui import writing_service
        self._mock_llm_pipeline()
        task_id = "w-test-behavior"
        req = {"project": PROJ, "chapter_no": 1, "task": "测试要点",
               "novel_name": PROJ, "genre_pack": None, "words": 2400,
               "target_score": 90, "quality_target": 85, "pass_line": 85}
        with writing_service._WRITING_LOCK:
            writing_service._WRITING_TASKS[task_id] = {
                "task_id": task_id, "status": "running", "mode": "llm",
                "attempts": [], "score": None, "quality_score": None,
            }
        # 同步直调后台函数（与线程内执行路径一致）
        writing_service._run_generate(task_id, {"meta": {}}, "system", req)
        t = writing_service.task_state(task_id)
        self.assertEqual(t["status"], "done",
                         f"record_words 抛异常后任务状态应为 done，实际 {t['status']!r}")
        self.assertIsNotNone(t["chapter_path"])
        self.assertIn("完成", t["message"])

    def test_import_chapter_ok_when_record_words_raises(self):
        from gui import writing_service
        self._mock_llm_pipeline()  # 复用 save_chapter / ensure_novel_structure 打桩
        result = writing_service.import_chapter(PROJ, 1, "正文内容。" * 100)
        self.assertEqual(result["chapter_no"], 1)
        self.assertGreater(result["char_count"], 0)


if __name__ == "__main__":
    unittest.main()
