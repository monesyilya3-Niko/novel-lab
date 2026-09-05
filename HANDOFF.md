# novel-lab 小说拆书学习 + 创作系统 · 完整交接文档

> **用途**：开启新对话时的完整上下文。新对话先读本文件即可无缝接手。
> **最后更新**：2026-09-01（整合"拆书系统" + 清出暮冬念春全部数据，工作区已重置干净）
> ⚠️ 本文数字与 PROJECT_SUMMARY.md 不一致时，一律以 PROJECT_SUMMARY（基于当日实测）为准。2026-09-01 下午已修正本文 5 处过时数字（13→14 资产 / 17→15 子命令 / 9-10→6-10 节 / 16→14 JSON）
> **项目路径**：`C:\Users\monesy\WorkBuddy\2026-08-06-16-49-41\novel-lab\`

---

## 一、项目定位

**一句话**：把优秀小说拆成可复用的结构化资产，再用这些资产驱动创作。

**核心价值**：
1. 拆书独立成层，产出**可版本化的资产文件**（voice-card / craft-card / genre-pack）
2. **商业层分析**（爽点密度/付费卡点）——市面同类项目零覆盖
3. **笔法深度分析**（10 维技法拆解）——从"拆结构"到"拆笔法"
4. **章节质量自检**（12 维 100 分制）+ **全书内容质检**（6 类检测）
5. **三维度改写循环**（一致性 + 章节质量 + 内容质检）

---

## 二、当前状态（2026-09-01，暮冬念春数据已清出，可开新一轮）

### 已拆书目（3 本）

| 书名 | 角色 | 口头禅 | 比喻 | 五感 | 修辞 | 笔法技法 | 笔法维度 | 置信 |
|---|---|---|---|---|---|---|---|---|
| 炽炀（chireng） | 4 | 21 | 2 | 5 | 2 | 10 | 5/10 | 0.9 |
| 青柠（qingning） | 4 | 33 | 2 | 5 | 1 | 8 | 5/10 | 0.9 |
| 桑式（sangshi） | 7 | 30 | 2 | 5 | 2 | 6 | 3/10 | 0.9 |

> 暮冬念春（原第 4 本，10/10 维度最全）已于 2026-09-01 整体清出（用户要求开新一轮干净工作区）。其终稿最新精修版已归档至 `D:\fanqie-auto\终稿_最新精修版_2026-09-01\`（161 文件逐字节校验一致）；全部 QA 工作区与拆书数据在 `C:\Users\monesy\WorkBuddy\_TRASH\暮冬念春_清理_2026-09-01\`（可还原）。

### 产出文件

**assets/**（13 个资产文件，全部通过校验+合规；2026-09-05 起合成测试卡已退役删除）
- 3 × voice-card.json（声线卡）
- 3 × craft-card.json（笔法卡）
- 3 × structure-obs.json（结构观测）
- 3 × commercial-obs.json（商业观测）
- 1 × campus-redemption-genre-pack.json（题材包）

**reports/**（6 份报告，可交付）
- 3 × 拆书报告.md
- 3 × 笔法分析.md

### 题材包

- **铁律 4 条**：第三人称限知 / 情绪爆发短句 / 体感式情绪 / 日常物件比喻
- **必需要素 4 条**：直白内心活动 / 校园生活细节 / 情感物件 / 短句爆发点
- **禁用词 11 条**：恍若/霎时/眸/幽幽/宛如/仿佛/深邃/凝视/嘴角上扬/眸光/薄唇
- **疲劳词 5 条**：深吸一口气≤2 / 心跳漏了一拍≤1 / 她不知道≤3 / 像是≤4 / 她忽然≤3
- **置信度**：0.85

---

## 三、架构与工作流

```
┌─ 拆书 ──────────────────────────────────────────────┐
│ pipeline.py   TXT → 采样 → 五遍扫描 → 归一化 → 资产 │
│   ├ sampler.py     27章采样（开篇10+中段15+卷末2）   │
│   ├ metrics.py     量化指标（句长/对话占比/TTR/五感） │
│   ├ Pass1-4 prompt 结构/人物/文风/商业 各自独立可跑   │
│   ├ Pass5 prompt   笔法分析（10维技法拆解）           │
│   ├ normalize.py   中文键 → schema 结构（模糊匹配）   │
│   └ validate/compliance  校验 + 版权合规              │
├─ 聚合 ──────────────────────────────────────────────┤
│ pass5_aggregate.py  ≥3本同题材 → genre-pack 题材包    │
├─ 创作 ──────────────────────────────────────────────┤
│ inject.py   资产 → 写作 system prompt（6-10节）      │
│ write.py    生成+三维度改写循环(一致性+质量+质检)     │
│ consistency.py 五维打分（声线35/情绪20/叙述15/禁忌20/意象10）│
│ chapter_check.py 12维100分制章节质量自检              │
│ book_quality.py 6类全书内容质检                       │
├─ 产出 ──────────────────────────────────────────────┤
│ report.py       资产 → 可交付拆书报告                 │
│ report_craft.py craft-card → 可交付笔法分析报告       │
│ novel.py        CLI 统一入口（15 子命令）             │
└──────────────────────────────────────────────────────┘
```

**Python 运行**：
```bash
PY="C:/Users/monesy/.workbuddy/binaries/python/versions/3.13.12/python.exe"
cd C:/Users/monesy/WorkBuddy/2026-08-06-16-49-41/novel-lab
```

---

## 四、CLI 命令速查

```bash
# 一键分析新书（拆书+报告+笔法+自动质检）
novel.py 分析 book.txt --genre campus-redemption

