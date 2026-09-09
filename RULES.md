# novel-lab 项目规则（v1）

> 拆书 + 资产驱动创作系统的可执行规则。每次改动引擎或写作流程前先读这里。
> 目标：**章节一致性 ≥ 90**、拆书合规零风险、流程可复现。

---

## 一、架构与流程

```
pipeline.py  拆书：TXT → 采样 → 四遍扫描 → 归一化 → 资产（voice-card/结构/商业）
inject.py    注入：资产 → 8 节写作 system prompt（prompts/generated/）
write.py     写作：prompt + 要点 → 生成 → 改写循环(≥90) → 入库 → 质量门禁
consistency.py  打分：五维（声线35/情绪20/叙述15/禁忌20/意象10）
validate.py  schema 校验（voice-card 严格，观测文件延后）
compliance.py  版权合规（12字匹配原文→REJECT，title 字段豁免）
```

## 二、模型调用规则（⚠️ 2026-09-01 起本节仅作历史存档：外部模型已删除，LLM 层由 WorkBuddy 内置智能承担，见 HANDOFF.md 第六节。json_mode 等规则仅在未来恢复外部模型时适用）

### 2.0 批量拆书与报告（M3）
- `batch.py <目录> --genre xxx [--report]`：遍历目录多本 TXT 逐本拆解，产出每本的 voice-card/结构/商业资产；`--report` 时每本生成拆书报告。
- `report.py <voice-card.json> [--structure ...] [--commercial ...]`：资产 → 可交付 Markdown 拆书报告（reports/），可直接用于闲鱼/公众号/知识星球变现。
- 拆够 ≥3 本同题材书 → 满足 Pass5 聚合条件，可生成题材包（genre-pack）。

1. **拆书任务必须 json_mode=true**（response_format json_object），否则模型输出 Markdown。
2. **写作任务必须 json_mode=false**，否则模型输出 `{}`+英文而非正文。
3. `llm_client.chat(..., json_mode=...)` 三态：None=沿用配置 / True / False。
4. token-plan 网关（mimo-v2.5-pro）用 **openai 协议**：`https://token-plan-cn.xiaomimimo.com/v1/chat/completions`。
   - 模型名必须是 `/v1/models` 列出的真实名（mimo-v2.5-pro），不是 `[1m]` 别名。
   - key 存 `.secrets.json`，models.json **不要设 api_key_env**（环境变量旧 key 会优先覆盖新 key）。

## 三、写作质量规则（≥90 关键）

### 3.0 Pass 输出完整性检查（pipeline 已内置）
- Pass4 模型输出结构不稳定：`opening_analysis`/`dry_spell_tolerance`/`paywall` 可能缺失或变形。
- pipeline 扫描后自动检查关键字段，缺失时警告「重跑该 Pass 或人工补」。
- 长引号片段（>20 字）会触发合规 WARN——分析文本里的引号包裹内容需改写为无引号描述。

### 3.1 改写循环
- write.py 默认 3 轮：初稿 → 打分 → <90 带扣分明细改写 → 再打。
- 每轮改写 prompt 必须包含：**具体扣分点** + **每个出场角色必须出现的具体词汇**（从 voice-card 提取）+ 密度要求。
- 改写轮次不足 3 轮就达标 → 直接入库。

### 3.2 体感词密度（情绪写法 20 分）
- **每 400 字至少 1 处**体感式生理反应（心跳/指尖/耳根/手心/脊背/呼吸/发烫等）。
- 2400 字目标 6-8 处 → 满分 20。
- 零直陈式情绪词（很愤怒/很难过/很紧张 是 AI 味重灾区，每个扣 4 分）。

### 3.3 角色声线（35 分）
- 每个出场角色必须实际使用声线卡里的【口头禅/昵称/称呼】≥2 种。
- 改写时把具体词列给模型（「务必让对话中出现『老子』『唐小雨』」），泛泛说「按声线卡」无效。
- 未出场角色不计分（不拉低总分）。

### 3.4 比喻取材（意象 10 分）
- 比喻必须从 voice-card 的 high_freq_metaphor_domains 取材（如动物/日常物件）。
- 有比喻但领域不同 → 5 分；无比喻 → 3 分（中性）；领域命中 → 满分。

### 3.5 结构/禁忌（35 分，通常满分）
- 叙述层：第三人称 + 对话短句 ≥2 + 单句成段 ≥2。
- 禁忌词表零出现（雷雨/刀剑/宫殿/深邃 等）。

## 四、归一化规则（normalize.py）

