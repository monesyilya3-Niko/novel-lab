# Changelog

本文件记录面向用户的显著变更。版本发布由 `.github/workflows/release.yml` 驱动：推送 `v*` tag 即从 Conventional Commits 自动生成发布说明。

## [Unreleased]

### Added

- **对话占比满分区题材可配（P1-4）**：题材包 `quality_thresholds.dialogue_optimal`（或 `commercial.quality_thresholds.dialogue_optimal`）可覆盖默认 (0.15, 0.40)；campus-redemption 按语料 voice-card 实测（0.0737–0.3016）标定为 **0.07–0.35**，慢热抒情不再被 15% 硬线征税
- `docs/detection-authority.md`：同类检测「以谁为准」权威口径（重复 / 矛盾 / 章节分 / 资产校验）
- `llm_client.describe_llm_degradation`：LLM 额度/网络失败时显式列出「不可用能力 / 仍然可用能力」；pipeline 与 write 在 chat 失败时输出该提示（评估报告 item 10）
- `tests/test_dialogue_band_and_setting.py`：对话带解析/题材包实装/setting_check 检测行为（世界观禁词、属性矛盾、别名）/LLM 降级文案
- `tests/test_logic_check.py`：24 个用例，为下列三处修复建立回归护栏
- `tests/test_model_config.py`：4 个用例，守住 `model_config` 可导入底线
- 前端新增 `assetKindLabels.test.ts` 与 `HomeDashboard.test.tsx`（共 7 个用例），锁定「同一张标签表同时服务 snake_case 与 camelCase 键、首页饼图不出现原始英文 kind / undefined」
- `tests/test_asset_contract_e2e.py`：18 个用例，把蒸馏卡与题材文风卡索引的契约串成端到端护栏——内存四维蒸馏输出 → 专用校验 → 渲染 → 注入写作 prompt → 服务边界拒绝「蒸馏当单书卡打分」；索引判为独立 kind；部分覆盖题材（某维度无贡献书）仍写出四个文件；章节加载诊断结构（`files` / `ignored` / `duplicates` / `aliases`）。全部使用内存对象或临时目录，不读写真实资产
- 资产体系新增两个独立 kind：`distilled`（跨书题材蒸馏卡）与 `genre-prose-card-index`（题材文风卡寻址索引），各有专用校验契约；GUI 资产库把两者列为独立分类（「蒸馏规则」「题材文风卡索引」），写作台新增「蒸馏规则（可选）」独立下拉
- `tests/test_llm_fallback.py`：LLM 备用模型路由 31 用例（余额/权限类不重试立即切换、全链路失败汇总原因、`test_model` 强制 `allow_fallback=False`）
- `tests/test_fatigue_calibration.py`：「了」字密度按语料分位数（p75/p90）标定的回归护栏
- `tests/test_qc_intra_repeat.py`：QC D9 接入章内重复后的分数与 `cross_chapter`/`intra_chapter` 计数契约
- `tests/test_scoring_continuity.py`：章节评分连续化回归（边界无悬崖、单调性、锚点、了字密度 p75→p90 线性扣分）
- `scripts/model_config.py` 新增 `fallback` 子命令，可为模型写入备用链
- GUI 质检台问题列表支持展开/收起完整清单，并提示截断条数

### Fixed

