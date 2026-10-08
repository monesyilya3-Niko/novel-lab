"""API 边界脏输入的回归（2026-10-08 全路由 500 扫描）。

做法：把 `gui/router.py` 的 ROUTES 全表用一批脏 body 打一遍真实 HTTP 服务，
凡是返回 500 的都算缺陷——500 的意思是"服务端没接住这个输入"，而调用方
拿到的是没有信息量的"内部错误，请稍后重试"，既不知道哪个参数错了，也无从修正。

这里钉住扫描出来的 9 处（project / name / text / style_card / base_prompt 传非字符串，
以及把质检 target 指向整盘目录）。新增接口时按同样口径补断言。
"""
from __future__ import annotations

import json
import socket
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import _isolation  # noqa: E402


class TestDirtyBodiesGet400(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gui import server as server_mod

        cls._tmp = Path(tempfile.mkdtemp(prefix="apival_"))
        cls._iso = _isolation.isolate_paths(cls._tmp)
        cls._iso.__enter__()
        # 关掉启动备份：本用例只关心参数校验，不跑 SQLite 在线备份
        from gui import server as _s
        cls._orig_bk = (_s.auto_backup.startup_backup, _s.auto_backup.daily_backup_if_due)
        _s.auto_backup.startup_backup = lambda: None
        _s.auto_backup.daily_backup_if_due = lambda: None
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        cls.srv = server_mod.GuiServer(preferred_port=port)
        _host, cls.port = cls.srv.start()

    @classmethod
    def tearDownClass(cls):
        from gui import server as _s
        cls.srv.shutdown()
        _s.auto_backup.startup_backup, _s.auto_backup.daily_backup_if_due = cls._orig_bk
        cls._iso.__exit__(None, None, None)
        _isolation.remove_tree(cls._tmp)

    def _post(self, path: str, body: dict) -> tuple[int, str]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, ""
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", "replace")
            try:
                msg = json.loads(payload).get("message", "")
            except json.JSONDecodeError:
                msg = payload[:120]
            return exc.code, msg

    # (端点, 脏 body, 期望出现在错误信息里的关键词)
    CASES = [
        ("/api/writing/projects", {"name": 1}, "字符串"),
        ("/api/writing/chapters", {"project": 1, "chapter_no": 1, "content": "正文"}, "字符串"),
        ("/api/writing/outlines", {"project": 1, "title": "t"}, "字符串"),
        ("/api/writing/characters", {"project": 1, "name": "c"}, "字符串"),
        ("/api/writing/notes", {"project": 1, "content": "n"}, "字符串"),
        ("/api/quality/check", {"text": 123}, "字符串"),
        ("/api/quality/book", {"text": 123}, "字符串"),
        ("/api/quality/check", {"target": "C:/Windows"}, "target"),
        ("/api/assets", {"name": 1, "kind": "voice-card", "content": {}}, "资产名"),
        ("/api/style/save", {"name": 1, "style_card": {}}, "字符串"),
        ("/api/style/apply", {"style_name": "不存在", "base_prompt": 5}, "字符串"),
        # 章节序号：静默截断会让"第 2.5 章"覆盖掉真正的第 2 章
        ("/api/writing/chapters",
         {"project": "极端", "chapter_no": 2.5, "content": "正文" * 200}, "整数"),
        ("/api/writing/chapters",
         {"project": "极端", "chapter_no": True, "content": "正文" * 200}, "整数"),
        ("/api/writing/chapters",
         {"project": "极端", "chapter_no": 10 ** 20, "content": "正文" * 200}, "过大"),
        ("/api/platform/format",
         {"platform_id": "qidian", "chapter_num": 1.5, "title": "t", "content": "c"}, "整数"),
    ]

    def test_every_dirty_body_is_4xx_not_500(self):
        for path, body, keyword in self.CASES:
            with self.subTest(path=path, body=body):
                code, msg = self._post(path, body)
                self.assertNotEqual(code, 500, f"{path} {body} → 500（缺参数校验）")
                self.assertIn(code, (400, 404, 409), f"{path} {body} → {code} {msg}")
                self.assertIn(keyword, msg, f"{path} {body} 的错误信息没指出问题：{msg!r}")

    def test_good_project_name_still_works(self):
        # 反向守卫：校验不能把正常输入也挡掉
        code, msg = self._post("/api/writing/projects", {"name": "校验回归书"})
        self.assertEqual(code, 200, msg)

    def test_good_text_check_still_works(self):
        code, msg = self._post("/api/quality/check", {"text": "第一章正文。" * 60})
        self.assertEqual(code, 200, msg)


if __name__ == "__main__":
    unittest.main()
