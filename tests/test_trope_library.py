#!/usr/bin/env python3
"""
novel-lab P1 trope-library 桥段库回归测试（纯标准库 unittest，零第三方依赖）。

对应架构师设计 system_design_P1_trope_library.md §5 任务 T03 的 8 项验收标准：

  1. 资产文件存在且 json.loads 可解析、meta.total_count == len(tropes)
  2. 每条 abstraction_level ∈ {structural, scenic}（断言不含 verbal）
  3. 每条 effectiveness.payoff_strength 为 1-10 整数
  4. 每条 skeleton 含 setup/escalation/payoff/aftermath 四键且 escalation 非空
  5. 每条 category ∈ 8 个合法枚举值
  6. validate_trope_library(asset) 返回的 ERRORS 为空
  7. 全库不存在 contains_verbatim == true 的条目
  8. 每条 tropes[].id 非空且唯一（资产自洽补充校验）

用法：
  python run_tests.py            # 自动 discover 本文件（pattern test_*.py）
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
ASSETS = ROOT / "assets"
ASSET_PATH = ASSETS / "trope-library.json"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    """按文件名从 scripts/ 动态加载模块（与 test_distill 同模式）。"""
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


VALIDATE = _load("validate")

# 与 schema/trope-library.schema.json 的 category enum 完全一致（8 值）
CATEGORY_ENUM = {"打脸", "身份", "危机", "情感", "试炼", "机缘", "日常", "阵营转换"}
# abstraction_level 红线：仅 structural / scenic 可入库，verbal 一律拒收
ALLOWED_ABSTRACTION = {"structural", "scenic"}
# skeleton 四段键（schema required 至少 setup/escalation/payoff，设计 §3.5 要求四段齐全）
SKELETON_KEYS = ("setup", "escalation", "payoff", "aftermath")


def _load_asset():
    """读取并解析资产文件，返回 (asset_dict, raw_text)。"""
    raw = ASSET_PATH.read_text(encoding="utf-8")
    return json.loads(raw), raw


class TestTropeLibrary(unittest.TestCase):
    """P1 trope-library 首个资产实例的回归护栏。"""

    @classmethod
    def setUpClass(cls):
        cls.asset, cls.raw = _load_asset()

    def setUp(self):
        # validate 模块使用模块级全局 ERRORS/WARNS，跨用例会累积，必须每次清空
        VALIDATE.ERRORS.clear()
        VALIDATE.WARNS.clear()

    # ------------------------------------------------------------------
    # 1. 资产文件存在 + json 可解析 + total_count 自洽
    # ------------------------------------------------------------------
    def test_asset_file_exists_and_parses(self):
        self.assertTrue(ASSET_PATH.is_file(), f"资产文件不存在: {ASSET_PATH}")

    def test_meta_total_count_matches_tropes_length(self):
        meta = self.asset.get("meta", {})
        tropes = self.asset.get("tropes", [])
        self.assertIn("total_count", meta, "meta 缺少 total_count 字段")
        self.assertEqual(
            meta["total_count"], len(tropes),
            f"meta.total_count({meta['total_count']}) != len(tropes)({len(tropes)})",
        )
        self.assertEqual(meta["total_count"], 8, "首版 total_count 应为 8")

    # ------------------------------------------------------------------
    # 2. abstraction_level ∈ {structural, scenic}，且无 verbal
    # ------------------------------------------------------------------
    def test_abstraction_level_no_verbal(self):
        for i, t in enumerate(self.asset.get("tropes", [])):
            lvl = t.get("abstraction_level")
            self.assertIn(
                lvl, ALLOWED_ABSTRACTION,
                f"tropes[{i}].abstraction_level 为 {lvl!r}，须 ∈ {sorted(ALLOWED_ABSTRACTION)}（verbal 一律拒收）",
            )

    # ------------------------------------------------------------------
    # 3. payoff_strength 为 1-10 整数
    # ------------------------------------------------------------------
    def test_payoff_strength_int_1_to_10(self):
        for i, t in enumerate(self.asset.get("tropes", [])):
            eff = t.get("effectiveness", {})
            ps = eff.get("payoff_strength")
            self.assertIsInstance(
                ps, int,
                f"tropes[{i}].effectiveness.payoff_strength 应为 int，实际 {type(ps).__name__}",
            )
            self.assertTrue(
                1 <= ps <= 10,
                f"tropes[{i}].effectiveness.payoff_strength 为 {ps}，须 ∈ [1, 10]",
            )

    # ------------------------------------------------------------------
    # 4. skeleton 四键齐全 + escalation 非空
    # ------------------------------------------------------------------
    def test_skeleton_has_four_keys_and_nonempty_escalation(self):
        for i, t in enumerate(self.asset.get("tropes", [])):
            sk = t.get("skeleton", {})
            for k in SKELETON_KEYS:
                self.assertIn(
                    k, sk,
                    f"tropes[{i}].skeleton 缺 '{k}' 键",
                )
            esc = sk.get("escalation")
            self.assertIsInstance(
                esc, list,
                f"tropes[{i}].skeleton.escalation 应为数组，实际 {type(esc).__name__}",
            )
            self.assertTrue(
                len(esc) > 0,
                f"tropes[{i}].skeleton.escalation 为空（爽感靠递进层数）",
            )

    # ------------------------------------------------------------------
    # 5. category ∈ 8 个合法枚举值
    # ------------------------------------------------------------------
    def test_category_in_enum(self):
        for i, t in enumerate(self.asset.get("tropes", [])):
            cat = t.get("category")
            self.assertIn(
                cat, CATEGORY_ENUM,
                f"tropes[{i}].category 为 {cat!r}，须 ∈ {sorted(CATEGORY_ENUM)}",
            )

    # ------------------------------------------------------------------
    # 6. validate_trope_library(asset) 返回 ERRORS 为空
    # ------------------------------------------------------------------
    def test_validate_trope_library_no_errors(self):
        VALIDATE.validate_trope_library(self.asset)
        self.assertEqual(
            VALIDATE.ERRORS, [],
            f"validate_trope_library 产出硬错误:\n{chr(10).join(VALIDATE.ERRORS)}",
        )

    # ------------------------------------------------------------------
    # 7. 全库不存在 contains_verbatim == true
    # ------------------------------------------------------------------
    def test_no_contains_verbatim_true(self):
        for i, t in enumerate(self.asset.get("tropes", [])):
            cv = t.get("contains_verbatim")
            self.assertNotEqual(
                cv, True,
                f"tropes[{i}].contains_verbatim == true，一律拒收",
            )

    # ------------------------------------------------------------------
    # 8. id 非空且唯一（资产自洽补充校验）
    # ------------------------------------------------------------------
    def test_trope_ids_nonempty_and_unique(self):
        ids = []
        for i, t in enumerate(self.asset.get("tropes", [])):
            tid = t.get("id")
            self.assertTrue(
                tid and isinstance(tid, str),
                f"tropes[{i}].id 缺失或非字符串: {tid!r}",
            )
            ids.append(tid)
        self.assertEqual(
            len(ids), len(set(ids)),
            f"trope id 存在重复: {ids}",
        )


if __name__ == "__main__":
    unittest.main()