1. **中文键 → schema 英文键**：模型 json_mode 下倾向中文键（情绪写法模式/拒绝方式），normalize 做映射，不要反复调 prompt。
2. **引号兼容**：模型可能用中文弯引号（‘ ’ U+2018/2019）或直角引号（「」），正则必须两者都覆盖。
3. **体感词提取**：从「感官重心.具体化方式」「人物互动公式」「句法节奏」嵌套字段提取引号内短语；过滤角色口头禅（老子/唐小雨）等非体感词。
4. **anti_pattern**：只取「anti_pattern/反例」键；「负空间」是 banned 词表不是反例（历史 bug）。
5. **角色 role**：spec 里「角色」字段优先，否则按名字猜测（男主/女主/反派）。

## 五、合规规则（compliance.py）

1. 连续 12 字匹配原文 → REJECT（绝不入库）。
2. abstraction_level=verbal / contains_verbatim=true → REJECT。
3. 引号内片段 >20 字 → WARN 人工复核。
4. **title 字段豁免**：章节标题是书目元数据，不构成版权表达（历史误报）。
5. 写作生成的内容也要过 compliance（LLM 可能引用原文对话）。

## 六、冲突检测（M2.4，novel.py cmd_conflict）

1. 只对「同一实体同一属性取值矛盾」告警（X的Y是Z / 穿着/住在/毕业于 模式）。
2. **值字符集不含逗号**——否则贪婪吞掉后续内容造成误报（历史 bug）。
3. 属性长度 `{1,6}`——单字属性（剑/书）必须能匹配（历史 bug）。
4. 自然语言设定（「女主唐雨：安静坚韧」）提取不到事实 → 不误报，这是特性不是缺陷。

## 七、已知坑（Windows 环境）

1. **Git Bash 路径**：`/c/xxx` 传给 Python 会被当字面路径 → 用 `C:/xxx` 或先 cd。
2. **沙箱回收站不可用**：shutil.rmtree 删除失败 → 项目内测试数据用逐文件 unlink + rmdir。
3. **tail -c 按字节截断 UTF-8** 会显示乱码 → 用 Python 读文件验证内容。
4. **路径叠加**：cd novel 后再 init 会创建 novel/novel 嵌套 → 统一在项目根操作。

## 八、评分阈值

| 场景 | 阈值 |
|---|---|
| 章节一致性 | ≥90 合格（write.py 默认目标） |
| 章节一致性 | ≥75 基本合格 / <60 明显偏离 |
| schema 校验 | 0 硬错误（voice-card） |
| 合规扫描 | 0 REJECT（3 份资产全过） |
| 拆书准确度（M1.6） | 人工校验 ≥70% |

## 九、Pass5 笔法分析规则（2026-08-10 新增）

### 9.1 Pass5 输出格式兼容（4 种）
pass5 模型输出格式不稳定，pipeline 必须全部兼容：
- **格式 A**：`{"craft_analysis": {foreshadowing: {techniques: [...]}, ...}, "craft_summary": {...}}`
- **格式 B**：`{"chapter_analysis": [{chapter_range, techniques: [{technique_name, ...}]}]}`
- **格式 C**：`{"techniques": [{name/technique_name/scenario, abstract_skeleton, effect, ...}]}`
- **格式 D**：`{"foreshadowing": [{abstract_pattern, 反例, effect}], ...}`（维度直接在顶层）

字段名变体：`name`/`technique_name`/`scenario`、`abstract_pattern`/`skeleton`、`anti_example`/`反例`/`counter_example`、`execution`/`method`。

**只取 pass5 实际输出了的维度，不创建空壳维度。**

字段名变体：`name`/`technique_name`/`scenario`、`anti_example`/`counter_example`、`execution`/`method`/`example_in_text`。

### 9.2 技法归类到 10 维（2026-08-11 扩展）
pipeline 用关键词把 pass5 输出的技法归类到 10 维（DIMENSION_KEYWORDS 映射）。未命中的默认归入 `tension_building`。

10 维：foreshadowing / information_release / pov_control / scene_transition / tension_building / dialogue_craft / rhythm_control / sensory_craft / **narrative_engine** / **emotional_algorithm**

新增维度关键词：
- narrative_engine: 驱动/翻页/悬念/牵挂/承诺/兑现/命运/牵引/吸引/期待/好奇
- emotional_algorithm: 情绪/升起/伪装/转移/释放/压抑/爆发/隐忍/隐藏/流泪/哽咽

### 9.3 置信度公式
`confidence = 0.6 if n_chapters < 10 else min(0.9, 0.65 + n_chapters / 80)`
- 10 章→0.78, 15 章→0.84, 22 章→0.9

### 9.4 合规阻塞规则
- voice-card / craft-card 合规 REJECT → **阻塞入库**
- structure-obs / commercial-obs 合规 REJECT → **仅警告，不阻塞**

