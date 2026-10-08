"""平台投稿格式化（``gui/platform_service.py``）回归测试。

2026-10-08 实测到的缺陷：稿子里的章节首行本来就写着"第1章 初见"，
`chapter_format` 再套一次模板就导出成"第1章 第1章 初见"。用户是拿这个
直接投稿的，重复章号等于交付物带脏字。这里钉住去重规则与它的边界：
模板不补 {num} 的平台（知乎盐言）绝不能剥前缀。
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import platform_service  # noqa: E402


def _title(platform: str, num: int, title: str) -> str:
    return platform_service.format_chapter(
        platform, num, title, "正文内容")["formatted_title"]


class TestChapterTitleDedupe(unittest.TestCase):
    def test_existing_prefix_not_doubled(self):
        self.assertEqual(_title("qidian", 1, "第1章 初见"), "第1章 初见")
        self.assertEqual(_title("fanqie", 12, "第 12 章 夜袭"), "第12章 夜袭")

    def test_chinese_numeral_prefix_recognised(self):
        self.assertEqual(_title("qidian", 1, "第一章、起步"), "第1章 起步")

    def test_latin_chapter_prefix_recognised(self):
        self.assertEqual(_title("qidian", 1, "Chapter 3: Home"), "第1章 Home")

    def test_bare_title_still_gets_number(self):
        # 没写章号的标题必须补上——去重不能变成"少一章"
        self.assertEqual(_title("qidian", 7, "初见"), "第7章 初见")

    def test_title_that_is_only_a_number_not_duplicated(self):
        self.assertEqual(_title("qidian", 1, "第1章"), "第1章")

    def test_empty_title_has_no_trailing_space(self):
        # 模板 "第{num}章 {title}" 遇空标题会留下"第1章 "，投稿时是个显眼的脏尾巴
        got = _title("qidian", 1, "")
        self.assertEqual(got, "第1章")
        self.assertFalse(got.endswith(" "))

    def test_platform_without_num_keeps_title_untouched(self):
        # 知乎盐言模板是纯 "{title}"：剥前缀会把章号整个丢掉
        self.assertEqual(_title("zhihu", 1, "第1章 初见"), "第1章 初见")
        self.assertEqual(_title("zhihu", 1, "第三十二章 归途"), "第三十二章 归途")


class TestChapterNumberGuard(unittest.TestCase):
    """章号会拼进投稿标题，脏值必须在服务层就挡住，而不是贴到编辑眼前。"""

    def test_zero_and_negative_rejected(self):
        from gui.services import ServiceError
        for num in (0, -3):
            with self.assertRaises(ServiceError) as cm:
                platform_service.format_chapter("qidian", num, "标题", "正文")
            self.assertEqual(cm.exception.code, 400, num)
            self.assertIn("chapter_num", cm.exception.message)

    def test_bool_rejected(self):
        # True 是 int 的子类，直接格式化会产出"第1章"却没有任何调用方是想写 1 章
        from gui.services import ServiceError
        with self.assertRaises(ServiceError) as cm:
            platform_service.format_chapter("qidian", True, "标题", "正文")
        self.assertEqual(cm.exception.code, 400)


class TestExportChapterTitles(unittest.TestCase):
    """整本导出走的是同一套标题规则，章号来自文件排序而不是原标题。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="plat_export_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_export_titles_are_clean(self):
        (self.tmp / "第1章.txt").write_text("第1章 初见\n\n她推开门。\n", encoding="utf-8")
        (self.tmp / "第2章.txt").write_text("第2章 离别\n\n他没有回头。\n", encoding="utf-8")
        data = platform_service.export_book_for_platform("qidian", str(self.tmp))
        self.assertEqual(
            [c["title"] for c in data["chapters"]], ["第1章 初见", "第2章 离别"])

    def test_export_numbers_follow_file_order(self):
        # 文件名与首行章号不一致时以导出顺序为准，避免整本出现两个"第3章"
        (self.tmp / "01.txt").write_text("第一章 开端\n\n正文。\n", encoding="utf-8")
        (self.tmp / "02.txt").write_text("第一章 开端\n\n正文。\n", encoding="utf-8")
        data = platform_service.export_book_for_platform("qidian", str(self.tmp))
        self.assertEqual(
            [c["title"] for c in data["chapters"]], ["第1章 开端", "第2章 开端"])


if __name__ == "__main__":
    unittest.main()
