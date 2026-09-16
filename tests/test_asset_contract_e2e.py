#!/usr/bin/env python3
"""资产契约端到端回归（2026-09-16 高优先级修复 · Task 8 收尾）。

把前面各任务单点修复串成一条**端到端链路**，确认它们在真实调用顺序下仍然成立：

    distill_genre（内存资产）
      → validate_asset_data("distilled", …)      ← Task 1 专用契约
      → render_distilled / render_all_distilled  ← 渲染不崩溃
      → inject.build_prompt(distilled=…)         ← 蒸馏段真的进了 prompt
      → gui.services.assert_asset_kind           ← 服务边界拒绝「蒸馏当单书卡」打分

    auto_kind(index) == "genre-prose-card-index" ← Task 5 index 独立 kind
    chapter_loader.discover_chapter_files        ← Task 2 诊断结构（files/ignored/duplicates/aliases）

设计约束（brief 明确要求）：
    * **不读、不写任何真实资产**——四维资产在内存里构造，`collect_assets` 被 patch
      掉，因此走的是真实的 `distill_genre` 编排代码，但不碰 `assets/`；
    * 章节相关用例全部落在 `tempfile.TemporaryDirectory()` 里；
    * 诊断键用**子集断言**（`<=`）而非集合相等——键集合会随版本扩展；
    * 不依赖网络、LLM 与任何服务进程。

用法：
  python -m unittest discover -s tests -p "test_asset_contract_e2e.py" -v
  python run_tests.py            # 自动 discover 本文件（pattern test_*.py）
"""
import contextlib
import copy
import importlib.util
import os
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
    """按文件名从 scripts/ 动态加载模块，同一源文件只加载一次。

    与 test_distill_gate 同模式：复用 ``sys.modules`` 中同路径的既有实例，
    避免同一文件被加载成两份导致类身份/全局状态分叉（``inject`` 模块级
    ``from distill_render import render_distilled`` 也依赖 ``sys.modules`` 唯一）。
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
RENDER = _load("distill_render")
VALIDATE = _load("validate")
LOADER = _load("chapter_loader")
INJECT = _load("inject")

GENRE = "e2e-fixture"
BOOKS = ("book_a", "book_b", "book_c")

INDEX_FILENAME = "genre-prose-card-index.json"


# ---------------------------------------------------------------------------
# 内存 fixture（绝不读真实 assets/）
# ---------------------------------------------------------------------------

def memory_voice_card() -> dict:
    """内存单书 voice-card（供 build_prompt 注入用，不落盘）。"""
    return {
        "meta": {"source_title": "fixture-book", "genre": GENRE},
        "narration": {"pov": "第三人称限知"},
        "dialogue": {"character_voices": []},
        "emotion_handling": {"mode": "混合式"},
        "imagery": {},
        "banned": {"never_used_words": ["竟然"]},
    }


def memory_index() -> dict:
    """内存题材文风卡索引（寻址表，非文风卡本身）。"""
    return {
        "_count": 1,
        "_description": "题材文风卡索引：题材中文名 → id / 落库文件名。",
        "cards": {"都市": {"id": "genre-dushi", "file": "genre-prose-card-genre-dushi.json"}},
    }


def memory_assets() -> dict:
    """三本书 × 四维的内存资产，形状对齐 ``assets/*-<dimension>.json``。"""
    assets = {dim: {} for dim in CORE.DIMENSIONS}
    for book in BOOKS:
        assets["voice-card"][book] = {
            "meta": {"source_title": book, "genre": GENRE},
            "narration": {"pov": "第三人称限知"},
            "dialogue": {"character_voices": []},
            "emotion_handling": {"mode": "混合式"},
            "imagery": {},
            "banned": {"never_used_words": ["竟然", "顿时"]},
        }
        assets["craft-card"][book] = {
            "meta": {"source_title": book, "genre": GENRE},
            "craft_analysis": {
                "foreshadowing": {
                    "techniques": [{"name": "三段式钩子", "skeleton": "先抛悬念再揭晓"}]
                }
            },
            "craft_summary": {"top_3_strengths": ["三段式钩子"]},
        }
        assets["structure-obs"][book] = {
            "meta": {"source_title": book, "genre": GENRE, "scope": "full"},
            "aggregate": {
                "hook_type_freq": {"悬念揭示": 3},
                "hook_min_interval": 2,
                "climax_cycle": "3章一次",
                "foreshadow_avg_span": 5,
                "foreshadow_max_span": 9,
                "foreshadow_concurrent_open": 2,
            },
            "chapter_analyses": [{"role": "铺垫"}],
        }
        assets["commercial-obs"][book] = {
            "meta": {"source_title": book, "genre": GENRE, "scope": "full"},
            "payoff_density": {
                "per_chapter": 3,
                "per_thousand_words": 1.5,
                "payoff_types": [{"type": "情感回应", "ratio": 7}],
                "buildup_length": 3000,
            },
            "opening_analysis": {"chapter_1": {"common_mistakes": ["开篇堆设定"]}},
            "paywall": {"position_chapter": 20},
        }
    return assets


def distill_in_memory(genre: str = GENRE) -> dict:
    """在内存里跑**真实** ``distill_genre`` 编排，返回 ``{dimension: distilled}``。

    只把 ``collect_assets`` 换成内存资产：编排、对齐、聚合、冲突解决、置信度、
    盲区诊断、schema 组装全部走生产代码；``assets/`` 目录一次都不会被读到。
    """
    with mock.patch.object(
        CORE,
        "collect_assets",
        side_effect=lambda *args, **kwargs: copy.deepcopy(memory_assets()),
    ):
        return CORE.distill_genre(genre)


@contextlib.contextmanager
def physical_alias(target: Path, alias: Path):
    """构造「两个不同文件名指向同一物理文件」的临时 fixture。

    优先创建真实文件符号链接；环境不支持（Windows 需开发者模式/特权）时退化为
    确定性等价 fixture：把 alias 的物理路径 mock 成 target 的物理路径——
    ``_resolve_physical`` 是 loader 判定「同一物理文件」的唯一依据，两条分支
    走的检测逻辑完全一致。
    """
    try:
        os.symlink(target, alias)
        yield
        return
    except (OSError, NotImplementedError, AttributeError):
        pass

    alias.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    real = LOADER._resolve_physical
    target_resolved = real(target)

    def fake(path):
        return target_resolved if Path(path) == alias else real(path)

    with mock.patch.object(LOADER, "_resolve_physical", side_effect=fake):
        yield


# ---------------------------------------------------------------------------
# 1. distilled 端到端：校验 → 渲染 → 注入 → 服务边界
# ---------------------------------------------------------------------------

class TestDistilledEndToEnd(unittest.TestCase):
    """distilled 全链路：专用校验通过、不被单书卡契约接受、渲染可注入。"""

    @classmethod
    def setUpClass(cls):
        cls.distilled = distill_in_memory()

    def test_all_four_dimensions_pass_distilled_validation(self):
        """四维真实蒸馏输出必须零硬错误地通过 distilled 专用契约。"""
        self.assertEqual(sorted(self.distilled), sorted(CORE.DIMENSIONS))
        for dimension in CORE.DIMENSIONS:
            with self.subTest(dimension=dimension):
                payload = self.distilled[dimension]
                errors, _ = VALIDATE.validate_asset_data("distilled", payload)
                self.assertEqual(errors, [], f"{dimension} 蒸馏输出硬错误: {errors}")
                # 内容自证 kind：不得再被兜底判为 voice-card。
                self.assertEqual(
                    VALIDATE.auto_kind(payload, f"{GENRE}-{dimension}-distilled.json"),
                    "distilled",
                )

    def test_distilled_is_rejected_by_single_book_contract(self):
        """反向锁定：若把蒸馏卡当单书 voice-card 校验，必然报硬错误。

        这正是历史 bug 的形态（蒸馏资产套用单书卡校验 → 整份 REJECT）。
        """
        for dimension in CORE.DIMENSIONS:
            with self.subTest(dimension=dimension):
                errors, _ = VALIDATE.validate_asset_data(
                    "voice-card", self.distilled[dimension]
                )
                self.assertTrue(errors, "蒸馏卡不应能通过单书 voice-card 校验")

    def test_render_distilled_and_render_all(self):
        """渲染：单维含标记；四维合渲染不崩溃且带出蒸馏段。"""
        voice = self.distilled["voice-card"]
        rendered = RENDER.render_distilled(voice)
        self.assertIn("蒸馏规则", rendered)
        self.assertIn("必守", rendered)

        all_text = RENDER.render_all_distilled(self.distilled)
        self.assertIsInstance(all_text, str)
        self.assertIn("蒸馏规则", all_text)

    def test_build_prompt_injects_distilled_section(self):
        """inject.build_prompt(distilled=…) 必须把蒸馏段注入 prompt。"""
        voice = memory_voice_card()
        distilled = self.distilled["voice-card"]

        baseline = INJECT.build_prompt(voice, None, None)
        self.assertNotIn("蒸馏规则", baseline, "未传 distilled 时不应出现蒸馏段")

        prompt = INJECT.build_prompt(voice, None, None, distilled=distilled)
        self.assertIn("蒸馏规则", prompt)
        # 蒸馏段定位在叙述层之前（§0 注入点约定）。
        self.assertLess(prompt.index("蒸馏规则"), prompt.index("## 一、叙述层"))

    def test_service_boundary_rejects_distilled_before_scoring(self):
        """服务边界：蒸馏卡当单书 voice 传入必须在打分前被拒（400）。"""
        from gui.services import ServiceError, assert_asset_kind

        with self.assertRaises(ServiceError) as ctx:
            assert_asset_kind(
                self.distilled["voice-card"], "voice", "fixture-voice-card.json"
            )
        self.assertEqual(ctx.exception.code, 400)


# ---------------------------------------------------------------------------
# 2. genre-prose-card-index：独立 kind，不得当文风卡消费
# ---------------------------------------------------------------------------

class TestIndexKindContract(unittest.TestCase):
    """索引是寻址表，不是文风卡；auto_kind 必须给出专用 kind。"""

    def test_index_is_not_a_prose_card(self):
        index = memory_index()
        kind = VALIDATE.auto_kind(index, INDEX_FILENAME)
        self.assertEqual(kind, "genre-prose-card-index")
        self.assertNotEqual(kind, "voice-card")

        errors, _ = VALIDATE.validate_asset_data("genre-prose-card-index", index)
        self.assertEqual(errors, [], f"合法索引不应有硬错误: {errors}")
        self.assertFalse([e for e in errors if "voice-card" in e])

    def test_index_is_rejected_by_card_contracts(self):
        """反向锁定：按单书卡 / 文风卡契约校验索引必然报硬错误。"""
        index = memory_index()
        for kind in ("voice-card", "genre-prose-card"):
            with self.subTest(kind=kind):
                errors, _ = VALIDATE.validate_asset_data(kind, index)
                self.assertTrue(errors, f"索引不应能通过 {kind} 校验")

    def test_service_boundary_rejects_index_as_prose_card(self):
        from gui.services import ServiceError, assert_asset_kind

        with self.assertRaises(ServiceError) as ctx:
            assert_asset_kind(memory_index(), "prose_card", INDEX_FILENAME)
        self.assertEqual(ctx.exception.code, 400)


# ---------------------------------------------------------------------------
# 3. chapter_loader 诊断结构（临时目录，不碰真实小说正文）
# ---------------------------------------------------------------------------

class TestChapterLoaderDiagnostics(unittest.TestCase):
    """discover_chapter_files 的诊断键与冲突记录。"""

    def test_diagnostics_keys_are_superset_of_contract(self):
        """诊断键用子集断言：键集合会随版本扩展，不得用集合相等锁死。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "chapter-001.txt").write_text("第一章", encoding="utf-8")
            (root / "notes.txt").write_text("不是章节", encoding="utf-8")
            backup = root / "_备份"
            backup.mkdir()
            (backup / "chapter-009.txt").write_text("旧稿", encoding="utf-8")

            diag = LOADER.discover_chapter_files(root)

            self.assertTrue(
                {"files", "ignored", "duplicates", "aliases"} <= set(diag),
                f"诊断结构缺少约定键: {sorted(diag)}",
            )
            self.assertEqual(set(diag["files"]), {1})
            self.assertIn(root / "notes.txt", diag["ignored"])
            self.assertIn(backup / "chapter-009.txt", diag["ignored"])
            self.assertNotIn(root / "chapter-001.txt", diag["ignored"])
            self.assertEqual(diag["duplicates"], {})
            self.assertEqual(diag["aliases"], {})

    def test_duplicate_chapter_number_is_recorded_not_silently_overwritten(self):
        """同章号多文件：记入 duplicates 并从 files 移除，加载时显式报错。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "第001章.txt"
            second = root / "chapter-001.txt"
            first.write_text("A", encoding="utf-8")
            second.write_text("B", encoding="utf-8")

            diag = LOADER.discover_chapter_files(root)
            self.assertEqual(list(diag["duplicates"]), [1])
            self.assertEqual(sorted(diag["duplicates"][1]), sorted([first, second]))
            self.assertNotIn(1, diag["files"], "冲突章号不得留在 files 中")

            with self.assertRaises(LOADER.ChapterLoadError) as ctx:
                LOADER.load_chapter_texts(root)
            self.assertEqual(ctx.exception.chapter_number, 1)

    def test_physical_alias_is_recorded_and_rejected(self):
        """同一物理文件被两个章号引用：记入 aliases，加载抛 ChapterAliasError。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "chapter-001.txt"
            target.write_text("第一章正文", encoding="utf-8")
            alias = root / "chapter-002.txt"

            with physical_alias(target, alias):
                diag = LOADER.discover_chapter_files(root)

            self.assertEqual(len(diag["aliases"]), 1)
            _physical, by_number = next(iter(diag["aliases"].items()))
            self.assertEqual(sorted(by_number), [1, 2])
            self.assertNotIn(1, diag["files"])
            self.assertNotIn(2, diag["files"])

            with physical_alias(target, alias):
                with self.assertRaises(LOADER.ChapterAliasError):
                    LOADER.load_chapter_texts(root)

    def test_missing_path_returns_empty_diagnostics(self):
        """不存在的路径：结构仍完整（三键齐备）且为空。"""
        with tempfile.TemporaryDirectory() as tmp:
            diag = LOADER.discover_chapter_files(Path(tmp) / "不存在")
            self.assertTrue(
                {"files", "ignored", "duplicates", "aliases"} <= set(diag),
                f"诊断结构缺少约定键: {sorted(diag)}",
            )
            self.assertEqual(diag["files"], {})
            self.assertEqual(diag["ignored"], [])
            self.assertEqual(diag["duplicates"], {})
            self.assertEqual(diag["aliases"], {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