- **悬崖式档位导致假性掉分与刷分空间（P1-2）**：章节 12 维中字数/对话占比/情绪密度/段落节奏/了字密度/让字密度/直陈式情绪词/旁白情绪标签等改为**分段线性连续打分**（`chapter_check._ramp`），满分区与权重不变；1499→1500、14.9%→15.0%、27.0→27.1 等边界不再整档跳 2–4 分。分数可带 1 位小数；历史章节分会变化
- **「了」字密度阈值与语料脱节**：旧 `>5`/`>8` 使语料 100% 章扣满、维度零区分度；改为 corpus p75=27.0 / p90=31.2，并在 p75→p90 间连续扣分（0→3）
- **QC 与 `novel 质检` 双命令不对称**：章内碎片重复此前只进 `book_quality` 不进 `qc`；现 D9（句子重复）并行消费跨章句与章内重复，`raw` 分列 `cross_chapter`/`intra_chapter`
- **payoff_types 四种单位混加成 103**：蒸馏聚合前按书内归一为占比再跨书中位数；`sources` 保留原始值；dashboard 按实际量纲渲染
- **LLM 无备用路由**：`chat()` 支持 `resolve_fallback_chain` + `allow_fallback`；余额/权限类错误不重试立即切换；`test_model` 显式关闭回退以免误报连通成功
- **蒸馏/index 资产被套用单书卡校验（整份 REJECT）**：`validate.py` 此前没有 distilled 与题材文风卡索引的校验器，`auto_kind` 兜底把它们判成 `voice-card`，于是「缺少 narration / dialogue / emotion_handling / banned」等单书卡硬错误全部报在蒸馏卡与索引上，四个 `*-distilled.json` 与题材文风卡索引均无法通过校验。现新增 `validate_distilled` 与 `validate_genre_prose_card_index`（并注册进 `DISPATCH`），`auto_kind` 支持按文件名线索识别索引、按 `meta.dimension` 或 `rules`/`blindspots`/`stats` 三元组识别蒸馏卡；`validate_asset_data(kind, data)` 提供纯数据校验结果，且不污染全局 `ERRORS`/`WARNS`
- **蒸馏写盘无结构门禁**：`distill.py` 曾直接 `json.dump` 四维结果落盘，残缺 payload 会安静写进 `assets/`。现 `write_distilled_outputs` 在**任何 mkdir/写文件之前**对四个维度全量校验（维度齐备、`meta.dimension` 与输出维度一致、`meta.genre` 白名单、distilled 专用契约），任一硬错误即抛 `ValueError` 且不留半成品；警告不阻断写盘
- **部分覆盖题材的蒸馏被门禁判死（零文件写出）**：写盘门禁要求 `meta.source_books` 至少 1 项，而某维度**无任何贡献书**时蒸馏产物天然是 `source_books: []`（`books_count: 0`、`rules: []`），于是「3 本书只有 voice-card」这类部分覆盖题材从「可蒸馏」变成整体失败、一个文件都不写。现空维度（无来源书 / 书数为 0 / 无规则三者同时成立）豁免该要求，其余情况仍要求非空；同时 GUI 服务层把门禁的 `ValueError` 转成 400 可读错误（原先冒到路由层变成 500，用户只看到「服务器内部错误」）
- **单文件重索引破坏资产 key 口径**：`gui/migrate.py` 的 `sync_asset` 用 `asset_key=stem` 重索引，而迁移与详情定位都用 `kind:stem`（`get_asset_by_key(f"{kind}:{name}")`）——写盘后重索引会另插一行重复资产，或在 path 冲突时把既有行的 `asset_key` 静默改写掉，详情查询随即落空。现统一为 `f"{kind}:{stem}"` 且 path 用 `_rel_path`（与 `run_migrate` 同口径）
- GUI 首页资产类型分布的标签改为复用共享表 `assetKindLabels.ts`（原先首页另有一份本地表，键为 camelCase 且缺 `distilled` / `prose_card_index`，「蒸馏规则」「题材文风卡索引」在饼图里显示成原始英文 kind）
- **章节加载污染与静默覆盖**：`book_quality` / `qc` / `logic_check` 各自递归扫 `*.txt` 并 `texts[num] = read_text()` 直接赋值，导致 `_备份/`、`备份/`、`backup/`、`.git/`、`build/`、`dist/` 下的旧稿被当正文参与质检；同一章号命中多个文件时又按遍历顺序静默覆盖、结果不可复现。现统一委托 `chapter_loader`：排除备份/构建目录（大小写不敏感）、文件名取不到章号记入 `ignored`、同一章号命中多个**不同物理文件**抛 `ChapterLoadError`、同一物理文件被多个章号引用（别名）抛 `ChapterAliasError`，并保留 `novel_dir` 与其 `chapters/` 的双根语义（外部符号链接补扫、同一物理文件只加载一次）
- **章节评分与量化指标漏算四角引号**：对白统计只认 `"` 与 `“”`，以 `「」`、`『』` 成文的章节对白占比被算成 0，连带影响节奏类维度。现 `metrics.dialogue_char_count` 统一四类引号口径，`chapter_check` 与 `metrics` 共用同一分子
- **单书评分/注入接受错配 kind**：资产引用只给文件名，而蒸馏卡历史上落成 `*-voice-card-distilled.json` 这类基础卡后缀，服务层会把它当单书 voice 卡打分、把索引当文风卡注入。现服务层按**内容**自证 kind（`assert_asset_kind`），蒸馏卡当 voice、索引当 prose-card 传入一律以 400 拒绝；GUI 侧两者独立成 kind 与独立分类，不再与 `voice` / `prose_card` 混用
- **`novel 模型` 完全不可用**：`model_config.py` 写的是 `from llm_client import (..., secret_store)`，但 `llm_client.py` 里的 `secret_store` 是**函数内延迟 import**（`load_secrets`/`save_secrets` 各自 `import secret_store`），并非模块级属性，因此该 import 必然抛 `ImportError: cannot import name 'secret_store' from 'llm_client'`——连 `list` 都进不去，模型配置在加载阶段就被拦死。现改为独立 `import secret_store`
- **时间线检测误报（严重）**：旧实现把「昨天/今天/明天」当作时间锚点，并以**全书不回落的最高水位线**逐章比较，导致任何不含前瞻时间词的章节都被判「时间线倒退」。在一本 157 章中文长篇上实测产生 **33 条误报（占 21% 章节）**，直接把「逻辑合理」维度打到 0 分、连带 `novel qc` 判定 FAIL。根因是把**相对指代**当成了**绝对位置**，且不区分对白与比喻。现改为：剥离引号内对白与比喻（「好像昨天才见过」）后，只在**同一场景窗口（1000 字）内**校验「句首第N天」的日序单调性——同一段叙述里出现「第三天…第二天…第三天」才报「编号错误」
- **数值类矛盾检测零覆盖**：正则只认阿拉伯数字，而中文小说的年龄/天数/金额普遍写作汉字数字，实测全书「阿拉伯数字+岁」为 0 处——报「0 问题」并非一致，而是读不到数据。现同时接受汉字数字（含「十八」「一百二十」），并用实体名粗筛（剔除「已经不是」「我那时候」这类非人名片段）控制误报；「十八」与「18」视为同一取值
- **`qc` 空声线卡未走兜底**：声线卡存在但 `dialogue.character_voices` 为空列表时，`check_voices` 恒返回 0——「人物弧线」被直接打到 0 分（而卡片为 `None` 时反而按「无法评估」记 100，两条分支不一致）；「手法运用」的 35 分声线子项同样恒为 0，使该维度凭空被压到 65 分。现统一按「无法评估」跳过（人物弧线），并按可评估子项（情绪 20 + 叙述 15 + 禁忌 20 + 意象 10 = 65）重归一（手法运用）
- **质检问题列表静默截断**：`total_issues=61` 却只展示 50 条且无提示；现上报 `issues_truncated`/`issues_limit`，CLI/GUI 均提示可见条数，质检台可展开全量
- GUI 首页「资产总数」排除报告/语料虚拟类别，消除 69 虚报（实际 55），饼图口径同步对齐
- echarts 5.6.0 → 6.1.0，修复 XSS 漏洞（GHSA-fgmj-fm8m-jvvx）
- `dashboard/smoke-test.js` 曾硬编码另一套 WorkBuddy 实例路径，导致冒烟测试测的是陈旧快照；已改为读本仓库产物
- `.githooks/pre-commit` 索引模式 `100644→100755`，POSIX 克隆上钩子不再被静默跳过；并校验暂存资产 schema

