"""GUI 桥接层后端单元/集成测试（QA 严过关）。

覆盖：
1. state_store：原子写、单调 state_revision、cursor 解析/推进、崩溃恢复。
2. engine_adapter：split_chapters / split_batches 真实 txt 切分正确性。
3. router/services：import / status / asset 接口逻辑 + GET /api/asset 路径穿越防护。
4. 断点续传：resume 是否跳过 success 批、重跑失败批。

纯标准库 unittest，隔离真实 gui_state/assets 目录（monkeypatch 到临时目录）。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import config, state_store, engine_adapter, router, services  # noqa: E402
from gui import services as svc  # noqa: E402


# ---------------------------------------------------------------------------
# 隔离：把 STATE_ROOT / STATE_JSON_DIR / ASSETS_ROOT 指向临时目录，避免污染
# 真实状态。
#
# 注意：patch 必须放在 setUpModule()/tearDownModule() 里成对执行，**不能**放
# 在模块 import 期。unittest discover 会先 import 全部测试模块再逐个执行，
# 模块级 patch 一旦生效就持续整个测试会话、且永不还原——那会让本模块替其它
# 漏 patch 的模块兜底，掩盖真实泄漏（防线假绿）。成对 patch 保证：本模块测试
# 结束后 config 精确还原，任何后续模块的泄漏都逃不过末位泄漏守卫。
# ---------------------------------------------------------------------------

_TMP = None
_ORIG_STATE_ROOT = None
_ORIG_STATE_JSON_DIR = None
_ORIG_ASSETS_ROOT = None


def setUpModule():
    """进入本模块测试前：成对重定向三个数据路径常量到临时目录。"""
    global _TMP, _ORIG_STATE_ROOT, _ORIG_STATE_JSON_DIR, _ORIG_ASSETS_ROOT
    _TMP = tempfile.mkdtemp(prefix="gui_qa_")
    _ORIG_STATE_ROOT = config.STATE_ROOT
    _ORIG_STATE_JSON_DIR = config.STATE_JSON_DIR
    _ORIG_ASSETS_ROOT = config.ASSETS_ROOT
    config.STATE_ROOT = Path(_TMP) / "gui_state"
    # R1：STATE_JSON_DIR 必须与 STATE_ROOT 成对隔离。save_state 把 JSON 写进
    # STATE_JSON_DIR，漏 patch 会让全部夹具落进真实 gui/state/ 并跨轮累积。
    config.STATE_JSON_DIR = Path(_TMP) / "gui" / "state"
    config.ASSETS_ROOT = Path(_TMP) / "assets"
    # state_store 通过 config 间接引用，运行时一致。


def tearDownModule():
    """本模块测试结束后：精确还原全部常量，并回收临时目录。"""
    global _TMP
    config.STATE_ROOT = _ORIG_STATE_ROOT
    config.STATE_JSON_DIR = _ORIG_STATE_JSON_DIR
    config.ASSETS_ROOT = _ORIG_ASSETS_ROOT
    if _TMP:
        # ignore_errors：Windows 上隔离库文件句柄可能仍被占用，回收失败不影响
        # 正确性（config 已还原），只影响临时目录是否残留。
        shutil.rmtree(_TMP, ignore_errors=True)
        _TMP = None


def _cleanup_state_files():
    """清理隔离目录下的状态文件（STATE_ROOT + STATE_JSON_DIR 成对覆盖）。"""
    for root in (config.STATE_ROOT, config.STATE_JSON_DIR):
        for p in root.glob("gui_state_*.json"):
            p.unlink(missing_ok=True)
        for p in root.glob("*.tmp"):
            p.unlink(missing_ok=True)

SAMPLE_TXT = """第一章 风起

这是第一段正文。张三走进门，说道：“你好。”

第二段，继续写一些内容，让章节足够长。

第二章 云涌

第二章的正文开始了。李四回应道：“你也好。”

