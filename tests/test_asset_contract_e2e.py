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


def distill_gate():
    """延迟取 ``distill`` 模块（写盘门禁 ``write_distilled_outputs``）。

    **不能**在模块级加载：``distill.py`` 模块级 ``from validate import
    validate_asset_data`` 会把「当时那份」``validate`` 实例绑定进自己的全局，而
    ``tests/test_distill.py`` 的 ``_load`` 会**替换** ``sys.modules["validate"]``。
    若在模块级加载 ``distill``，``test_distill_gate`` 中「门禁与断言必须共享同一个
    validate 实例」的前置断言就会误报（两条 import 链绑到了不同实例）。
    延迟到用例执行期取模块即可保证与最终实例一致，且与运行顺序无关。
    """
    return _load("distill")

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


def memory_valid_voice_card() -> dict:
    """内存**结构合法**的单书 voice-card（正向对照，不落盘）。

    覆盖单书卡契约的全部必填项：``meta`` 的 source_title / genre / extracted_at /
    sample_chapters / confidence，以及 narration / dialogue / emotion_handling /
    banned 四个必填段（另含 imagery / provenance，避免落到硬错误）。

    存在的意义是**反向排除「校验器一律拒绝」**：下面的反向断言只能证明「蒸馏卡
    过不了单书卡校验」，若没有这张合法卡做对照，同样的断言在「校验器对任何输入
    都报错」的实现下也会通过。
    """
    return {
        "meta": {
            "source_title": "fixture-book",
            "genre": "campus-redemption",
            "extracted_at": "2026-09-16T00:00:00Z",
            "sample_chapters": [1, 2, 3],
            "confidence": 0.8,
        },
        "narration": {
            "pov": "第三人称限知",
            "sentence_rhythm": {
                "avg_length": 18,
                "short_ratio": 0.4,
                "long_ratio": 0.2,
                "burst_pattern": "短句起手，长句收束",
            },
            "paragraph": {"avg_lines": 3, "single_line_para_ratio": 0.3},
        },
        "dialogue": {
            "dialogue_ratio": 0.3,
            "subtext_level": "偶有潜台词",
            "character_voices": [],
        },
        "emotion_handling": {
            "mode": "混合式",
            "examples": [
                {"pattern": "动作外化收束情绪", "anti_pattern": "直白喊出情绪"}
            ],
        },
        "imagery": {
            "high_freq_metaphor_domains": ["雨", "光"],
            "sensory_preference": {"视觉": 0.5, "听觉": 0.5},
            "signature_devices": ["通感"],
        },
        "banned": {"never_used_words": ["竟然"]},
        "provenance": {"contains_verbatim": False},
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


def partial_memory_assets() -> dict:
    """**部分覆盖**题材的内存资产：三本书只有 voice-card，其余三维无任何贡献书。"""
    full = memory_assets()
    return {dim: (full[dim] if dim == "voice-card" else {}) for dim in CORE.DIMENSIONS}


def distill_partial_in_memory(genre: str = GENRE) -> dict:
    """部分覆盖题材的真实 ``distill_genre`` 编排（不读、不写真实 assets/）。"""
    with mock.patch.object(
        CORE,
        "collect_assets",
        side_effect=lambda *args, **kwargs: copy.deepcopy(partial_memory_assets()),
    ):
        return CORE.distill_genre(genre)


def _link_file(target: Path, link: Path) -> bool:
    """尝试创建指向 target 的文件符号链接；环境不支持时返回 False。

    与 ``tests/test_chapter_loader.py`` 同写法：**只有 ``os.symlink`` 在 try 内**，
    调用方据返回值选择分支——绝不把 ``yield`` 放进 ``try``（否则 with 体内抛出的
    ``OSError`` / ``AttributeError`` 会被 ``except`` 吞掉，并让 with 体二次执行）。
    """
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError, AttributeError):
        return False
    return True


