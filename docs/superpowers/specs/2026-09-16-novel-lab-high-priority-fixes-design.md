# novel-lab 高优输入与资产边界修复设计

**日期**：2026-09-16  
**状态**：待用户复核后进入实现计划  
**范围**：资产类型校验与消费边界、章节输入加载安全、中文对白统计、回归测试

## 1. 背景与问题定义

当前项目把四类不同语义的 JSON 文件放在同一 `assets/` 目录中，但校验器、目录索引、评分器和注入器没有共享完整的资产类型契约：

- `*-distilled.json` 按项目设计是 `meta/rules/blindspots/stats` 蒸馏资产，不是单书 `voice-card`。
- `validate.py` 对未知结构回退到 `voice-card`，造成蒸馏卡被错误 REJECT。
- GUI 资产索引又把 distilled 后缀映射到基础 kind，允许它进入单书 voice-card 选择路径。
- 章节加载器递归扫描所有 `.txt`，排除规则和同章号冲突处理缺失，备份/副本可能静默覆盖正文。
- `chapter_check.py` 只识别 ASCII 双引号和 `“”`，漏掉中文常用的 `「」`、`『』`，使章节对话比例失真。

本设计只修复输入边界和契约，不在本轮改变“了”字阈值、重复算法、连续评分或 LLM 路由策略。

## 2. 目标与非目标

### 2.1 目标

1. 让 `distilled` 和 `genre-prose-card-index` 有明确的自动识别与专用校验结果。
2. 蒸馏结果写盘前执行结构校验，失败时不产生新的半成品文件。
3. GUI 和单书评分路径不能把 distilled 当作单书 voice/craft/structure/commercial 资产。
4. 所有章节扫描入口共享一致的目录排除和同章号冲突策略。
5. 章节评分与量化指标共用同一套对白字符抽取口径，并支持四种引号：`"..."`、`“...”`、`「...」`、`『...』`。
6. 用回归测试锁定上述行为，且既有全量测试不回退。

### 2.2 非目标

- 不修改现有小说正文、资产内容或用户个人目录。
- 不重标定疲劳词、对话比例、字数档位。
- 不在本轮把重复检测改成 n-gram，也不改变其严重度规则。
- 不新增外部依赖，不调用网络或 LLM。
- 不重构全部 GUI 资产数据模型；只增加必要的 distilled kind 边界。

## 3. 设计方案

### 3.1 资产类型契约

#### 3.1.1 校验器

修改 `scripts/validate.py`：

- 新增 `validate_distilled(d)`，校验：
  - 顶层包含 `meta`、`rules`、`blindspots`、`stats`。
  - `meta.id`、`meta.schema_version`、`meta.dimension`、`meta.genre`、`meta.source_books`、`meta.books_count` 类型正确。
  - `meta.dimension` 只能是项目蒸馏维度：`voice-card`、`craft-card`、`structure-obs`、`commercial-obs`。
  - `rules`、`blindspots`、`stats` 为对象/数组的正确类型；规则项至少包含 `id`、`dimension`、`field`、`kind`、`books_count`、`value`、`confidence`、`conflict`、`over_generalized`、`blindspot_books`。
  - `confidence` 在 0-1；`kind` 为 `hard`、`soft` 或 `personal`；`books_count` 为非负整数。
  - 规则 `dimension` 与 `meta.dimension` 一致，若不一致为硬错误。
- 新增 `validate_genre_prose_card_index(d)`，校验索引顶层 `_count`、`_description`、`cards` 基本类型，以及每个 card 的 `id`、`file` 字符串；索引不是卡片，不套用 `genre-prose-card` schema。
- 在 `DISPATCH`、CLI `--kind` 选择项和 `AUTO_HINTS` 中注册 `distilled`、`genre-prose-card-index`；`genre-prose-card-index` 只作为校验器 kind，不改成 `genre-prose-card`。
- `auto_kind()` 优先顺序：显式 `meta.kind == genre-prose-card` → 索引结构 `cards` 且文件名含 `index` → distilled 结构 `meta.dimension + rules + stats` → 既有类型判断 → voice-card 兜底。
- 保持既有单书卡、题材包、桥段库校验行为不变。

