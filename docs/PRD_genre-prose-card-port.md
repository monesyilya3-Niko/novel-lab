# 增量 PRD · 阶段②：移植 oh-story 30+ 题材文风卡

> 项目：novel-lab（拆书 → 资产 → AI 写作闭环）
> 阶段：阶段②（突破单题材瓶颈，从 1 个题材包扩展到 30+ 题材）
> 作者：产品经理 许清楚
> 日期：2026-09-09
> 文档类型：增量 PRD（本阶段交付边界内的增量需求，不改动既有拆书/写作主链路）

---

## 一、项目信息

| 项 | 值 |
|---|---|
| 语言 | 中文 |
| 编程语言 | Python 3.13（**纯标准库，零第三方依赖**） |
| 项目路径 | `C:\Users\monesy\niko\novel-lab\` |
| 上游调研 | `C:\Users\monesy\niko\deliverables\github-skill-tuijian.md` |
| 移植来源 | `zenstory-ai/oh-story-claudecode`（6614★，MIT）的 `genre-prose-cards/` |

---

## 二、产品目标（本阶段）

1. **落库**：把 oh-story 的 30+ 题材文风卡，以「新的轻量资产」形态落入 novel-lab 的 `assets/`，且**不污染、不冒充**现有 genre-pack（题材包）语义。
2. **可引用**：这批新资产能被写作流程（`inject.py` 注入、`chapter_check`/`qc` 阈值解析）**引用或降级回退**，让用户在尚无拆书范文的题材上也能起步创作。
3. **为升格铺路**：每张卡保留「未来用 ≥3 本真实范文填充 → 升格为正式 genre-pack」的清晰路径与字段占位，不堵死铁律一的聚合通道。

**明确非目标（本阶段不做）**：不为每个题材跑通拆书、不虚构范文数据、不臆造商业层数值。30+ 题材卡「能落库 + 能引用」即为本阶段完成标准。

---

## 三、背景与核心矛盾

### 3.1 现状：单题材瓶颈

- novel-lab 目前**只有 1 个正式 genre-pack**：`assets/campus-redemption-genre-pack.json`（校园救赎）。
- genre-pack 是**多书聚合规则包**，四层结构 + 硬门槛：
  - `meta.source_books` 要求 **≥3 本同题材范文**（否则 confidence ≤0.5，且 `validate.py` 会 `warn`「题材包应由 ≥3 本聚合」）。
  - `structure` / `commercial` 层含**大量量化字段**（钩子 frequency/strength、爽点 ratio/buildup_length、每千字爽点密度、付费卡点章节等），这些**只能从真实范文的拆书观测中得出**。
  - `language_rules.iron_rules` 要求每条带 `rule/bad_example/good_example`，`validate_genre_pack` 强制 `min_items=1`。

### 3.2 移植来源：oh-story 文风卡是什么

- `genre-prose-cards/` 是 30+ 张**「散文式描述卡」**：东方仙侠、传统玄幻、历史古代、宫斗宅斗、豪门总裁、青春甜宠、悬疑灵异……
- 每张卡结构（已由项目内 `scripts/convert_genre_card.py` 的 `_SECTION_TITLES` 确认）：**YAML frontmatter（genre/aliases/platform/confidence/source）+ 13 个 `##` 小节**（正文提示词、开场抓手、冲突发动机、爽点与情绪释放、对话与声线、章尾钩子、场景颗粒、正文落点、前中后期打法、节奏密度、本章取舍、禁止漂移、证据摘要）。
- **本质是「题材写作的散文式提示」**，不是结构化枚举数据，更**没有单本范文拆书数据**。

### 3.3 核心矛盾（本 PRD 要解决的根问题）

| 维度 | genre-pack（题材包） | oh-story 文风卡 |
|---|---|---|
| 数据来源 | ≥3 本范文聚合 | 单题材散文描述，**无范文** |
| 结构 | 严格 schema + 量化枚举 | 自由散文 + 13 小节提示 |
| 商业层 | 爽点密度/卡点/留存（量化） | 只有「爽点与情绪释放」定性描述 |
| 置信度 | 0.5~0.9（随范文数） | 仅 frontmatter 一个 high/medium/low 标签 |
| 生成流程 | 单本 voice-card → 多本聚合 → genre-pack | 直接成卡，无上游 |

**结论：两者是不同物种，不能直接复制粘贴，也不能把文风卡「伪装」成 genre-pack。**

### 3.4 已存在的半成品（关键发现）