## 十、章节质量自检规则（chapter_check.py，2026-08-11 新增）

### 10.1 评分体系（12 维 100 分）
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
| 疲劳词检测 | 8 | "了"字密度/情绪标签/连接词/感叹词 |
| "让"字专项 | 5 | "让"字过多=AI味重灾区 |
| 情绪标签词 | 7 | 旁白中的情绪标签滥用 |

### 10.2 疲劳词分类（借鉴 novel-deconstruct）
- "了"字密度（>8/千字扣分）
- 情绪标签词（紧张/害怕/开心/难过 等）
- 连接词滥用（突然/忽然/就在这时）
- 感叹词（啊/呀/哇/唉/哎）
- "让"字密度（>2/千字扣分）
- 旁白情绪标签（她感到/他感到/她意识到）

## 十一、全书内容质检规则（book_quality.py，2026-08-11 新增）

### 11.1 检测维度（6 类）
1. **跨章重复**：重复章节(>70%)/重复段落(>30字)/重复句子(>12字跨≥3章)
2. **情节连贯**：时间线矛盾/人物情绪矛盾
3. **风格一致**：比喻密度波动/情绪写法模式漂移
4. **凑字数**：段落重复/环境描写占比过高(>40%)
5. **乱编检测**：人名错误/数字矛盾
6. **AI味检测**：作者预告旁白/记忆闪回模板/伤口比喻等8种

### 11.2 判定规则
- critical > 0 → FAIL
- high ≥ 5 → FAIL
- high > 0 → WARN
- 其他 → PASS

## 十二、写作者三维度改写循环（write.py，2026-08-11 新增）

write.py 改写循环从双维度升级为三维度：
1. **一致性**（voice-card：声线/情绪/叙述/禁忌/意象）
2. **章节质量**（chapter_check：12维100分制）
3. **内容质检**（book_quality：重复/连贯/凑字数/乱编/AI味）

三维度全部达标才通过，否则自动改写（最多3轮）。

## 十三、verbal_tics 兼容规则（2026-08-10 新增）

### 10.1 pass2 输出格式变体
pass2 输出的 `characters` 数组里，声线字段可能是：
- `speech_signature`（旧格式）或 `speech_style`（新格式）
- `verbal_tics` 可能是字符串数组（新）或 dict 数组（旧 `{情境, 规则}`）

### 10.2 normalize 处理链
`_tics_to_str_list` → `extract_tics_from_text`（引号提取 + "例如：X"模式提取）→ 兼容 `\u2018\u2019` Unicode 弯引号。

### 10.3 never_says 降级
新 pass2 格式不输出 `never_says`。validate.py 从 error 降为 warn。可从 `key_rules` 衍生补充。

## 十四、imagery 提取规则（2026-08-10 新增）

### 11.1 多路径查找
pass3 输出结构不稳定，imagery 数据可能在：
- 顶层 `imagery_system`（chireng 格式）
- `patterns.意象系统`（qingning 格式）
- `imagery`（旧格式）

### 11.2 中文键映射
sensory_preference 的中文键→英文键：`视觉→visual, 听觉→auditory, 触觉→tactile, 嗅觉→olfactory, 味觉→gustatory`。

### 11.3 signature_devices 兼容
可能是字符串（需包装为单元素数组）或列表。

## 十五、拆书实操经验（2026-09-07 新增，源自《溯雨信笺》全流程复盘）

> 本书记录无模型模式下「pass1-5 JSON → 组装 → 校验 → 合规 → 报告」链路中踩到的 4 类问题与解决方案。
> 拆新书前先读本章，可避免重复踩坑。详细复盘另见 `docs/拆书经验总结_溯雨信笺_2026-09-07.md`。

### 15.1 role 字段只用白名单 6 词（voice-card 硬错误根因）

**现象**：`dialogue.character_voices[1].role 值 '男主' 不在允许集合 ['主角','反派','女主','导师','工具人','配角']`。

**根因**：voice-card 的 `role` 有白名单，**不含「男主」**；但 `normalize_pass2` 的排序字典里有 `"男主": 1` 映射（仅用于排序），两套词汇表错位。

**解决/预防**：写 pass2 角色 role 时只用 6 个白名单词。男性主角→「主角」，女性主角→「女主」，不要写「男主」「男二」「女配」。排查时先 grep 校验代码里的「允许集合/白名单」字面量，再对照排序字典区分「排序用词」与「校验用词」。

### 15.2 pass3 情绪示例必须写顶层 switching_rules + anti_pattern

**现象**：`emotion_handling.examples 为空——建议补充情绪写法示例 → REJECT`。

