# novel-lab 高优输入与资产边界修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 novel-lab 的资产类型误判、章节递归扫描覆盖、中文对白引号漏识别，并用回归测试把这些输入边界固定下来。

**Architecture:** 将资产校验拆成“单书卡 / distilled / prose-card-index”三个明确 kind，保留既有 `validate.py` CLI 兼容并增加纯数据校验接口；新增一个无第三方依赖的章节加载器，所有 QC/逻辑/全书质检入口委托它加载文本；在 `metrics.py` 提供唯一对白字符计数函数，`chapter_check.py` 与量化指标只共享分子抽取逻辑、不改变各自分母和评分权重。GUI 资产索引把 distilled/index 分离展示，单书评分拒绝错误 kind，蒸馏仍通过专用渲染器注入。

**Tech Stack:** Python 3.13 标准库 `unittest`/`pathlib`/`json`/`re`；现有 SQLite GUI 持久化；Vite + React + TypeScript；不增加第三方 Python 依赖，不调用网络或 LLM。

**Spec:** `docs/superpowers/specs/2026-09-16-novel-lab-high-priority-fixes-design.md`

## Global Constraints

- `scripts/` 与 `gui/` 后端只能使用 Python 标准库；不得引入 `psutil`、`jsonschema`、`pytest` 等第三方包。
- 所有测试使用临时目录或内存对象，不触碰真实 `assets/`、`gui_state/`、`gui/state/`、用户小说目录或个人目录。
- 使用受管解释器：`C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B`。
- 当前全量测试基线是 **401 个用例**，不是历史文档中的 373/397；每个任务结束都必须运行对应专项测试，收尾必须运行全量测试。
- 不修改现有小说正文或生产资产 JSON 内容；不得重建本轮之外的便携版 `build/dist/novel-lab-portable-v1.0.0`。
- 资产 kind 的新值 `distilled`、`prose_card_index` 仅用于 `assets` 表/索引；不得加入 `migrate.GENRE_KIND_ENUM`，因为它只表示题材来源 kind。
- 保持 `logic_check._load_texts` 对传入 `novel_dir` 时同时探测 `novel_dir` 与 `novel_dir/chapters` 的既有语义。
- 共享对白抽取只统一“引号内字符数”分子；`metrics.py` 继续用去空白总字符作分母，`chapter_check.py` 继续用汉字数作分母。

---

### Task 1: 建立 distilled 与 index 的专用校验契约

**Files:**
- Create: `schema/distilled.schema.json`
- Create: `schema/genre-prose-card-index.schema.json`
- Modify: `scripts/validate.py:36-42, 110-253, 564-606, 609-649`
- Create: `tests/test_validate.py`

**Interfaces:**
- Produces `validate_asset_data(kind: str, data: dict) -> tuple[list[str], list[str]]`，返回不带颜色前缀的硬错误/警告文本；该接口不得依赖调用方读取全局 `ERRORS/WARNS`。
- Produces `validate_distilled(d: dict) -> None` 与 `validate_genre_prose_card_index(d: dict) -> None`，沿用现有 `err()`/`warn()` 累积机制供 CLI 使用。
- Changes `auto_kind(d: dict, filename: str | None = None) -> str`；`filename` 可选，旧的单参数调用继续有效；CLI 必须把 `path.name` 传入以识别 index。
- Registers `distilled` 与 `genre-prose-card-index` in `DISPATCH` and CLI `--kind` choices.

- [ ] **Step 1: 写失败测试，先锁定 kind 与纯数据返回接口**

在 `tests/test_validate.py` 中按项目现有动态加载方式加载 `scripts/validate.py`，加入以下行为测试：

```python
class TestAssetKindDetection(unittest.TestCase):
    def test_distilled_is_not_voice_card(self):
        d = {
            "meta": {"dimension": "voice-card", "id": "g-voice-card-distilled",
                     "schema_version": "1.0", "genre": "campus-redemption",
                     "source_books": ["a", "b", "c"], "books_count": 3},
            "rules": [], "blindspots": [], "stats": {},
        }
        self.assertEqual(validate.auto_kind(d, "g-voice-card-distilled.json"), "distilled")

    def test_index_is_distinct_kind(self):
        self.assertEqual(
            validate.auto_kind({"_count": 1, "_description": "x", "cards": {}},
                               "genre-prose-card-index.json"),
            "genre-prose-card-index",
        )

class TestDistilledValidation(unittest.TestCase):
    def test_current_shape_passes(self):
        errors, warns = validate.validate_asset_data("distilled", self.sample)
        self.assertEqual(errors, [])

    def test_rule_dimension_mismatch_rejects(self):
        bad = copy.deepcopy(self.sample)
        bad["rules"] = [{"id": "x", "dimension": "craft-card", "field": "x",
                          "kind": "hard", "books_count": 3, "value": None,
                          "confidence": 0.8, "conflict": False,
                          "over_generalized": False, "blindspot_books": []}]
        errors, _ = validate.validate_asset_data("distilled", bad)
        self.assertTrue(any("dimension" in e for e in errors))

    def test_index_shape_passes(self):
        errors, _ = validate.validate_asset_data(
            "genre-prose-card-index",
            {"_count": 1, "_description": "x",
             "cards": {"都市": {"id": "genre-dushi", "file": "genre-prose-card-genre-dushi.json"}}},
        )
        self.assertEqual(errors, [])
```

