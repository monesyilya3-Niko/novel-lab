#!/usr/bin/env python3
"""
distill.py 写盘门禁回归测试（纯标准库 unittest，零第三方依赖）。

覆盖 2026-09-16 高优先级修复 Task 4：

  1. ``write_distilled_outputs`` 必须先对四个维度全量执行 distilled 专用校验，
     任一硬错误立即抛 ``ValueError``，且在任何 mkdir / 写盘之前失败（不留半成品）。
  2. 校验通过后按既有命名 ``f"{genre}-{dimension}-distilled.json"`` 写入，
     保持 ``ensure_ascii=False, indent=2``。
  3. 警告不阻断写盘；``rules=[]`` 的蒸馏结果必须被允许（brief 明确要求）。
  4. ``run_distill`` 返回键 ``genre`` / ``written`` / ``dimensions`` 保持兼容，
     写盘统一走门禁函数（相关用例 patch 掉真实写盘，绝不触碰生产 assets/）。
  5. ``meta.genre`` 白名单：payload 自带的 genre 参与拼输出文件名，含路径分隔符
     或上跳的非法值必须在写盘前拦下（``validate_distilled`` 本身不校验 genre）。

用法：
  python run_tests.py            # 自动 discover 本文件（pattern test_*.py）
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))


def _source_of(mod):
    """返回模块的源文件绝对路径；无 ``__file__`` 时返回 None。"""
    try:
        return Path(mod.__file__).resolve()
    except (AttributeError, TypeError, OSError):
        return None


def _load(name: str):
    """按文件名从 scripts/ 动态加载模块，且同一源文件只加载一次。

    ``distill.py`` 通过 ``from validate import validate_asset_data`` 拿到的是
    ``sys.modules["validate"]`` 里的那个实例。若本文件再独立加载第二份 ``validate``，
    门禁实际读写的 ``ERRORS`` / ``WARNS`` 与测试断言的就会是**两个不同模块实例**的
    全局变量，使「门禁不得污染全局状态」的断言退化为恒真（假绿）。因此这里复用
    ``sys.modules`` 中同路径的既有实例，从根上消除同一文件被加载两次。

    注：必须先注册进 ``sys.modules`` 再 ``exec_module``——``dataclass`` 等装饰器
    会通过 ``sys.modules[__module__]`` 反查本模块。
    """
    path = (SCRIPTS / f"{name}.py").resolve()
    mod = sys.modules.get(name)
    if mod is None or _source_of(mod) != path:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return mod


CORE = _load("distill_core")
DISTILL = _load("distill")
VALIDATE = _load("validate")

GENRE = "campus-redemption"


def valid_distilled(dimension: str, genre: str = GENRE) -> dict:
    """最小合法 distilled payload（``rules`` 允许为空，见 brief 注意事项）。"""
    return {
        "meta": {
            "id": f"{genre}-{dimension}-distilled",
            "schema_version": "1.0",
            "dimension": dimension,
            "genre": genre,
            "distilled_at": "2026-09-16T00:00:00",
            "source_books": ["book_a", "book_b", "book_c"],
            "books_count": 3,
        },
        "rules": [],
        "blindspots": [],
        "stats": {
            "total_rules": 0,
            "hard_rules": 0,
            "soft_rules": 0,
            "personal_styles": 0,
            "conflicts": 0,
            "blindspots": 0,
        },
    }


def valid_payloads() -> dict:
    """四维全量合法 payload。"""
    return {dim: valid_distilled(dim) for dim in CORE.DIMENSIONS}


def warn_only_rule() -> dict:
    """硬校验全过、仅触发 warn（sources 为空）的规则。"""
    return {
        "id": f"{GENRE}-voice-card-narration-pov-0001",
        "dimension": "voice-card",
        "field": "narration.pov",
        "kind": "hard",
        "books_count": 3,
        "value": "第三人称限知",
        "sources": [],
        "confidence": 0.8,
        "conflict": False,
        "over_generalized": False,
        "blindspot_books": [],
    }


class TestValidateDistilledPayload(unittest.TestCase):
    """``validate_distilled_payload``：薄包装 distilled 专用校验。"""

    def test_clean_payload_has_no_errors(self):
        errors, warns = DISTILL.validate_distilled_payload(valid_distilled("voice-card"))
        self.assertEqual(errors, [], f"合法 payload 不应有硬错误: {errors}")
        self.assertEqual(warns, [], f"合法 payload 不应有警告: {warns}")

    def test_empty_rules_allowed(self):
        payload = valid_distilled("craft-card")
        payload["rules"] = []
        errors, _ = DISTILL.validate_distilled_payload(payload)
        self.assertEqual(errors, [])

    def test_empty_dimension_payload_is_allowed(self):
        """I-1 回归：``_empty_distilled`` 产物（无贡献书）必须零硬错误通过门禁。

        这是部分覆盖题材的真实形态（如 3 本书只有 voice-card，其余三维为空）。
        """
        payload = CORE._empty_distilled(GENRE, "craft-card")
        self.assertEqual(payload["meta"]["source_books"], [])
        self.assertEqual(payload["meta"]["books_count"], 0)
        errors, warns = DISTILL.validate_distilled_payload(payload)
        self.assertEqual(errors, [], f"空维度不应有硬错误: {errors}")
        self.assertEqual(warns, [], f"空维度不应有警告: {warns}")

    def test_errors_are_prefixed_with_dimension(self):
        payload = valid_distilled("voice-card")
        payload["rules"] = [{"id": "broken"}]
        errors, _ = DISTILL.validate_distilled_payload(payload)
        self.assertTrue(errors, "残缺规则应产生硬错误")
        self.assertTrue(all(e.startswith("[voice-card]") for e in errors),
                        f"错误文本应按 dimension 加前缀: {errors}")

    def test_warnings_do_not_produce_errors(self):
        payload = valid_distilled("voice-card")
        payload["rules"] = [warn_only_rule()]
        errors, warns = DISTILL.validate_distilled_payload(payload)
        self.assertEqual(errors, [], f"仅警告不应升级为硬错误: {errors}")
        self.assertTrue(warns, "sources 为空应触发警告")

    def test_does_not_pollute_global_validate_state(self):
        """门禁不得污染 validate 的全局 ``ERRORS`` / ``WARNS``。

        断言对象必须是**门禁实际使用的那个 validate 模块实例**：``distill.py`` 中的
        ``validate_asset_data`` 取自 ``sys.modules["validate"]``，其 ``__globals__``
        就是该模块的 ``__dict__``。若测试另加载一份 validate 副本再去读它的全局变量，
        断言读到的是另一个模块的状态，两边永远相等（恒真假绿）。故这里先用
        ``assertIs`` 把「同一实例」钉死，再对 ``__globals__`` 内的真实状态做断言；
        另加一次调用计数，防止门禁压根没调校验器时断言空转。
        """
        gate_globals = DISTILL.validate_asset_data.__globals__
        self.assertIs(gate_globals, VALIDATE.__dict__,
                      "测试必须与门禁共享同一个 validate 模块实例，否则断言恒真")

        self.addCleanup(VALIDATE.reset)  # 用完还原，不给后续用例留污染
        VALIDATE.reset()
        VALIDATE.err("调用前已存在的错误", "pre")
        before_errors = list(VALIDATE.ERRORS)
        before_warns = list(VALIDATE.WARNS)
        self.assertTrue(before_errors, "前置条件：哨兵错误应已注入，否则断言无意义")

        calls = []
        real = DISTILL.validate_asset_data

        def spy(kind, data):
            calls.append(kind)
            return real(kind, data)

        with mock.patch.object(DISTILL, "validate_asset_data", side_effect=spy):
            DISTILL.validate_distilled_payload(valid_distilled("structure-obs"))

        self.assertEqual(calls, ["distilled"],
                         "门禁必须真的调用 validate_asset_data，否则本用例空转")
        self.assertEqual(gate_globals["ERRORS"], before_errors,
                         "门禁不得污染 validate 全局 ERRORS")
        self.assertEqual(gate_globals["WARNS"], before_warns,
                         "门禁不得污染 validate 全局 WARNS")


class TestDistillGate(unittest.TestCase):
    """写盘门禁：先全量校验，再写盘。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_root = Path(self._tmp.name)
        # 目录故意不存在：既验证会按需创建，也验证校验失败时不会创建。
        self.assets_dir = self.tmp_root / "assets"

    def test_valid_payloads_are_written_after_validation(self):
        payloads = {dim: valid_distilled(dim) for dim in CORE.DIMENSIONS}
        written = DISTILL.write_distilled_outputs(payloads, self.assets_dir)
        self.assertEqual(len(written), 4)
        self.assertTrue(all(Path(p).is_file() for p in written))

    def test_one_invalid_dimension_writes_nothing(self):
        payloads = {dim: valid_distilled(dim) for dim in CORE.DIMENSIONS}
        payloads["voice-card"]["rules"] = [{"id": "broken"}]
        with self.assertRaises(ValueError) as ctx:
            DISTILL.write_distilled_outputs(payloads, self.assets_dir)
        self.assertIn("distilled", str(ctx.exception))
        self.assertEqual(list(self.assets_dir.glob("*.json")), [])

    def test_invalid_payload_does_not_create_assets_dir(self):
        """校验失败必须发生在任何 mkdir 之前（不留半成品）。"""
        payloads = valid_payloads()
        payloads["commercial-obs"]["meta"]["dimension"] = "craft-card"
        with self.assertRaises(ValueError):
            DISTILL.write_distilled_outputs(payloads, self.assets_dir)
        self.assertFalse(self.assets_dir.exists(), "校验失败不得创建 assets 目录")

    def test_illegal_meta_genre_writes_nothing(self):
        """HIGH：``meta.genre`` 参与拼输出文件名，非法值必须在写盘前拦下。

        覆盖 ``write_distilled_outputs`` 内新增的 ``meta.genre`` 白名单分支。
        ``validate_distilled`` 对 ``meta.genre`` 只做 ``check_str(min_len=2)``
        （类型 + 长度），**不校验字符集**，故 ``"../evil"`` / ``"a/b"`` 能通过
        distilled 校验，本分支是唯一防线——禁用后 ``"../evil"`` 会真的把文件写到
        ``assets/`` 之外（见 task-4-report.md 的红灯证据）。
        """
        for illegal in ("../evil", "..", "", "a/b", "a\\b", None):
            with self.subTest(genre=illegal):
                payloads = valid_payloads()
                payloads["voice-card"]["meta"]["genre"] = illegal
                with self.assertRaises(ValueError) as ctx:
                    DISTILL.write_distilled_outputs(payloads, self.assets_dir)
                self.assertIn("非法 meta.genre", str(ctx.exception))
                self.assertFalse(self.assets_dir.exists(),
                                 "非法 meta.genre 不得创建 assets 目录")
                self.assertEqual(list(self.tmp_root.rglob("*")), [],
                                 "校验失败不得在临时目录留下任何文件/目录")

    def test_missing_dimension_writes_nothing(self):
        payloads = valid_payloads()
        del payloads["structure-obs"]
        with self.assertRaises(ValueError) as ctx:
            DISTILL.write_distilled_outputs(payloads, self.assets_dir)
        self.assertIn("structure-obs", str(ctx.exception))
        self.assertEqual(list(self.assets_dir.glob("*.json")), [])

    def test_dimension_key_mismatch_writes_nothing(self):
        """meta.dimension 与 key 不一致必须拦下（禁止跨维度错装）。"""
        payloads = valid_payloads()
        payloads["voice-card"]["meta"]["dimension"] = "craft-card"
        with self.assertRaises(ValueError) as ctx:
            DISTILL.write_distilled_outputs(payloads, self.assets_dir)
        self.assertIn("dimension", str(ctx.exception))
        self.assertEqual(list(self.assets_dir.glob("*.json")), [])

    def test_warn_only_payload_still_writes(self):
        """警告不阻断写盘：仅 warn 的维度必须照常落盘。"""
        payloads = valid_payloads()
        payloads["voice-card"]["rules"] = [warn_only_rule()]
        written = DISTILL.write_distilled_outputs(payloads, self.assets_dir)
        self.assertEqual(len(written), 4)
        self.assertTrue(all(Path(p).is_file() for p in written))

    def test_written_paths_use_existing_naming(self):
        written = DISTILL.write_distilled_outputs(valid_payloads(), self.assets_dir)
        names = [Path(p).name for p in written]
        self.assertEqual(
            names,
            [f"{GENRE}-{dim}-distilled.json" for dim in CORE.DIMENSIONS],
        )
        self.assertTrue(all(Path(p).is_absolute() for p in written),
                        f"应返回绝对路径: {written}")

    def test_written_json_keeps_utf8_and_indent(self):
        payloads = valid_payloads()
        payloads["voice-card"]["blindspots"] = [
            {"book": "book_a", "dimension": "voice-card",
             "field": "narration.pov", "note": "字段缺失或无法归一化"}
        ]
        written = DISTILL.write_distilled_outputs(payloads, self.assets_dir)
        target = next(p for p in written if "voice-card" in Path(p).name)

        raw = Path(target).read_text(encoding="utf-8")
        self.assertIn("字段缺失或无法归一化", raw, "ensure_ascii=False：中文不得转义")
        self.assertNotIn("\\u", raw, "不应出现 unicode 转义")
        self.assertIn('\n  "meta"', raw, "indent=2：顶层键应缩进两空格")
        self.assertEqual(json.loads(raw), payloads["voice-card"])

    def test_no_write_before_validation_completes(self):
        """最后一个维度非法时，前面的合法维度也不得落盘。"""
        payloads = valid_payloads()
        payloads["commercial-obs"]["rules"] = [{"id": "broken"}]
        with self.assertRaises(ValueError):
            DISTILL.write_distilled_outputs(payloads, self.assets_dir)
        self.assertEqual(list(self.assets_dir.glob("*.json")), [])

    def test_empty_dimension_writes_all_four_files(self):
        """I-1 回归：某维度无资产（空维度）时仍必须写出四个文件。

        修复前 ``validate_distilled`` 要求 ``meta.source_books`` 至少 1 项，而
        ``_empty_distilled`` 产出 ``source_books: []``，于是门禁对四维全量校验时
        必然抛 ``ValueError``——部分覆盖题材从「可蒸馏」退化为**零文件写出**。
        """
        payloads = valid_payloads()
        empty_dim = "craft-card"
        payloads[empty_dim] = CORE._empty_distilled(GENRE, empty_dim)

        written = DISTILL.write_distilled_outputs(payloads, self.assets_dir)

        self.assertEqual(len(written), 4, f"空维度也必须落盘: {written}")
        self.assertTrue(all(Path(p).is_file() for p in written))
        target = next(p for p in written if empty_dim in Path(p).name)
        self.assertEqual(
            json.loads(Path(target).read_text(encoding="utf-8"))["meta"]["source_books"],
            [],
            "空维度的 source_books 应原样保留空数组",
        )

    def test_all_four_dimensions_empty_still_writes(self):
        """四维全空（极端部分覆盖）也不得整体失败。"""
        payloads = {dim: CORE._empty_distilled(GENRE, dim) for dim in CORE.DIMENSIONS}
        written = DISTILL.write_distilled_outputs(payloads, self.assets_dir)
        self.assertEqual(len(written), 4)