#### 3.1.2 蒸馏写盘门禁

修改 `scripts/distill.py`：

- 先在内存中生成四类结果。
- 对四个结果调用 `validate_distilled`，区分硬错误和警告。
- 任一硬错误时抛出明确错误并在任何输出文件写入前停止。
- 校验通过后再写入四个目标文件；不改变现有文件命名。
- 该门禁只负责蒸馏 schema/结构，不执行版权正文扫描。

为避免对 `validate.py` 全局 `ERRORS/WARNS` 状态产生跨文件副作用，提供一个可供 Python 调用的纯数据校验包装函数，调用方获得 `(errors, warns)`，CLI 仍复用同一逻辑输出。

#### 3.1.3 GUI 消费边界

修改 `gui/asset_index.py`、`gui/migrate.py`、必要的 GUI 服务测试：

- `ASSET_KINDS` 增加 `distilled` 和 `prose_card_index`；`_SUFFIX_KIND` 中四类 distilled 后缀映射为 `distilled`，且必须排在基础后缀前；`genre-prose-card-index` 必须优先于通用 `genre-prose-card-`，映射为 `prose_card_index`。
- `migrate.infer_kind()` 对 distilled 返回 `distilled`，对 `genre-prose-card-index.json` 返回 `prose_card_index`，更新相关迁移测试；`infer_book_id` 对题材级 distilled/index 返回空书 ID，避免挂到某本书。
- 前端资产清单给 `distilled` 和 `prose_card_index` 独立标签；既有 prose-card 选择器只接受 `prose_card`，不把 index 当可注入卡片。
- `gui/services.py` 的单书卡加载只接受基础后缀，不再把 distilled 作为基础卡的 fallback。
- 资产清单可以展示 distilled，但 voice/craft/structure/commercial 选择器不能把 `distilled` 混入基础 kind 结果。
- `quality_service` 和 `writing_service` 对 `voice` 参数加载后增加结构边界检查：若资产是 distilled，返回清晰的 400 错误，提示使用 `distilled` 参数而不是 `voice`。
- `distilled` 仍由注入路径使用，交给 `distill_render.render_distilled()`，不送入 `consistency.score_text()`。

### 3.2 统一章节加载

新增 `scripts/chapter_loader.py`，提供纯标准库函数：

```python
def load_chapter_texts(source: str | Path) -> dict[int, str]: ...
```

设计规则：

- 单文件：按现有规则从文件名提取章号；没有数字时按 1 章兼容。
- 目录：递归扫描 `.txt`，路径中任一目录名大小写折叠后属于 `_备份`、`备份`、`backup`、`.git`、`build`、`dist` 时跳过。
- 文件名仍沿用现有 `chapter-001.txt` / `第001章.txt` 等数字提取兼容范围；目录扫描中不含数字的 `.txt` 按现有行为跳过并记录为 ignored，单文件没有数字时仍按 1 章兼容。
- 同一个章号对应多个未被排除的文件时抛出 `ChapterLoadError`，错误信息包含章号和所有候选相对路径；禁止按遍历顺序静默覆盖。
- 返回章号按数字排序；读取失败时抛出包含路径的错误。
- 可选诊断函数返回 `loaded_files`、`ignored_files`、`duplicate_chapters`，供 QC 元信息和测试使用；现有 CLI 默认仍以 dict 结果为主。

替换或委托现有实现：

- `scripts/book_quality.py` 的目录加载。
- `scripts/qc.py::_load_texts`。
- `scripts/logic_check.py::_load_texts`。
- `setting_check.py` 通过 `logic_check` 复用时保持接口兼容。

错误映射：

- `book_quality_check()` 将 `ChapterLoadError` 转成现有风格的 `{"error": ...}`。
- `qc.run_qc()` 保持抛出 `ValueError`/调用方错误处理，不返回伪造空报告。
- `logic_check.main()` 输出错误并以非零退出。