增加测试断言：四个当前 distilled 文件的结构通过 `validate_asset_data("distilled", ...)`；`genre-prose-card-index.json` 的索引结构不触发 voice-card 错误；一个缺 `meta.dimension` 或缺规则必填键的对象返回硬错误。

- [ ] **Step 2: 运行专项测试确认当前实现失败**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_validate.py" -v
```

Expected: FAIL，当前没有 `validate_asset_data`、`distilled` kind 和 index kind。

- [ ] **Step 3: 添加 schema 文档和手工校验器**

在 `schema/distilled.schema.json` 记录顶层 `meta/rules/blindspots/stats` 契约；`meta.dimension` 枚举为 `voice-card`、`craft-card`、`structure-obs`、`commercial-obs`；规则项 required 为 `id`、`dimension`、`field`、`kind`、`books_count`、`value`、`confidence`、`conflict`、`over_generalized`、`blindspot_books`。在 `schema/genre-prose-card-index.schema.json` 记录 `_count`、`_description`、`cards` 与 card 的 `id/file`。

在 `scripts/validate.py`：

1. 增加 `DISTILLED_DIMENSIONS`、`DISTILLED_RULE_REQUIRED` 常量。
2. 增加 `validate_distilled()`，检查顶层字段、meta 类型/枚举、rules 中每条规则的类型与 dimension 一致性、confidence 范围、bool 字段、blindspot_books 列表。
3. 增加 `validate_genre_prose_card_index()`，检查 `_count` 为非负整数、`_description` 为字符串、`cards` 为 dict；每个卡条目必须有非空字符串 `id` 与 `file`。
4. 增加 `validate_asset_data(kind, data)`：保存当前全局错误/警告，调用 `reset()` 与对应 DISPATCH，复制结果后恢复调用前全局状态，避免蒸馏门禁污染后续校验。
5. 将 `auto_kind` 改为可选 `filename`；先检查显式 `meta.kind == "genre-prose-card"`，再检查 filename 含 `genre-prose-card-index` 且有 `cards`，再检查 distilled 的 `meta.dimension/rules/stats`，最后走既有 hints 与 voice-card 回退。
6. CLI `main()` 传入 `path.name`，输出新 kind；`--kind` choices 加两项。

- [ ] **Step 4: 运行专项测试确认通过**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_validate.py" -v
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B C:/Users/monesy/niko/novel-lab/novel.py 校验 C:/Users/monesy/niko/novel-lab/assets/campus-redemption-voice-card-distilled.json
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B C:/Users/monesy/niko/novel-lab/novel.py 校验 C:/Users/monesy/niko/novel-lab/assets/genre-prose-card-index.json
```

Expected: 专项测试 PASS；两条 CLI 命令分别输出 `校验类型: distilled` 与 `校验类型: genre-prose-card-index`，退出码为 0。

- [ ] **Step 5: 提交独立变更**

```text
git -C C:/Users/monesy/niko/novel-lab add schema/distilled.schema.json schema/genre-prose-card-index.schema.json scripts/validate.py tests/test_validate.py
git -C C:/Users/monesy/niko/novel-lab commit -m "fix: add dedicated distilled asset validation"
```

---

### Task 2: 新增统一章节加载器并接入三条后端检测入口

**Files:**
- Create: `scripts/chapter_loader.py`
- Modify: `scripts/book_quality.py:330-353`
- Modify: `scripts/qc.py:100-114`
- Modify: `scripts/logic_check.py:71-90`
- Create: `tests/test_chapter_loader.py`
- Modify: `tests/test_regressions.py` only if an existing loader regression assertion needs import relocation

**Interfaces:**
- Produces `ChapterLoadError(ValueError)` with `source`, `chapter_number`, and `candidates` attributes.
- Produces `discover_chapter_files(source: str | Path) -> dict` returning `{"files": {int: Path}, "ignored": list[Path], "duplicates": dict[int, list[Path]]}`; this is the diagnostic API and is not optional once implemented.
- Produces `load_chapter_texts(source: str | Path) -> dict[int, str]`; it raises `ChapterLoadError` for same-number collisions and `OSError`/`UnicodeError` with the offending path.
- Preserves `logic_check._load_texts(source)` as a compatibility wrapper that returns the dict and retains the `source/chapters` dual-root behavior.

- [ ] **Step 1: 写失败测试覆盖排除、冲突和双根路径**

在 `tests/test_chapter_loader.py` 使用 `tempfile.TemporaryDirectory()` 创建：