项目内已有一个**原型转换器** `scripts/convert_genre_card.py`，它做了「散文卡 → genre-pack」的**启发式硬映射**，但存在三个硬伤，恰好暴露了「直接转 genre-pack」这条路是错的：

1. **产出大量空壳**：`source_books: []`、`chapter_word_range: {}`、`hook_types` 的 frequency/strength 全为 `None`、`per_thousand_words: None`、`iron_rules: []`。
2. **过不了校验**：`validate_genre_pack` 会报硬错误——`buildup_length` 必须给具体数字、`iron_rules` min_items=1、`payoff_types` min_items=1（关键词没命中时为空）。
3. **单题材硬编码**：`_HOOK_KEYWORD_MAP` / `_PAYOFF_KEYWORD_MAP` / `_extract_required_elements` 全是「青春甜宠」专用关键词，无法推广到 30+ 题材。

**该转换器是「验证反面路径」的有价值遗产，但不应作为本阶段的主力形态。**

---

## 四、关键决策（回答 5 问）

### 决策 1 · 移植形态定位：**新增轻量资产 `genre-prose-card`（中间层），不是直接变 genre-pack**

**判断：team-lead 的初步判断「后者更合理」成立，予以确认并明确化。**

理由：
- genre-pack 的**商业层量化数据只能来自真实范文拆书**，文风卡没有范文，硬转必然产出空壳（已被 `convert_genre_card.py` 证明）。
- 但文风卡又**确实携带有效信息**（题材禁忌、桥段套路、语言倾向、爽点定性描述），直接丢弃是浪费。
- 因此引入一个**介于 voice-card（单本）与 genre-pack（多本聚合）之间的新资产**：

```
voice-card（单本声线，已有）
        │  聚合 ≥3 本
        ▼
genre-pack（题材规则包，多本，已有）
        ▲  升格（未来，用范文填充）
        │
genre-prose-card（题材散文卡，NEW，本阶段新增）
        ▲  转换（本阶段）
        │
oh-story genre-prose-cards（源，外部）
```

- `genre-prose-card` 的定位：**「题材写作的轻量参考卡 / 种子模板」**，字段语义上对应 genre-pack 的一个「退化子集」，但**不通过 genre-pack 的严格校验**，走自己的轻量 schema。
- 这条新资产**不违反铁律一**，因为它明确标注「非聚合产物、无范文来源」，写作注入时降级为「参考级提示」而非「题材铁律」。

### 决策 2 · 数据映射（文风卡字段 → novel-lab 结构）

**核心原则：能结构化 → 结构化；不能结构化 → 原文保留为 `prose` 字段；无数据 → 空置不臆造。**

| oh-story 文风卡字段（13 小节 + frontmatter） | 映射到 genre-prose-card | 处理方式 |
|---|---|---|
| frontmatter.genre / aliases | `meta.id` / `meta.name` / `meta.sub_tags` | ✅ 直接映射 |
| frontmatter.platform | `meta.target_platform` | ✅ 直接映射 |
| frontmatter.confidence | `meta.confidence`（high=0.85/med=0.65/low=0.4） | ✅ 直接映射（沿用转换器 `_confidence_map`） |
| frontmatter.source | `meta.provenance.source` | ✅ 直接映射（标注 MIT + repo） |
| 「对话与声线」「语言倾向」 | `language_rules`（**软规则**：倾向/避用词/题材禁忌） | 🟡 部分映射：禁忌词、避用表达可提取；「声线」是散文描述，保留原文 |
| 「章尾钩子」「正文落点」 | `structure.hook_types`（**定性**：type + 描述，无 frequency/strength 数值） | 🟡 定性映射：只留类型名 + 描述句，**不臆造频率/强度** |
| 「爽点与情绪释放」 | `commercial.payoff_types`（**定性**：type + 描述，无 ratio/buildup_length） | 🟡 定性映射：同上 |
| 「节奏密度」「前中后期打法」 | `structure.arc_rhythm`（定性描述） | 🟡 映射为描述字段，非量化 |
| 「开场抓手」「冲突发动机」「场景颗粒」 | `structure`/`commercial.opening_analysis`（定性） | 🟡 映射为 `prose` 描述 |
| 「禁止漂移」 | `language_rules.forbidden_elements` + `banned_phrases` | ✅ 可提取「不要/禁止」句式 |
| 「证据摘要」 | `meta.provenance.evidence` | ✅ 原文保留（未来升格时的溯源依据） |
| 「正文提示词」「本章取舍」 | `prose.prompt_hints` | ✅ 原文保留 |
| **商业层量化字段**（每千字爽点密度、卡点章节、dry_spell_tolerance、buildup_length 等） | —— | ❌ **无法映射，留空占位**，升格时由范文拆书填充 |
| **`source_books` 范文明细** | —— | ❌ **无法映射，置空**，升格时填充 |

