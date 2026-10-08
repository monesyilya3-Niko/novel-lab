"""正文读取准入 ``gui/text_access.py`` 的回归测试。

两件事都要钉住，缺一条就会在半年后被"顺手放宽一点"磨掉：

1. 稿子放在项目外（``%TEMP%``、D 盘）能读到——这是用户反馈
   「有些路径放不进去」的直接修复；
2. 放开的是**目录边界**，不是**内容边界**：非正文后缀、符号链接、
   超体积/超数量一律拒。旧代码用路径前缀挡任意文件读取，现在换成
   后缀白名单，判据变了，挡的东西不能变。
符号链接相关的用例需要建链接的权限，只在 POSIX 跑（Windows 自动 skip），
由 CI 的 ubuntu 矩阵实际覆盖。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gui import text_access  # noqa: E402
from gui.services import ServiceError  # noqa: E402


class _TmpCase(unittest.TestCase):
    """每个用例一棵独立临时树，teardown 用 remove_tree 兜住 Windows 句柄。"""

    prefix = "text_access_"

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix=self.prefix))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, name: str, text: str = "第一章正文，够长就能读。") -> Path:
        fp = self.tmp / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(text, encoding="utf-8")
        return fp


class TestTextField(_TmpCase):
    def test_file_outside_project_roots_is_readable(self):
        fp = self.write("我的书.txt")
        # 临时目录在仓库与用户数据目录之外，旧规则会在这里直接 400/403
        self.assertEqual(text_access.text_file(fp, field="chapter_path"), fp.resolve())

    def test_relative_path_resolves_against_cwd(self):
        fp = self.write("相对.txt")
        cwd = Path(os.getcwd())
        try:
            os.chdir(self.tmp)
            self.assertEqual(text_access.text_file("相对.txt", field="book_path"), fp.resolve())
        finally:
            os.chdir(cwd)

    def test_non_text_suffix_rejected(self):
        for name in ("index.db", "settings.json", "id_rsa", "note.docx"):
            fp = self.write(name)
            with self.assertRaises(ServiceError) as cm:
                text_access.text_file(fp, field="book_path")
            self.assertEqual(cm.exception.code, 400, name)
            self.assertIn("book_path", cm.exception.message)

    def test_missing_file_is_404(self):
        with self.assertRaises(ServiceError) as cm:
            text_access.text_file(self.tmp / "不存在.txt", field="chapter_path")
        self.assertEqual(cm.exception.code, 404)

    def test_directory_passed_as_file_is_404(self):
        # 后缀合法但根本不是文件：必须报"不存在"，不能假装读到了空正文
        (self.tmp / "其实是个目录.md").mkdir()
        with self.assertRaises(ServiceError) as cm:
            text_access.text_file(self.tmp / "其实是个目录.md", field="chapter_path")
        self.assertEqual(cm.exception.code, 404)

    def test_oversize_rejected(self):
        fp = self.write("超长.txt", "字" * 500)
        orig = text_access.MAX_FILE_BYTES
        text_access.MAX_FILE_BYTES = 100
        try:
            with self.assertRaises(ServiceError) as cm:
                text_access.text_file(fp, field="chapter_path")
        finally:
            text_access.MAX_FILE_BYTES = orig
        self.assertEqual(cm.exception.code, 400)
        self.assertIn("过大", cm.exception.message)

    @unittest.skipIf(os.name == "nt", "Windows 建符号链接需要额外权限")
    def test_symlink_to_non_text_target_rejected(self):
        secret = self.write("秘密.db", "不该被读到")
        link = self.tmp / "章节.txt"
        link.symlink_to(secret)
        # 后缀是 .txt，但链接本身必须先拒，否则后缀白名单被软链绕过
        with self.assertRaises(ServiceError) as cm:
            text_access.text_file(link, field="chapter_path")
        self.assertEqual(cm.exception.code, 400)


class TestTextFilesInDir(_TmpCase):
    def test_dir_outside_project_roots_lists_text_files(self):
        self.write("01.txt")
        self.write("02.md")
        self.write("index.db")
        (self.tmp / "子目录").mkdir()
        (self.tmp / "子目录" / "03.txt").write_text("递归不该读到", encoding="utf-8")
        got = text_access.text_files_in(self.tmp, field="book_dir")
        self.assertEqual([p.name for p in got], ["01.txt", "02.md"])

    def test_missing_dir_is_404(self):
        with self.assertRaises(ServiceError) as cm:
            text_access.text_files_in(self.tmp / "没有这层", field="book_dir")
        self.assertEqual(cm.exception.code, 404)

    def test_dir_without_text_is_400(self):
        self.write("secret.json", "{}")
        with self.assertRaises(ServiceError) as cm:
            text_access.text_files_in(self.tmp, field="book_dir")
        self.assertEqual(cm.exception.code, 400)
        self.assertIn("没有正文文件", cm.exception.message)

    def test_file_count_cap(self):
        for i in range(5):
            self.write(f"{i}.txt")
        orig = text_access.MAX_FILES
        text_access.MAX_FILES = 3
        try:
            with self.assertRaises(ServiceError) as cm:
                text_access.text_files_in(self.tmp, field="book_dir")
        finally:
            text_access.MAX_FILES = orig
        self.assertEqual(cm.exception.code, 400)

    def test_total_bytes_cap(self):
        self.write("a.txt", "字" * 400)
        self.write("b.txt", "字" * 400)
        orig = text_access.MAX_TOTAL_BYTES
        text_access.MAX_TOTAL_BYTES = 100
        try:
            with self.assertRaises(ServiceError) as cm:
                text_access.text_files_in(self.tmp, field="book_dir")
        finally:
            text_access.MAX_TOTAL_BYTES = orig
        self.assertIn("总量过大", cm.exception.message)

    def test_single_file_in_dir_over_size_cap(self):
        self.write("a.txt", "字" * 500)
        orig = text_access.MAX_FILE_BYTES
        text_access.MAX_FILE_BYTES = 100
        try:
            with self.assertRaises(ServiceError) as cm:
                text_access.text_files_in(self.tmp, field="book_dir")
        finally:
            text_access.MAX_FILE_BYTES = orig
        self.assertIn("a.txt", cm.exception.message)

    @unittest.skipIf(os.name == "nt", "Windows 建符号链接需要额外权限")
    def test_symlinked_chapter_excluded(self):
        self.write("01.txt")
        outside = self.write("真实身份.txt", "正文")
        (self.tmp / "02.txt").symlink_to(outside)
        got = text_access.text_files_in(self.tmp, field="book_dir")
        self.assertEqual([p.name for p in got], ["01.txt", "真实身份.txt"])

    @unittest.skipIf(os.name == "nt", "Windows 建符号链接需要额外权限")
    def test_symlinked_dir_rejected(self):
        real = self.tmp / "真实目录"
        real.mkdir()
        (real / "01.txt").write_text("正文", encoding="utf-8")
        link = self.tmp / "链接目录"
        link.symlink_to(real, target_is_directory=True)
        with self.assertRaises(ServiceError) as cm:
            text_access.text_files_in(link, field="book_dir")
        self.assertEqual(cm.exception.code, 400)


class TestCallersRouteThroughGuard(_TmpCase):
    """服务层必须真的走这道闸，而不是只在新模块里躺着。"""

    def test_platform_export_reads_external_dir(self):
        from gui import platform_service
        self.write("第1章.txt", "第一章正文内容。")
        self.write("第2章.txt", "第二章正文内容。")
        self.write("metadata.json", "{}")
        data = platform_service.export_book_for_platform("qidian", str(self.tmp))
        self.assertEqual(data["total_chapters"], 2)

    def test_platform_export_still_refuses_secret_dir(self):
        from gui import platform_service
        self.write("passwd", "root:x:0:0")
        self.write("index.db", "binary")
        with self.assertRaises(ServiceError) as cm:
            platform_service.export_book_for_platform("qidian", str(self.tmp))
        self.assertEqual(cm.exception.code, 400)

    def test_writing_score_accepts_external_chapter_file(self):
        from gui import writing_service
        fp = self.write("第3章.txt", "第三章正文，字数不多但够读出来。")
        # 资产不存在（404）说明已经越过目录闸门；闸门若仍在会是 400 且提到 chapter_path
        with self.assertRaises(ServiceError) as cm:
            writing_service.score(voice="voice:__no_such_asset__", chapter_path=str(fp))
        self.assertNotIn("chapter_path", cm.exception.message)
        self.assertEqual(cm.exception.code, 404)

    def test_writing_score_refuses_non_text_chapter(self):
        from gui import writing_service
        fp = self.write("index.db", "binary-ish")
        with self.assertRaises(ServiceError) as cm:
            writing_service.score(voice="voice:__no_such_asset__", chapter_path=str(fp))
        self.assertEqual(cm.exception.code, 400)
        self.assertIn("chapter_path", cm.exception.message)

if __name__ == "__main__":
    unittest.main()
