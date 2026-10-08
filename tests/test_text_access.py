"""正文读取准入 ``gui/text_access.py`` 的回归测试。

四件事都要钉住，缺一条就会在半年后被"顺手放宽一点"磨掉：

1. 稿子放在项目外（``%TEMP%``、D 盘）能读到——这是用户反馈
   「有些路径放不进去」的直接修复；
2. 放开的是**目录边界**，不是**内容边界**：非正文后缀、符号链接、FIFO、
   超体积一律拒。旧代码用路径前缀挡任意文件读取，现在换成后缀白名单 +
   同一个 fd 上的常规文件/体积校验，判据变了，挡住的还是同一件事；
3. GBK 稿子必须读得出来。国内用户的 `.txt` 相当一部分不是 UTF-8，
   只按 UTF-8 解要么报错、要么（导出路径上）静默少一章；
4. 符号链接与 FIFO 用例需要建链接/管道的权限，只在 POSIX 跑（Windows 自动 skip），
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
    """每个用例一棵独立临时树，teardown 用 rmtree(ignore_errors) 兜住 Windows。"""

    prefix = "text_access_"

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix=self.prefix))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, name: str, text: str = "第一章正文，够长就能读。") -> Path:
        fp = self.tmp / name
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(text, encoding="utf-8")
        return fp

    def write_bytes(self, name: str, data: bytes) -> Path:
        fp = self.tmp / name
        fp.write_bytes(data)
        return fp


class TestReadTextFile(_TmpCase):
    def test_reads_file_outside_project_roots(self):
        fp = self.write("我的书.txt", "推开的是别人的门。")
        # 临时目录在仓库与用户数据目录之外，旧规则会在这里直接 400/403
        self.assertEqual(text_access.read_text(fp, field="chapter_path"), "推开的是别人的门。")

    def test_markdown_accepted(self):
        fp = self.write("大纲.md", "# 第一章")
        self.assertEqual(text_access.read_text(fp, field="chapter_path"), "# 第一章")

    def test_relative_path_resolves_against_cwd(self):
        self.write("相对.txt", "以工作目录为准")
        cwd = Path(os.getcwd())
        try:
            os.chdir(self.tmp)
            got = text_access.read_text("相对.txt", field="book_path")
        finally:
            os.chdir(cwd)
        self.assertEqual(got, "以工作目录为准")

    def test_gbk_fallback(self):
        # GBK 稿子是"读不进来"最常见的真相，解出来的字符还不能错
        fp = self.write_bytes("gbk章节.txt", "第三章　他笑了".encode("gbk"))
        self.assertEqual(text_access.read_text(fp, field="chapter_path"), "第三章　他笑了")

    def test_undecodable_rejected_with_clear_message(self):
        fp = self.write_bytes("坏编码.txt", b"\xff\xfe\x00\x01\x02")
        with self.assertRaises(ServiceError) as cm:
            text_access.read_text(fp, field="chapter_path")
        self.assertEqual(cm.exception.code, 400)
        self.assertIn("编码", cm.exception.message)

    def test_non_text_suffix_rejected(self):
        for name in ("index.db", "settings.json", "id_rsa", "note.docx"):
            fp = self.write(name)
            with self.assertRaises(ServiceError) as cm:
                text_access.read_text(fp, field="book_path")
            self.assertEqual(cm.exception.code, 400, name)
            self.assertIn("book_path", cm.exception.message)

    def test_missing_file_is_404(self):
        with self.assertRaises(ServiceError) as cm:
            text_access.read_text(self.tmp / "不存在.txt", field="chapter_path")
        self.assertEqual(cm.exception.code, 404)

    def test_directory_passed_as_file_is_refused(self):
        # 后缀合法但根本不是文件：不能假装读到了空正文
        (self.tmp / "其实是个目录.md").mkdir()
        with self.assertRaises(ServiceError) as cm:
            text_access.read_text(self.tmp / "其实是个目录.md", field="chapter_path")
        self.assertEqual(cm.exception.code, 400)

    def test_oversize_rejected(self):
        fp = self.write("超长.txt", "字" * 500)
        orig = text_access.MAX_FILE_BYTES
        text_access.MAX_FILE_BYTES = 100
        try:
            with self.assertRaises(ServiceError) as cm:
                text_access.read_text(fp, field="chapter_path")
        finally:
            text_access.MAX_FILE_BYTES = orig
        self.assertEqual(cm.exception.code, 400)
        self.assertIn("过大", cm.exception.message)

    @unittest.skipIf(os.name == "nt", "Windows 建符号链接需要额外权限")
    def test_symlink_to_other_file_rejected(self):
        secret = self.write("秘密.txt", "不该被读到")
        link = self.tmp / "章节.txt"
        link.symlink_to(secret)
        # 后缀是 .txt，但链接本身必须先拒，否则后缀白名单被软链绕过
        with self.assertRaises(ServiceError) as cm:
            text_access.read_text(link, field="chapter_path")
        self.assertEqual(cm.exception.code, 403)

    @unittest.skipIf(not hasattr(os, "mkfifo"), "平台不支持 FIFO")
    def test_fifo_rejected_instead_of_hanging(self):
        # FIFO 会让 open 阻塞（请求挂死）或读出空内容；O_NONBLOCK + fstat 才是正解
        fp = self.tmp / "管道.txt"
        os.mkfifo(fp)
        with self.assertRaises(ServiceError) as cm:
            text_access.read_text(fp, field="chapter_path")
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
        real = self.write("真实身份.txt", "正文")
        (self.tmp / "02.txt").symlink_to(real)
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
        self.assertEqual(cm.exception.code, 403)


class TestCallersRouteThroughGuard(_TmpCase):
    """服务层必须真的走这道闸，而不是让新模块躺在仓库里。"""

    def test_platform_export_reads_external_dir(self):
        from gui import platform_service
        self.write("第1章.txt", "第一章正文内容。")
        self.write("第2章.txt", "第二章正文内容。")
        self.write("metadata.json", "{}")
        data = platform_service.export_book_for_platform("qidian", str(self.tmp))
        self.assertEqual(data["total_chapters"], 2)

    def test_platform_export_does_not_drop_gbk_chapter(self):
        # 旧实现 fp.read_text(encoding="utf-8") 失败时只 warning + continue，
        # 一本 GBK 稿子会"导出成功但整本没内容"——静默丢章比报错更坏
        from gui import platform_service
        (self.tmp / "第1章.txt").write_bytes("第一章　GBK正文。".encode("gbk"))
        (self.tmp / "第2章.txt").write_text("第二章 UTF 正文。", encoding="utf-8")
        data = platform_service.export_book_for_platform("qidian", str(self.tmp))
        self.assertEqual(data["total_chapters"], 2)
        self.assertGreater(data["total_chars"], 0)

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

    def test_writing_score_reads_gbk_chapter(self):
        from gui import writing_service
        fp = self.tmp / "第4章.txt"
        fp.write_bytes("第四章　GBK正文。".encode("gbk"))
        with self.assertRaises(ServiceError) as cm:
            writing_service.score(voice="voice:__no_such_asset__", chapter_path=str(fp))
        self.assertEqual(cm.exception.code, 404)  # 一路走到资产校验才停

    def test_writing_score_refuses_non_text_chapter(self):
        from gui import writing_service
        fp = self.write("index.db", "binary-ish")
        with self.assertRaises(ServiceError) as cm:
            writing_service.score(voice="voice:__no_such_asset__", chapter_path=str(fp))
        self.assertEqual(cm.exception.code, 400)
        self.assertIn("chapter_path", cm.exception.message)


if __name__ == "__main__":
    unittest.main()