**新建字段（genre-prose-card 独有，genre-pack 没有）**：
- `meta.kind = "genre-prose-card"`（资产类型标记，与 genre-pack 区分）
- `meta.provenance`（source 仓库、license、证据摘要——保证 MIT 溯源与未来升格可信）
- `meta.upgrade_status`（`"seed"` / `"upgraded"`，标记是否已升格为 genre-pack）
- `prose`（原文散文正文，整段保留，作为写作时的兜底参考与升格素材）

**丢弃字段**：无（全部信息以「结构化 + 原文保留」双轨收纳，不丢数据）。

### 决策 3 · 与铁律的关系：**「种子模板」路线，不触发 ≥3 本门槛**

**判断：文风卡走「独立轻量题材卡」路径，作为「种子模板」，不要求先有范文；未来用真实范文填充后升格为正式 genre-pack。**

- 铁律一（题材隔离）**不冲突**：`genre-prose-card` 本身按题材聚合、`meta.id` 唯一、写入时校验题材不混用，与 genre-pack 的隔离规则一致。
- 铁律「≥3 本才出 genre-pack」**不触发**：因为本阶段产出的**不是 genre-pack**，是 `genre-prose-card`，二者 schema 与校验规则分离。
- 铁律二（万字报告）**不触发**：万字报告是「拆书」交付门槛，文风卡移植**不涉及拆书**，不产生拆书报告，故不适用。
- 铁律三（纯标准库）**必须遵守**：转换脚本、落库脚本、注入引用逻辑，全部用 Python 标准库（`json`/`argparse`/`pathlib` 等），不引入任何 pip 包。

**关键护栏**：写作注入时，`genre-prose-card` 的定位**必须与 genre-pack 区分**——
- genre-pack → 注入为「**题材铁律（最高优先级）**」（现有 `inject.py` `render_genre_pack` 行为）。
- genre-prose-card → 注入为「**题材参考提示（低优先级，软约束）**」，不冒充铁律，避免无范文支撑的散文描述被当成硬规则误导写作与质检。

### 决策 4 · 需求池（见第五节表格）

### 决策 5 · 待确认问题（见第七节）

---

## 五、需求池（P0 / P1 / P2）

### P0（本阶段必做，交付边界内）

| 编号 | 需求 | 说明 / 验收标准 |
|---|---|---|
| P0-1 | 新增 `genre-prose-card` 轻量 schema | 落盘 `schema/genre-prose-card.schema.json`；required 仅 `meta`（id/name/kind/confidence）+ `language_rules`（软规则）+ `prose`；**不含** genre-pack 的量化硬必填字段 |
| P0-2 | 落库 30+ 题材卡 | 产出 `assets/genre-prose-card-<题材>.json`（≥30 个），每个含 `meta.provenance` 溯源 + 原文 `prose` 兜底 |
| P0-3 | 通用转换脚本（替换单题材硬编码） | 将 `convert_genre_card.py` 的青春甜宠专用 `_HOOK_KEYWORD_MAP`/`_PAYOFF_KEYWORD_MAP` 改为**题材无关的通用提取**；或新建 `import_genre_prose_cards.py` 批量导入；纯标准库 |
| P0-4 | 独立校验函数 | `validate.py` 新增 `validate_genre_prose_card`（轻量，不套用 genre-pack 的量化硬校验），保证落库资产 schema 合法 |
| P0-5 | 写作注入引用（降级回退） | `inject.py` 支持 `--genre-prose-card` 参数；无 genre-pack 时用 prose-card 作为「参考提示」注入，**不冒充铁律**；有 genre-pack 时 genre-pack 优先 |
| P0-6 | 题材隔离校验 | prose-card 落库时校验 `meta.id`/题材唯一、不跨题材混用（呼应铁律一） |

### P1（本阶段可做，提升可用性）