```python
class TestChapterLoader(unittest.TestCase):
    def test_backup_is_ignored(self):
        root = Path(self.tmp.name)
        (root / "第001章.txt").write_text("正文", encoding="utf-8")
        (root / "_备份").mkdir()
        (root / "_备份" / "第001章_改前.txt").write_text("备份", encoding="utf-8")
        loaded = chapter_loader.load_chapter_texts(root)
        self.assertEqual(loaded, {1: "正文"})

    def test_same_number_non_backup_files_raise(self):
        root = Path(self.tmp.name)
        (root / "第001章.txt").write_text("A", encoding="utf-8")
        (root / "chapter-001.txt").write_text("B", encoding="utf-8")
        with self.assertRaises(chapter_loader.ChapterLoadError) as ctx:
            chapter_loader.load_chapter_texts(root)
        self.assertEqual(ctx.exception.chapter_number, 1)
        self.assertIn("第001章.txt", str(ctx.exception))
        self.assertIn("chapter-001.txt", str(ctx.exception))

    def test_directory_file_without_number_is_ignored(self):
        root = Path(self.tmp.name)
        (root / "notes.txt").write_text("不是章节", encoding="utf-8")
        (root / "chapter-002.txt").write_text("第二章", encoding="utf-8")
        result = chapter_loader.discover_chapter_files(root)
        self.assertEqual(set(result["files"]), {2})
        self.assertIn(root / "notes.txt", result["ignored"])

    def test_novel_dir_and_chapters_are_both_supported(self):
        root = Path(self.tmp.name)
        (root / "chapter-001.txt").write_text("外层", encoding="utf-8")
        (root / "chapters").mkdir()
        (root / "chapters" / "chapter-002.txt").write_text("内层", encoding="utf-8")
        loaded = logic_check._load_texts(root)
        self.assertEqual(loaded, {1: "外层", 2: "内层"})
```

再为 `book_quality.book_quality_check()`、`qc._load_texts()` 增加同号冲突时不返回伪造结果的断言；为 `_备份`、`备份`、`backup`、`.git`、`build`、`dist` 各加一个排除目录参数化用例。

- [ ] **Step 2: 运行专项测试确认失败**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_chapter_loader.py" -v
```

Expected: FAIL，当前没有 `chapter_loader`，现有递归扫描会静默覆盖同章号。

- [ ] **Step 3: 实现 `chapter_loader.py`**

实现以下确定规则：

1. `EXCLUDED_DIR_NAMES = {"_备份", "备份", "backup", ".git", "build", "dist"}`，比较时 `casefold()`。
2. 单文件直接读取；文件名提取不到数字时返回 chapter 1，保持现有单文件兼容。
3. 目录使用 `Path.rglob("*.txt")`，先检查相对路径的每个 parent 名称是否在排除集合；不含数字的文件进入 `ignored`，不进入 files。
4. 按章号把候选路径收集到 list；候选数量大于 1 时创建 `ChapterLoadError`，错误信息列出排序后的相对路径。
5. `load_chapter_texts()` 调用 discover，冲突直接抛错，逐个 `read_text(encoding="utf-8")`，返回按章号排序的普通 dict。
6. `discover_chapter_files()` 的 `files` 仅保留唯一章号；诊断结构完整记录 ignored 与 duplicates，便于未来写入 QC meta。

- [ ] **Step 4: 接入 `book_quality.py`、`qc.py`、`logic_check.py`**

1. `book_quality.book_quality_check()` 用 loader 取得 texts；捕获 `ChapterLoadError`，返回 `{"error": str(exc), "error_type": "chapter_load"}`，保持主函数错误 JSON 兼容。
2. `qc._load_texts()` 直接委托 `chapter_loader.load_chapter_texts()`；`run_qc()` 不吞掉冲突，保持异常让服务层记录错误。
3. `logic_check._load_texts()` 保留“传入 novel_dir 时追加 `source/chapters`”逻辑：先按 loader 规则加载 source，再加载 chapters；同章号冲突按 loader 规则抛错。不要把 novel_dir 简化为只看 chapters。
4. `setting_check.py` 不新增第二套 loader；它继续从 `logic_check` 导入 `_load_texts`，脚本直跑 fallback 也要改为调用 `chapter_loader`，避免两套规则漂移。

- [ ] **Step 5: 运行专项与既有回归测试**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_chapter_loader.py" -v
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_regressions.py" -v
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_logic_check.py" -v
```

Expected: 全部 PASS；递归结构既有测试仍能发现 nested `arc-N` 章节，备份目录不再参与加载。

- [ ] **Step 6: 提交独立变更**

```text
git -C C:/Users/monesy/niko/novel-lab add scripts/chapter_loader.py scripts/book_quality.py scripts/qc.py scripts/logic_check.py scripts/setting_check.py tests/test_chapter_loader.py tests/test_regressions.py
git -C C:/Users/monesy/niko/novel-lab commit -m "fix: make chapter loading deterministic and backup-safe"
```

---

### Task 3: 统一四类引号的对白字符抽取

**Files:**
- Modify: `scripts/metrics.py:20-77`
- Modify: `scripts/chapter_check.py:23-101`
- Create: `tests/test_dialogue_quotes.py`
- Modify: `tests/test_thresholds.py` only to reuse existing chapter-check fixtures if needed

**Interfaces:**
- Produces `metrics.dialogue_char_count(text: str) -> int`.
- `metrics.dialogue_ratio(text)` uses `dialogue_char_count` and retains current denominator.
- `chapter_check.check_dialogue_ratio(text)` imports and uses the same function, retaining current Han-character denominator and score thresholds.