### 3.3 统一对白字符抽取

在 `scripts/metrics.py` 增加无副作用的 `dialogue_char_count(text)`，支持四种成对引号，使用按字符扫描而不是互相独立的开闭字符计数，以避免混合引号错配：

- ASCII：`"..."`
- 中文双引号：`“...”`
- 直角引号：`「...」`
- 双直角引号：`『...』`

要求：

- 只累计引号内部字符，不累计引号本身。
- 未闭合引号只计已打开到文本结尾的内容，保持对不完整草稿的容错。
- 不把不同类型的关闭引号误当作当前打开引号的关闭。
- `metrics.dialogue_ratio()` 改为使用该函数；分母口径保持现有“去空白总字符”。
- `chapter_check.check_dialogue_ratio()` 使用同一函数；分母仍保持现有“汉字数”，不改变评分维度的既有权重，只修正对白字符识别。

### 3.4 测试

新增/修改测试：

- `tests/test_validate.py` 或现有校验测试：distilled PASS、错误字段 REJECT、index PASS、auto_kind 优先级。
- `tests/test_migrate.py`：distilled kind、题材级 book_id 为空、旧基础卡不回退到 distilled。
- `tests/test_chapter_loader.py`：备份排除、同章号冲突、嵌套目录、单文件、无数字文件名兼容、读取错误。
- `tests/test_thresholds.py` 或新 `tests/test_chapter_check.py`：四类引号均被统计、混合引号、空对白、不闭合对白。
- 端到端测试：构造最小原始资产，运行蒸馏内存结果→专用校验→渲染；验证 distilled 不会被单书评分消费。

所有测试使用临时目录和 `-B`，不触碰真实 `assets/`、`gui_state/`、`gui/state/` 或用户小说目录。

## 4. 错误处理与兼容性

- 既有合法单书资产、题材包、桥段库和 prose card 继续通过原校验。
- 既有 API 路由名称不变；只扩展 kind 白名单和错误信息。
- 对旧的 GUI SQLite 资产记录，迁移/同步时根据文件名重新识别 distilled kind；不删除历史记录。
- 输入目录出现同章号冲突后宁可失败，不自动选择正文/备份；用户必须修正输入范围或目录结构。
- 蒸馏校验失败不覆盖已有合法 distilled 文件；本轮实现可以先校验后逐文件写入，后续若需要强原子性再引入临时目录替换，但不得产生新的半成品。

## 5. 验收标准

1. 当前 55 个资产重新逐个校验时，四个 distilled 文件被识别为 `distilled` 并通过专用校验；index 被校验器识别为 `genre-prose-card-index`、被 GUI 识别为 `prose_card_index`，并通过索引校验；原有单书资产结果不回退。
2. `python scripts/distill.py --genre campus-redemption` 在当前资产上能完成内存校验并写出四个 distilled 文件；构造缺字段结果时在写盘前失败。
3. GUI 资产清单中 distilled kind 与基础 voice kind 分离；把 distilled 传给单书评分接口得到明确错误，不再返回空声线评分。
4. 目录包含正文与 `_备份` 同章号文件时，备份被忽略；两个非排除文件同章号时命令失败并列出冲突路径。
5. `chapter_check.check_dialogue_ratio()` 对 `「你好？」`、`『你好？』` 得到非零且与对应 `“你好？”` 的字符计数一致。
6. 新增回归测试全部通过，当前全量基线 401 个测试仍全部通过。
7. `git diff` 只包含本设计范围内的源码、测试和必要设计记录，不修改小说正文和现有资产内容。

## 6. 实施顺序

1. 先写失败测试：资产 kind、对白引号、章节加载冲突。
2. 实现共享工具和最小生产代码。
3. 接入蒸馏门禁与 GUI kind 边界。
4. 运行专项测试，修复回归。
5. 运行全量测试、静态 diff 与资产只读校验。
6. 重建便携包不是本轮默认动作；若用户要发布便携版，另开发布任务强制重建并比对 hash。