| 编号 | 需求 | 说明 |
|---|---|---|
| P1-1 | `chapter_check`/`qc` 阈值回退 | prose-card 无 `quality_thresholds` 时，回退默认 75/60（现有 `resolve_thresholds` 已兼容 `None`，确认 prose-card 不误伤） |
| P1-2 | 卡片目录索引 | 生成 `assets/genre-prose-card-index.json`（题材名 → 文件路径 / id 映射），供检索与选择 |
| P1-3 | 升格占位字段 | prose-card 内置 `upgrade_status="seed"` + 空 `source_books` 占位，供未来 `pass5_aggregate` 升格时填入 |

### P2（后续阶段）

| 编号 | 需求 | 说明 |
|---|---|---|
| P2-1 | 升格流水线 | 用户拆 ≥3 本某题材范文后，prose-card + 范文聚合 → 正式 genre-pack（复用 `pass5_aggregate`） |
| P2-2 | 逐题材跑通拆书 | 为高价值题材（仙侠/都市/甜宠）逐个补齐范文拆书，产出真正的 genre-pack |
| P2-3 | 文风卡质量评级 | 对 30+ 卡做来源/质量分级，低质卡降级为「参考」不参与注入 |

### 交付边界（阶段②收口标准）

- ✅ 30+ 题材卡**全部落库**为 `genre-prose-card`，schema 合法、纯标准库。
- ✅ 写作流程**能引用**（`inject.py --genre-prose-card` 生效，降级回退正常）。
- ✅ 与铁律共存（不冒充 genre-pack、不触发 ≥3 本门槛、不跨题材混用）。
- ❌ 不要求每个题材都跑通拆书、不产出商业量化数据、不升格为 genre-pack。

---

## 六、用户故事

1. **作为网文作者**，我想在「东方仙侠」题材尚未拆过任何范文时就能参考它的文风卡开始写作，**以便**不被「只有校园救赎一个题材」卡住。
2. **作为网文作者**，我想在写作时让系统明确区分「题材铁律」和「题材参考提示」，**以便**不被无范文支撑的散文描述误导成硬性规则。
3. **作为拆书作者**，我想看到每张文风卡的来源与证据摘要，**以便**判断它是否可信、未来是否值得拆范文升格。
4. **作为系统维护者**，我想用一条通用命令批量导入 30+ 题材卡，**以便**不逐张手写、不维护题材专用的硬编码关键词表。
5. **作为产品/架构师**，我想让文风卡（种子）与题材包（聚合）在 schema 与校验上彻底分离，**以便**铁律「≥3 本才出 genre-pack」不被绕过。

---

## 七、待确认问题（需用户拍板）

1. **资产命名**：新资产叫 `genre-prose-card` 是否认可？还是复用 `convert_genre_card.py` 里暗示的「直接转 genre-pack」方向（不建议）？
2. **注入定位**：文风卡注入写作 prompt 时，定位为「低优先级参考提示（软约束）」是否接受？还是希望某些题材（如仙侠）直接按铁律级注入？
3. **30+ 卡片来源获取**：oh-story 的 `genre-prose-cards` 源文件尚未下载到本地（`reference/oh-story/` 目录当前不存在）。由谁、以何种方式获取这批 .md 源文件？（GitHub clone / 手动下载 / 交由主理人统一拉取）
4. **卡片完整清单**：30+ 张卡的**确切题材清单与数量**需要最终确认（本 PRD 按「≥30」口径规划，实际以源仓库为准）。是否需要先出一份「题材清单 → genre-pack 缺失度」对照表？
5. **转换器去留**：现有 `convert_genre_card.py`（青春甜宠专用）是**改造通用化**，还是**弃用、另起 `import_genre_prose_cards.py`**？
6. **升格优先级**：未来哪些题材优先「拆 ≥3 本范文升格为 genre-pack」？是否需要在本次 PRD 里附带一个升格优先级建议？

---

## 八、风险与备注

- **数据可信度风险**：文风卡是「散文式经验描述」，无范文支撑，置信度标签（high/medium/low）是**来源自报**，非拆书实测。必须在 `meta.provenance` 标注「未经验证」，避免与 genre-pack 的实测 confidence 混淆。
- **License**：MIT，允许移植，但须保留 attribution（`meta.provenance.source` 标注仓库 + license）。
- **与已有 `convert_genre_card.py` 的兼容**：本 PRD 建议将其「青春甜宠硬编码」改造为通用，或弃用另起；二者不能并存两套口径。
- **不修改现有代码的主链路**：本阶段为「新增资产 + 新增脚本 + 注入参数扩展」，不动 `pipeline.py`/`write.py`/`pass5_aggregate.py` 的既有拆书逻辑。
