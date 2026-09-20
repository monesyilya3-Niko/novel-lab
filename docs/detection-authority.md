# 检测口径权威说明（评估报告 P2-3）

> 目的：同类问题存在多套检测时，明确**以谁为准**，避免用户拿到两套数字无所适从。
> 更新：2026-09-21（钩子/开头口径重标定 + realistic-romance 对话带实测）

## 1. 重复检测

| 场景 | 权威入口 | 口径 |
|---|---|---|
| 全书质检 / `novel 质检` | `scripts/book_quality.py` | 跨章句：同一句 ≥2 章报 `low`（相邻标 `adjacent`），≥3 章 `medium`；整段 >30 字相同报段落重复；章内：句读重复 + **无标点 20 字 n-gram 碎片**（区间并集覆盖），按占比 low/medium/high；句读侧有发现时以句读占比定档 |
| QC 十二维 D9「句子重复」 | `scripts/qc.py` | **同上两个检测器并行**：`check_duplicate_sentences` + `check_intra_chapter_repeats`；`raw` 分列 `cross_chapter` / `intra_chapter` |
| QC 十二维 D10「章节重复」 | `scripts/qc.py` | 仅 `check_duplicate_chapters` + `check_duplicate_paragraphs`（整章/整段），**不含**章内碎片 |

**结论**：对外报告与修复优先级，以 **`novel 质检` / `book_quality` 的 issues** 为准（召回最全）；`novel qc` 的 D9/D10 用于评分维度，权重表不因召回提升而改公式。

自写的一次性扫描脚本（历史会话中的 ≥15 字 / ≥2 章等）**不是**权威口径，仅作人工复核参考。

## 2. 矛盾 / 逻辑检测

| 场景 | 权威入口 | 说明 |
|---|---|---|
| 默认（无外部模型） | `scripts/logic_check.py` + `scripts/setting_check.py` | 纯算法：时间线日序（同场景窗口）、数值属性、世界观禁词、别名混用 |
| 可选增强 | `qc --llm-hook` | LLM 二次判定因果；**失败或未配置时自动降级为纯算法**，不得把 LLM 结果当作唯一真相 |

**结论**：交付与门禁以**纯算法结果 + coverage 字段**为准；`coverage.skipped` 非空表示「没检查」而非「0 问题」。

**entities 写入口径（2026-09-18/21，以《暮冬念春》实测为准）**

| 字段 | 规则 | 原因 |
|---|---|---|
| `characters[].attributes` | 登记稳定身份项；**跨年故事禁止静态年龄** | 检测器仅实现「年龄 N 岁」数值对比，成长线会假阳性 |
| `characters[].aliases` | **禁止**常见称谓/短称：「阿姨」「建国」「霜禾」「春屿」等 | 「阿姨」匹配食堂/宿管；「建国」匹配李建国；短称跨章交替会被 appellation 误判 |
| aliases 可登记样例 | 与全名同现的职场称呼（如「温经理」） | 0「仅别名出现」章 → 可开启 alias 检测且零误报 |

## 3. 章节质量分

| 场景 | 权威入口 |
|---|---|
| 单章 12 维 100 分 | `scripts/chapter_check.chapter_check(text, genre_pack)` |
| 阈值 | 默认 PASS≥75 / WARN≥60；题材包 `commercial.quality_thresholds` 可覆盖 |
| 对话占比满分区 | 默认 (0.15, 0.40)；题材包 `dialogue_optimal` 可覆盖 |

**题材对话带实测（权威值，覆盖时以题材包为准）**

| 题材 | dialogue_optimal | 标定依据 |
|---|---|---|
| campus-redemption | 0.07–0.35 | 4 本 voice-card 实测 0.0737–0.3016 |
| realistic-romance | **0.06–0.45** | 《暮冬念春》157 章 p10≈0.087 / median≈0.13 / p90≈0.25，对峙自白章 0.40–0.46（2026-09-21，`f997e22`） |

**章末钩子（2026-09-21 重标定，`9c928ce`）**

| 条件 | 分 |
|---|---|
| hits≥3 + 有效收束 | **12** |
| hits≥3 无收束 / hits==2 + 收束 | 9 |
| hits==2 + 极短收束（末行≤15字） | 10 |
| hits==2 无收束 / hits==1 + 收束 | 6 |
| hits==1 无收束 | 3 |
| 无命中 | 收束 2 / 截断 0 |
| 截断风险 | 再扣 3 |

旧口径「每命中 +3、收束 +2、封顶 12」会使「3 类钩子 + 有效收束」**永远停在 11**，属检测悬崖，已废止。

**开头吸引力（2026-09-21）**

- 窗口：正文 `lstrip()` 后前 400 字；对话看前 200；动作看前 120。
- 四项各 +2：场景建立 / 冲突引入 / 对话开场 / 动作开场。
- 词表须覆盖现实题材：会议室、巷口、车厢、教学楼等；动作含拆/递/签等。
- **6/8 且缺「对话开场」的叙述章属文风选择，不作硬伤**。

连续打分（2026-09-18）后分数可带 1 位小数；**历史分与口径变更前分数不可横比**。

## 4. 资产校验

| 场景 | 权威入口 |
|---|---|
| CLI | `python novel.py 校验 <asset.json>` → `scripts/validate.py` |
| 提交门禁 | `.githooks/pre-commit` 对**暂存的** `assets/*.json` 跑 schema 校验 |
| 服务边界 | GUI `assert_asset_kind`：蒸馏卡/索引不得当单书卡注入或打分 |

**结论**：`validate.py` 的硬错误 = REJECT；警告可入库但需人工复核。

**KNOWN_GENRES 白名单**：craft-card / voice-card 的 `meta.genre` 必须 ∈ `validate.KNOWN_GENRES`。当前：`campus-redemption`、`realistic-romance`。新增题材时先扩白名单，再放资产。

---

维护约定：新增检测器时必须在本表登记权威入口；两套口径并存时必须写明「以谁为准」；**标定类参数变更必须写日期、语料范围与提交号**。

