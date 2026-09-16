"""quality_service 单元测试（W13/W14 spec 要求）。

覆盖：check / book / resolve_chapter_target / clean_stale_scratch / 并发上限 / 路径穿越。
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import config, quality_service  # noqa: E402
from gui.services import ServiceError, detect_asset_kind  # noqa: E402

_TMP = None
_SAVED = {}


def setUpModule():
    global _TMP, _SAVED
    _TMP = tempfile.mkdtemp(prefix="quality_qa_")
    _SAVED["ROOT_DIR"] = config.ROOT_DIR
    config.ROOT_DIR = Path(_TMP)
    for name in ("STATE_ROOT", "STATE_JSON_DIR", "ASSETS_ROOT", "NOVEL_DIR",
                 "CORPUS_DIR", "REPORTS_DIR", "PROMPTS_DIR", "CONFIG_DIR"):
        _SAVED[name] = getattr(config, name)
        setattr(config, name, config.ROOT_DIR / name.lower())
    # 派生常量同样重定向到临时根（保持与 config 中的派生关系一致）。
    for name in ("DB_PATH", "LOCK_PATH"):
        _SAVED[name] = getattr(config, name)
    config.DB_PATH = config.STATE_ROOT / "index.db"
    config.LOCK_PATH = config.STATE_ROOT / ".lock"
    config.ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
    config.NOVEL_DIR.mkdir(parents=True, exist_ok=True)
    config.CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # 测试 voice-card
    vc = {
        "meta": {"title": "测试书", "genre": "campus-redemption", "confidence": 0.9},
        "narration": {"pov": "third_limited"},
        "dialogue": {"character_voices": []},
        "emotion_handling": {"mode": "体感"},
        "banned": {"never_used_words": []},
    }
    (config.ASSETS_ROOT / "testbook-voice-card.json").write_text(
        json.dumps(vc, ensure_ascii=False), encoding="utf-8")
    # 测试 distilled（跨书题材蒸馏卡）：靠 meta.dimension + rules/blindspots/stats 自证。
    distilled = {
        "meta": {"dimension": "voice-card", "genre": "campus-redemption"},
        "rules": [], "blindspots": [], "stats": {},
    }
    (config.ASSETS_ROOT / "campus-redemption-voice-card-distilled.json").write_text(
        json.dumps(distilled, ensure_ascii=False), encoding="utf-8")
    # 缺 meta.dimension、仅靠 rules/blindspots/stats 三元组自证的蒸馏卡：
    # scripts/validate.py 的 auto_kind 用 OR 语义（dimension ∈ 四维 **或** 三元组），
    # 服务层必须同构，否则这类卡会被放行当 voice 用。
    distilled_triple_only = {
        "meta": {"genre": "campus-redemption"},
        "rules": [], "blindspots": [], "stats": {},
    }
    (config.ASSETS_ROOT / "campus-redemption-voice-card-distilled-triple-only.json").write_text(
        json.dumps(distilled_triple_only, ensure_ascii=False), encoding="utf-8")
    # 测试章节目录
    ch_dir = config.NOVEL_DIR / "testproj" / "chapters"
    ch_dir.mkdir(parents=True, exist_ok=True)
    (ch_dir / "chapter-001.txt").write_text("这是第一章测试内容。" * 50, encoding="utf-8")


def _scratch_entries() -> set:
    """STATE_ROOT/scratch/ 下的现存条目名（用于断言校验失败不残留 scratch）。"""
    root = config.STATE_ROOT / "scratch"
    return {p.name for p in root.iterdir()} if root.is_dir() else set()


def _assert_kind_mismatch(tc: unittest.TestCase, exc: BaseException,
                          expected: str, actual: str) -> None:
    """断言错误表达的是「内容 kind 与参数期望不符」，而非仅仅出现某个关键词。"""
    msg = str(exc)
    tc.assertIn("kind 不匹配", msg)
    tc.assertIn(f"内容自证为 {actual}", msg)
    tc.assertIn(f"不能作为 {expected} 使用", msg)


def tearDownModule():
    for name, value in _SAVED.items():
        setattr(config, name, value)
    if _TMP:
        shutil.rmtree(_TMP, ignore_errors=True)


class TestResolveChapterTarget(unittest.TestCase):
    def test_empty_rejected(self):
        with self.assertRaises(ServiceError):
            quality_service.resolve_chapter_target("")

    def test_nonexistent_404(self):
        with self.assertRaises(ServiceError) as cm:
            quality_service.resolve_chapter_target("no/such/path")
        self.assertEqual(cm.exception.code, 404)

    def test_path_traversal_rejected(self):
        # 绝对路径在项目外
        with self.assertRaises(ServiceError):
            quality_service.resolve_chapter_target("C:/Windows/System32")

    def test_valid_relative_path(self):
        fp = quality_service.resolve_chapter_target("testproj/chapters/chapter-001.txt")
        self.assertTrue(fp.is_file())

    def test_valid_dir(self):
        fp = quality_service.resolve_chapter_target("testproj/chapters")
        self.assertTrue(fp.is_dir())


class TestMaterializeText(unittest.TestCase):
    def test_creates_per_task_subdir(self):
        fp = quality_service._materialize_text("测试内容", "test-task-001")
        self.assertTrue(fp.is_file())
        self.assertEqual(fp.parent.name, "test-task-001")
        # 清理
        fp.unlink()
        fp.parent.rmdir()


class TestCleanStaleScratch(unittest.TestCase):
    def test_cleans_files_and_dirs(self):
        scratch = config.STATE_ROOT / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        # 旧格式文件
        (scratch / "old.txt").write_text("stale", encoding="utf-8")
        # 新格式子目录
        sub = scratch / "old-task"
        sub.mkdir(exist_ok=True)
        (sub / "input.txt").write_text("stale", encoding="utf-8")
        n = quality_service.clean_stale_scratch()
        self.assertGreaterEqual(n, 2)
        self.assertFalse((scratch / "old.txt").exists())
        self.assertFalse(sub.exists())

    def test_empty_dir_returns_zero(self):
        # 确保 scratch 目录不存在时返回 0
        scratch = config.STATE_ROOT / "scratch"
        if scratch.exists():
            import shutil
            shutil.rmtree(scratch)
        n = quality_service.clean_stale_scratch()
        self.assertEqual(n, 0)


class TestCheck(unittest.TestCase):
    def test_no_input_rejected(self):
        with self.assertRaises(ServiceError):
            quality_service.check()

    def test_check_with_text(self):
        text = "她站在教室门口。\"你来了。\"他说。她没有回答。" * 20
        r = quality_service.check(text=text, voice="voice:testbook-voice-card")
        self.assertIn("quality", r)
        self.assertIn("consistency", r)
        self.assertIn("score", r["quality"])

    def test_check_without_voice(self):
        text = "测试内容。" * 30
        r = quality_service.check(text=text)
        self.assertIn("quality", r)
        self.assertNotIn("consistency", r)


class TestBook(unittest.TestCase):
    def test_no_input_rejected(self):
        with self.assertRaises(ServiceError):
            quality_service.book()

    def test_book_with_target_dir(self):
        r = quality_service.book(target="testproj/chapters")
        self.assertIsInstance(r, dict)


class TestAssetKindContract(unittest.TestCase):
    """Task 6：错误 kind 的资产（distilled 当 voice）必须同步拒绝为 400。

    distilled 是跨书题材蒸馏卡，不是单书 voice 卡；把它当 voice 传入会让打分/
    质检用错维度的资产，因此服务层要在解析后立刻按内容契约拒绝。
    """

    def test_check_rejects_distilled_as_voice(self):
        with self.assertRaises(ServiceError) as ctx:
            quality_service.check(
                text="她推门而入。" * 30,
                voice="voice:campus-redemption-voice-card-distilled")
        self.assertEqual(ctx.exception.code, 400)
        _assert_kind_mismatch(self, ctx.exception, expected="voice", actual="distilled")

    def test_check_valid_voice_still_works(self):
        r = quality_service.check(text="她推门而入。" * 30, voice="voice:testbook-voice-card")
        self.assertIn("consistency", r)

    def test_book_rejects_distilled_as_voice(self):
        with self.assertRaises(ServiceError) as ctx:
            quality_service.book(
                target="testproj/chapters",
                voice="voice:campus-redemption-voice-card-distilled")
        self.assertEqual(ctx.exception.code, 400)
        _assert_kind_mismatch(self, ctx.exception, expected="voice", actual="distilled")

    def test_book_text_path_rejects_distilled_without_scratch(self):
        """I1：book() 的 text 路径先建 scratch 再校验 voice，校验抛 400 时
        清理用的 try/finally 尚未进入，会每次泄漏一个 scratch 目录。"""
        before = _scratch_entries()
        with self.assertRaises(ServiceError) as ctx:
            quality_service.book(
                text="她推门而入。" * 30,
                voice="voice:campus-redemption-voice-card-distilled")
        self.assertEqual(ctx.exception.code, 400)
        _assert_kind_mismatch(self, ctx.exception, expected="voice", actual="distilled")
        self.assertEqual(_scratch_entries(), before, "校验失败后不得残留 scratch 目录")

    def test_qc_text_path_rejects_distilled_without_scratch(self):
        """qc() 的前置校验对齐用例：text 路径校验失败同样不得留 scratch。"""
        before = _scratch_entries()
        with self.assertRaises(ServiceError) as ctx:
            quality_service.qc(
                text="她推门而入。" * 30,
                voice="voice:campus-redemption-voice-card-distilled")
        self.assertEqual(ctx.exception.code, 400)
        _assert_kind_mismatch(self, ctx.exception, expected="voice", actual="distilled")
        self.assertEqual(_scratch_entries(), before, "校验失败后不得残留 scratch 目录")

    def test_qc_rejects_distilled_as_voice_before_thread(self):
        """校验必须在启动后台线程之前完成：错误同步 400，且不占用并发槽位。"""
        before = quality_service._active_quality_count()
        with self.assertRaises(ServiceError) as ctx:
            quality_service.qc(
                target="testproj/chapters",
                voice="voice:campus-redemption-voice-card-distilled")
        self.assertEqual(ctx.exception.code, 400)
        _assert_kind_mismatch(self, ctx.exception, expected="voice", actual="distilled")
        self.assertEqual(quality_service._active_quality_count(), before)


class TestDistilledDetectionParity(unittest.TestCase):
    """I2：detect_asset_kind 必须与 scripts/validate.py:auto_kind 同构。

    validate.py 用 OR 语义识别蒸馏卡：
      ``meta.dimension ∈ 四维`` **或** ``rules/blindspots/stats 三元组齐备``。
    服务层若用 AND，缺 meta.dimension 的蒸馏卡会被放行当 voice 用（口径分叉）。
    """

    def test_triple_only_without_dimension_is_distilled(self):
        data = {"meta": {"genre": "campus-redemption"},
                "rules": [], "blindspots": [], "stats": {}}
        self.assertEqual(detect_asset_kind(data), "distilled")

    def test_dimension_only_without_triple_is_distilled(self):
        data = {"meta": {"dimension": "voice-card"}}
        self.assertEqual(detect_asset_kind(data), "distilled")

    def test_dimension_outside_four_values_not_distilled(self):
        """dimension 必须落在四个合法值内，非法值不得单独构成 distilled 识别依据。"""
        self.assertIsNone(detect_asset_kind({"meta": {"dimension": "not-a-dimension"}}))

    def test_check_rejects_triple_only_distilled_as_voice(self):
        with self.assertRaises(ServiceError) as ctx:
            quality_service.check(
                text="她推门而入。" * 30,
                voice="voice:campus-redemption-voice-card-distilled-triple-only")
        self.assertEqual(ctx.exception.code, 400)
        _assert_kind_mismatch(self, ctx.exception, expected="voice", actual="distilled")


class TestConcurrencyLimit(unittest.TestCase):
    def test_active_count_starts_zero(self):
        with quality_service._QUALITY_LOCK:
            quality_service._QUALITY_TASKS.clear()
        self.assertEqual(quality_service._active_quality_count(), 0)

    def test_running_task_counted(self):
        with quality_service._QUALITY_LOCK:
            quality_service._QUALITY_TASKS["q-test"] = {"status": "running"}
        self.assertEqual(quality_service._active_quality_count(), 1)
        with quality_service._QUALITY_LOCK:
            quality_service._QUALITY_TASKS.clear()

    def test_done_task_not_counted(self):
        with quality_service._QUALITY_LOCK:
            quality_service._QUALITY_TASKS["q-done"] = {"status": "done"}
        self.assertEqual(quality_service._active_quality_count(), 0)
        with quality_service._QUALITY_LOCK:
            quality_service._QUALITY_TASKS.clear()


class TestListQcReports(unittest.TestCase):
    def test_empty_reports_dir(self):
        reports = quality_service.list_qc_reports()
        self.assertIsInstance(reports, list)


if __name__ == "__main__":
    unittest.main()


class TestQcSubmitNoDeadlock(unittest.TestCase):
    """回归：qc() 提交路径的并发检查在持锁状态下调用 _active_quality_count()，
    非重入 Lock 会自死锁（GUI 质检台 QC 按钮曾因此完全不可用）。
    修复为 RLock 后，提交必须立即返回 running 态。"""

    def test_qc_submit_returns_promptly(self):
        # 隔离的小章节目录（corpus 相对目标在 setUpModule 已 patch 到 _TMP）
        ch_dir = config.CORPUS_DIR / "qa_deadlock_chapters"
        ch_dir.mkdir(parents=True, exist_ok=True)
        body = "第一章 测试\n\n" + "他推门而入。\n" * 30
        (ch_dir / "001.txt").write_text(body, encoding="utf-8")
        import time
        t0 = time.time()
        r = quality_service.qc(target="qa_deadlock_chapters")
        elapsed = time.time() - t0
        self.assertEqual(r["status"], "running")
        self.assertLess(elapsed, 5.0, f"qc() 提交耗时 {elapsed:.1f}s——疑似锁自死锁回归")
        # 等后台线程收尾，避免泄漏到其他用例
        for _ in range(30):
            st = quality_service.qc_task_state(r["task_id"])
            if st["status"] in ("done", "error"):
                break
            time.sleep(1)
        self.assertEqual(st["status"], "done")