class TestRunDistillContract(unittest.TestCase):
    """``run_distill`` 返回键兼容 + 统一走门禁（用例内不触碰生产 assets/）。"""

    def test_returns_compatible_keys_and_uses_gate(self):
        payloads = valid_payloads()
        seen = {}

        def fake_write(distilled_by_dim, assets_dir):
            seen["distilled"] = distilled_by_dim
            seen["assets_dir"] = Path(assets_dir)
            return [str(Path(assets_dir) / f"{GENRE}-{d}-distilled.json")
                    for d in CORE.DIMENSIONS]

        with mock.patch.object(DISTILL, "distill_genre", return_value=payloads), \
                mock.patch.object(DISTILL, "write_distilled_outputs", side_effect=fake_write):
            result = DISTILL.run_distill(GENRE)

        self.assertEqual(set(result.keys()), {"genre", "written", "dimensions"})
        self.assertEqual(result["genre"], GENRE)
        self.assertEqual(result["dimensions"], payloads)
        self.assertEqual(len(result["written"]), 4)
        self.assertIs(seen["distilled"], payloads, "写盘应统一走门禁函数")
        self.assertEqual(seen["assets_dir"].name, "assets")

    def test_illegal_genre_still_rejected(self):
        with mock.patch.object(DISTILL, "distill_genre", return_value=valid_payloads()), \
                mock.patch.object(DISTILL, "write_distilled_outputs") as writer:
            with self.assertRaises(ValueError):
                DISTILL.run_distill("../evil")
        writer.assert_not_called()