@contextlib.contextmanager
def physical_alias(target: Path, alias: Path):
    """构造「两个不同文件名指向同一物理文件」的临时 fixture。

    优先创建真实文件符号链接；环境不支持（Windows 需开发者模式/特权）时退化为
    确定性等价 fixture：把 alias 的物理路径 mock 成 target 的物理路径——
    ``_resolve_physical`` 是 loader 判定「同一物理文件」的唯一依据，两条分支
    走的检测逻辑完全一致。
    """
    if _link_file(target, alias):
        yield
        return

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
        """反向锁定：若把蒸馏卡当单书 voice-card 校验，必然报出**单书卡必填段缺失**。

        这正是历史 bug 的形态（蒸馏资产套用单书卡校验 → 整份 REJECT）。

        断言的是**具体缺失字段**而不是「errors 非空」：后者对任意残缺 dict 都成立，
        无法区分「校验器按单书卡契约精确拒绝」与「校验器一律拒绝」。
        """
        required_sections = ("narration", "dialogue", "emotion_handling", "banned")
        for dimension in CORE.DIMENSIONS:
            with self.subTest(dimension=dimension):
                errors, _ = VALIDATE.validate_asset_data(
                    "voice-card", self.distilled[dimension]
                )
                joined = "\n".join(errors)
                for section in required_sections:
                    self.assertIn(
                        f"缺少必填字段 '{section}'",
                        joined,
                        f"{dimension} 蒸馏卡按单书卡校验应报缺少 '{section}'：{errors}",
                    )

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
# 1b. 部分覆盖题材（I-1）：某维度无贡献书时仍必须写出四个文件
# ---------------------------------------------------------------------------

class TestPartialCoverageGenre(unittest.TestCase):
    """I-1 回归：题材只覆盖部分维度时，四维蒸馏产物仍全部通过门禁并落盘。

    修复前 ``validate_distilled`` 对 ``meta.source_books`` 用 ``min_items=1``，而
    ``_empty_distilled`` 在「该维度无任何贡献书」时产出 ``source_books: []``——
    ``write_distilled_outputs`` 对四维全量校验，任一空维度即抛 ``ValueError``，
    部分覆盖题材从「可蒸馏」变成整体失败、零文件写出。
    """

    def test_empty_dimensions_pass_validation(self):
        """空维度必须零硬错误，且保持 ``source_books=[] / books_count=0 / rules=[]``。"""
        distilled = distill_partial_in_memory()
        self.assertEqual(sorted(distilled), sorted(CORE.DIMENSIONS))

        for dim in CORE.DIMENSIONS:
            if dim == "voice-card":
                continue
            with self.subTest(dimension=dim):
                payload = distilled[dim]
                self.assertEqual(payload["meta"]["source_books"], [])
                self.assertEqual(payload["meta"]["books_count"], 0)
                self.assertEqual(payload["rules"], [])
                errors, _ = VALIDATE.validate_asset_data("distilled", payload)
                self.assertEqual(errors, [], f"{dim} 空维度硬错误: {errors}")

    def test_non_empty_dimension_keeps_its_books(self):
        """对照：有贡献书的维度仍必须带出三本书与规则（豁免不得放大）。"""
        voice = distill_partial_in_memory()["voice-card"]
        self.assertEqual(sorted(voice["meta"]["source_books"]), sorted(BOOKS))
        self.assertEqual(voice["meta"]["books_count"], len(BOOKS))
        self.assertTrue(voice["rules"], "voice-card 有资产，应产出规则")

    def test_partial_coverage_still_writes_four_files(self):
        """端到端：部分覆盖题材必须写出四个文件（不读不写真实 assets/）。"""
        distilled = distill_partial_in_memory()
        with tempfile.TemporaryDirectory() as tmp:
            written = distill_gate().write_distilled_outputs(distilled, Path(tmp))
            self.assertEqual(len(written), 4, f"应写出四个文件: {written}")
            self.assertTrue(all(Path(p).is_file() for p in written))
            names = sorted(Path(p).name for p in written)
            self.assertEqual(
                names, sorted(f"{GENRE}-{d}-distilled.json" for d in CORE.DIMENSIONS)
            )


# ---------------------------------------------------------------------------
# 2. 正向对照：合法单书卡必须通过——证明校验器不是「一律拒绝」
# ---------------------------------------------------------------------------

