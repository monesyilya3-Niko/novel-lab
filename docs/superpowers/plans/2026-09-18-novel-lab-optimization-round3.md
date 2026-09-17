# novel-lab 优化第三轮（用户已决 6 项）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落实用户对 6 项待决事项的决定：阈值重标定、章内重复接入 qc、payoff_types 口径归一、LLM 备用模型路由、Inno Setup 安装与 setup.exe 重建；并解释悬崖档位。

**Architecture:** 三项改评分/检测语义（3.1 阈值、3.2 qc 接入、3.3 数据口径），两项改基础设施（3.4 模型路由、3.5 安装包）。前三项会**改变历史分数**（用户已明确接受），因此必须同步更新受影响的资产与快照。

**Tech Stack:** Python 3.13 标准库；POSIX sh；Inno Setup 6（经 winget 安装）；零第三方 Python 依赖。

**用户决定（原话）**：
1. 了字密度阈值 → 「最优方案」
2. 悬崖档位 → 「解释一下」（**本轮只解释，不实施**）
3. 章内重复接入 qc → 「加入并且完善」
4. setup.exe → 「同意」
5. payoff_types ratio → 「最优方案」
6. LLM 备用模型 → 「可以」

## Global Constraints

- `scripts/` 与 `gui/` 后端只用 Python 标准库。
- 测试使用临时目录或内存对象；不触碰真实 `assets/`（除 Task 3.3 明确要求的资产再生成）、`gui_state/`、用户目录。
- 每任务收尾运行全量 `run_tests.py`（当前基线 **648 tests OK**）；55 资产保持 **0 REJECT**。
- 使用 `C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B`。
- 提交信息用英文小写前缀。
- 不访问 `C:/Users/monesy/.workbuddy/` 与 `C:/Users/monesy/WorkBuddy/`。

---

### Task 3.1: 了字密度阈值按语料分位数重标定（决定 1「最优方案」）

**Files:**
- Modify: `scripts/chapter_check.py`（`check_fatigue_words`）
- Modify: `tests/test_thresholds.py` 或新建 `tests/test_fatigue_calibration.py`

**现状（实测）**：`>5` 扣 1 分 / `>8` 扣 3 分。章粒度分位数（6 本书 54 章）：`p05=13.3 / p50=23.9 / p75=27.0 / p90=31.2`。**现行阈值导致 100% 的章扣满 3 分、0% 不扣分**，该维度完全无区分度。

**设计（分位数标定）**：
- 不扣分：`le_density <= 27.0`（语料 p75）
- 扣 1 分：`27.0 < le_density <= 31.2`（p75–p90）
- 扣 3 分：`le_density > 31.2`（> p90）

**为什么用 p75 而非报告里草拟的 p50**：p50 仍会对**一半的合格作品**征税，与本修复的目的（让维度只标记真正的异常）相悖。p75 意味着语料内 75% 的章节不再被扣分，只有 top 25% 轻微扣分、top 10% 明显扣分——这才是一个「疲劳」信号该有的形状。**若用户更认可 p50/p90，改两个常量即可。**

**实现要求**：
- 把三个阈值提为模块级常量并加注释写明标定依据（语料、章数、分位数、标定日期）。
- 其余两个子项（情绪标签词 `> cn/200` 扣 2；连接词 `>5` 扣 1）**保持不变**。
- `check_fatigue_words` 的返回格式与 `details` 文案结构不变（只改数值与阈值判断）。

**验收**：
- `le_density = 10`（旧口径扣 3）→ 新口径 **8/8 不扣分**。
- `le_density = 29` → 扣 1 分（7/8）。
- `le_density = 35` → 扣 3 分（5/8）。
- 情绪标签词与连接词两个子项的既有行为**逐项不变**（补回归断言）。
- 全量测试通过（受影响的既有断言需按新口径更新，并注明原因）。

---

### Task 3.2: 章内重复接入 QC 十二维并完善（决定 3「加入并且完善」）

**Files:**
- Modify: `scripts/qc.py`（`_dim_sentence_dup` / `_dim_chapter_dup`）
- Modify: `tests/test_quality_service.py` 或新建 `tests/test_qc_intra_repeat.py`

**现状**：`qc.py` 的 D9（句子重复）只调 `check_duplicate_sentences`；D10（章节重复）只调 `check_duplicate_chapters` + `check_duplicate_paragraphs`。**`check_intra_chapter_repeats`（上一轮新增）未被任何维度消费** → `novel 质检` 会因章内 46% 重复报 WARN，但 `novel qc` 总分完全不受影响（双命令不对称）。