# 拆书（pipeline 五遍扫描）
novel.py 拆书 book.txt --genre campus-redemption

# 组装资产（AI 产出 pass1-5 后一键入库，2026-09-01 新增）
novel.py 组装 书名 --genre campus-redemption

# 注入资产为写作 prompt（含 craft-card）
novel.py 注入 voice-card.json --craft-card craft-card.json --genre-pack genre-pack.json

# 写章节（三维度改写循环）
novel.py 写作 voice-card.json --chapter 3 --task "要点" --voice voice-card.json

# 章节检查（12维100分制 + 一致性）
novel.py 检查 chapter.txt --voice voice-card.json

# 全书质检（重复/连贯/凑字数/乱编/AI味）
novel.py 质检 chapter_dir/

# 拆书报告 / 笔法报告
novel.py 报告 voice-card.json --structure ... --commercial ...
novel.py 笔法报告 craft-card.json

# 其他
novel.py 校验 asset.json
novel.py 合规 asset.json book.txt
novel.py 模型 --test mimo
novel.py 状态
```

---

## 五、核心脚本清单（19 个）

| 脚本 | 作用 |
|---|---|
| `pipeline.py` | 拆书主流程：采样→量化→五遍扫描→归一化→资产→校验→合规 |
| `assemble.py` | 资产组装（2026-09-01 新增）：读 pass1-5 → 归一化 → 组装 4 类资产入库，补上"AI 产出→入库"最后一公里 |
| `sampler.py` | 分层采样：开篇10+中段15+卷末2 |
| `metrics.py` | 量化指标：句长/对话占比/TTR/五感词 |
| `normalize.py` | LLM 中文键→schema 结构（模糊匹配，兼容 4 种 pass2 格式） |
| `validate.py` | schema 校验（voice-card/craft-card/genre-pack/trope-library） |
| `compliance.py` | 版权合规（12字原文匹配→REJECT） |
| `inject.py` | 资产→写作 system prompt（10节：叙述/声线/情绪/意象/结构/商业/笔法/禁忌/执行清单） |
| `write.py` | 章节生成：三维度改写循环（一致性+章节质量+质检） |
| `consistency.py` | 五维一致性打分（声线35/情绪20/叙述15/禁忌20/意象10） |
| `chapter_check.py` | 12维100分制章节质量自检（字数/对话/钩子/开头/情绪/直陈式/节奏/结构/AI味/疲劳词/让字/情绪标签） |
| `book_quality.py` | 全书内容质检（跨章重复/情节连贯/风格一致/凑字数/乱编/AI味） |
| `report.py` | 拆书报告生成器 |
| `report_craft.py` | 笔法分析报告生成器 |
| `pass5_aggregate.py` | ≥3本同题材→题材包聚合 |
| `batch.py` | 批量拆书 |
| `clean_verbatim.py` | 清除资产中夹带的原文台词 |
| `model_config.py` | 模型配置 CLI |
| `llm_client.py` | 统一调用层（openai/anthropic/ollama） |

---

## 六、模型配置（2026-09-01 起：无外部模型，LLM 层 = WorkBuddy 内置智能）

**当前模式**：不调用任何外部 LLM API。拆书五遍扫描（pass1-5）与写作改写循环由 **WorkBuddy AI（主会话智能体）直接读文本完成**——AI 自己阅读采样章节，按 `prompts/pass1-5` 的要求产出分析，再走 normalize → validate → compliance 流程入库。

**已删除**（2026-09-01 用户指令）：mimo（token-plan 网关，401 失效）与 ds（未配密钥）的全部配置和密钥，备份在 `_TRASH\暮冬念春_清理_2026-09-01\novel-lab内\config删除\`。

**新工作流（AI 内置模式）**：
1. AI 读 `prompts/pass1_structure.md` 等 prompt 要求 + 采样章节（corpus/sampled/）
2. AI 在会话中直接产出分析 JSON（无需 llm_client.py）
3. 用 `scripts/normalize.py` + `novel.py 校验` + `novel.py 合规` 走完入库流程
4. 写作同理：AI 按 inject 产出的 system prompt 写章节，用 `novel.py 检查`（本地 12 维打分）自检

**如需恢复外部模型**（可选）：`python scripts/model_config.py` 重新配置，`config/.secrets.json` 存密钥。llm_client.py 保留在 scripts/ 但当前无配置不使用。

---

## 七、pass5 输出格式兼容（4 种）

pass5 模型输出格式不稳定，pipeline 必须兼容 4 种：

| 格式 | 特征 | 示例书 |
|---|---|---|
| A | `{craft_analysis: {dim: {techniques: [...]}}, craft_summary: {...}}` | 理想格式 |
| B | `{chapter_analysis: [{chapter_range, techniques: [...]}]}` | chireng |
| C | `{techniques: [{name, abstract_skeleton, effect, ...}]}` | qingning/sangshi |
| D | `{foreshadowing: [{abstract_pattern, 反例, effect}], ...}` | 暮冬念春 |

字段名变体：`name`/`technique_name`/`scenario`、`abstract_pattern`/`skeleton`、`anti_example`/`反例`/`counter_example`、`execution`/`method`。

pipeline 已全部兼容，新增书不需要额外处理。

---

## 八、chapter_check 评分体系（12 维 100 分）

| 维度 | 分值 | 检测内容 |
|---|---|---|
| 字数 | 8 | ≥1500 满分 |
| 对话占比 | 12 | 15-40% 满分 |
| 章末钩子 | 12 | 悬念/断句/情感冲击 |
| 开头吸引力 | 8 | 前 200 字冲突/悬念/场景 |
| 情绪密度 | 12 | 每 400 字≥1 处体感词 |
| 直陈式情绪词 | 8 | 零出现满分 |
| 段落节奏 | 8 | 短段占比 10-40% |
| 结构完整性 | 8 | 有开头/发展/收束 |
| AI 味检测 | 4 | 模板句式扣分 |
| **疲劳词检测** | **8** | "了"字密度/情绪标签/连接词/感叹词 |
| **"让"字专项** | **5** | "让"字过多=AI味重灾区 |
| **情绪标签词** | **7** | 旁白中的情绪标签滥用 |

---

## 九、book_quality 全书质检（6 类）

| 类型 | 检测内容 | 严重度 |
|---|---|---|
| 跨章重复 | 重复章节(>70%)/重复段落(>30字)/重复句子(>12字跨≥3章) | 🔴🟠🟡 |
| 情节连贯 | 时间线矛盾/人物情绪矛盾 | 🟡 |
| 风格一致 | 比喻密度波动/情绪写法模式漂移 | 🟡 |
| 凑字数 | 段落重复/环境描写占比过高(>40%) | 🟠🟡 |
| 乱编检测 | 人名错误/数字矛盾 | 🟠 |
| AI味检测 | 作者预告旁白/记忆闪回模板/伤口比喻等8种 | 🟡 |

---

## 十、write.py 三维度改写循环

```
生成初稿
  ↓