**根因**：`normalize_pass3` 的 `extract_emotion_examples(pass3, mode)` 只从 pass3 **顶层**的 `switching_rules`(list) / `anti_pattern`(dict) / `banned` 提取（经 `_find_key` 递归），**不读** `emotion_handling.examples` 嵌套键。

**解决/预防**：pass3_style.json 顶层（`narration` 之前）加：
- `switching_rules`：list，每条含 `scene / mode / example_pattern`（如 愤怒→动作外化式、悲伤→体感式、心动→环境投射式）。
- `anti_pattern`：dict，按情绪给「避免写法」。

改完 pass 文件先看对应 normalize 函数读哪个键，再决定数据放哪。

### 15.3 commercial-obs 可选变体字段必须放顶层（层级陷阱）

**现象**：`⚠ commercial-obs 缺少 'skeleton' / 'dry_spell_tolerance' / 'common_mistakes'（可选变体字段）→ WARN`。

**根因**：`validate.py` 的 `COMMERCIAL_OBS_VARIANT_FIELDS = ("skeleton","dry_spell_tolerance","update_rhythm","retention_risk_points","common_mistakes")` 要求这 5 个字段在 **commercial-obs 顶层**；而 `assemble_obs` 只是**透传** pass4 的非 `_` 前缀顶层键，不做嵌套展开。把它们写进 `payoff_density`/`opening_analysis` 内部 → 顶层找不到。

**解决/预防**：pass4_commercial.json 顶层补入，类型如下：
- `skeleton`：**字符串**（多阶段叙事骨架）。
- `dry_spell_tolerance`：**字符串**（如 `"3章（约9000字）"`）。
- `common_mistakes`：**字符串**（编号列表 `1.…；2.…`）。
- `update_rhythm`：dict（`chapters_per_day` + `burst_timing`）。
- `retention_risk_points`：list（每条 `position/reason/mitigation`）。

写 pass4 前先对照一本已 PASS 的参考书（如 `assets/chireng_chosen-commercial-obs.json`）看顶层键结构，一次写对。

### 15.4 pass5 技法必带 deep_analysis 7 字段（万字报告字数来源）

**现象**：笔法分析报告 `⚠ 5600 < 硬门槛 10000 → sys.exit(1)`。

**根因**：`report_craft.py` 的字数主要来自 craft-card 每条技法的 `deep_analysis` 7 字段；pass5 的 20 条技法都没有 `deep_analysis`，7 段深度内容全空。

**解决/预防**：pass5_craft.json 每条技法必须补 `deep_analysis`，7 字段齐全（每字段 100-200 字高质量中文）：
- `reader_psychology`（读者心理机制）/ `execution_steps`（执行步骤）/ `applicable_scene`（适用场景）/ `usage_boundary`（使用边界）/ `intensity_control`（强度控制）/ `combo_patterns`（组合套路）/ `migration_checklist`（迁移清单）。

关键：`assemble_craft_card` 在 `if "craft_analysis" in pass5:` 分支**透传**整个 craft_analysis，**不截断** deep_analysis；深度内容必须由 Pass5 直接写进 pass5_craft.json，本地 `deep_analyze.py` 只校验、不补内容（遵循「AI 不编造数据」红线）。

### 15.5 铁律二口径：真·合计口径（已修复，2026-09-08）

- **条文**（PROJECT_LAW.md 第11行）：拆书报告 + 笔法分析 **合计** ≥10000 字符。
- **最终口径（已落地）**：`novel.py 分析` 收尾处做**合计校验**——拆书报告字符数 + 笔法分析字符数 ≥ 10000 才通过，不足 `sys.exit(1)` 阻断交付（见 novel.py 第 211-221 行）。
- **单份脚本行为**：`report.py`（第 279-280 行）与 `report_craft.py`（第 205-206 行）各自 `MIN_REPORT_CHARS=10000` 仅 **soft warning**，不阻断（`⚠ 单份字数 < 10000，请确认...`）。
- **结论**：代码已与条文一致（真·合计口径）。本例《溯雨信笺》拆书报告 4719 字 + 笔法分析 20625 字 = 合计 25344 字 ≥ 10000，铁律二通过。历史「单份硬门槛」问题已消除。

### 15.6 回归验证闭环（不可省略）

每次改 pass 文件后，必须三步走完：**重新组装 → 重新校验 → 重新生成报告**。只改文件不回归，会导致「改了但校验结果仍是旧的」的假象。

### 15.7 组装 name 参数约定

`python novel.py 组装 <name> --genre <题材>` 的 `<name>` 必须是 `corpus/raw/` 下的**目录名**（如 `suyixinjian_chosen`），不是书名。
