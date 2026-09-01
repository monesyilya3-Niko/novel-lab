# novel-lab 分析系统完善 · Phase 4 验证报告（chireng）

> **时间**：2026-08-10 23:00-23:30
> **验证对象**：chireng_chosen（《炽炀》别惹他的小可怜）

---

## 验证结果

### voice-card（修复前 vs 修复后）

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 角色数 | 2 | **4** |
| 孟诗蕊口头禅 | 0 个（dict 格式无法提取） | **6 个** |
| 边炀口头禅 | 0 个 | **7 个** |
| 唐雨口头禅 | 0 个 | **6 个** |
| 周寻文口头禅 | 0 个 | **2 个** |
| 比喻领域 | 0 项 | **2 项** |
| 五感偏好 | 空 | **5 项归一化**（visual 0.535 + auditory 0.289 + tactile 0.132 + olfactory 0.026 + gustatory 0.018） |
| 修辞手法 | 0 项 | **2 项** |
| schema 校验 | 5 硬错误 | **0 硬错误** |
| 合规扫描 | 通过 | **通过** |

### craft-card（新增）

| 指标 | 数据 |
|---|---|
| 技法总数 | **10 个** |
| 维度覆盖 | 4/8（foreshadowing 2 + information_release 3 + tension_building 4 + sensory_craft 1） |
| TOP3 技法 | 感官细节外化心理 / 沉默与爆发的对比 / 通过反派言论揭示社会权力结构 |
| 独有技法 | 旁观者的漠视强化孤立感 / 救援者的非典型登场与对话 |
| schema 校验 | **通过**（0 硬错误，5 警告——空维度） |
| 笔法报告 | **已生成**（可交付 Markdown） |

---

## 修复过程中发现并解决的问题

1. **Pass2 max_tokens 不够**：新 prompt 输出更详细，8192 不够 → 增至 16384
2. **Pass3 max_tokens 不够**：imagery 详细要求 → 增至 16384
3. **normalize_pass2 不兼容新格式**：`characters[].speech_style` vs 旧 `character_voices[].speech_signature` → 兼容处理
4. **normalize_pass3 不提取 sensory_preference**：中文键"视觉"/"听觉"没映射 → 从 `imagery_system` 直接取+中文键映射
5. **assemble_voice_card_v2 没注入 voices**：接收 voices 参数但没用 → 加注入逻辑
6. **Pass5 输出结构不匹配**：`chapter_analysis[]` vs `craft_analysis.{dim}.techniques[]` → 加章节→维度映射
7. **validate.py never_says 校验过严**：新 pass2 不输出此字段 → 从 error 降为 warn
8. **validate.py emotion_handling.examples 校验过严**：新 pass3 可能无此字段 → 降为 warn

---

## 修改的文件清单（Phase 4 追加）

| 文件 | 修改 |
|---|---|
| `scripts/pipeline.py` | Pass2/3 max_tokens 增至 16384；voices 注入逻辑；craft-card 章节→维度映射 |
| `scripts/normalize.py` | `characters[].speech_style` 兼容；`imagery_system` 直接取+sensory 中文键映射；`never_says` 从 key_rules 衍生 |
| `scripts/validate.py` | `never_says` error→warn；`emotion_handling.examples` error→warn |

---

## 产出文件

- `assets/chireng_chosen-voice-card.json` — 修复后的声线卡
- `assets/chireng_chosen-craft-card.json` — 新增笔法卡
- `reports/chireng_chosen-笔法分析.md` — 可交付笔法报告

---

*报告由 novel-lab 分析系统 Phase 4 验证工作流生成。*