- [ ] **Step 1: 写失败测试锁定四种引号与混合边界**

在 `tests/test_dialogue_quotes.py` 加入：

```python
class TestDialogueQuotes(unittest.TestCase):
    def test_four_quote_pairs_count_same_inner_chars(self):
        texts = [
            '"甲乙"他说。',
            '“甲乙”他说。',
            '「甲乙」他说。',
            '『甲乙』他说。',
        ]
        for text in texts:
            self.assertEqual(metrics.dialogue_char_count(text), 2)

    def test_mixed_pairs_do_not_close_each_other(self):
        self.assertEqual(metrics.dialogue_char_count('「甲“乙”丙」'), 4)

    def test_unclosed_pair_counts_to_end(self):
        self.assertEqual(metrics.dialogue_char_count('「甲乙'), 2)

    def test_chapter_check_recognizes_corner_quotes(self):
        score, detail = chapter_check.check_dialogue_ratio('「甲乙」他说。')
        self.assertNotIn('几乎无对话', detail)
        self.assertGreater(score, 0)
```

另加 `metrics.dialogue_ratio('「甲乙」丙丁') == 0.5` 的明确分母断言，以及 ASCII/中文双引号不改变既有结果的回归断言。

- [ ] **Step 2: 运行专项测试确认当前失败**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_dialogue_quotes.py" -v
```

Expected: FAIL，当前 `chapter_check` 对 `「」`/`『』` 返回 0 对话字符。

- [ ] **Step 3: 实现 `dialogue_char_count`**

在 `metrics.py` 使用显式配对状态：

- `PAIR_CLOSE = {"\"": "\"", "“": "”", "「": "」", "『": "』", "‘": "’"}`。
- 遇到 ASCII `"` 时在打开/关闭间切换；遇到其他开引号时只在当前没有打开引号时打开；遇到当前状态对应的关闭引号时关闭；其他类型的关闭引号作为正文字符但不结束当前对白。
- 打开状态时累计字符，开闭引号本身不累计；文末仍打开则保留已累计数量。
- 删除 `metrics.dialogue_ratio` 内独立的 `inside` 扫描，改为调用新函数。

在 `chapter_check.py` 导入 `from metrics import dialogue_char_count`，将 `dialogue_chars = sum(...)` 替换为 `dialogue_chars = dialogue_char_count(text)`。不得改变 `total`、阈值和返回文案之外的评分逻辑。

- [ ] **Step 4: 运行专项及现有阈值回归**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_dialogue_quotes.py" -v
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_thresholds.py" -v
```

Expected: 全部 PASS，既有阈值判定不改变，新增四类引号用例通过。

- [ ] **Step 5: 提交独立变更**

```text
git -C C:/Users/monesy/niko/novel-lab add scripts/metrics.py scripts/chapter_check.py tests/test_dialogue_quotes.py tests/test_thresholds.py
git -C C:/Users/monesy/niko/novel-lab commit -m "fix: count Chinese dialogue quote styles consistently"
```

---

### Task 4: 给蒸馏写盘流程接入专用 schema 门禁

**Files:**
- Modify: `scripts/distill.py:28-52`
- Modify: `tests/test_distill.py:179-201`
- Create: `tests/test_distill_gate.py`

**Interfaces:**
- Produces `validate_distilled_payload(distilled: dict) -> tuple[list[str], list[str]]` in `scripts/distill.py` as a thin wrapper over Task 1's `validate_asset_data("distilled", ...)`.
- Produces `write_distilled_outputs(distilled_by_dim: dict, assets_dir: Path) -> list[str]`; it validates all dimensions before writing any file and returns written absolute paths.
- Preserves `run_distill(genre, book_names=None) -> dict` return keys `genre`, `written`, `dimensions`.

- [ ] **Step 1: 写失败测试验证“先全量校验，再写盘”**

在 `tests/test_distill_gate.py` 中使用临时 assets 目录和两个 payload：

```python
class TestDistillGate(unittest.TestCase):
    def test_valid_payloads_are_written_after_validation(self):
        payloads = {dim: valid_distilled(dim) for dim in distill_core.DIMENSIONS}
        written = distill.write_distilled_outputs(payloads, self.assets_dir)
        self.assertEqual(len(written), 4)
        self.assertTrue(all(Path(p).is_file() for p in written))

    def test_one_invalid_dimension_writes_nothing(self):
        payloads = {dim: valid_distilled(dim) for dim in distill_core.DIMENSIONS}
        payloads["voice-card"]["rules"] = [{"id": "broken"}]
        with self.assertRaises(ValueError) as ctx:
            distill.write_distilled_outputs(payloads, self.assets_dir)
        self.assertIn("distilled", str(ctx.exception))
        self.assertEqual(list(self.assets_dir.glob("*.json")), [])
```

- [ ] **Step 2: 运行专项测试确认当前失败**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_distill_gate.py" -v
```

Expected: FAIL，当前 `distill.py` 没有 `write_distilled_outputs`，且没有 distilled 校验门禁。

- [ ] **Step 3: 实现门禁并保持写盘行为兼容**

