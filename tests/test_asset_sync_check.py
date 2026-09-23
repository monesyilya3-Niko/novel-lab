#!/usr/bin/env python3
"""资产同步检查回归（2026-09-21）。

`asset_sync_check.check_one()` 负责发现「pass 产出与资产不同步」——这是拆书
两段式流程最容易静默出问题的地方（改了 pass 忘了组装，资产看着正常其实已过期）。

本测试只碰临时目录，不读不写任何真实资产。

用法：
  python -m unittest tests.test_asset_sync_check -v
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

import asset_sync_check as asc  # noqa: E402

KINDS = ["voice-card", "structure-obs", "commercial-obs", "craft-card"]
PASS_FILES = {
    "voice-card": "pass2_character.json",
    "structure-obs": "pass1_structure.json",
    "commercial-obs": "pass4_commercial.json",
    "craft-card": "pass5_craft.json",
}


class TestAssetSyncCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.raw = base / "raw"
        self.assets = base / "assets"
        self.sampled = base / "sampled"
        self.reports = base / "reports"
        for d in (self.raw, self.assets, self.sampled, self.reports):
            d.mkdir(parents=True)
        # 注意：新增「报告铁律二」检查后，REPORTS_DIR 也必须 patch，
        # 否则 check_one 会去读真实 reports/ 并引入与夹具无关的问题。
        self._patches = [
            mock.patch.object(asc, "RAW_DIR", self.raw),
            mock.patch.object(asc, "ASSETS_DIR", self.assets),
            mock.patch.object(asc, "SAMPLED_DIR", self.sampled),
            mock.patch.object(asc, "REPORTS_DIR", self.reports),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self.tmp.cleanup()

    # ---- helpers ----

    def _make_book(self, name="书", *, passes=True, assets=True, indices=None):
        if passes:
            d = self.raw / name
            d.mkdir(parents=True, exist_ok=True)
            for pf in PASS_FILES.values():
                (d / pf).write_text("{}", encoding="utf-8")
        if assets:
            for k in KINDS:
                (self.assets / f"{name}-{k}.json").write_text("{}", encoding="utf-8")
        if indices is not None:
            (self.sampled / name).mkdir(parents=True, exist_ok=True)
            (self.sampled / name / "manifest.json").write_text(
                json.dumps({"selected_indices": indices}), encoding="utf-8")
            (self.assets / f"{name}-voice-card.json").write_text(
                json.dumps({"meta": {"sample_chapters": indices}}), encoding="utf-8")

    def _write_fingerprint(self, name, kind, pass_file, fp=None):
        """给某资产写入来源指纹；fp 省略则按当前 pass 内容算（= 同步状态）。"""
        import hashlib
        if fp is None:
            fp = hashlib.sha256(
                (self.raw / name / pass_file).read_bytes()).hexdigest()[:16]
        p = self.assets / f"{name}-{kind}.json"
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        d.setdefault("meta", {})["source_fingerprint"] = {pass_file: fp}
        p.write_text(json.dumps(d), encoding="utf-8")

    # ---- cases ----

    def test_fingerprint_match_is_clean(self):
        """指纹与 pass 内容一致 → 不报过期。"""
        self._make_book(indices=[1])
        self._write_fingerprint("书", "structure-obs", "pass1_structure.json")
        stale = [x for x in asc.check_one("书") if "过期" in x]
        self.assertEqual(stale, [], stale)

    def test_fingerprint_mismatch_detected(self):
        """指纹与 pass 内容不一致 → 报「内容已变」。"""
        self._make_book(indices=[1])
        self._write_fingerprint("书", "structure-obs", "pass1_structure.json",
                                fp="deadbeefdeadbeef")
        issues = asc.check_one("书")
        self.assertTrue(any("内容已变" in x for x in issues), issues)

    def test_mtime_fallback_when_no_fingerprint(self):
        """老资产无指纹 → 退回 mtime 判据，并明确标注是启发式。"""
        import os
        self._make_book(indices=[1])
        target = self.raw / "书" / "pass1_structure.json"
        st = target.stat()
        os.utime(target, (st.st_atime + 100, st.st_mtime + 100))
        issues = asc.check_one("书")
        self.assertTrue(any("mtime 启发式" in x for x in issues), issues)

    def test_missing_book(self):
        """未拆的书应报「不存在」。"""
        issues = asc.check_one("不存在")
        self.assertEqual(len(issues), 1)
        self.assertIn("不存在", issues[0])

    def test_missing_assets(self):
        """pass 已产出但资产缺失 → 每类各报一条。"""
        self._make_book(assets=False)
        issues = asc.check_one("书")
        self.assertEqual(len(issues), len(KINDS))
        self.assertTrue(all("缺资产" in x for x in issues))

    def test_fully_synced(self):
        """pass 与资产齐备且采样一致 → 无问题。"""
        self._make_book(indices=[1, 2, 3])
        self.assertEqual(asc.check_one("书"), [])

    def test_sample_drift_detected(self):
        """manifest 采样与资产记录不一致 → 报「采样已变」。"""
        self._make_book(indices=[1, 2, 3])
        (self.sampled / "书" / "manifest.json").write_text(
            json.dumps({"selected_indices": [1, 2, 5, 9]}), encoding="utf-8")
        issues = asc.check_one("书")
        self.assertTrue(any("采样已变" in x for x in issues), issues)

    def test_stale_pass_detected(self):
        """pass 比资产新 → 报「可能过期」。"""
        import os
        self._make_book(indices=[1])
        target = self.raw / "书" / "pass1_structure.json"
        st = target.stat()
        os.utime(target, (st.st_atime + 100, st.st_mtime + 100))
        issues = asc.check_one("书")
        self.assertTrue(any("可能过期" in x for x in issues), issues)

    # ---- 非流水线产出（会话直接产出）的误报修正（2026-09-23 新增）----

    def test_no_pass_outputs_skips_sampling_comparison(self):
        """无 pass 产出的书不得报采样漂移——manifest 与资产是两次独立决策，不可比。

        背景：`corpus/raw/Lord_of_the_Mysteries/` 是空目录（资产由会话直接产出，
        `novel.py 组装` 会报「缺少 pass1_structure.json」）。旧实现仍拿后来的采样器
        manifest 去比会话当时选的章，报出一条无法成立的漂移（27 章 vs 19 章）。
        """
        self._make_book("书", passes=False)
        (self.raw / "书").mkdir(parents=True, exist_ok=True)  # 空 raw 目录
        (self.assets / "书-voice-card.json").write_text(
            json.dumps({"meta": {"genre": "campus-redemption",
                                 "sample_chapters": [1, 2, 5]}}),
            encoding="utf-8")
        (self.sampled / "书").mkdir(parents=True, exist_ok=True)
        (self.sampled / "书" / "manifest.json").write_text(
            json.dumps({"selected_indices": [1, 2, 3, 4, 5, 6, 7]}), encoding="utf-8")

        issues = asc.check_one("书")
        self.assertEqual(issues, [], f"非流水线产出不应报采样漂移: {issues}")

    def test_pipeline_book_still_reports_sampling_drift(self):
        """反向守护：有 pass 产出的书**仍然**要报采样漂移（别把守卫改成永远通过）。"""
        self._make_book(indices=[1, 2, 5, 9])  # 默认 passes=True，资产记 4 章
        (self.sampled / "书" / "manifest.json").write_text(
            json.dumps({"selected_indices": [1, 2, 3, 4, 5, 6, 7]}), encoding="utf-8")
        issues = asc.check_one("书")
        self.assertTrue(any("采样已变" in x for x in issues),
                        f"流水线产出应仍报采样漂移: {issues}")

    def test_provenance_note_for_session_produced_book(self):
        """非流水线产出的书必须给出**显式说明**（不静默跳过）。"""
        self._make_book("书", passes=False)
        (self.raw / "书").mkdir(parents=True, exist_ok=True)
        note = asc.provenance_note("书")
        self.assertIn("非流水线产出", note)
        self.assertIn("书", note)
        self.assertIn("跳过", note)

    def test_provenance_note_empty_for_pipeline_book(self):
        self._make_book("书")  # 默认 passes=True
        self.assertEqual(asc.provenance_note("书"), "")

    def test_provenance_note_empty_for_missing_raw_dir(self):
        self.assertEqual(asc.provenance_note("不存在"), "")

    def test_has_pipeline_outputs_detects_any_pass_file(self):
        self._make_book("书")
        self.assertTrue(asc.has_pipeline_outputs(self.raw / "书"))
        (self.raw / "空书").mkdir(parents=True, exist_ok=True)
        self.assertFalse(asc.has_pipeline_outputs(self.raw / "空书"))

    def test_list_books(self):
        self._make_book("甲")
        self._make_book("乙")
        self.assertEqual(asc.list_books(), ["乙", "甲"] if "乙" < "甲" else ["甲", "乙"])

    # ---- 报告铁律二（2026-09-23 新增）----

    def _write_reports(self, name, book_chars, craft_chars):
        (self.reports / f"{name}-拆书报告.md").write_text("甲" * book_chars, encoding="utf-8")
        (self.reports / f"{name}-笔法分析.md").write_text("乙" * craft_chars, encoding="utf-8")

    def test_report_below_threshold_detected(self):
        """合计 < 10000 字符 → 报「报告铁律二不达标」，并给出缺口字数。"""
        self._make_book(indices=[1])
        self._write_reports("书", 2907, 3495)  # 合计 6402
        issues = asc.check_one("书")
        hits = [x for x in issues if "报告铁律二不达标" in x]
        self.assertEqual(len(hits), 1, issues)
        self.assertIn("6402", hits[0])
        self.assertIn("缺 3598 字", hits[0])

    def test_report_at_threshold_is_clean(self):
        """合计恰好 10000 字符 → 达标（边界：≥ 门槛即通过）。"""
        self._make_book(indices=[1])
        self._write_reports("书", 6000, 4000)  # 合计 10000
        issues = asc.check_one("书")
        self.assertFalse([x for x in issues if "报告铁律二" in x], issues)

    def test_no_reports_is_not_an_issue(self):
        """完全没产出报告的书 → 不报（是否该产出属业务选择，不是同步缺陷）。"""
        self._make_book(indices=[1])
        issues = asc.check_one("书")
        self.assertFalse([x for x in issues if "报告铁律二" in x], issues)

    def test_report_check_only_needs_one_of_the_pair(self):
        """只有一份报告时也要检查（缺的那份按 0 字计）。"""
        self._make_book(indices=[1])
        (self.reports / "书-拆书报告.md").write_text("甲" * 3000, encoding="utf-8")
        issues = asc.check_one("书")
        hits = [x for x in issues if "报告铁律二不达标" in x]
        self.assertEqual(len(hits), 1, issues)
        self.assertIn("3000", hits[0])

    def test_check_one_does_not_touch_real_reports_dir(self):
        """夹具必须完全隔离 REPORTS_DIR，否则会读到真实 reports/ 引入无关问题。"""
        self._make_book(indices=[1])
        issues = asc.check_one("书")
        self.assertEqual(issues, [], f"夹具隔离失效，出现与夹具无关的问题: {issues}")


if __name__ == "__main__":
    sys.exit(unittest.main())
