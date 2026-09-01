# novel-lab 项目总结文档

> **版本**：2026-09-01（v1.0，基于当日全链路实测撰写，与代码现状一致）
> **项目路径**：`C:\Users\monesy\WorkBuddy\2026-08-06-16-49-41\novel-lab\`
> **用途**：新会话直接参考本文件即可了解全部结构与用法；历史沿革见 HANDOFF.md
> **诚实声明**：本文件所有命令均在本机实测通过（2026-09-01），未实测的部分在 FAQ 中明确标注

---

## 一、项目定位与核心功能

**一句话**：把优秀小说拆成可复用的结构化资产，再用这些资产驱动 AI 创作。

| 核心功能 | 说明 |
|---|---|
| 拆书引擎 | TXT 全本 → 分层采样（开篇10+中段15+卷末2）→ 量化 → 五遍扫描 → 归一化 → 结构化资产 |
| 资产体系 | voice-card（声线卡）/ craft-card（笔法卡）/ structure-obs（结构观测）/ commercial-obs（商业观测）/ genre-pack（题材包） |
| 资产驱动写作 | 资产注入 → system prompt → 生成 → 三维度改写循环（一致性+章节质量+内容质检） |
| 质量体系 | 章节检查（12 维 100 分制）+ 全书质检（6 类检测）+ 版权合规（12 字原文匹配拦截） |
| 指纹拆书（副线） | 基于 Skill 脚本的统计指纹提取（句长/节奏/对话占比），与主引擎互补 |
| 可交付报告 | 一键生成拆书报告 + 笔法分析报告（Markdown，可直接交付） |

**LLM 层模式（2026-09-01 起）**：**无外部模型、无 API 依赖**。拆书五遍扫描与写作改写由 WorkBuddy AI 在会话内直接完成；采样/量化/校验/合规/打分全部本地 Python 计算。

---

## 二、整体架构

```
┌─ 拆书层 ─────────────────────────────────────────────────────┐
│ novel.py 拆书 book.txt --genre campus-redemption             │
│   [1] sampler.py    分层采样 27章（开篇10+中段15+卷末2）        │
│   [2] metrics.py    量化（句长/对话占比/TTR/五感）              │
│   [3] 五遍扫描       ⚠ 无外部模型时：生成 AI接管任务.md 并优雅   │
│                      停止，pass1-5 由 WorkBuddy 会话内完成     │
│   [4] normalize.py  中文键 → schema 英文键（模糊匹配4种格式）   │
│   [5] validate.py   schema 校验（voice/craft/structure/commercial/genre-pack/trope）│
│   [6] compliance.py 版权合规（12字原文匹配→REJECT）            │
├─ 聚合层 ─────────────────────────────────────────────────────┤
│ pass5_aggregate.py  ≥3本同题材 → genre-pack 题材包            │
├─ 写作层 ─────────────────────────────────────────────────────┤
│ inject.py    资产 → 写作 system prompt（6~10节，见§4.3）       │
│ write.py     生成+三维度改写循环（一致性≥90/质量≥75/质检）     │
│ consistency.py   五维一致性打分（声线35/情绪20/叙述15/禁忌20/意象10）│
│ chapter_check.py 12维100分制章节自检                          │
│ book_quality.py   6类全书质检（重复/连贯/凑字/乱编/AI味）       │
├─ 指纹拆书（Skill 副线，目录 指纹拆书/）──────────────────────┤
│ webnovel-reverse-analysis/novel_analyzer.py   拆结构           │
│ novel-writing-pipeline/fingerprint_extract.py 提统计指纹       │
│ ai_taste_check.py                             去AI味门禁       │
├─ 产出层 ─────────────────────────────────────────────────────┤
│ report.py / report_craft.py  拆书报告 / 笔法分析报告           │
│ novel.py                     CLI 统一入口（15 个子命令）       │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、模块职责

### 3.1 代码文件（novel-lab 根 + scripts/，共 21 个，py_compile 全过）

