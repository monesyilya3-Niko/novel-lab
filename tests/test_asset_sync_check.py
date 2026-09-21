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
        for d in (self.raw, self.assets, self.sampled):
            d.mkdir(parents=True)
        self._patches = [
            mock.patch.object(asc, "RAW_DIR", self.raw),
            mock.patch.object(asc, "ASSETS_DIR", self.assets),
            mock.patch.object(asc, "SAMPLED_DIR", self.sampled),
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

    def test_list_books(self):
        self._make_book("甲")
        self._make_book("乙")
        self.assertEqual(asc.list_books(), ["乙", "甲"] if "乙" < "甲" else ["甲", "乙"])


if __name__ == "__main__":
    sys.exit(unittest.main())
