# novel-lab 优化第二轮（报告「立即可做」清单）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 `novel-lab问题评估_20260916.md` 中「立即可做（低风险、高收益）」尚未完成的 3 项，并补齐 3 项存量数据缺口。

**Architecture:** 三项代码改动均为**加性/收敛性**改动——重复检测提高召回、检测项新增覆盖率字段、pre-commit 增加资产校验；不改任何既有返回签名、不改评分权重、不改严重度判定规则（`critical>0→FAIL`、`high>=5→FAIL`、`high>0→WARN`）。三项数据补齐只补缺失字段/重建过期快照。

**Tech Stack:** Python 3.13 标准库；POSIX sh（pre-commit）；零第三方依赖。

**Spec:** `C:\Users\monesy\niko\2026-09-16-15-51-35\novel-lab问题评估_20260916.md`（问题清单与建议来源）

## Global Constraints

- `scripts/` 与 `gui/` 后端只用 Python 标准库；不得引入第三方包。
- 不得修改既有函数签名与返回结构；新增信息一律以**追加字段**方式提供。
- 不得改动严重度判定规则与 12 维评分权重/阈值。
- 测试使用临时目录或内存对象，不触碰真实 `assets/`、`gui_state/`、用户目录。
- 使用受管解释器：`C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe -B`。
- 当前基线：**Ran 558 tests / OK**；55 个生产资产 **0 REJECT**。
- 每任务收尾运行全量 `run_tests.py`；提交信息用英文小写前缀（`fix:` / `feat:` / `test:` / `chore:` / `data:`）。

---

### Task A: 提升重复检测召回（报告 P0-2）

**Files:**
- Modify: `scripts/book_quality.py`（`check_duplicate_sentences`、`check_duplicate_paragraphs` 附近，新增函数）
- Modify: `scripts/book_quality.py::book_quality_check`（接入新检测）
- Create: `tests/test_duplicate_recall.py`

**问题（报告 P0-2 实证）：**
1. `check_duplicate_sentences` 只在同一句出现在 **≥3 章** 时报告 → 只在相邻两章重复的（读者最易察觉）永远不报。
2. 段落检测只认「>30 字整段完全相同」→ 无法识别「同一句碎片散布在多个段落中」的形态。项目自己吃过亏：一次 2000 字里 937 字重复的 automerge 编辑事故被 `novel 质检` 判 PASS。

**设计：**

1. `check_duplicate_sentences` 阈值 **≥3 章 → ≥2 章**；新增 `adjacent` 布尔字段标记「重复章号中存在相邻章（差值为 1）」。
   - **严重度不变**：2 章 → `low`（新增，不影响判定规则）；≥3 章 → `medium`（与现状一致）。
   - `detail` 在相邻时追加「（相邻章）」字样。
2. 新增 `check_intra_chapter_repeats(texts) -> list`：检测**章内**重复句子（≥10 字的句子在同一章内出现 ≥2 次）。
   - 按「重复句子占该章句子总数的比例」定严重度：`>= 0.25` → `high`；`0.10 ~ 0.25` → `medium`；`< 0.10` → `low`。
   - 每章最多报 1 条（聚合），`detail` 含重复句数、总句数、占比、最长重复句前 30 字。
   - 类型 `intra_chapter_repeat`。
3. `check_duplicate_paragraphs` **保持不变**（>30 字整段），避免召回口径漂移；碎片形态由第 2 项覆盖。
4. `book_quality_check` 在 `len(texts) >= 2` 分支接入 `check_duplicate_sentences`（已接入）、并把 `check_intra_chapter_repeats` 放到**逐章循环**里（单章也需检测）。

**验收：**
- 同一句出现在 2 章 → 报告 1 条 `duplicate_sentence`、`severity=low`、`adjacent=true`。
- 同一句出现在 3 章 → 报告 1 条、`severity=medium`（与现状一致，不回退）。
- 章内 46% 句子重复 → 报告 1 条 `intra_chapter_repeat`、`severity=high`。
- 章内 5% 句子重复 → `severity=low`。
- 无重复文本 → 0 条。
- 全量 558 测试仍 OK（新增用例数上升）。

---

### Task B: 检测项补覆盖率字段（报告 P2-1）

**Files:**
- Modify: `scripts/logic_check.py`（`check_logic` 返回值旁提供覆盖率信息）
- Modify: `scripts/setting_check.py`（`check_setting` 同上）
- Modify: `scripts/book_quality.py`（`book_quality_check` 结果加覆盖率）
- Create: `tests/test_coverage_fields.py`

**问题：** 缺 `entities.json` 时「称呼矛盾/状态矛盾」直接跳过、数值检测读不到数据、声线卡无角色 —— 输出都是「0 问题」，**与「没检查」无法区分**。

**设计（加性、不改签名）：**
1. 各检测模块新增 `*_coverage(...) -> dict` 函数（**新函数，不动既有签名**），返回形如：
   ```python
   {"entities_loaded": bool, "checks": {"number": True, "timeline": True,
     "appellation": False, "state": False}, "evaluable": ["number","timeline"],
     "skipped": ["appellation","state"], "skipped_reason": "缺少 entities.json"}
   ```
