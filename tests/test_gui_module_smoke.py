"""三个此前零测试覆盖的 gui 模块冒烟测试（2026-09-23 总工补）。

背景：`gui/launch.py`、`gui/platform_service.py`、`gui/style_service.py` 在本次排查前
**没有任何测试文件引用**（其余 gui 模块有 1–15 个）。其中 `launch.py` 是 GUI 的唯一
入口，零覆盖偏薄弱。

本文件只做**冒烟级**覆盖——守住"能导入、能调用、错误路径有正确契约"，不追求业务分支
全覆盖。纯标准库（铁律三）。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import _isolation  # noqa: E402
from gui import config, db, launch, platform_service, style_service  # noqa: E402
from gui.services import ServiceError  # noqa: E402


class TestLaunchSmoke(unittest.TestCase):
    """GUI 入口自检（不起服务、不弹浏览器）。"""

    def test_run_check_returns_zero(self):
        """run_check() 必须能导入全部后端模块并返回 0（交付前冒烟入口）。"""
        self.assertEqual(launch.run_check(), 0)

    def test_main_check_flag_returns_zero(self):
        self.assertEqual(launch.main(["--check"]), 0)

    def test_check_reports_missing_dist_dir(self):
        """前端产物缺失时必须给出警告而非崩溃（全新克隆的常见状态）。"""
        import contextlib
        import io

        orig = config.DIST_DIR
        config.DIST_DIR = Path(tempfile.mkdtemp()) / "no_such_dist"
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = launch.run_check()
        finally:
            config.DIST_DIR = orig
        self.assertEqual(rc, 0, "缺少 dist 不应导致自检失败（只是警告）")
        self.assertIn("警告", buf.getvalue())


class TestPlatformServiceSmoke(unittest.TestCase):
    """平台合规服务：清单可用 + 未知平台给出 404 语义。"""

    def test_list_platforms_non_empty_and_shaped(self):
        platforms = platform_service.list_platforms()
        self.assertIsInstance(platforms, list)
        self.assertGreater(len(platforms), 0, "平台清单不应为空")
        for p in platforms:
            for key in ("id", "name", "chapter_min_chars", "chapter_max_chars",
                        "supports_serialization", "genre_count"):
                self.assertIn(key, p, f"平台条目缺字段 {key}: {p}")

    def test_get_platform_unknown_raises_404(self):
        """路径参数取资源：未知平台按 router 约定返回 404（2026-09-23 由 400 修正）。"""
        with self.assertRaises(ServiceError) as ctx:
            platform_service.get_platform("__no_such_platform__")
        self.assertEqual(getattr(ctx.exception, "code", None), 404,
                         "未知平台（路径参数）应给出 404 资源不存在")

    def test_body_param_platform_apis_use_400(self):
        """请求体参数的平台接口：platform_id 非法属参数校验 → 400（与路径参数区分）。"""
        for call in (
            lambda: platform_service.check_chapter_compliance("__no_such__", "正文"),
            lambda: platform_service.format_chapter("__no_such__", 1, "标题", "正文"),
            lambda: platform_service.export_book_for_platform("__no_such__", "novel/x"),
        ):
            with self.subTest(call=call):
                with self.assertRaises(ServiceError) as ctx:
                    call()
                self.assertEqual(getattr(ctx.exception, "code", None), 400)


class TestStyleServiceSmoke(unittest.TestCase):
    """文风档案服务：保存/读取/列表/删除全链路 + 路径穿越拒绝（隔离临时目录）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="style_smoke_")
        self.addCleanup(self._tmp.cleanup)
        self._iso = _isolation.isolate_paths(Path(self._tmp.name))
        self._iso.__enter__()
        self.addCleanup(lambda: self._iso.__exit__(None, None, None))
        self.addCleanup(db.close)

    def test_styles_dir_follows_config_assets_root(self):
        """回归：`_styles_dir()` 必须跟随 config.ASSETS_ROOT 的当前值（导入期快照同族缺陷）。"""
        self.assertTrue(
            str(style_service._styles_dir()).startswith(str(config.ASSETS_ROOT)),
            f"styles 目录未跟随 config.ASSETS_ROOT: {style_service._styles_dir()}",
        )
        self.assertFalse(
            str(style_service._styles_dir()).startswith(str(_isolation.ROOT_DIR)),
            "隔离态下 styles 目录仍落在项目根内",
        )

    def test_save_get_list_delete_roundtrip(self):
        style_service.save_style("测试风格", {"metrics": {"avg_sentence_len": 12.5}})
        self.assertIn("测试风格", [s["name"] for s in style_service.list_styles()])
        detail = style_service.get_style("测试风格")
        self.assertEqual(detail["metrics"]["avg_sentence_len"], 12.5)

        style_service.delete_style("测试风格")
        self.assertNotIn("测试风格", [s["name"] for s in style_service.list_styles()])

    def test_duplicate_save_raises_409(self):
        style_service.save_style("dup", {})
        with self.assertRaises(ServiceError) as ctx:
            style_service.save_style("dup", {})
        self.assertEqual(getattr(ctx.exception, "code", None), 409)

    def test_get_missing_style_raises_404(self):
        with self.assertRaises(ServiceError) as ctx:
            style_service.get_style("__no_such_style__")
        self.assertEqual(getattr(ctx.exception, "code", None), 404)

    def test_path_traversal_name_rejected(self):
        """风格名不得含路径分隔符 / `..`（否则可越权读写任意文件）。"""
        for bad in ("../evil", "..\\evil", "a/b", "a\\b", "..", "x\x00y"):
            with self.subTest(name=bad):
                with self.assertRaises(ServiceError):
                    style_service.save_style(bad, {})

    def test_empty_name_rejected(self):
        for bad in ("", "   "):
            with self.subTest(name=bad):
                with self.assertRaises(ServiceError):
                    style_service.save_style(bad, {})


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
