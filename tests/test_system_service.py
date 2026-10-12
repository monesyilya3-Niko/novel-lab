"""system_service 单元测试（M5 spec 要求）。"""
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

from gui import config, system_service  # noqa: E402
from gui.services import ServiceError  # noqa: E402

_TMP = None
_SAVED = {}


def setUpModule():
    global _TMP, _SAVED
    _TMP = tempfile.mkdtemp(prefix="system_qa_")
    _SAVED["ROOT_DIR"] = config.ROOT_DIR
    config.ROOT_DIR = Path(_TMP)
    for name in ("STATE_ROOT", "STATE_JSON_DIR", "ASSETS_ROOT", "NOVEL_DIR",
                 "CORPUS_DIR", "REPORTS_DIR",
                 # system_service 真的读 config.DB_PATH（健康页报库大小与路径），而
                 # DB_PATH 是 STATE_ROOT 的导入期快照：不一起重定向，这里量到的就是
                 # 用户真实数据目录里的 index.db。
                 "DB_PATH", "LOCK_PATH"):
        _SAVED[name] = getattr(config, name)
        setattr(config, name, config.ROOT_DIR / name.lower())
    config.ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
    config.NOVEL_DIR.mkdir(parents=True, exist_ok=True)
    config.CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    config.STATE_ROOT.mkdir(parents=True, exist_ok=True)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
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


def tearDownModule():
    for name, value in _SAVED.items():
        setattr(config, name, value)
    if _TMP:
        shutil.rmtree(_TMP, ignore_errors=True)


class TestSystemStatus(unittest.TestCase):
    def test_returns_expected_keys(self):
        r = system_service.system_status()
        for key in ("disk", "counts", "model", "paths", "python"):
            self.assertIn(key, r)

    def test_counts_assets(self):
        r = system_service.system_status()
        self.assertGreaterEqual(r["counts"]["assets"], 1)

    def test_dir_size_cache_reflects_disk(self):
        """目录体积缓存（2026-10-12）必须反映真实磁盘，且能感知新增文件。

        缓存键是路径字符串 + TTL。风险点：测试隔离会切换 config.*_ROOT，
        若缓存不随路径隔离而失效，测试就会量到上一次运行留下的旧值。
        这里通过 invalidate + 新增文件来验证缓存确实重新统计。
        """
        import os
        os.environ["NOVEL_LAB_SYS_TTL"] = "0"   # 关闭 TTL 快路径，每次重算
        try:
            system_service.invalidate_dir_size_cache()
            before = system_service.system_status()["disk"]["assets_bytes"]

            # 加一个 2KB 文件
            blob = config.ASSETS_ROOT / "cache-probe.json"
            blob.write_text("x" * 2048, encoding="utf-8")
            system_service.invalidate_dir_size_cache()
            after = system_service.system_status()["disk"]["assets_bytes"]

            self.assertGreater(after, before,
                               f"新增文件后体积未变：{before} -> {after}")
            self.assertGreaterEqual(after - before, 2048,
                                    "体积增量小于新增文件大小")
        finally:
            blob = config.ASSETS_ROOT / "cache-probe.json"
            blob.unlink(missing_ok=True)
            os.environ.pop("NOVEL_LAB_SYS_TTL", None)
            system_service.invalidate_dir_size_cache()

    def test_dir_size_cache_actually_hits(self):
        """性能守卫：TTL 内重复调用必须跳过目录遍历（否则每次请求全盘 stat）。

        注意：隔离目录里文件很少时，遍历本身就快（<3ms），冷热差异会被
        计时噪声淹没。故本用例**先造出足够多的文件**让遍历成本可见，
        再断言倍数——否则在干净的测试环境里这个守卫恒假绿。
        """
        import os
        import time
        os.environ.pop("NOVEL_LAB_SYS_TTL", None)   # 用默认 TTL
        probe_dir = config.ASSETS_ROOT / "_perf_probe"
        created = []
        try:
            probe_dir.mkdir(parents=True, exist_ok=True)
            for i in range(300):
                p = probe_dir / f"f{i}.json"
                p.write_text("x" * 64, encoding="utf-8")
                created.append(p)

            system_service.invalidate_dir_size_cache()
            t0 = time.perf_counter()
            system_service.system_status()
            cold = time.perf_counter() - t0
            t0 = time.perf_counter()
            for _ in range(10):
                system_service.system_status()
            warm = (time.perf_counter() - t0) / 10
            self.assertGreater(
                cold, warm * 5,
                f"目录体积缓存未生效：冷 {cold*1000:.1f}ms 热 {warm*1000:.2f}ms，"
                f"倍数仅 {cold/max(warm,1e-9):.1f}x（应 >5x）",
            )
        finally:
            for p in created:
                p.unlink(missing_ok=True)
            try:
                probe_dir.rmdir()
            except OSError:
                pass
            system_service.invalidate_dir_size_cache()


class TestComplianceScan(unittest.TestCase):
    def test_scan_all(self):
        r = system_service.compliance_scan()
        self.assertIn("results", r)
        self.assertIn("summary", r)
        self.assertGreaterEqual(r["summary"]["total"], 1)

    def test_scan_single_asset(self):
        r = system_service.compliance_scan(voice="voice:testbook-voice-card")
        self.assertEqual(len(r["results"]), 1)
        self.assertEqual(r["results"][0]["name"], "testbook-voice-card")

    def test_scan_nonexistent_404(self):
        with self.assertRaises(ServiceError) as ctx:
            system_service.compliance_scan(voice="voice:nonexistent")
        self.assertEqual(ctx.exception.code, 404)

    def test_scan_path_traversal_rejected(self):
        with self.assertRaises(ServiceError):
            system_service.compliance_scan(voice="voice:../../etc/passwd")


class TestModelInfo(unittest.TestCase):
    def test_returns_configured_flag(self):
        r = system_service.model_info()
        self.assertIn("configured", r)
        self.assertIn("models", r)
        self.assertIn("note", r)

    def test_model_id_uses_adapter_id_key(self):
        """engine_adapter.list_models 返回 id/model_name，不得误读 model_id 致 id 为空。"""
        r = system_service.model_info()
        if not r.get("models"):
            self.skipTest("本机未配置模型，跳过 id 键契约")
        for m in r["models"]:
            self.assertIn("id", m)
            self.assertIn("name", m)
            if m.get("name"):
                self.assertTrue(str(m.get("id", "")).strip(),
                                f"模型 {m.get('name')} 的 id 不得为空（键名错配）")


class TestSettings(unittest.TestCase):
    def test_get_settings(self):
        r = system_service.get_settings()
        for key in ("port", "batch_size", "thresholds", "writing", "paths", "env_overrides"):
            self.assertIn(key, r)

    def test_update_thresholds(self):
        r = system_service.update_settings({"thresholds": {"consistency_target": 85}})
        self.assertEqual(r["thresholds"]["consistency_target"], 85)

    def test_update_writing(self):
        r = system_service.update_settings({"writing": {"default_words": 3000}})
        self.assertEqual(r["writing"]["default_words"], 3000)

    def test_invalid_threshold_rejected(self):
        with self.assertRaises(ServiceError):
            system_service.update_settings({"thresholds": {"consistency_target": 150}})

    def test_invalid_words_rejected(self):
        with self.assertRaises(ServiceError):
            system_service.update_settings({"writing": {"default_words": 50}})

    def test_reset_settings(self):
        system_service.update_settings({"thresholds": {"consistency_target": 80}})
        r = system_service.reset_settings()
        self.assertEqual(r["thresholds"]["consistency_target"], 90)  # default


if __name__ == "__main__":
    unittest.main()