1. 在 `distill.py` 导入 `validate_asset_data`。
2. 实现 `validate_distilled_payload`，把错误文本按 `dimension` 加前缀，警告保留但不阻断。
3. `write_distilled_outputs` 先遍历固定 `DIMENSIONS`，确认每个维度存在、`meta.dimension` 与 key 相同，并执行全量 validation；遇到错误立即抛 `ValueError`，在 validation 完成前不得调用 `mkdir`、`write_text`。
4. 通过后创建 assets 目录，使用现有命名 `f"{genre}-{dimension}-distilled.json"` 写入 JSON；保持 `ensure_ascii=False, indent=2`。
5. `run_distill` 继续负责 genre 白名单检查，但将直接写盘循环替换为 `write_distilled_outputs`；返回字段与现有调用方兼容。
6. 更新 `tests/test_distill.py::TestDistillGenre`，增加断言返回的每个 dimension 同时满足 distilled 校验；不要把 distilled 断言成 voice-card 顶层字段。

- [ ] **Step 4: 运行蒸馏专项和完整蒸馏回归**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_distill*.py" -v
```

Expected: 全部 PASS；现有蒸馏聚合/检索/渲染测试不回归，新增门禁测试确认 invalid payload 不写盘。

- [ ] **Step 5: 提交独立变更**

```text
git -C C:/Users/monesy/niko/novel-lab add scripts/distill.py tests/test_distill.py tests/test_distill_gate.py
git -C C:/Users/monesy/niko/novel-lab commit -m "fix: gate distilled outputs before writing"
```

---

### Task 5: 修正 SQLite 迁移与后端资产索引的 kind 边界

**Files:**
- Modify: `gui/asset_index.py:12-52, 185-222, 244-259, 416-438`
- Modify: `gui/migrate.py:33-112, 324-370, 450-470`
- Modify: `gui/services.py:600-625`
- Modify: `tests/test_asset_index.py`
- Modify: `tests/test_migrate.py`

**Interfaces:**
- Extends `AssetKind` backend vocabulary with `distilled` and `prose_card_index` while leaving `GENRE_KIND_ENUM = ("genre_pack", "prose_card", "book")` unchanged.
- `migrate.infer_kind(name, content)` returns `distilled` for `*-distilled.json`, `prose_card_index` for `genre-prose-card-index.json`, and preserves existing `trope`/`prose_card` behavior for other files.
- `asset_index._classify_asset_name()` maps `-voice-card-distilled`, `-structure-obs-distilled`, `-commercial-obs-distilled`, `-craft-card-distilled` before base suffixes; maps exact `genre-prose-card-index` before generic `genre-prose-card-`.
- `migrate.infer_book_id()` returns `None` for distilled and index; existing `_chosen` card behavior stays unchanged.

- [ ] **Step 1: 写失败测试锁定迁移与索引结果**

在 `tests/test_migrate.py` 修改既有 index 期望：`genre-prose-card-index.json` 从 `trope` 改为 `prose_card_index`，并增加：

```python
    def test_infer_kind_distilled(self):
        self.assertEqual(
            migrate.infer_kind("campus-redemption-voice-card-distilled.json", {"meta": {}}),
            "distilled",
        )

    def test_index_has_no_book_id(self):
        self.assertIsNone(migrate.infer_book_id("genre-prose-card-index"))
```

在 `tests/test_asset_index.py` 增加 scan fixture：同一目录放基础 voice-card、voice-card-distilled 和 index，断言 kind 分别为 `voice`、`distilled`、`prose_card_index`；断言 `_book_id_from_name` 对 distilled/index 返回 `None`。

- [ ] **Step 2: 运行迁移/索引专项测试确认失败**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_migrate.py" -v
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_asset_index.py" -v
```

Expected: FAIL，当前 index 是 `trope`，distilled 是基础卡 kind。

- [ ] **Step 3: 实现 `migrate.py` kind 规则**

1. `infer_kind` 在通用 `genre-prose-card-` 之前优先识别精确 index；在基础卡后缀之前优先识别 `-distilled`，返回 `distilled`。
2. `infer_book_id` 保留现有 `genre-prose-card-`/trope/index 无归属规则，并显式覆盖 distilled 后缀，确保题材级 distilled 为 NULL。
3. 不修改 `GENRE_KIND_ENUM`、`GENRE_KIND_PRIORITY` 和 `_sanitize_genre_kind` 的题材来源约束；distilled/index 只进入 `assets.kind`。
4. `run_migrate` 的 unrecognized 统计与 `check()` 结果要接受新 kind；不删除或重建现有 SQLite 记录。

- [ ] **Step 4: 实现 `asset_index.py` 与单书加载边界**

1. `ASSET_KINDS` 增加 `distilled`、`prose_card_index`；`_ALL_KINDS` 自动包含两者。
2. `_SUFFIX_KIND` 按长后缀优先顺序更新：四个 distilled 后缀、精确 index、基础后缀、通用 prose-card。
3. `_book_id_from_name` 对 `distilled` 与 `prose_card_index` 先返回 `None`。
4. `gui/services._load_assembled_card()` 只查找基础后缀，不再把 distilled 作为候选 fallback；蒸馏结果由 writing inject 的显式 `distilled` 参数加载。
5. 更新模块 docstring 的 kind 清单，避免文档与白名单漂移。

