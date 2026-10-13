#!/usr/bin/env python3
"""CLI 退出码传播契约（2026-09-21）。

背景：`novel.py` 通过 `run_script()` 调 `scripts/*.py`，并用返回码判断成败
（例如 `分析` 命令：`rc1 = run_script("pipeline.py", …); if rc1 != 0: return rc1`）。

但 7 个子脚本的入口全是：

    if __name__ == "__main__":
        main()          # ← 返回值被丢弃，进程退出码恒为 0

于是 `main()` 里的 `return 1`（校验失败 / 章号异常 / LLM 中断）**对上层完全不可见**，
`novel.py` 的失败分支永远不会触发。2026-09-21 实测：组装因 schema REJECT 而失败时，
退出码仍为 0。

本测试锁定该契约：凡是 `scripts/*.py` 与 `novel.py` 里有 `__main__` 块的，
其最后一句必须是 `sys.exit(main())`（或至少含 `sys.exit(`）。

用法：
  python -m unittest tests.test_cli_exit_code -v
  python run_tests.py     # 自动 discover
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MAIN_RE = re.compile(
    r'if\s+__name__\s*==\s*["\']__main__["\']\s*:(?P<body>(?:\n[ \t]+.*|\n)*)')


def _main_block_tail(text: str) -> str | None:
    """返回 __main__ 块里最后一条非空语句。"""
    m = MAIN_RE.search(text)
    if not m:
        return None
    lines = [ln.strip() for ln in m.group("body").splitlines() if ln.strip()]
    return lines[-1] if lines else ""


# 明确豁免：这些文件的 __main__ 块不是「返回码语义」的 CLI 入口。
#   - chapter_loader.py: 源码已标 `# pragma: no cover - 诊断入口`，纯打印诊断
#   - llm_client.py    : 末尾是 print 用法提示（连通性测试入口）
#   - secret_store.py  : 末尾是 print 密钥条目数
# （consistency.py 已于 2026-09-21 补上退出码语义，不再豁免）
EXEMPT = {"chapter_loader.py", "llm_client.py", "secret_store.py"}


class TestCliExitCodePropagation(unittest.TestCase):
    """所有 CLI 入口都必须把 main() 的返回值交给 sys.exit()。"""

    def _targets(self):
        files = [ROOT / "novel.py"]
        files += sorted((ROOT / "scripts").glob("*.py"))
        return [f for f in files if f.exists() and f.name not in EXEMPT]

    def test_every_entrypoint_propagates_exit_code(self):
        offenders = []
        for f in self._targets():
            tail = _main_block_tail(f.read_text(encoding="utf-8"))
            if tail is None:          # 无 __main__ 块（纯库模块），跳过
                continue
            if "sys.exit(" not in tail and "SystemExit(" not in tail:
                offenders.append(f"{f.relative_to(ROOT)} → {tail}")
        self.assertEqual(
            offenders, [],
            "以下入口未把 main() 的返回值交给 sys.exit()，失败退出码会丢失：\n  "
            + "\n  ".join(offenders))

    def test_scripts_import_sys_when_needed(self):
        """用了 sys.exit 就必须 import sys，否则运行期 NameError。"""
        offenders = []
        for f in self._targets():
            text = f.read_text(encoding="utf-8")
            tail = _main_block_tail(text)
            if tail and "sys.exit(" in tail and not re.search(r"^\s*import sys\b", text, re.M):
                offenders.append(str(f.relative_to(ROOT)))
        self.assertEqual(offenders, [], f"以下文件用了 sys.exit 但没 import sys：{offenders}")


class TestVerdictReflectedInExitCode(unittest.TestCase):
    """判定结果必须反映到退出码（2026-10-12 审计修复 CLI-03/04）。

    缺陷背景：`检查` 与 `质检` 两个子命令算完判定后**裸 return 0**——
    质量 FAIL、一致性 FAIL、乃至含 critical 级问题，退出码都是 0。
    这与直连脚本的语义**相反**：
      scripts/chapter_check.py  -> sys.exit(0 if verdict == "PASS" else 1)
      scripts/book_quality.py   -> sys.exit(0 if verdict == "PASS" else 1)

    退出码是 CI / 脚本编排的唯一判定依据，恒 0 等于把门禁变成装饰。

    本组用**静态断言**锁定 return 表达式（行为级测试需起子进程跑完整
    pipeline，成本高且依赖 LLM 配置；这里钉住关键表达式即可防回退）。
    """

    def setUp(self):
        self.novel_src = (ROOT / "novel.py").read_text(encoding="utf-8")

    def test_check_command_reads_verdict(self):
        """`检查` 的收尾必须同时依据质量与一致性两个维度。

        CLI-03（2026-10-12）先让质量维度的 verdict 参与退出码；
        CLI-14（2026-10-13）补齐一致性维度——实测一致性 56 分（远低于 75 线）
        被打印出来，命令却 EXIT=0，CI 据此放行声线走样的章节。
        """
        self.assertIn("quality_ok", self.novel_src,
                      "「检查」的退出码未反映质量判定")
        self.assertIn("consistency_ok", self.novel_src,
                      "「检查」的退出码未反映一致性判定——双维度命令退化为单维度门禁")
        self.assertIn("return 0 if (quality_ok and consistency_ok) else 1",
                      self.novel_src,
                      "「检查」的收尾必须要求两个维度都达标")

    def test_qc_command_reads_verdict(self):
        """`质检` 的收尾必须依据 result['verdict']。"""
        self.assertIn(
            'return 0 if result.get("verdict") == "PASS" else 1',
            self.novel_src,
            "「质检」的退出码未反映判定——FAIL 会静默返回 0",
        )

    def test_no_bare_return_zero_after_verdict(self):
        """反向守卫：判定已算出却裸 return 0 的模式不得再出现。

        原缺陷形态是：算完 verdict → `return 0`（不带条件）。
        这里扫描「检查」「质检」两个分支区间，确保没有无条件 return 0。
        """
        # 定位两个命令分支
        for cmd in ('args.cmd == "检查"', 'args.cmd == "质检"'):
            start = self.novel_src.index(cmd)
            # 到下一个 args.cmd == 为止
            nxt = self.novel_src.find("args.cmd ==", start + len(cmd))
            block = self.novel_src[start:nxt] if nxt > 0 else self.novel_src[start:]
            bare_return = "\n" + " " * 8 + "return 0\n"
            self.assertNotIn(
                bare_return, block,
                f"{cmd} 分支里仍有裸 return 0——判定结果被丢弃",
            )


class TestConsoleEncodingTolerance(unittest.TestCase):
    """CLI 在 GBK 控制台下不得因特殊符号崩栈（2026-10-12 审计修复 CLI-05）。

    缺陷背景：CLI 大量使用 ✓ / ✗ / ⚠ / 🔴 等符号，而 Windows 中文控制台
    默认 GBK——实测 `PYTHONIOENCODING=gbk` 下 print('✓') 直接抛
    UnicodeEncodeError。最讽刺的是这发生在**报错路径**上：本想告诉用户
    "质检失败"，结果先崩在打印失败信息那一行。

    修法：novel.py 入口调 _configure_console_encoding()，把 stdout/stderr
    的错误处理器设为 backslashreplace（不可编码字符降级为 ✓ 转义）；
    run_script 给子进程注入 PYTHONIOENCODING 使其同样容错。
    """

    # GBK 无法编码的符号（实测确认）
    NON_GBK = ["✓", "✗", "⚠", "✅", "❌", "🔴"]

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("novel_cli_enc", ROOT / "novel.py")
        self.novel = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.novel)

    def test_these_symbols_really_are_non_gbk(self):
        """前置事实核验：本测试依据的符号确实无法 GBK 编码。

        若某天这些符号变得可编码（例如换用 GB18030），本组测试的前提
        就不成立，应重新评估——故显式断言，避免守卫变成空转。
        """
        for ch in self.NON_GBK:
            with self.assertRaises(UnicodeEncodeError, msg=f"{ch!r} 竟然可 GBK 编码"):
                ch.encode("gbk")

    def test_reconfigure_makes_symbols_printable_under_gbk(self):
        """核心守卫：GBK 编码下打印这些符号不得抛异常。"""
        import io
        # 造一个 GBK 编码且 strict 的流，模拟 Windows 中文控制台
        raw = io.BytesIO()
        gbk_stream = io.TextIOWrapper(raw, encoding="gbk", errors="strict")

        orig_out, orig_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = gbk_stream, gbk_stream
        try:
            self.novel._configure_console_encoding()
            for ch in self.NON_GBK:
                print(ch)          # 修复前这里会抛 UnicodeEncodeError
            gbk_stream.flush()
        finally:
            sys.stdout, sys.stderr = orig_out, orig_err

        out = raw.getvalue().decode("gbk", "replace")
        # 降级为转义序列，内容是可见的
        self.assertIn("\\u2713", out, "未降级为可读转义")

    def test_utf8_stream_untouched(self):
        """反向守卫：已是 UTF-8 的流不应被改动（避免影响重定向/管道）。"""
        import io
        utf8_stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        before = utf8_stream.errors
        orig_out, orig_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = utf8_stream, utf8_stream
        try:
            self.novel._configure_console_encoding()
            self.assertEqual(utf8_stream.errors, before, "UTF-8 流被无谓改动了")
        finally:
            sys.stdout, sys.stderr = orig_out, orig_err

    def test_entrypoint_actually_calls_configure(self):
        """入口必须真的调用配置函数——否则本模块其余测试都是空转。

        （变异测试发现：只测 _configure_console_encoding 本身，
        把入口里的调用删掉测试仍绿。）
        """
        src_text = (ROOT / "novel.py").read_text(encoding="utf-8")
        self.assertRegex(
            src_text,
            r"__main__[\s\S]{0,200}_configure_console_encoding\(\)",
            "novel.py 入口未调用 _configure_console_encoding()——GBK 下仍会崩",
        )

    def test_subprocess_gets_encoding_env(self):
        """子进程（scripts/*.py）也必须拿到容错编码设置。"""
        src = (ROOT / "novel.py").read_text(encoding="utf-8")
        self.assertIn("PYTHONIOENCODING", src,
                      "run_script 未给子进程注入编码设置——被调脚本仍会崩在输出上")


class TestValidateKindChoicesSync(unittest.TestCase):
    """「校验」--kind choices 必须与 validate.DISPATCH 同步（2026-10-12 CLI-06）。

    缺陷背景：choices 原先是手写的 7 项硬编码列表，而 DISPATCH 已有 10 个
    校验器——distilled / genre-prose-card-index / tool-library 三类资产
    用户根本无法通过 CLI 校验（argparse 直接拒绝该 --kind 值）。

    修法：choices 从 DISPATCH 派生（单一来源），永不漂移。
    """

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("novel_cli_kind", ROOT / "novel.py")
        self.novel = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.novel)

    def test_choices_match_dispatch_exactly(self):
        import validate as validate_mod
        expected = sorted(validate_mod.DISPATCH.keys())
        self.assertEqual(
            self.novel._validate_dispatch_keys(), expected,
            "CLI --kind choices 与 validate.DISPATCH 不一致——新增校验器时"
            "用户无法通过 CLI 使用它",
        )

    def test_previously_missing_kinds_are_offered(self):
        """回归锚点：这三个曾因硬编码列表落后而被拒。"""
        keys = self.novel._validate_dispatch_keys()
        for k in ("distilled", "tool-library", "genre-prose-card-index"):
            self.assertIn(k, keys, f"{k} 又不在 CLI choices 里了")

    def test_parser_actually_uses_derived_choices(self):
        """argparse 构建出的 --kind choices 必须是派生值，不是手写列表。

        （变异测试发现：只测 _validate_dispatch_keys() 本身，
        把 argparse 那行改回手写列表测试仍绿——必须测真实的 parser。）
        """
        import contextlib
        import io
        # 构造 parser 需要跑 main() 的参数解析部分；这里直接抓 --help 输出
        buf = io.StringIO()
        old_argv = sys.argv
        sys.argv = ["novel.py", "校验", "--help"]
        try:
            with contextlib.redirect_stdout(buf), contextlib.suppress(SystemExit):
                self.novel.main()
        finally:
            sys.argv = old_argv
        help_text = buf.getvalue()
        # 三个曾缺失的 kind 必须出现在 help 里
        for k in ("distilled", "tool-library", "genre-prose-card-index"):
            self.assertIn(k, help_text,
                          f"{k} 未出现在「校验 --kind」的 choices 中")

    def test_fallback_when_validate_unavailable(self):
        """validate 导入失败时回退到历史 7 项，CLI 仍可用。"""
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **kw):
            if name == "validate":
                raise ImportError("模拟缺失")
            return real_import(name, *a, **kw)

        builtins.__import__ = fake_import
        try:
            keys = self.novel._validate_dispatch_keys()
        finally:
            builtins.__import__ = real_import
        self.assertEqual(keys, self.novel._FALLBACK_KINDS)
        self.assertIn("voice-card", keys)


class TestStatusCommandHealth(unittest.TestCase):
    """`novel 状态` 的退出码必须反映健康度（2026-10-12 审计修复 CLI-09）。

    缺陷背景：对损坏的资产 / 项目 / 模型配置文件只打印"（损坏，跳过）"
    却**仍 return 0** —— 于是该命令无法用作门禁（CI 里"有损坏也报成功"）。

    修法：任一文件损坏即 return 1，但内容照常打印（信息不丢）。
    """

    def setUp(self):
        import importlib.util
        import tempfile
        self.tmp = Path(tempfile.mkdtemp(prefix="status_"))
        spec = importlib.util.spec_from_file_location("novel_status", ROOT / "novel.py")
        self.novel = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.novel)
        self._orig_root = self.novel.ROOT
        self.novel.ROOT = self.tmp
        for d in ("assets", "reports", "novel", "config"):
            (self.tmp / d).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        self.novel.ROOT = self._orig_root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.novel.cmd_status()
        return rc, buf.getvalue()

    def test_healthy_project_returns_zero(self):
        (self.tmp / "assets" / "good-voice-card.json").write_text(
            '{"meta":{"confidence":0.9,"genre":"x"}}', encoding="utf-8")
        rc, _ = self._run()
        self.assertEqual(rc, 0, "健康项目不应报非零")

    def test_damaged_asset_returns_nonzero(self):
        """核心守卫：损坏资产必须让退出码非零（可作门禁）。"""
        (self.tmp / "assets" / "bad-voice-card.json").write_text(
            "{ 坏掉的 json", encoding="utf-8")
        rc, out = self._run()
        self.assertEqual(rc, 1, "有损坏却返回 0——无法用于门禁")
        self.assertIn("损坏", out, "损坏信息仍应打印（不能因改退出码而丢信息）")

    def test_damaged_project_state_returns_nonzero(self):
        d = self.tmp / "novel" / "proj"
        d.mkdir()
        (d / "state.json").write_text("{ bad", encoding="utf-8")
        rc, _ = self._run()
        self.assertEqual(rc, 1)

    def test_damaged_model_config_returns_nonzero(self):
        (self.tmp / "config" / "models.json").write_text("{ bad", encoding="utf-8")
        rc, _ = self._run()
        self.assertEqual(rc, 1)


class TestAutoQcHookRobustness(unittest.TestCase):
    """「分析」的自动质检 Hook（2026-10-12 审计修复 CLI-08）。

    两处缺陷：
      a) `if corpus_file.exists():` 无 else —— 语料不在 corpus/ 时什么都不打印，
         用户看到 "[Hook] 自动质检:" 后是空的，以为质检跑过了。
      b) 整个质检段无 try —— Hook 崩溃会冒泡中断「分析」，而此时报告**已发布**，
         用户以为整个分析失败。Hook 是辅助信息，不该拖垮主流程。

    本组用**静态断言**锁定这两处结构（行为级需跑完整 pipeline 且依赖 LLM 配置，
    成本高；结构断言足以防回退）。
    """

    def setUp(self):
        self.src = (ROOT / "novel.py").read_text(encoding="utf-8")

    def test_hook_has_else_branch_when_corpus_missing(self):
        self.assertIn("if not corpus_file.exists():", self.src)
        self.assertIn("未执行", self.src, "语料缺失时应明确说明未执行")

    def test_hook_is_wrapped_in_try(self):
        """Hook 崩溃不得冒泡——必须被捕获并降级为提示。"""
        self.assertIn("质检 Hook 执行失败", self.src,
                      "Hook 异常未被降级处理：崩溃会中断已发布报告的分析命令")

    def test_hook_failure_message_points_to_manual_command(self):
        """降级提示应告诉用户如何手动质检，而不是留下一个无助的警告。"""
        self.assertIn("如需质检，请单独跑", self.src)


class TestSysPathHygiene(unittest.TestCase):
    """CLI 不得把 gui/ 塞进顶层模块搜索路径（2026-10-12 审计修复 CLI-11）。

    缺陷背景：cmd_reset_admin_password 曾执行
    ``sys.path.insert(0, str(ROOT / "gui"))`` 再 ``from gui import admin``。

    两个问题：
      a) **完全多余** —— 实测不加也能导入（ROOT 已在 sys.path，gui 是可导入包）
      b) 把 gui/ 加入顶层搜索路径后，gui/config.py、gui/db.py 会以**顶层模块名**
         config / db 暴露。scripts/ 也在 sys.path 中，同名模块会按插入顺序互相
         遮蔽（实测 insert(0) 后顶层 config 指向 gui/config.py）——这与
         AGENTS.md §2 的依赖方向约定相悖，且冲突是隐式的。

    修法：删掉该行，统一用包路径 ``from gui import admin``。

    ⚠️ 本组只做静态检查：实际调用会重置真实管理员密码（有副作用）。
    """

    def _active_syspath_lines(self):
        """返回活代码里的 sys.path 操作（排除注释行）。"""
        out = []
        for raw in (ROOT / "novel.py").read_text(encoding="utf-8").split('\n'):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "sys.path" in line:
                out.append(line)
        return out

    def test_gui_not_added_to_sys_path(self):
        lines = self._active_syspath_lines()
        bad = [l for l in lines if '"gui"' in l or "'gui'" in l or "/ \"gui\"" in l]
        self.assertEqual(bad, [], f"gui/ 被加进了顶层搜索路径：{bad}")

    def test_scripts_path_is_provided(self):
        """反向守卫：scripts/ 的 sys.path 注入是设计意图，不得被误删。"""
        lines = self._active_syspath_lines()
        self.assertTrue(
            any("SCRIPTS" in l for l in lines),
            "scripts/ 的 sys.path 注入被删了——scripts 下模块会导入失败",
        )

    def test_reset_password_imports_via_package_path(self):
        """重置密码应走包路径导入，而非依赖 sys.path 技巧。"""
        src_text = (ROOT / "novel.py").read_text(encoding="utf-8")
        self.assertIn("from gui import admin", src_text)


if __name__ == "__main__":
    sys.exit(unittest.main())