| 文件 | 职责 |
|---|---|
| `novel.py` | CLI 统一入口（拆书/注入/写作/检查/质检/报告/笔法报告/校验/合规/模型/状态/分析等子命令）|
| `scripts/pipeline.py` | 拆书主流程；**无模型时自动生成 `corpus/raw/<书>/AI接管任务.md` 并优雅退出（exit 0）** |
| `scripts/sampler.py` | 分层采样：开篇10+中段15+卷末2，抽取对话切片 |
| `scripts/metrics.py` | 量化指标：均句长/短句率/对话占比/TTR/标点密度 |
| `scripts/normalize.py` | LLM/中文键输出 → schema 结构（兼容 pass2 的 4 种格式、imagery 3 种存放位置）|
| `scripts/validate.py` | schema 校验 6 类资产，auto_kind 自动识别（**2026-09-01 修复 craft-card 误判 + 补齐 structure-obs/commercial-obs 校验器**）|
| `scripts/compliance.py` | 版权合规：连续 12 字原文匹配→REJECT；title 字段豁免 |
| `scripts/inject.py` | 资产 → 写作 system prompt（恒定6节+按资产追加4节，见 §4.3；支持 --out）|
| `scripts/write.py` | 章节生成 + 三维度改写循环（默认一致性目标 90 / 章节质量目标 75 / 最多 3 轮）；**无模型时生成 AI接管写作任务.md 优雅退出（2026-09-01 下午新增）**|
| `scripts/consistency.py` | 五维一致性打分（100 分制）|
| `scripts/chapter_check.py` | 12 维 100 分制章节自检（字数/钩子/情绪密度/疲劳词/让字等）|
| `scripts/book_quality.py` | 全书 6 类质检，critical>0→FAIL、high≥5→FAIL、high>0→WARN |
| `scripts/report.py` / `report_craft.py` | 生成可交付的拆书报告 / 笔法分析报告 |
| `scripts/pass5_aggregate.py` | ≥3 本同题材聚合题材包 |
| `scripts/batch.py` | 批量拆书（目录级）|
| `scripts/clean_verbatim.py` | 清除资产中夹带的原文台词 |
| `scripts/llm_client.py` | 外部模型统一调用层（当前无配置不使用；`any_model_configured()` 供 pipeline 检测）|
| `scripts/model_config.py` | 外部模型配置 CLI（仅恢复外部模型时用）|
| `fix_quotes.py` / `test_regex.py` | 历史修复/测试工具 |

### 3.2 目录职责

| 目录 | 内容 |
|---|---|
| `assets/` | 拆书资产（14 个 JSON：3 本书的 voice/craft/structure/commercial 4 类卡共 12 张 + 题材包 1 + 合成测试卡 1）|
| `reports/` | 可交付报告（6 份：3 本书 × 拆书报告+笔法分析）|
| `schema/` | 6 个 JSON Schema（voice-card / craft-card / structure-obs / commercial-obs / genre-pack / trope-library；纯文档用途，实际校验逻辑在 validate.py）|
| `prompts/` | pass1-5 分析 prompt + analysis-pipeline.md（设计文档）+ generated/（生成的写作 prompt）|
| `corpus/` | 语料库：**根目录**放原书 TXT（chireng/qingning/sangshi_chosen.txt 等 5 本）；raw/（五遍扫描原始输出 + AI接管任务.md，不含原书）、sampled/（采样切片）、metrics/（量化指标）、fanqie/（番茄抓取工具，需 fontTools）|
| `docs/` | 项目评估报告 4 份 + 指纹拆书使用说明 + archive/（过期计划 v1-v3）|
| `指纹拆书/` | 指纹法工作目录：样本测试 / 指纹库 / 分析报告 |
| `outputs/` | 输出文件 |
| `config/` | **空**（外部模型配置已按用户指令删除；恢复时用 model_config.py）|
| `novel/` | **当前不存在**——首次运行 `novel.py 写作` 时由 write.py 自动创建（--novel-dir 默认 novel，创建 chapters/arc-N/chapter-NNN.txt 结构）|