- [ ] **Step 5: 运行专项测试和迁移隔离回归**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_migrate.py" -v
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_asset_index.py" -v
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_config_isolation.py" -v
```

Expected: 全部 PASS；测试仍只在临时 SQLite 中运行，真实 `gui_state` 不新增记录。

- [ ] **Step 6: 提交独立变更**

```text
git -C C:/Users/monesy/niko/novel-lab add gui/asset_index.py gui/migrate.py gui/services.py tests/test_asset_index.py tests/test_migrate.py
git -C C:/Users/monesy/niko/novel-lab commit -m "fix: separate distilled and prose index asset kinds"
```

---

### Task 6: 拒绝错误 kind 进入单书评分并开放 distilled 注入

**Files:**
- Modify: `gui/quality_service.py:114-166, 252-268`
- Modify: `gui/writing_service.py:61-80, 107-157`
- Modify: `gui/router.py` only if request payload must expose a missing `distilled` field
- Modify: `tests/test_quality_service.py`
- Modify: `tests/test_writing_service.py`

**Interfaces:**
- Produces a shared local helper in `gui/services.py` or a small new `gui/asset_contract.py`: `assert_asset_kind(data: dict, expected: str, ref: str) -> None`; it raises `ServiceError(message, 400)` for distilled passed as `voice`, and for index passed as `prose_card`.
- `writing_service.inject(..., distilled=...)` remains the existing explicit path and passes the JSON to `engine_adapter.build_writing_prompt(..., distilled=...)`.
- `quality_service.check/book/qc` continue accepting `voice` references but return 400 when the resolved asset is distilled; no API route name changes.

- [ ] **Step 1: 写失败服务测试**

在临时 `ASSETS_ROOT` 中创建：

```python
DISTILLED = {
    "meta": {"dimension": "voice-card", "genre": "campus-redemption"},
    "rules": [], "blindspots": [], "stats": {},
}
```

增加断言：

```python
with self.assertRaises(ServiceError) as ctx:
    quality_service.check(text="正文", voice="voice:campus-redemption-voice-card-distilled")
self.assertEqual(ctx.exception.code, 400)
self.assertIn("distilled", str(ctx.exception))
```

在 `tests/test_writing_service.py` 增加：`writing_service.inject(voice=valid_voice, distilled="distilled:...")` 返回 prompt 且 `injected_kinds` 同时包含 `voice`、`distilled`；传 index 作为 `prose_card` 返回 400。

- [ ] **Step 2: 运行专项测试确认失败**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_quality_service.py" -v
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_writing_service.py" -v
```

Expected: 新增测试 FAIL，当前 `_load_asset_json` 不区分文件内容 kind。

- [ ] **Step 3: 实现服务层资产边界校验**

1. 在 `gui/services.py` 增加不接触磁盘的 `assert_asset_kind`：检查 `meta.dimension` 与 `rules/blindspots/stats` 识别 distilled；检查 `meta.kind == "genre-prose-card"` 且不存在 index 结构识别 prose_card；对期望 `voice/structure/commercial/craft` 拒绝 distilled，对期望 `prose_card` 拒绝 index。
2. `quality_service.check()` 解析 voice JSON 后先调用 `assert_asset_kind(..., "voice", voice)`，`qc()` 的 `voice_path` 在后台线程前完成同样校验；错误必须同步返回 400，不进入线程。
3. `writing_service.inject()` 对 `voice` 调用 `assert_asset_kind(..., "voice", voice)`；对 `prose_card` 加载后调用期望 `prose_card`；`distilled` 继续作为专门参数加载并标记 injected kind。
4. 不把验证逻辑复制到每个服务函数；所有 API 路由参数和返回结构保持兼容。

