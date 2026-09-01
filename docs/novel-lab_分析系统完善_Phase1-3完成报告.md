# novel-lab 分析系统完善 · Phase 1-3 完成报告

> **时间**：2026-08-10 22:23-22:50
> **状态**：Phase 1-3 全部完成，Phase 4 待执行（需调 LLM）

---

## 一、已完成的修改

### Phase 1.1: normalize.py verbal_tics 提取修复
**问题**：chireng 的 verbal_tics 是 dict 列表 `{情境:..., 规则:...}`，但 `_QUOTE_RE` 正则只匹配 ASCII `'` `'`，chireng 数据用的是 Unicode 弯引号 `\u2018` `\u2019`——导致口头禅提取为空。

**修复**：
- 扩展 `_QUOTE_RE` 正则，兼容 `\u2018\u2019\u201c\u201d`（Unicode 弯引号）
- 新增 `extract_tics_from_text()` 函数，双重提取策略：引号内短语 + "例如：X"模式
- 更新 `_tics_to_str_list()` 使用新函数

**效果**：
- 边炀：0 个口头禅 → **10 个**（"我为什么要帮你？""关你屁事""手给老子拿开"等）
- 孟诗蕊：0 → 3 个（原始 Pass2 数据被截断，需重跑）

### Phase 1.2: Pass3 prompt 强制 imagery 提取
**问题**：imagery 字段经常为空（chireng/sangshi）或被自然语言污染（qingning）。

**修复**：
- pass3_style.md SYSTEM 铁律新增第 3 条：imagery 必填
- USER 模板中标注每个 imagery 字段为 required，加示例说明
- 字段说明区加强：high_freq_metaphor_domains ≥2、sensory_preference 非空、signature_devices ≥1

### Phase 1.3: validate.py 加 imagery 校验
**新增**：在 `validate_voice_card()` 中加 imagery 字段校验（WARN 级）：
- high_freq_metaphor_domains 为空 → WARN
- sensory_preference 为空 → WARN
- 比喻领域过长（>10字）→ WARN（检测自然语言污染）
- sensory_preference 各项和偏离 1.0 → WARN
- signature_devices 为空 → WARN

### Phase 2: Pass5 笔法深度分析 prompt
**新增** `prompts/pass5_craft.md`，8 维写作技法分析：

| 维度 | 内容 |
|---|---|
| 伏笔技法 | 伏笔类型、埋设手法、回收节奏 |
| 信息释放 | 什么信息在什么时候给读者 |
| 视角控制 | 限制性信息处理、全知/限知切换 |
| 场景转换 | 转场手法（硬切/淡出/物件过渡） |
| 张力构建 | 紧张感从0到10再回落 |
| 对话技法 | 潜台词/打断/沉默/错位对话 |
| 节奏控制 | 快慢交替规律 |
| 感官运用 | 五感的具体运用方式 |

每个技法要求：名称 + 手法描述 + 效果 + 可复用骨架 + 反例。

### Phase 3: craft-card schema + 报告生成器 + pipeline 集成
- `schema/craft-card.schema.json`：8 维技法资产结构定义
- `scripts/report_craft.py`：craft-card → 人类可读 Markdown 报告
- `pipeline.py`：从 6 步升级为 7 步，集成 Pass5 + craft-card 组装 + 校验 + 合规
- `validate.py`：注册 craft-card 校验
- `novel.py`：新增"笔法报告"子命令

---

## 二、修改的文件清单

| 文件 | 修改类型 | 内容 |
|---|---|---|
| `scripts/normalize.py` | 修改 | verbal_tics 提取逻辑修复 |
| `prompts/pass3_style.md` | 修改 | imagery 强制提取 |
| `scripts/validate.py` | 修改 | imagery 校验 + craft-card 校验注册 |
| `prompts/pass5_craft.md` | **新增** | 笔法深度分析 prompt |
| `schema/craft-card.schema.json` | **新增** | 笔法资产 schema |
| `scripts/report_craft.py` | **新增** | 笔法报告生成器 |
| `scripts/pipeline.py` | 修改 | 集成 Pass5 + craft-card |
| `novel.py` | 修改 | 新增笔法报告子命令 |
| `HANDOFF.md` | 修改 | 更新待办事项 |

---

## 三、验证结果

- ✅ 全部 16 个 Python 脚本 py_compile 通过
- ✅ pipeline.py dry-run 通过（步骤编号正确 3/7 → 4/7 → ...）
- ✅ chireng 边炀 verbal_tics 从 0 → 10 个口头禅
- ✅ craft-card schema JSON 合法
- ✅ validate.py craft-card 校验注册成功

---

## 四、Phase 4 待执行

用修复后的 prompt 重新拆解 3 本书，验证：
1. verbal_tics 全部为字符串数组且非空
2. imagery 字段填充完整
3. 新增 craft-card 产出 + 笔法报告
4. 一致性打分提升

**注意**：Phase 4 需要调用 LLM（mimo），会产生 token 消耗。

---

*报告由 novel-lab 分析系统完善工作流生成。*
