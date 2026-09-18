# 检测口径权威说明（评估报告 P2-3）

> 目的：同类问题存在多套检测时，明确**以谁为准**，避免用户拿到两套数字无所适从。
> 更新：2026-09-18

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

## 3. 章节质量分

| 场景 | 权威入口 |
|---|---|
| 单章 12 维 100 分 | `scripts/chapter_check.chapter_check(text, genre_pack)` |
| 阈值 | 默认 PASS≥75 / WARN≥60；题材包 `commercial.quality_thresholds` 可覆盖 |
| 对话占比满分区 | 默认 (0.15, 0.40)；题材包 `dialogue_optimal` 可覆盖（campus-redemption=0.07–0.35） |

连续打分（2026-09-18）后分数可带 1 位小数；**历史分与旧档位不可比**。

## 4. 资产校验

| 场景 | 权威入口 |
|---|---|
| CLI | `python novel.py 校验 <asset.json>` → `scripts/validate.py` |
| 提交门禁 | `.githooks/pre-commit` 对**暂存的** `assets/*.json` 跑 schema 校验 |
| 服务边界 | GUI `assert_asset_kind`：蒸馏卡/索引不得当单书卡注入或打分 |

**结论**：`validate.py` 的硬错误 = REJECT；警告可入库但需人工复核。

---

维护约定：新增检测器时必须在本表登记权威入口；两套口径并存时必须写明「以谁为准」。