2. `book_quality_check()` 的返回 dict **追加** `"coverage"` 键（既有键全部保留、语义不变）。
3. `logic_check.main()` / `setting_check.main()` 在非 JSON 输出下，若存在 skipped 项，打印一行「⚠ 未评估: X（原因）」；`--json` 输出追加 `coverage` 键。
4. `qc.py` 的 `meta` 追加 `coverage`（可选，若改动最小）。

**验收：**
- 无 `entities.json` → `logic_check` 的 coverage 中 `appellation`/`state` 为 `False`，`skipped_reason` 非空；`book_quality_check` 返回含 `coverage` 且既有键一个不少。
- 有 `entities.json` → 四项均 `True`。
- 既有测试全部通过（签名与既有键未变）。

---

### Task C: 校验接入提交守卫（报告 P3-2）

**Files:**
- Modify: `.githooks/pre-commit`
- Modify: `.githooks/README.md`（若存在，补说明）

**问题：** `novel 校验` 是手动命令，不在任何流水线里 → 5 个不合规资产长期躺在库里没人发现。

**设计：**
1. pre-commit 在跑完 `run_tests.py` 之后，取本次暂存的 `assets/*.json` 列表（`git diff --cached --name-only --diff-filter=ACM`），逐个调用 `scripts/validate.py`。
2. 任一资产返回码 1（REJECT）→ 打印错误并 `exit 1` 阻止提交；返回码 2（WARN）→ 只提示不阻止。
3. 无变更资产 → 打印「无变更资产，跳过」并 exit 0（不增加耗时）。
4. 用与 `run_tests.py` 相同的解释器解析逻辑（复用现有 `resolve_python`）。
5. 纯 POSIX sh，无第三方依赖。

**验收：**
- 手动构造：暂存一个合规资产 → 守卫通过；暂存一个不合规资产 → 守卫 exit 1 并打印原因。
- 不暂存资产 → 跳过。
- 全量 558 测试仍 OK（不受影响）。

---

### Task D: 补齐存量数据完整性

**Files:**
- Modify: `corpus/metrics/qingning_chosen.json`（未入库，本地）
- Modify: `corpus/metrics/sangshi_chosen.json`（未入库，本地）
- Create: `corpus/metrics/autumn_chosen.json`、`corpus/metrics/duwo_chosen.json`（未入库，本地）
- Modify: `dashboard/dashboard-data.js`（入库）

**设计：**
1. `qingning_chosen` / `sangshi_chosen` 的 metrics 用 `metrics.compute()` 补齐 `short_ratio` / `long_ratio`（其余字段保持不变——只补这两个键）。
2. `autumn_chosen` / `duwo_chosen` 生成完整 metrics（此前有语料无 metrics）。
3. `dashboard-data.js` 用 `python -B dashboard/build_data.py` 整体重建（此前只做了 dialogue_ratio 的 4 值最小更新，整体仍停留在 9-08 快照）。
4. 逐项记录差异；重建后运行 `dashboard/smoke-test.js`。

**验收：**
- 6 个语料的 metrics 均存在且字段完整。
- `dashboard-data.js` 语义差异与「9-08 快照 vs 当前资产」一致（预期含 `.distilled.*.rules` 大量差异），且冒烟测试 19/19 通过。
- 55 个资产仍 0 REJECT；全量 558 测试 OK。

---

### Task E: 推送

**Files:** 无（git 操作）

**设计：**
1. 先确认远程状态（`origin/master` 显示 gone，需核实 `git remote -v` 与 `git ls-remote`）。
2. 按实际情况选择：推送到 `origin/master`，或新建分支推送。
3. 推送前运行全量测试与 55 资产校验，确认绿。

**验收：** 推送成功且 `git status` 显示与远程同步。

---

## 依赖与顺序

```text
Task A ─┐
Task B ─┼─ 互不冲突（A/B 改 book_quality.py 的不同区域，需串行执行避免冲突）
Task C ─┘
Task D ── 独立（数据），可与 A/B/C 串行
Task E ── 最后（依赖 A~D 全部完成并验证）
```

Task A 与 Task B 都改 `scripts/book_quality.py`，必须串行；Task C 只改 `.githooks/`，Task D 只改数据，均可与代码任务串行。

## 明确不做（需另行决策，本轮不碰）

- 疲劳词/对话占比/字数档位重标定、悬崖式档位改连续打分（报告 P1-1/P1-2/P1-4）——会改变所有章节的历史分数，需用户先决定是否接受历史分失效。
- LLM 备用模型路由（报告 P2-4）——需要模型配置决策。
- `build/installer.iss` 的 `setup.exe` 重建——本机未安装 Inno Setup。

## 计划自审

- **Spec coverage:** 报告「立即可做」6 条中，#5（递归扫描排除名单）已在上一轮完成；本轮覆盖 #1（pre-commit 校验）、#3+#4（重复检测召回）、#6（覆盖率字段）；#2（distill 字段映射）经复核判定为原报告误判，已在上一轮以「专用校验 + 服务层 kind 拒绝」等价解决。
- **Placeholder scan:** 每个任务给出精确文件、函数名、阈值、严重度映射与验收条件，无未定义步骤。
- **Type consistency:** `coverage` 字典结构在 Task B 内统一定义；`adjacent`/`intra_chapter_repeat` 命名在 Task A 内一致；无跨任务类型依赖。