- [ ] **Step 4: 运行专项与 API 回归**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_quality_service.py" -v
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_writing_service.py" -v
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_phase2_api.py" -v
```

Expected: 全部 PASS；错误 kind 被同步拒绝，合法 distilled 注入仍生成包含“蒸馏规则”的 prompt。

- [ ] **Step 5: 提交独立变更**

```text
git -C C:/Users/monesy/niko/novel-lab add gui/services.py gui/quality_service.py gui/writing_service.py gui/router.py tests/test_quality_service.py tests/test_writing_service.py
git -C C:/Users/monesy/niko/novel-lab commit -m "fix: reject mismatched assets in scoring services"
```

---

### Task 7: 更新 GUI kind 类型、选择器和构建产物

**Files:**
- Modify: `gui/web/src/types.ts:86-105`
- Modify: `gui/web/src/components/WritingWorkbench.tsx:46-115`
- Modify: `gui/web/src/components/AdvancedWorkbench.tsx:147-152, 196-220`
- Modify: `gui/web/src/components/QualityWorkbench.tsx:49-65` only if the backend list response needs an explicit kind filter
- Modify: `gui/web/dist/` generated hashed assets after the build
- Test: `gui/web` TypeScript build and existing frontend checks in `package.json`

**Interfaces:**
- `AssetKind` adds `'distilled' | 'prose_card_index'`.
- Writing inject panel adds optional `distilled` selection filtered by `kind === 'distilled'`, sends `distilled: distilled || undefined` in the existing POST body, and never includes `distilled` in the `voice-card` menu.
- Asset edit/overview labels show `distilled` and `prose_card_index` as separate labels; they are not selectable as `voice`, `craft`, or `prose_card`.

- [ ] **Step 1: 写前端静态行为测试或最小类型断言**

如果项目现有前端没有单元测试框架，不新增测试依赖；在 `gui/web/src` 通过 TypeScript 类型编译锁定 `AssetKind`，并在现有组件测试/Playwright fixture 能复用时加一条选择器断言。至少确认源代码中：

- `byKind('voice')` 只绑定 voice-card select。
- distilled select 使用 `byKind('distilled')`。
- `writingApi.inject` body 传 `distilled`。
- `prose_card_index` 不出现在 prose-card 选择器。

- [ ] **Step 2: 运行前端构建确认当前类型/组件基线**

Run:

```text
C:/Users/monesy/.niko/binaries/node/versions/22.22.2-2/npm.cmd --prefix C:/Users/monesy/niko/novel-lab/gui/web run build
```

Expected: 当前基线构建成功；记录构建前 git status，避免把历史无关 dist 变化混入提交。

- [ ] **Step 3: 实现前端 kind 边界**

1. 更新 `AssetKind` union。
2. `WritingWorkbench.InjectPanel` 增加 `const [distilled, setDistilled] = useState('')`；加载资产后默认选择第一张 distilled；增加“蒸馏规则（可选）” `TextField`，选项来自 `byKind('distilled')`。
3. `doInject` 的 body 增加 `distilled: distilled || undefined`；保持 voice 必选与其他可选资产逻辑不变。
4. `AdvancedWorkbench` 的 kind label 增加 `distilled: '蒸馏规则'`、`prose_card_index: '题材文风卡索引'`；资产编辑下拉禁止 index 进入可编辑卡片列表，或明确显示只读。
5. `QualityWorkbench` 保持 `assetApi.list({kind: 'voice'})`，不要为了显示 distilled 改成无 kind 的全量请求。

- [ ] **Step 4: 构建并检查生成产物**

Run:

```text
C:/Users/monesy/.niko/binaries/node/versions/22.22.2-2/npm.cmd --prefix C:/Users/monesy/niko/novel-lab/gui/web run build
git -C C:/Users/monesy/niko/novel-lab status --short
git -C C:/Users/monesy/niko/novel-lab diff --stat
```

Expected: TypeScript/Vite 构建退出码 0；只有预期的 TSX/TS 文件与对应 `gui/web/dist/assets/*` hash 文件变化；不修改 portable build。

- [ ] **Step 5: 提交独立变更**

```text
git -C C:/Users/monesy/niko/novel-lab add gui/web/src/types.ts gui/web/src/components/WritingWorkbench.tsx gui/web/src/components/AdvancedWorkbench.tsx gui/web/src/components/QualityWorkbench.tsx gui/web/dist
git -C C:/Users/monesy/niko/novel-lab commit -m "feat: expose distilled assets separately in GUI"
```

---

### Task 8: 补端到端护栏并完成全量验证

**Files:**
- Create: `tests/test_asset_contract_e2e.py`
- Modify: `tests/test_distill.py` only for shared fixture reuse
- Modify: `tests/test_stdlib_only.py` only if the new loader/validator import graph needs an explicit standard-library assertion
- Modify: `CHANGELOG.md` under `[Unreleased]`
- Review only: `docs/superpowers/specs/2026-09-16-novel-lab-high-priority-fixes-design.md`

**Interfaces:**
- End-to-end fixture covers `distill payload -> validate_asset_data("distilled") -> render_distilled -> build_prompt(distilled=...)`.
- The same fixture passes distilled payload to `consistency.score_text` only through an explicit negative test that verifies the service boundary rejects it before scoring.
- No test reads or writes production assets; all JSON is constructed in memory or a temp directory.

- [ ] **Step 1: 写端到端失败/回归测试**

在 `tests/test_asset_contract_e2e.py` 加入：

```python
class TestAssetContractE2E(unittest.TestCase):
    def test_distilled_flows_through_render_not_voice_scoring(self):
        distilled = make_valid_distilled("voice-card")
        errors, _ = validate.validate_asset_data("distilled", distilled)
        self.assertEqual(errors, [])
        rendered = distill_render.render_distilled(distilled)
        self.assertIn("蒸馏规则", rendered)
        prompt = inject.build_prompt(valid_voice_card(), None, None, distilled=distilled)
        self.assertIn("蒸馏规则", prompt)

    def test_index_is_not_a_prose_card(self):
        index = {"_count": 1, "_description": "x", "cards": {}}
        self.assertEqual(validate.auto_kind(index, "genre-prose-card-index.json"),
                         "genre-prose-card-index")
```

增加验证：所有 4 个 `distill_core.DIMENSIONS` 的真实内存输出通过专用 validator；`distill_render.render_all_distilled` 对四类输出均不崩溃；`chapter_loader` 的 diagnostics 有 loaded/ignored/duplicates 三个键。

- [ ] **Step 2: 运行端到端专项**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -m unittest discover -s C:/Users/monesy/niko/novel-lab/tests -p "test_asset_contract_e2e.py" -v
```

Expected: PASS；任何 distilled 都不再被当成单书 voice-card 消费。

- [ ] **Step 3: 更新 CHANGELOG**

在 `[Unreleased]` 下加入准确条目：

- Fixed：蒸馏/index 资产不再错误套用单书卡校验；蒸馏写盘增加专用结构门禁。
- Fixed：章节加载排除备份/构建目录并拒绝同章号静默覆盖。
- Fixed：章节质量评分与量化指标支持 `「」`、`『』` 中文对白引号。
- Added：GUI 分离展示 distilled 与 prose-card index，单书评分拒绝错误 kind。

不得写“全部质量问题已修复”或改变当前测试数字之外的历史统计。

- [ ] **Step 4: 运行全量 Python 测试**

Run:

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B C:/Users/monesy/niko/novel-lab/run_tests.py
```

Expected: exit code 0，输出 `Ran 401+ tests` 与 `OK`；若新增测试数量变化，以实际 `Ran N tests` 为准，不在文档中继续写死 401。

- [ ] **Step 5: 只读校验 55 个生产资产和变更范围**

Run：

```text
C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B -c "import json, subprocess; from pathlib import Path; root=Path(r'C:/Users/monesy/niko/novel-lab'); py=r'C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe'; bad=[]; counts={};\nfor p in sorted((root/'assets').glob('*.json')):\n r=subprocess.run([py, str(root/'scripts'/'validate.py'), str(p)], capture_output=True, text=True, encoding='utf-8');\n line=next((x for x in (r.stdout+r.stderr).splitlines() if x.startswith('校验类型:')), ''); counts[line.split(':',1)[1].split('|',1)[0].strip() if ':' in line else 'unknown']=counts.get(line.split(':',1)[1].split('|',1)[0].strip() if ':' in line else 'unknown',0)+1;\n if r.returncode==1: bad.append((p.name, line));\nprint('assets', len(list((root/'assets').glob('*.json')))); print('kinds', counts); print('rejects', bad)"
git -C C:/Users/monesy/niko/novel-lab diff --check
git -C C:/Users/monesy/niko/novel-lab status --short --untracked-files=all
```

Expected: 55 个资产；4 个 distilled 与 index 不再出现在 REJECT；既有合法单书资产仍通过；`diff --check` 无空白错误；没有小说正文、个人目录或 portable build 变化。

- [ ] **Step 6: 最终提交并记录结果**

```text
git -C C:/Users/monesy/niko/novel-lab add tests/test_asset_contract_e2e.py tests/test_distill.py tests/test_stdlib_only.py CHANGELOG.md
git -C C:/Users/monesy/niko/novel-lab commit -m "test: close novel-lab asset contract regression loop"
```

提交前在会话工作区的复核产物中记录：实际测试数量、资产 kind 分布、拒绝数、GUI 构建结果、未解决问题；不要把生产校验产生的报告写回 `novel-lab/assets/`。

---

## 依赖图与推荐执行顺序

```text
Task 1 (validator contract)
  ├── Task 4 (distill write gate)
  ├── Task 5 (migrate/index kind)
  └── Task 8 (end-to-end)
Task 2 (chapter loader)
  └── Task 8 (diagnostics + full regression)
Task 3 (dialogue extractor)
  └── Task 8 (full regression)
Task 5
  └── Task 6 (service boundary)
Task 5 + Task 6
  └── Task 7 (GUI types/selectors/build)
Task 4 + Task 6 + Task 7
  └── Task 8 (final gate)
```

Task 1、Task 2、Task 3 可由不同工程师并行实现，但如果在同一工作区执行，必须先分离 worktree 或严格避免共享文件冲突；Task 4、5、6、7 按依赖顺序串行；Task 8 必须最后执行。

## 计划自审结果

- **Spec coverage:** 资产专用校验/门禁（Task 1/4）、章节排除与冲突（Task 2）、四类引号（Task 3）、GUI kind/服务边界（Task 5/6/7）、端到端与全量验收（Task 8）均有明确任务。
- **架构审查意见已吸收:** `auto_kind` 增加可选 filename；index 迁移 kind 改为 `prose_card_index`；不改 `GENRE_KIND_ENUM`；保留 novel_dir 双根语义；只统一对白分子；诊断 API 落地为正式接口；401 仅作当前基线，最终以实际 `Ran N tests` 为准；不重建 portable build。
- **Placeholder scan:** 每个任务都有精确文件、接口、命令、预期结果和提交点，没有未定义的实现步骤。
- **Type consistency:** Task 1 的 `validate_asset_data` 被 Task 4/8 使用；Task 2 的 `ChapterLoadError`/`load_chapter_texts` 被三个入口使用；Task 3 的 `dialogue_char_count` 被 metrics/chapter_check 共用；Task 5 的 kind 值被 Task 6/7 使用，名称一致。