---

## 四、交付物清单

### 4.1 数据资产（校验状态：2026-09-01 全量实测，14 个资产硬错误 0）

- 3 × voice-card（chireng / qingning / sangshi，置信 90%）→ WARN（burst_pattern 等历史警告，可入库）
- 3 × craft-card → **PASS**（0 错 0 警）
- 3 × structure-obs + 3 × commercial-obs → **2026-09-01 起可校验**（此前无校验器被误判 voice-card 而假性 REJECT）：全 0 硬错误，qingning structure-obs / sangshi commercial-obs 有真实数据特征的 WARN，其余 PASS
- 1 × campus-redemption-genre-pack（PASS；铁律4条/必需要素4条/禁用词11条/疲劳词5条）
- 1 × synthetic_book_c-voice-card（合成测试用，WARN）
- 6 份可交付报告（reports/）

### 4.2 配置文件

| 文件 | 状态 |
|---|---|
| `config/models.json`、`config/.secrets.json` | **已删除**（备份在 `_TRASH\暮冬念春_清理_2026-09-01\novel-lab内\config删除\`）|
| `RULES.md` | 可执行规则全集 v1（14 节，编号已理顺；第二节标注为历史存档）|
| `HANDOFF.md` | 交接文档（15 节，含整合与清理记录）|
| `MODELS.md` | 外部模型手册（头部已标注"仅存档参考"）|

### 4.3 注意：prompt 节数以代码为准（2026-09-01 实测修正）

inject.py 实际生成 **6~10 节**（标题块不计）：
- **恒定 6 节**：一叙述层 + 二角色声线 + 三情绪写法 + 四意象感官 + 八禁忌 + 九写作执行清单
- **按资产追加 4 节**：〇题材规则（有 genre-pack）/ 五结构规律（有 structure-obs）/ 六商业节奏（有 commercial-obs）/ 七写作技法（有 craft-card）
- 2026-09-01 修复：五/六节此前在未传参时也会注入「（无结构观测）」占位文本，现已改为跳过
- 注入命令支持 `--out` 重定向（novel.py 注入 已透传）
- RULES.md 旧文说"8 节"、HANDOFF 旧文说"10 节"均不准确——**以本节为准**

### 4.4 依赖项

- **Python 3.13.12（managed）**：`C:/Users/monesy/.workbuddy/binaries/python/versions/3.13.12/python.exe`（下文以 `$PY` 代指）
- **零第三方依赖**：核心引擎只用标准库
- **可选**：fontTools + numpy + Pillow（仅番茄抓书需要，**已装于项目 venv** `~/.workbuddy/binaries/python/envs/default`：fontTools 4.63.0 / numpy 2.5.1 / Pillow 12.3.0，2026-09-01 实测联网抓取可用）；注意须用 venv 的 `Scripts/python.exe`（`$PY` 裸版无 Pillow），且须在 novel-lab 根目录运行 fetch_book.py（脚本用相对路径 `corpus/fanqie`）
- **技能依赖**：全局 `~/.workbuddy/skills/` 12 个小说技能；项目级 `2026-08-06-16-49-41\.workbuddy\skills\` 装 2 个核心（novel-writing-pipeline、webnovel-reverse-analysis），bug 修复在两处均生效

---

## 五、使用指南

### 5.1 环境准备

```bash
# 统一入口变量（Git Bash）
PY="C:/Users/monesy/.workbuddy/binaries/python/versions/3.13.12/python.exe"
cd "C:/Users/monesy/WorkBuddy/2026-08-06-16-49-41/novel-lab"
```

- 无需安装任何第三方包；无需 API 密钥
- 路径一律用 `C:/...` 形式传给 Python（Git Bash 的 `/c/...` 会被当字面路径）

### 5.2 启动与常用命令

```bash
# 查看项目状态
$PY novel.py 状态

# ① 拆一本新书（本地跑完采样+量化，生成 AI 接管任务清单后退出）
$PY novel.py 拆书 <book.txt> --genre campus-redemption
#    → 产出：corpus/raw/<书名>/AI接管任务.md + sampled/ 切片 + metrics 指标