**设计**：
- D9「句子重复」= `check_duplicate_sentences`（跨章句）**+** `check_intra_chapter_repeats`（章内碎片）。理由：两者都是「句子级重复」，语义同族；且章内碎片正是「句子重复」的最严重形态。
- D10「章节重复」保持 `check_duplicate_chapters` + `check_duplicate_paragraphs` 不变。
- 「完善」的具体含义（3 项）：
  1. `raw` 中分别记录两个来源的 issue 数（`cross_chapter` / `intra_chapter`），便于追溯是哪种重复拉低了分数。
  2. D9 的 issue 严重度沿用检测器给出的值（章内 ≥25% 为 `high`），**不改扣分权重表**。
  3. 在 `qc.py` 模块 docstring 的四层十二维映射表中，把 D9 的来源更新为两个函数。

**验收**：
- 构造「章内 46% 碎片重复」的章节目录 → `run_qc()` 的 D9 分数下降（不再是 100），且 `raw` 含 `cross_chapter`/`intra_chapter` 两个计数。
- 构造「相邻两章共享一句」→ D9 有 issue 且分数下降（上一轮已生效，不得回退）。
- 构造无重复文本 → D9 = 100.0。
- `verdict` 判定规则与 `_severity_to_deduct` 权重表**零改动**。

---

### Task 3.3: payoff_types 的 ratio 口径归一（决定 5「最优方案」）

**Files:**
- Modify: `scripts/distill_core.py`（`align` 的 payoff_types 归一 / `_dedup_payoff_types` 聚合）
- Modify: `tests/test_distill.py`
- 再生成：`assets/campus-redemption-commercial-obs-distilled.json`（经 `distill.run_distill`）+ `dashboard/dashboard-data.js`

**现状（实测四种单位混在一起）**：

| 来源书 | `ratio` 形态 | 样例 |
|---|---|---|
| chireng | 次数/百分比 | 打脸=40, 升级=10, 收益兑现=30, 情感回应=20 |
| qingning | 次数（散落字符串） | `"情感回应:7，他人认可:2，反杀:1"` |
| suyixinjian | **占比 0–1** | 情感回应=0.45, 他人认可=0.25, 反杀=0.15, 身份揭露=0.15 |
| sangshi | **另一种指标** | `"铺垫:爆发 = 10:1 (按章计算…)"` |

聚合后 `ratio` 变成 40+10+30+20+2.0+1.0 = **103**（既不是次数也不是占比），schema 却声明该字段是「在全书中的占比」。

**设计（归一为占比后再聚合）**：
1. 在 `align()` 处理 `commercial-obs` 的 `payoff_types` 时，对**每本书内部**先把该书的 ratio 归一为占比：`share = ratio_i / sum(该书可解析的 ratio)`。
   - chireng：40,10,30,20 → 0.4/0.1/0.3/0.2
   - qingning：7,2,1 → 0.7/0.2/0.1
   - suyixinjian：0.45,0.25,0.15,0.15 → 原样（其和已为 1.0）
   - sangshi：不可解析（不是占比也不是次数）→ 该书不贡献 ratio（记为 `None`）
2. 聚合时，同一 `type` 的 `ratio` 取**各书贡献值的中位数**（与其它数值字段的聚合策略一致），无任何书贡献则 `None`。
3. `sources` 保留各书**原始**值（不归一），保证溯源不丢信息。
4. 归一后的占比之和应 ≈ 1.0（同一 type 可能被多书贡献，故不强制断言；但需在测试中断言 chireng 单书归一后之和为 1.0）。

**验收**：
- 归一后，chireng 的四项占比之和 == 1.0（浮点容差 1e-6）。
- 聚合结果的 `ratio` 全部落在 `[0, 1]` 或为 `None`（**不得出现 40 / 103 这类值**）。
- `sources` 仍含各书原始值。
- 再生成蒸馏卡后 `validate.py` 通过（0 REJECT）。
- `dashboard/dashboard-data.js` 重建，冒烟测试 19/19。

---

### Task 3.4: LLM 备用模型路由（决定 6「可以」）

**Files:**
- Modify: `scripts/llm_client.py`（`chat` / 新增 fallback 解析）
- Modify: `scripts/model_config.py`（新增 `fallback` 子命令，可选）
- Modify: `tests/test_model_config.py` 或新建 `tests/test_llm_fallback.py`

