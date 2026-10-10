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


class TestDiagnoseChapter(unittest.TestCase):
    """网文签约过稿深度诊断测试。"""

    def test_diagnose_normal_chapter_passes(self):
        text = "林轩拔剑，冷笑一声：“就凭你们这群鼠辈也配？”\n" + "剑光破空，群雄战栗。" * 200
        res = platform_service.diagnose_chapter("fanqie", text, "第1章 拔剑", chapter_num=1)
        self.assertIn(res["grade"], ("A", "B"))
        self.assertGreaterEqual(res["score"], 70)
        self.assertIn("signing_prob", res)


    def test_diagnose_short_chapter_penalized(self):
        text = "林轩拔剑冷笑。"
        res = platform_service.diagnose_chapter("fanqie", text, "第1章 拔剑", chapter_num=1)
        self.assertEqual(res["grade"], "C")
        self.assertTrue(any("字数不足" in r for r in res["veto_risks"]))

    def test_diagnose_opening_info_dump_penalized(self):
        text = "在这个世界，很久很久以前，力量体系分为七大境界……\n" + "他拔剑出招。" * 300
        res = platform_service.diagnose_chapter("qidian", text, "第1章", chapter_num=1)
        self.assertTrue(any("头号劝退点" in r for r in res["veto_risks"]))

    def test_diagnose_qidian_virgin_mary_penalized(self):
        text = "林轩叹了口气：“得饶人处且饶人，我原谅了他，饶他不死。”\n" + "他收剑入鞘，转身离去。" * 150
        res = platform_service.diagnose_chapter("qidian", text, "第1章 饶恕", chapter_num=1)
        self.assertTrue(any("主角出现无原则圣母行为" in r for r in res["veto_risks"]))

    def test_diagnose_jinjiang_greasy_and_emotion(self):
        text = "冷夜寒一把抓住她的手腕：“小妖精，女人你成功引起了我的注意。”\n" + "他霸道地将她推在墙上。" * 200
        res = platform_service.diagnose_chapter("jinjiang", text, "第1章 偶遇", chapter_num=1)
        self.assertTrue(any("油腻古早霸总" in r for r in res["veto_risks"]))

    def test_diagnose_qimao_insult_without_counter(self):
        text = "王琴破口大骂：“你这个上门女婿，窝囊废，穷光蛋，滚出我家！”\n" + "陈阳默默低头扫地，受尽欺凌。" * 100
        res = platform_service.diagnose_chapter("qimao", text, "第1章 受辱", chapter_num=1)
        self.assertTrue(any("七猫爽点脱节预警" in r for r in res["veto_risks"]))

    def test_list_platforms_includes_creative_params(self):
        platforms = platform_service.list_platforms()
        self.assertEqual(len(platforms), 5)
        for p in platforms:
            self.assertIn("climax_interval", p)
            self.assertIn("rhythm_type", p)

    def test_diagnose_router_dispatch(self):
        from gui import router
        resp, _ = router.dispatch(
            "POST",
            "/api/platform/diagnose",
            {"platform_id": "fanqie", "chapter_text": "林轩拔剑，冷笑一声。" * 150, "chapter_num": 1},
            {}
        )
        self.assertEqual(resp["code"], 0)
        self.assertIn("grade", resp["data"])
        self.assertIn("score", resp["data"])


if __name__ == "__main__":
    unittest.main()