# ② AI 接管五遍扫描（WorkBuddy 会话内完成，见 §5.3）

# ②b 组装资产（AI 产出 pass1-5 JSON 后，一键组装成 4 类资产）
$PY novel.py 组装 <书名> --genre campus-redemption
#    读 corpus/raw/<书名>/pass1-5 → 归一化 → 写 assets/<书名>-{voice-card,structure-obs,commercial-obs,craft-card}.json

# ③ 校验/合规（AI 产出 pass JSON 后）
$PY novel.py 校验 <asset.json>        # schema 校验
$PY novel.py 合规 <asset.json> <book.txt>  # 版权合规

# ④ 注入资产为写作 prompt（可选 --out 重定向输出路径）
$PY novel.py 注入 assets/<book>-voice-card.json --craft-card assets/<book>-craft-card.json --genre-pack assets/campus-redemption-genre-pack.json

# ⑤ 写章节 → 无模型时自动生成 AI 接管写作任务（2026-09-01 下午新增降级路径）
$PY novel.py 写作 assets/<book>-voice-card.json --chapter 1 --task "要点"
#    无外部模型 → 在 --novel-dir 下生成 AI接管写作任务.md（含写作要求全文、
#    保存路径、可复制的自检命令、达标标准）后优雅退出（exit 0）
#    AI 会话内完成正文 → 按接管文档保存 → novel.py 检查 自检达标入库

# ⑥ 章节检查 / 全书质检（纯本地，随时可跑）
$PY novel.py 检查 <chapter.txt> --voice assets/<book>-voice-card.json
$PY novel.py 质检 <章节目录/>

# ⑦ 报告
$PY novel.py 报告 assets/<book>-voice-card.json
$PY novel.py 笔法报告 assets/<book>-craft-card.json