class TestSingleBookVoiceCardPositiveControl(unittest.TestCase):
    """正向对照：结构合法的单书卡零硬错误通过。

    没有这条对照，上面所有「errors 非空」的反向断言都无法排除「校验器把任何
    输入都判错」这一可能；有了它，反向断言才真正锁定「拒绝的原因是缺单书卡
    必填字段」。卡片完全在内存构造，不读真实 assets。
    """

    def test_valid_single_book_voice_card_passes(self):
        """结构合法的单书卡：errors == []，且 kind 自证为 voice-card。"""
        card = memory_valid_voice_card()
        errors, _ = VALIDATE.validate_asset_data("voice-card", card)
        self.assertEqual(errors, [], f"合法单书卡不应有硬错误: {errors}")
        self.assertEqual(
            VALIDATE.auto_kind(card, "fixture-voice-card.json"),
            "voice-card",
            "结构合法的单书卡必须被判为 voice-card",
        )

    def test_missing_required_section_is_the_reason(self):
        """判别力对照：从合法卡里删掉 narration，报错必须精确指向该字段。

        证明校验器「通过」与「拒绝」之间的差别确实来自必填段本身。
        """
        card = memory_valid_voice_card()
        del card["narration"]
        errors, _ = VALIDATE.validate_asset_data("voice-card", card)
        self.assertIn("缺少必填字段 'narration'", "\n".join(errors))


# ---------------------------------------------------------------------------
# 3. genre-prose-card-index：独立 kind，不得当文风卡消费
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
        """反向锁定：按单书卡 / 文风卡契约校验索引必然报出**该类卡的必填项缺失**。

        同样断言具体缺失字段而非「errors 非空」——索引只有 ``cards`` 顶层键，
        任意卡契约都会报错，笼统的「非空」断言无法证明拒绝理由正确。
        """
        index = memory_index()
        expected_missing = {
            "voice-card": (
                "缺少必填字段 'meta'",
                "缺少必填字段 'narration'",
                "缺少必填字段 'dialogue'",
                "缺少必填字段 'emotion_handling'",
                "缺少必填字段 'banned'",
            ),
            "genre-prose-card": (
                "缺少必填字段 'language_rules'",
                "缺少必填字段 'prose'",
            ),
        }
        for kind, needles in expected_missing.items():
            with self.subTest(kind=kind):
                errors, _ = VALIDATE.validate_asset_data(kind, index)
                joined = "\n".join(errors)
                for needle in needles:
                    self.assertIn(
                        needle,
                        joined,
                        f"索引按 {kind} 校验应报 {needle}：{errors}",
                    )

    def test_service_boundary_rejects_index_as_prose_card(self):
        from gui.services import ServiceError, assert_asset_kind

        with self.assertRaises(ServiceError) as ctx:
            assert_asset_kind(memory_index(), "prose_card", INDEX_FILENAME)
        self.assertEqual(ctx.exception.code, 400)


# ---------------------------------------------------------------------------
# 4. chapter_loader 诊断结构（临时目录，不碰真实小说正文）
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
        """不存在的路径：结构仍完整（files / ignored / duplicates / aliases 四键齐备）且为空。"""
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


class TestPhysicalAliasFixture(unittest.TestCase):
    """M-9 回归：``physical_alias`` 只允许把 ``os.symlink`` 放进 ``try``。

    修复前 ``yield`` 被包在 ``try`` 内，``with`` 体内抛出的 ``OSError`` /
    ``AttributeError`` 会被 ``except`` 吞掉，随后走降级分支并**二次执行** ``with``
    体——真实失败被掩盖，断言还会在错误的执行次数上成立。

    用 mock 强制走「symlink 成功」分支，使本用例不依赖本机符号链接权限。
    """

    def test_body_exception_propagates_and_body_runs_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "chapter-001.txt"
            target.write_text("第一章正文", encoding="utf-8")
            alias = root / "chapter-002.txt"
            runs = []

            with mock.patch("os.symlink"):  # 强制 symlink 成功，不碰真实符号链接权限
                with self.assertRaises(OSError):
                    with physical_alias(target, alias):
                        runs.append(1)
                        raise OSError("with 体内的真实失败")

            self.assertEqual(runs, [1], "with 体只允许执行一次（不得被吞异常后二次执行）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