**现状**：`llm_client.py` 的模块 docstring 第 4 条写「失败可回退到备用模型」，但**代码里没有实现**——`chat()` 只对同一模型重试 `retries` 次，失败即抛 `LLMError`。且当前只配了 1 个模型。

**设计（加性、不改既有签名语义）**：
1. 新增 `resolve_fallback_chain(task, model_id) -> list[str]`：按顺序给出候选模型 id：
   - 主模型（`resolve_model` 的结果）→ `model.fallback`（模型配置里的可选列表）→ `roles.default` 指向的模型 → 其余已配置模型（按配置顺序）。
   - 去重、排除主模型本身、只保留实际存在于 `cfg["models"]` 的 id。
2. `chat()` 增加 `allow_fallback: bool = True` 参数（默认 True，向后兼容）：
   - 对链上**每个**模型执行现有的「重试 `retries` 次」逻辑；
   - 一个模型彻底失败后，换下一个候选；
   - 全部失败 → 抛 `LLMError`，错误信息包含**每个候选的失败原因**（而不是只报最后一个）。
   - **失败原因分类**：余额/权限类（HTTP 401/403 或响应含 `INSUFFICIENT_BALANCE` / `insufficient`）→ 标记为「不可重试」并立即换下一个候选（不浪费时间重试）；网络类（`URLError`/超时）→ 正常重试。
3. `model_config.py` 新增 `fallback <model_id> [<model_id> ...]` 子命令，把备用模型列表写入该模型的 `fallback` 字段（`[]` 表示清空）。
4. 保持 `test_model()` 的 `retries=0` 行为不变（连通性测试不应触发备用链路）。

**验收**：
- 主模型抛 403 + `INSUFFICIENT_BALANCE` → 立即切到备用模型并成功返回（**断言主模型未被重试**，即调用次数为 1）。
- 主模型网络失败 → 重试 `retries` 次后切备用。
- 全链路失败 → `LLMError` 且消息含每个候选的失败原因。
- 只有一个模型且它失败 → 错误信息明确说明「无可用备用模型」。
- `allow_fallback=False` → 行为与改造前完全一致（只重试主模型）。
- 不联网：用 monkeypatch 打桩协议 handler。

---

### Task 3.5: 安装 Inno Setup 并重建 setup.exe（决定 4「同意」）

**Files:**
- 产物：`build/dist/novel-lab-setup-v1.0.0.exe`（重新生成）

**设计**：
1. `winget install --id JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements`（Inno Setup 6.7.3）。
2. 确认 `ISCC.exe` 可执行（winget 装到 `%LOCALAPPDATA%\Programs\Inno Setup 6\` 或 `Program Files (x86)`）。
3. 用 `iscc build/installer.iss` 编译，产出覆盖 `build/dist/novel-lab-setup-v1.0.0.exe`。
4. **注意**：`installer.iss` 可能需要先有 `build/dist/novel-lab-portable-v1.0.0/`（便携包）作为输入——先读 iss 确认依赖顺序，必要时先重建便携包。

**验收**：
- `ISCC.exe` 编译退出码 0，产物存在且体积合理（此前约 13 MB）。
- 记录编译输出摘要（文件数、压缩率）。
- 不修改 `build/installer.iss` 的内容，除非其中含跨实例或失效路径（若需改，先报告再改）。

---

### 不实施项：悬崖档位（决定 2「解释一下」）

用户要求**先解释**。本轮只在交付报告中给出解释与方案对比，**不改任何代码**。解释要点见交付报告。

---

## 依赖与顺序

```text
3.1（阈值）─┐
3.2（qc 接入）─┼─ 均改评分语义，互不冲突（不同文件），可串行
3.3（数据口径）─┘  3.3 依赖 3.1/3.2 吗？不依赖，但改完 3.3 要重建 dashboard
3.4（模型路由）── 独立
3.5（安装包）── 必须最后（依赖全部代码改动完成后再打包）
```

## 明确不做

- 悬崖档位改连续打分（用户要求先解释）
- 便携包在 3.1~3.4 全部完成前不重建（避免反复失效）；3.5 会一并处理

## 计划自审

- **Spec coverage:** 用户 6 项决定全部有对应任务或明确标注「本轮只解释」。
- **Placeholder scan:** 每项给出精确文件、常量、阈值、验收条件。
- **Type consistency:** `resolve_fallback_chain` / `allow_fallback` 命名在 3.4 内一致；3.3 的 `share` 归一策略与既有 `_dedup_payoff_types` 衔接。