# ⑧ 指纹拆书（Skill 副线，详见 docs/指纹拆书_使用说明.md）
$PY "C:/Users/monesy/WorkBuddy/2026-08-06-16-49-41/.workbuddy/skills/webnovel-reverse-analysis/scripts/novel_analyzer.py" <书.txt> --output 指纹拆书/分析报告/
$PY "C:/Users/monesy/WorkBuddy/2026-08-06-16-49-41/.workbuddy/skills/novel-writing-pipeline/scripts/fingerprint_extract.py" --corpus 指纹拆书/<题材>/ --out 指纹拆书/指纹库/<名>.json
```

### 5.3 AI 内置拆书工作流（当前标准流程，替代外部模型）

1. `novel.py 拆书 <book.txt> --genre xxx` → 自动采样+量化+生成接管清单
2. AI 依次读 `prompts/pass1_structure.md` ~ `pass5_craft.md` 的要求
3. AI 读 `corpus/sampled/<书>/` 对应切片，在会话内产出分析 JSON
4. 存为 `corpus/raw/<书>/passN_*.json`（注意：pass 输出的中文键交给 normalize 归一化，不必强求英文键）
5. **`novel.py 组装 <书名> --genre xxx` → 一键读 pass1-5、归一化、组装 4 类资产写入 assets/**（2026-09-01 新增，补上"AI 产出→入库"最后一公里；pass5 缺失时加 `--skip-craft`）
6. `novel.py 校验` → `novel.py 合规`，全过 → 资产入库 assets/
7. 拆满 ≥3 本同题材 → `pass5_aggregate.py` 聚合题材包
8. 写作：`novel.py 注入` 产出 prompt → AI 写章节 → `novel.py 检查` 本地自检（≥75）→ 达标入库

**质量阈值速查**：一致性 ≥90 合格（<75 基本合格线、<60 明显偏离）｜章节质量 12 维 ≥75｜schema 0 硬错误｜合规 0 REJECT｜拆书人工校验 ≥70%

### 5.4 新会话接入步骤

1. 先读本文件 + `HANDOFF.md`（历史沿革）+ `RULES.md`（可执行规则）
2. `novel.py 状态` 确认资产完整
3. 按任务选择：拆新书（§5.3）｜写作（§5.2 ④⑤）｜质检（§5.2 ⑥）

---

## 六、常见问题（FAQ）

| 问题 | 答案 |
|---|---|
| 拆书命令报"尚未配置任何模型"？ | **不应再出现**。2026-09-01 已修复：无模型时优雅停止并生成 AI接管任务.md。若仍出现说明代码被回退 |
| 写作命令报"尚未配置任何模型"？ | **不应再出现**。2026-09-01 下午已修复：write.py 无模型时生成 AI接管写作任务.md 后优雅退出（exit 0），与拆书降级对称。此前该命令直接抛异常堆栈 |
| craft-card 校验报 9 条硬错误？ | 已修复的 bug（AUTO_HINTS 缺条目被误判 voice-card）。若复现检查 validate.py 的 AUTO_HINTS 是否含 `"craft-card"` |
| structure-obs / commercial-obs 校验报 15 条硬错误？ | 已修复（2026-09-01）：此前无对应校验器，auto_kind 兜底误判 voice-card。现已补齐校验器+schema，6 个 obs 资产实测 0 硬错误 |
| Git Bash 传 `/c/xxx` 路径报文件不存在？ | Windows Python 不认 `/c/`，用 `C:/xxx` 或先 `cd` |
| 番茄抓书失败？ | 依赖已装于项目 venv（fontTools/numpy/Pillow），2026-09-01 实测可用；须用 venv 的 `Scripts/python.exe` 且在 novel-lab 根目录运行 fetch_book.py；或手动找 TXT 放入 corpus/ |
| 资产校验出现 WARN？ | voice-card 的 WARN（burst_pattern 缺失等）可入库，建议人工复核；硬错误（✗）才阻塞 |
| pass 输出格式不稳定？ | normalize.py 已兼容 pass2 的 4 种格式与 pass5 的 4 种格式（A/B/C/D），不需要改 prompt |
| 想恢复外部模型？ | `$PY scripts/model_config.py add`，配置存 config/（旧配置备份在 _TRASH） |
| 旧数据在哪？ | 《暮冬念春》终稿：`D:\fanqie-auto\终稿_最新精修版_2026-09-01\`（正文+底层规则，161 文件校验过）；其余在 `C:\Users\monesy\WorkBuddy\_TRASH\`（4 批，可还原） |
| AI 内置拆书完整链路验证过吗？ | **诚实回答**：关键节点（采样/量化/降级/校验/合规）已实测；pass1-5 由 AI 产出→入库的端到端流程尚未在真实新书跑过完整一本，第一本新书即首次实战 |
| 项目还缺什么？ | 技能选用决策表已交付：`docs/技能选用决策表.md`（2026-09-01 下午）；12 技能冗余治理建议见表内 §四。RULES.md 与 HANDOFF.md 的历史节数描述与代码不一致处（以本文件 §4.3 为准） |

---

## 七、当前状态与统计（2026-09-01）

- 已拆书目 3 本：炽炀 / 青柠 / 桑式（campus-redemption 题材，置信 90%）
- 题材包 1 份（聚合产物）；报告 6 份；脚本 21 个（py_compile 全过）；schema 6 个
- **2026-09-01 下午修复**：write.py 无模型降级路径补齐（此前抛异常）；corpus/raw/ 根 4 个暮冬念春残留 pass JSON + novel/state.json 已归档至 `_TRASH\暮冬念春_清理_2026-09-01\novel-lab内\corpus-raw散落残留\`；HANDOFF.md 过时数字已修正
- 工作区干净：暮冬念春全部数据已清出（终稿归档在 D 盘，_TRASH 可还原）
- 《暮冬念春》终稿最新精修版：`D:\fanqie-auto\终稿_最新精修版_2026-09-01\`（159 章最新版 + 第 160 章双版本 + 底层规则包）
- LLM 模式：WorkBuddy 内置智能（无外部模型/密钥/API）
