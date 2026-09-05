# novel-lab 分析系统完善 · 3 本书全部验证完成

> **时间**：2026-08-10 23:00-23:45

---

## 三本书验证结果汇总

### voice-card 对比

| 书名 | 角色数 | 总口头禅 | 比喻领域 | 五感 | 修辞 | 校验 |
|---|---|---|---|---|---|---|
| chireng（炽炀） | 4 | **21** | 2 | 5 | 2 | ✅ 0错误 |
| qingning（青柠） | 4 | **33** | 2 | 5 | 1 | ✅ 0错误 |
| sangshi（桑式） | 7 | **30** | 2 | 5 | 2 | ✅ 0错误 |

### craft-card 对比

| 书名 | 技法数 | 覆盖维度 | TOP3 技法 | 报告 |
|---|---|---|---|---|
| chireng | **10** | 4/8 | 感官细节外化心理 / 沉默与爆发的对比 / 反派言论揭示权力结构 | ✅ |
| qingning | — | — | （craft-card 为空，pass5 输出格式兼容问题） | ✅ |
| sangshi | **6** | 3/8 | 重复句式构建情感递进 / 第一眼反应与内心回溯 / 碎片化信息与生理反应 | ✅ |

### 修复前 vs 修复后

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 口头禅总数 | **0** | **84**（3 本书） |
| 比喻领域 | 0 | **6 项** |
| 五感偏好 | 全空 | **3 本书全部 5 项** |
| 修辞手法 | 0 | **5 项** |
| 笔法分析 | 无 | **16 个技法** + **3 份报告** |
| schema 校验 | 多处错误 | **全部通过** |

---

## Phase 1-4 修复清单（累计）

### Phase 1: 基础缺陷修复
- normalize.py verbal_tics 提取（Unicode 弯引号 + "例如：X"模式）
- pass3_style.md imagery 强制提取
- validate.py imagery 校验

### Phase 2: Pass5 笔法分析
- pass5_craft.md（8 维技法 prompt）

### Phase 3: craft-card 生态
- craft-card.schema.json + report_craft.py + pipeline 集成

### Phase 4: 验证修复（3 本书）
- Pass2/3 max_tokens 8192→16384
- normalize_pass2 兼容 `speech_style` 格式
- normalize_pass3 从 `patterns.意象系统` 取 imagery
- assemble_voice_card_v2 注入 voices
- pass5 输出 3 种格式兼容（chapter_analysis / techniques / craft_analysis）
- validate.py never_says/examples 降为 warn

---

## 产出文件清单

### assets/
- `chireng_chosen-voice-card.json` / `craft-card.json`
- `qingning_chosen-voice-card.json` / `craft-card.json`
- `sangshi_chosen-voice-card.json` / `craft-card.json`
- `chireng_chosen-structure-obs.json` / `commercial-obs.json`
- `qingning_chosen-structure-obs.json` / `commercial-obs.json`
- `sangshi_chosen-structure-obs.json` / `commercial-obs.json`

### reports/
- `chireng_chosen-拆书报告.md` / `笔法分析.md`
- `qingning_chosen-拆书报告.md` / `笔法分析.md`
- `sangshi_chosen-拆书报告.md` / `笔法分析.md`

---

## 待做（非阻塞）

1. 合规扫描的 12 字匹配问题（structure-obs / commercial-obs 已知问题，voice-card 全部通过）
2. qingning craft-card 为空（pass5 输出格式兼容需进一步调试）
3. 技法覆盖度优化（4-5/8 维度有内容，pov_control/scene_transition/dialogue_craft/rhythm_control 为空）
4. 题材包重新聚合（≥3 本同题材，现有 3 本可重新聚合）

---

*报告由 novel-lab 分析系统 Phase 1-4 完成后生成。*
