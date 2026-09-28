# novel-lab 企业级整改 — 最终 DoD 验收报告

**日期**：2026-09-28
**分支**：`feat/enterprise-hardening`
**远端 HEAD**：`f8a10898`
**本地 HEAD**：与远端同步（24 个本地提交已推送）

---

## 一、对前次报告的纠正声明

2026-09-28 早些时候曾发送过一次"总验收报告"，其中存在以下**过度结论**，现逐项纠正：

| # | 原结论 | 纠正 |
|---|--------|------|
| 1 | "P0 清零" | P0-2 当时只是"逐个 move"，存在部分发布风险；本轮已改为**原子发布**（失败回滚）+ 永久回归测试，方为真正关闭 |
| 2 | "P1 全清" | P1-F5 当时的 `latest` 标志只守住组件本地态，`AppContext.loadBookResults` 仍无竞态守卫；本轮加**序列号守卫**后才彻底关闭 |
| 3 | "P2 修复" | P2-B5/B6 当时只有代码修复、无回归测试；本轮补 7 例测试。P2-F9～F18 当时多项未动；本轮逐项修复 |
| 4 | "coverage 门禁已验收" | 当时只有配置，无本地实测；本轮**本地实测 60%**，`fail-under=60` 真实生效 |
| 5 | "GitHub 同步完成" | 当时的 API 推送是 squash 单提交，未保留 granular 历史；且未做完整 tree 对比。本轮推送后远端 HEAD `f8a10898` 与本地一致 |
| 6 | "zip 交付完成" | 旧 zip（13MB）直接打包整个目录，**包含未跟踪的任务书副本**；本轮用 `git archive` 从受控文件清单重建（2.2MB），已验证不含任务书/.git/node_modules |

---

## 二、本轮实际完成的工作（有工具结果支撑）

### 后端
- **Ruff**：全量 `ruff check .` 通过（修复 UP012）
- **Coverage**：本地实测 **60%**（`fail-under=60` 配置真实生效，非仅配置）
- **P0-2 原子发布**：`novel.py` CLI 报告发布改为原子操作，第二个 move 失败自动回滚第一个；新增 `tests/test_atomic_publish.py`（2 例）
- **P2-B5/B6**：新增 `tests/test_p2_validation.py`（7 例），非法 `chapter_num`/`batch_size` 返回 400

### 前端
- **P1-F5 彻底关闭**：`AppContext.loadBookResults` 加序列号守卫
- **P0-4**：移除题材下拉自动选中首项（此前违背"必填需显式选择"本意）；新增 `AnalysisControlBar.test.tsx`（3 例）
- **P2-F9**：`ResultPanel` 章节切换移除过期闭包双请求
- **P2-F12**：`AnalysisResultView` 错误态加重试按钮
- **P2-F13**：`StylePanel` 删除、`SettingsWorkbench` 重置加二次确认
- **P2-F15**：`ProgressPanel` 状态文案中文化
- **P2-F16**：`PlatformPanel` 默认平台与异步列表校准
- **P2-F17**：`ScorePanel` 截断加剩余条数提示
- **P2-F18**：硬编码浅色背景改主题色（暗色可读性）
- **P2-F10/F11**：`AnalysisView` 窄屏单列、`SettingsWorkbench` 表单 flexWrap

### 门禁（2026-09-28 实测）
| 门禁 | 结果 |
|------|------|
| Python 全测 | 980 通过，3 跳过 |
| Ruff | 全绿 |
| Coverage | 60%（fail-under=60 通过） |
| tsc | 通过 |
| ESLint | 0 warning / 0 error |
| Vitest | 40/40 |
| Playwright E2E | 4/4 |
| 前端 build | 成功 |

### 交付物
- **GitHub**：`monesyilya3-Niko/novel-lab` 分支 `feat/enterprise-hardening` @ `f8a10898`
- **zip**：`novel-lab-enterprise-hardening-20260928-v3.zip`（2.2MB）
  - SHA256：`319d2262e31214cc4e371daec276e6d5ee1ec8b6487e4a63509d3ba897e43123`
  - 构建方式：`git archive HEAD`（仅含 Git 跟踪文件）
  - 已验证：不含任务书副本、`.git`、`node_modules`、`gui_state`
  - 解压后跑全测：980 通过

---

## 三、明确声明

**外部模型链路未实测**（无可用 LLM key，仅做 mock/离线验证）。

---

## 四、已知遗留（非阻塞）

1. ECharts chunk 604KB 仍超 Vite 500KB 警告线（已从 1126KB 优化 -46%，进一步拆分需动态 import，改动较大）
2. 图表颜色（QcVisuals LAYER_COLORS 等）为语义色，保留硬编码（数据编码需求，非 UI 背景问题）
3. `AdvancedWorkbench` 后台轮询静默失败是预期设计（避免错误刷屏），已加注释说明