### Changed

- 根目录 QA 调试产物归档至 `docs/archive/qa-artifacts/`
- 根目录 Agent 协作文档（HANDOFF / RULES / PROJECT_LAW / PROJECT_SUMMARY）归档至 `docs/internal/`；无许可第三方参考内容与本地拆书实验产物移出版本库（仅本地留存，已加入 `.gitignore`）
- README 新增 CI / License 徽章；截图区移除「暗色首页」（首页暂不响应暗色模式，修复后补回）
- 全量测试基线：**751+ tests OK**（2026-09-18）；55 资产 0 REJECT
- 检测口径权威说明见 `docs/detection-authority.md`

## [1.0.0-baseline] - 2026-09-13

开源基线。此前的完整变更历史见 `git log`，要点：

- 拆书引擎：五遍扫描 + 蒸馏 + 万字报告 + 版权合规检查（纯标准库）
- 资产体系八类：文风卡 / 笔法卡 / 结构观测 / 商业观测 / 题材包 / 蒸馏 / 文风卡库 / 桥段库
- GUI 工作台：首页 / 分析 / 资产库 / 写作台 / 质检台 / 高级 / 系统（65 个 API 端点）
- 质量体系：章节 12 维检查 + 全书质检 + QC 四层十二维
- 测试基线：353 用例全绿，pre-commit 钩子强制