这里继续补充内容。
"""


class TestStateStore(unittest.TestCase):
    """state_store 原子写 / 单调 revision / cursor。"""

    def tearDown(self):
        # 清理本测试产生的状态文件，保证独立性。
        _cleanup_state_files()

    def test_new_state_skeleton(self):
        st = state_store.new_state("bk1", "书")
        self.assertEqual(st["schema_version"], 1)
        self.assertEqual(st["book_id"], "bk1")
        self.assertEqual(st["state_revision"], 0)
        self.assertEqual(st["cursor"], "")
        self.assertEqual(st["chapter_states"], {})
        self.assertEqual(st["asset_index"], {})

    def test_atomic_write_uses_tmp_then_replace(self):
        st = state_store.new_state("bk-atomic", "书")
        st["state_revision"] = 1
        state_store.save_state(st)
        path = state_store.state_path_for("bk-atomic")
        self.assertTrue(path.is_file())
        # 写完后不应残留 .tmp 文件。
        tmp = path.with_suffix(path.suffix + ".tmp")
        self.assertFalse(tmp.exists(), "原子写完成后 .tmp 应被 os.replace 消耗掉")

    def test_bump_revision_monotonic(self):
        st = state_store.new_state("bk-rev", "书")
        self.assertEqual(st["state_revision"], 0)
        state_store.bump_revision(st)
        self.assertEqual(st["state_revision"], 1)
        state_store.bump_revision(st)
        self.assertEqual(st["state_revision"], 2)

    def test_cursor_parse_and_advance(self):
        self.assertIsNone(state_store.parse_cursor(""))
        self.assertIsNone(state_store.parse_cursor("garbage"))
        self.assertIsNone(state_store.parse_cursor("c1"))  # 缺 batch
        self.assertIsNone(state_store.parse_cursor("c1-b"))
        self.assertIsNone(state_store.parse_cursor("x1-b2"))
        self.assertEqual(state_store.parse_cursor("c3-b2"), (3, 2))
        self.assertEqual(state_store.parse_cursor("c10-b0"), (10, 0))

        st = state_store.new_state("bk-cur", "书")
        state_store.set_batch_state(st, 1, 0, "success", asset="a.json")
        self.assertEqual(st["cursor"], "c1-b1")
        self.assertEqual(st["state_revision"], 1)
        self.assertEqual(st["chapter_states"]["c1-b0"]["status"], "success")
        self.assertEqual(st["asset_index"]["c1"], ["c1-b0"])

    def test_crash_recovery_no_state_loss(self):
        """写入→模拟崩溃(不 save)→重新 load 恢复，验证已持久化数据不丢。"""
        st = state_store.new_state("bk-crash", "书")
        state_store.set_batch_state(st, 1, 0, "success", asset="a.json")
        state_store.set_batch_state(st, 1, 1, "success", asset="b.json")
        state_store.save_state(st)

        # 模拟进程崩溃后重新 load。
        loaded = state_store.load_state("bk-crash")
        self.assertEqual(loaded["cursor"], "c1-b2")
        self.assertEqual(loaded["state_revision"], 2)
        self.assertEqual(loaded["chapter_states"]["c1-b0"]["status"], "success")
        self.assertEqual(loaded["chapter_states"]["c1-b1"]["status"], "success")
        self.assertEqual(loaded["asset_index"]["c1"], ["c1-b0", "c1-b1"])

    def test_save_state_missing_book_id_raises(self):
        with self.assertRaises(ValueError):
            state_store.save_state({"no_book_id": True})


class TestEngineAdapter(unittest.TestCase):
    """split_chapters / split_batches 真实文本切分。"""

    def test_split_chapters(self):
        chapters = engine_adapter.split_chapters(SAMPLE_TXT)
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0][0], "第一章 风起")
        self.assertEqual(chapters[1][0], "第二章 云涌")

    def test_split_chapters_on_real_corpus(self):
        corpus = ROOT / "corpus" / "sampled" / "chireng_chosen" / "chapters"
        if not corpus.is_dir():
            self.skipTest("corpus 语料不存在")
        files = sorted(corpus.glob("*.txt"))
        self.assertGreaterEqual(len(files), 1)
        # 单章文件本身作为一章输入，验证不抛异常且非空。
        text = files[0].read_text(encoding="utf-8")
        chapters = engine_adapter.split_chapters(text)
        self.assertGreaterEqual(len(chapters), 1)

    def test_split_batches_respects_max_size(self):
        text = "这是一段测试文本。" * 2000  # 远大于 batch_size
        for bs in (100, 4000):
            batches = engine_adapter.split_batches(text, bs)
            self.assertGreater(len(batches), 1)
            for b in batches:
                self.assertLessEqual(len(b["text"]), bs, f"批 {b['batch_index']} 超过上限 {bs}")

    def test_split_batches_empty(self):
        self.assertEqual(engine_adapter.split_batches("", 100), [])
        self.assertEqual(engine_adapter.split_batches("   \n  ", 100), [])

    def test_split_batches_invalid_size(self):
        with self.assertRaises(ValueError):
            engine_adapter.split_batches("abc", 0)

    def test_split_batches_continuity(self):
        """批切分不丢字符：拼接所有批 = 原文本（去除空白边界可验证 char 范围连续）。"""
        text = "甲乙丙丁戊己庚辛" * 50
        batches = engine_adapter.split_batches(text, 20)
        self.assertEqual(batches[0]["char_start"], 0)
        self.assertEqual(batches[-1]["char_end"], len(text))
        for a, b in zip(batches, batches[1:]):
            self.assertEqual(a["char_end"], b["char_start"], "批次边界必须连续无缝隙/无重叠")


class TestRouterAssetSecurity(unittest.TestCase):
    """GET /api/asset 路径穿越防护 + 接口逻辑。"""

    def setUp(self):
        # 准备一个已导入的书（直接注入 services._BOOKS）。
        self.book_id = "sec-book"
        services._BOOKS[self.book_id] = {
            "title": "sec",
            "source_path": str(Path(".") / "x.txt"),
            "chapters": [("第1章", "正文")],
            "metrics": {"total_chars": 2},
        }

    def tearDown(self):
        services._BOOKS.clear()

    def test_asset_pass_whitelist_rejects_path_traversal(self):
        """pass 参数含 ../ 或非法名应被白名单拦截，返回 400 而非读取任意文件。"""
        for bad_pass in ("../../etc/passwd", "pass1_structure/../../x",
                         "..", "pass1_structure/../pass2_character", "foo"):
            with self.assertRaises(services.ServiceError) as cm:
                services.get_asset(self.book_id, 1, 0, bad_pass)
            self.assertEqual(cm.exception.code, 400, f"pass={bad_pass!r} 应返回 400")

    def test_asset_pass_whitelist_accepts_valid(self):
        # 合法 pass 但资产不存在 → 返回空 dict（不抛异常）。
        result = services.get_asset(self.book_id, 1, 0, "pass1_structure")
        self.assertEqual(result, {})

    def test_router_asset_endpoint_rejects_bad_pass(self):
        """通过 router.dispatch 全链路验证 path traversal 被拦截。

        dispatch 层不捕获 ServiceError（由 server 层 do_POST 捕获）；这里断言
        ServiceError 被抛出且 code=400，证明白名单校验生效、未泄露文件。
        """
        with self.assertRaises(services.ServiceError) as cm:
            router.dispatch(
                "GET", "/api/asset",
                {}, {"book_id": self.book_id, "chapter": "1", "batch": "0",
                     "pass": "../../secrets"})
        self.assertEqual(cm.exception.code, 400)

    def test_router_asset_endpoint_ok(self):
        payload, marker = router.dispatch(
            "GET", "/api/asset",
            {}, {"book_id": self.book_id, "chapter": "1", "batch": "0",
                 "pass": "pass1_structure"})
        self.assertIsNotNone(payload)
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"], {})


class TestServicesImport(unittest.TestCase):
    """导入链路（本地，不调 LLM）。"""

    def setUp(self):
        self.tmp_txt = Path(_TMP) / "sample_book.txt"
        self.tmp_txt.write_text(SAMPLE_TXT, encoding="utf-8")

    def tearDown(self):
        services._BOOKS.clear()
        services._runtime.clear()

    def test_import_book(self):
        result = services.import_book(str(self.tmp_txt))
        self.assertIn("book_id", result)
        self.assertEqual(result["total_chapters"], 2)
        self.assertEqual(len(result["chapters"]), 2)
        # 每章有 batch 元信息
        self.assertGreaterEqual(result["chapters"][0]["batch_count"], 1)

    def test_import_book_missing_file(self):
        with self.assertRaises(services.ServiceError) as cm:
            services.import_book(str(Path(_TMP) / "nope.txt"))
        self.assertEqual(cm.exception.code, 404)

    def test_import_book_non_txt(self):
        p = Path(_TMP) / "x.pdf"
        p.write_text("x")
        with self.assertRaises(services.ServiceError) as cm:
            services.import_book(str(p))
        self.assertEqual(cm.exception.code, 400)

    def test_book_id_stable(self):
        """同一文件重复导入得到同一 book_id（断点不丢的前提）。"""
        r1 = services.import_book(str(self.tmp_txt))
        r2 = services.import_book(str(self.tmp_txt))
        self.assertEqual(r1["book_id"], r2["book_id"])

    def test_get_status_after_import(self):
        book_id = services.import_book(str(self.tmp_txt))["book_id"]
        st = services.get_status(book_id)
        self.assertEqual(st["book_id"], book_id)
        self.assertEqual(st["cursor"], "")

    def test_start_analysis_requires_model(self):
        """未配置模型（无 key）时应报 400 而非崩溃。"""
        # 保存原始 any_model_configured 行为，这里模拟无模型。
        orig = engine_adapter.any_model_configured
        engine_adapter.any_model_configured = lambda: False
        try:
            book_id = services.import_book(str(self.tmp_txt))["book_id"]
            with self.assertRaises(services.ServiceError) as cm:
                services.start_analysis(book_id, "unknown")
            self.assertEqual(cm.exception.code, 400)
        finally:
            engine_adapter.any_model_configured = orig


class TestResumeSkipsSuccess(unittest.TestCase):
    """断点续传：resume 应跳过已 success 批，只重跑未完成批（核心验收点）。"""

    def setUp(self):
        self.tmp_txt = Path(_TMP) / "resume_book.txt"
        # 构造 2 章、每章 2 批的文本，用小 batch_size 强制多批。
        body1 = "第一章正文。" * 200
        body2 = "第二章正文。" * 200
        self.tmp_txt.write_text(f"第一章\n{body1}\n\n第二章\n{body2}", encoding="utf-8")
        # 记录 run_batch 被调用过的 (chapter, batch) 集合，用于验证跳过逻辑。
        self.called = []
        self._orig_run_batch = engine_adapter.run_batch

        def fake_run_batch(kind, ci, ctitle, btext, metrics, dry_run=False, model_id=None):
            self.called.append((ci, btext[:6]))
            # 返回模拟资产结果。
            return {"fake": True, "kind": kind}

        engine_adapter.run_batch = fake_run_batch
        # 让 any_model_configured 通过（避免 400）。
        self._orig_any = engine_adapter.any_model_configured
        engine_adapter.any_model_configured = lambda: True

    def tearDown(self):
        engine_adapter.run_batch = self._orig_run_batch
        engine_adapter.any_model_configured = self._orig_any
        services._BOOKS.clear()
        services._runtime.clear()
        # 清理状态文件（原 glob `gui_state_resume-*.json` 与真实命名
        # `gui_state_resume_book-*.json` 不匹配，改为成对目录全清）。
        _cleanup_state_files()

    def _wait_done(self, book_id, timeout=5.0):
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = services.get_status(book_id)
            if st["status"] in ("done", "error"):
                return st
            time.sleep(0.05)
        return services.get_status(book_id)

    def test_resume_skips_success_batches(self):
        """先跑完一次，标记所有批 success；再 resume，不应重复跑任何批。

        注：这是核心验收点。已发现 _run_analysis 无「跳过 success 批」逻辑，
        故本测试会 FAIL，用于路由给工程师修复。
        """
        book_id = services.import_book(str(self.tmp_txt))["book_id"]
        services.start_analysis(book_id, "unknown")
        st = self._wait_done(book_id)
        self.assertEqual(st["status"], "done", f"首次分析未完成: {st}")

        first_call_count = len(self.called)
        self.assertGreater(first_call_count, 0)

        # 重置调用记录，再 resume，并等待 resume 线程真正跑完。
        self.called.clear()
        services.resume(book_id)
        self._wait_done(book_id)
        # 额外小睡确保后台线程完成调度（避免竞态）。
        import time
        time.sleep(0.3)

        # 核心断言：已 success 的批不应再次调用 run_batch。
        self.assertEqual(
            len(self.called), 0,
            f"resume 后仍重复分析了 {len(self.called)} 个已 success 批 —— 断点续传未跳过已成功批！"
        )


class TestEndToEndLocalChain(unittest.TestCase):
    """纯本地链路端到端：导入→切章→切批→状态文件写入→断点恢复（不调 LLM）。"""

    def setUp(self):
        self.tmp_txt = Path(_TMP) / "e2e_book.txt"
        body = "这是端到端测试正文内容。" * 300
        self.tmp_txt.write_text(f"第一章\n{body}\n\n第二章\n{body}", encoding="utf-8")

    def tearDown(self):
        services._BOOKS.clear()
        services._runtime.clear()
        _cleanup_state_files()

    def test_full_local_chain(self):
        # 1. 导入
        r = services.import_book(str(self.tmp_txt))
        book_id = r["book_id"]
        self.assertEqual(r["total_chapters"], 2)

        # 2. 切批（默认 4000）
        ch = services.get_chapter(book_id, 1)
        self.assertGreaterEqual(ch["batch_count"], 1)

        # 3. 状态文件已写入
        state = state_store.load_state(book_id)
        self.assertEqual(state["title"], "e2e_book")
        self.assertTrue(state_store.state_path_for(book_id).is_file())

        # 4. 手动标记部分批 success 模拟中断（绕过 LLM），验证 cursor 与状态持久化。
        state = state_store.load_state(book_id)
        state_store.set_batch_state(state, 1, 0, "success", asset="assets/x/c1-b0-pass1.json")
        state_store.save_state(state)
        loaded = state_store.load_state(book_id)
        self.assertEqual(loaded["cursor"], "c1-b1")
        self.assertEqual(loaded["chapter_states"]["c1-b0"]["status"], "success")

        # 5. status 接口反映进度
        st = services.get_status(book_id)
        self.assertEqual(st["done"], 1)
        self.assertIn("c1-b0", st["chapter_states"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