① 一致性打分（voice-card: 声线/情绪/叙述/禁忌/意象）
② 章节质量（chapter_check: 12维100分制）
③ 内容质检（book_quality: 重复/连贯/凑字数/乱编/AI味）
  ↓
三维度全部达标 → 通过
任一不达标 → 提取扣分点 → 改写 → 重新打分（最多3轮）
```

---

## 十一、已知限制

1. **3 本旧书 craft-card 覆盖 3-5/10 维**：pass5 原始输出缺少 narrative_engine/emotional_algorithm 维度，需重跑 pass5 才能改善
2. **Pass2 输出格式不稳定**：有时输出 `characters[]`（新格式），有时输出 `character_voices[]`（旧格式），normalize.py 已兼容
3. **合规扫描 12 字匹配**：voice-card/craft-card 全部通过，structure-obs/commercial-obs 偶有匹配（已改为只警告不阻塞）
4. **番茄小说抓取**：依赖 fontTools+numpy+Pillow 已装于项目 venv，2026-09-01 实测联网可用；须用 venv 的 `Scripts/python.exe` 且在 novel-lab 根目录运行 fetch_book.py（脚本用相对路径）
5. **LLM 层已切换为 WorkBuddy 内置智能（2026-09-01）**：mimo/ds 外部模型及密钥已按用户指令删除。pass1-5 与写作改写由 AI 在会话内直接完成（见第六节新工作流），不再有 API 依赖；`novel.py 拆书` 等原走 llm_client 的命令需要 AI 按 prompts 手动接管。本地功能（指纹拆书/章节检查/全书质检/报告/校验合规）不受影响。

---

## 十二、下一步建议

1. **拆新书**：找一本新的校园救赎小说，用 `novel.py 分析 book.txt --genre campus-redemption` 一键分析
2. **重跑 3 本旧书 pass5**：用更新后的 10 维 prompt 重跑，提升 craft-card 覆盖度
3. **开新一轮创作**：用 3 本书的资产 + 题材包注入写作（`novel.py 注入 ... --genre-pack assets/campus-redemption-genre-pack.json`）
4. **M1.6 人工校验**：确认 voice-card 角色声线/文风准确度 ≥70%

---

## 十三、文件结构

```
novel-lab/
├── novel.py                    # CLI 统一入口（15 子命令）
├── HANDOFF.md                  # 本交接文档
├── RULES.md                    # 可执行规则全集
├── MODELS.md                   # 模型配置手册
├── assets/                     # 拆书产出资产（14个JSON）
├── config/                     # 模型配置 + 密钥
├── corpus/                     # 语料库（原始文本+采样+分析）
├── novel/                      # 创作项目目录
├── outputs/                    # 输出文件
├── prompts/                    # 拆书prompt + 生成的写作prompt
├── reports/                    # 拆书报告+笔法分析报告（8份）
├── schema/                     # JSON Schema（voice-card/craft-card/genre-pack/trope-library）
├── scripts/                    # 核心Python脚本（18个）
├── docs/                       # 评估报告 + 指纹拆书使用说明 + 过期计划归档
└── 指纹拆书/                    # 指纹法拆书工作目录（样本/指纹库/分析报告）
```

---

## 十四、2026-09-01 整合记录：指纹拆书工作流并入

原独立的"拆书系统"（2026-08-31 会话产物）已并入本项目，原目录已删除。整合内容：

### 新增目录

| 目录 | 内容 |
|---|---|
| `docs/` | 项目评估报告 4 份（完善度评估 + 3 本书验证 + Phase1-3 完善报告）|
| `docs/指纹拆书_使用说明.md` | 指纹法拆书完整工作流（实测数据、版权边界、已知局限）|
| `docs/archive/` | 过期分析计划 v1-v3（已被 v4 取代，留作历史）|
| `指纹拆书/` | 指纹法工作目录：样本测试（3 段风格样本）/ 指纹库 / 分析报告 |

### 指纹法工作流（与主拆书引擎互补）

主引擎（pipeline.py 五遍扫描）产出结构化资产；指纹法走 Skill 路线，两者互补：

1. 放书 → `指纹拆书/` 下建题材目录（支持 .txt/.epub，gb18030/gbk/utf-8 编码回退）
2. 拆结构：`~/.workbuddy/skills/webnovel-reverse-analysis/scripts/novel_analyzer.py <书> --output 分析报告/`
3. 提指纹：`~/.workbuddy/skills/novel-writing-pipeline/scripts/fingerprint_extract.py --corpus <书目录> --out 指纹库/<名>.json`
4. 人工把统计数字翻译成手法清单（句长/逗号密度/对话率 → 可执行写法规则）
5. 写作时配合 9 角色流水线 + `ai_taste_check.py` 去 AI 味门禁

**技能依赖**：两个核心 Skill **双重安装**——① 全局 `~/.workbuddy/skills/`（所有会话可用）；② 项目级 `2026-08-06-16-49-41\.workbuddy\skills\`（2026-09-01 装入，项目自包含）。3 个实测 bug 修复（章节正则首行漏检 / 角色动词表扩到 62 个 / 输出目录自动创建）已验证**两处安装位均生效**（副本 --help 冒烟通过）。全局另装 10 个小说类技能备用：story-deslop（去AI味）/ humanizer（降AI腔）/ long-novel-writer（长篇）/ novel-expert（创作指导）/ silver-novel-skills / novel-writing / open-novel-writing / human-writing / fbs-bookwriter / write。

**版权边界**：只提取统计特征（句长、节奏、对话占比），不落任何原文片段。学手法不抄内容。

### 本次清理

- 删除 `__pycache__/`、`scripts/__pycache__/`（可再生）、`corpus/debug/`（LLM 调试产物）、空目录 `报告/`
- 过期计划 v1-v3 移入 `docs/archive/`（未删除）

---

## 十五、2026-09-01 暮冬念春数据清出（工作区重置）

用户要求清掉已拆完的《暮冬念春》全部数据，开新一轮干净工作区。执行内容：

**清出前先归档（安全前提）**：
- 最新精修终稿（159 章最新版 + 第 160 章双版本）→ `D:\fanqie-auto\终稿_最新精修版_2026-09-01\`，161 文件逐字节 `cmp` 校验全部一致，含 README 说明来源
- 注意：`D:\fanqie-auto\fanqie_ready\` 是 08-13 旧版，最新版在上述归档目录

**清出的内容**（移入 `C:\Users\monesy\WorkBuddy\_TRASH\暮冬念春_清理_2026-09-01\`，可还原）：
- novel-lab 内：正文/（159章+11个备份）、规格/、评审/、设定/、追踪/、corpus/muzhidongnian_*（含 sampled/raw）、assets 4 件、reports 2 份、写作 prompt、output、创作项目 novel/muzhidongnian/、analysis_group_1-5.json、修复计划×2、analysis_plan_v4.md
- 旧 QA 会话整个目录：`2026-08-11-03-17-08/`（真实精读笔记、逐章深挖、各类备份）
- 题材包 campus-redemption-genre-pack.json 保留（聚合产物，不依赖被清资产）

**清出后状态**：novel-lab 内 `find -iname "*muzhi*" -o -iname "*暮冬*"` 零残留；已拆书目 4→3 本。

---

*本交接文档由 novel-lab 开发过程完整沉淀，确保新对话零信息损失接手。*