class TestDistillCliGenreGate(unittest.TestCase):
    """CLI「蒸馏」的题材存在性门禁（2026-10-12 审计修复 CLI-07）。

    缺陷背景：原实现只校验字符合法性（_GENRE_RE），**不校验题材是否真实存在**。
    实测：`novel 蒸馏 --genre definitely-not-a-genre` 写出 4 个 0 规则的空壳
    资产并 EXIT=0——既是"假成功"，又把垃圾文件灌进 assets/。

    修法：main() 里先查 genre_registry.known_genres()（磁盘派生，与铁律一一致），
    不存在则 return 1；且**校验先于落盘**，不产生任何文件。
    另外：即便题材合法，规则总数为 0 也判失败（不产出空壳当成功）。

    注意层次区分：本文件的 TestValidateDistilledPayload 允许 rules=[] 是
    **库函数**（write_distilled_outputs）的语义；这里拒绝 0 规则是 **CLI 命令**
    的语义——两者不冲突，且 CLI 门禁发生在调用库函数之前。
    """

    def _main(self, argv):
        """跑 distill.main()，捕获 stdout。"""
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = DISTILL.main(argv)
        return rc, buf.getvalue()

    def test_unknown_genre_returns_1_and_writes_nothing(self):
        """核心守卫：不存在的题材必须失败，且**不落盘**。"""
        with mock.patch.object(DISTILL, "run_distill") as rd:
            rc, out = self._main(["--genre", "definitely-not-a-genre"])
        self.assertEqual(rc, 1, "题材不存在却返回成功")
        self.assertIn("题材不存在", out)
        rd.assert_not_called(), "校验失败却仍调用了 run_distill（会落盘空壳）"

    def test_unknown_genre_hints_known_ones(self):
        """错误信息应给出已知题材，帮用户发现拼写错误。"""
        with mock.patch.object(DISTILL, "run_distill"):
            rc, out = self._main(["--genre", "definitely-not-a-genre"])
        self.assertEqual(rc, 1)
        self.assertIn("已知题材", out)

    def test_zero_rules_is_treated_as_failure(self):
        """题材合法但一条规则都没蒸出来：不该当作成功（会产出空壳污染资产库）。"""
        zero = {
            d: {"meta": {"dimension": d, "genre": "g", "books_count": 0},
                "stats": {"total_rules": 0, "hard_rules": 0, "soft_rules": 0,
                          "personal_styles": 0, "conflicts": 0, "blindspots": 0}}
            for d in DISTILL.DIMENSIONS
        }
        with mock.patch.object(DISTILL, "run_distill",
                               return_value={"genre": "g", "written": [],
                                             "dimensions": zero}):
            rc, out = self._main(["--genre", "campus-redemption"])
        self.assertEqual(rc, 1, "0 条规则却返回成功")
        self.assertIn("0 条规则", out)

    def test_illegal_genre_chars_rejected(self):
        """反向守卫：字符非法（路径穿越尝试）同样被拦。"""
        with mock.patch.object(DISTILL, "run_distill") as rd:
            rc, out = self._main(["--genre", "../../etc"])
        self.assertEqual(rc, 1)
        rd.assert_not_called()

    def test_known_genre_proceeds(self):
        """反向守卫：已知题材不得被误拦——必须真的走到 run_distill。"""
        ok = {
            d: {"meta": {"dimension": d, "genre": "g", "books_count": 2},
                "stats": {"total_rules": 5, "hard_rules": 3, "soft_rules": 2,
                          "personal_styles": 0, "conflicts": 0, "blindspots": 0}}
            for d in DISTILL.DIMENSIONS
        }
        with mock.patch.object(DISTILL, "run_distill",
                               return_value={"genre": "campus-redemption",
                                             "written": ["/tmp/x.json"],
                                             "dimensions": ok}) as rd:
            rc, _ = self._main(["--genre", "campus-redemption"])
        self.assertEqual(rc, 0, "合法题材被误拦")
        rd.assert_called_once()


if __name__ == "__main__":
    unittest.main()
