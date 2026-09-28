# novel-lab 企业出版级优化 — 最终验收报告 v5（2026-09-28）

> 本报告替代 `docs/internal/ACCEPTANCE_2026-09-28_v4.md`。
> 所有"已验证"断言均有本轮真实工具结果支撑；未验证项明确标注。
> 分支：`feat/enterprise-hardening`。远端：`9e5c5f87`（完整 recursive tree 对比验证，见 §一）。

## 一、远端一致性（本轮新验证方法）

v4 报告的问题：用 3 个文件抽查 blob SHA 包装成"本地 HEAD 与远端内容一致"，且推送脚本上传的是工作区原始字节
（CRLF），与 git 仓库存储的 LF 字节不一致，导致约 100 个文件的远端 blob SHA 与本地不一致；另有 8 个过期 dist
构建产物残留在远端。

本轮修复与验证：
- 重写推送脚本：blob 内容取自 `git show HEAD:path`（git 实际存储的字节），上传后逐个校验 SHA 与本地一致；
  远端多余文件（过期 dist）显式删除。
- 独立验证：GitHub API 取远端 recursive tree，与 `git ls-tree -r HEAD` 逐项对比**路径 / blob SHA / mode**：
  远端 373 blobs，本地 373 文件，**三项全一致**，远端 ref `9e5c5f87`。
- 此为完整对比，不是抽查。

## 二、本轮新增修复（全部已验证）

| # | 问题 | 修复 | 回归测试 |
|---|---|---|---|
| 1 | P0-2 原子发布逻辑内联在 `novel.py` 主流程，测试只能复制逻辑，无法调用生产函数 | 提取为 `novel.publish_reports_atomically(srcs, reports_dir)`，生产调用处改调函数 | `test_atomic_publish.py` 4 例直调生产函数（含回滚、缺源跳过、回滚失败忽略）✅ |
| 2 | `test_security_fixes.py::TestSecretStorePerms` 未调用生产函数，只重复 `os.open` | 直调 `scripts/secret_store.py::save_secrets`，断言落盘 0o600 + 回读一致 | 10 例全过 ✅ |
| 3 | 服务层 `batch_size or default`：内部调用传负数可绕过路由层 `_safe_batch_size`（负数 truthy，直接进后台线程） | 新增 `services._require_positive_batch_size`，`import_book`/`split_chapter_batches`/`start_analysis` 三处调用 | 3 例新回归 ✅ |
| 4 | `QcVisuals` 热力图 `type: 'heatmap'` 但 `BaseChart` 未注册 `HeatmapChart`（echarts 按需引入下静默空白） | `BaseChart.tsx` 注册 `HeatmapChart` | tsc ✅，`npm run build` ✅（echarts chunk 604KB→610KB，符合预期） |

## 三、测试与门禁（本轮实测）

| 门禁 | 结果 |
|---|---|
| Python | `Ran 1074 tests`，`OK (skipped=3)`（fresh run；3 跳过为 Windows-only/缺语料） |
| ruff | 全清 |
| coverage | 62%（`model_service.py` 0%→26%；`write.py`/`pipeline.py` 等 LLM 强依赖路径无 key 离线不可测，**不声称**已达上限） |
| tsc | 全清 |
| ESLint | 0 警告 0 错误 |
| vitest | 40/40 |
| npm run build | 成功 |

**未在本轮重跑**：Playwright 冒烟 4/4 与旅程 2/2（上一轮已通过，本轮未重跑，**不声称**本轮 6/6）。
`npm audit` 因环境代理 403 未执行，**不能声称**依赖漏洞扫描通过。

测试数口径：`AGENTS.md` §7 已同步为 1074（`test_doc_metrics.py` 强制文档数字与实测一致，漂移即失败）。

## 四、真实状态核查

- 目标端口（8000/18080/18081/18082）无监听；`gui_state/.lock` 为 stale（PID 已不存在），服务端下次启动会覆盖。
- `gui_state/index.db` 中发现 2026-09-27 测试遗留行 `analysis_tasks.book_id='genre_test-fc6b1375'`
 （idle 空状态，明确为测试产物），已删除；删除前已备份至 `/tmp/index_before_cleanup.db`。
- 其余行（`间谍-003fc6c6` idle、`b` running）非明确测试产物，**未动**。

## 五、前端审计结论（只读审计）

- 硬编码颜色：排除 `theme.ts` 集中色板后，剩余 32 处分布在 11 个文件，均为图表语义色板
 （`LAYER_COLORS`、严重度色、状态色）且已收敛为命名常量；属可接受的图表语义色，不再强行收敛。
- 竞态守卫：`AppContext` 序列号守卫与 `AnalysisResultView` 的 `latest` 标记均正确实现（P1-F5 早前已修）。
- `ResultPanel` 章节切换：P2-F9 修复仍在（切换重置 batchIndex，避免双请求）。

## 六、诚实声明

- **外部模型链路未实测**：secret store 无可用 key，本轮所有 LLM 相关路径均为 mock/离线验证。
- 覆盖率 62%，未达 80% 内控目标；剩余缺口主要为 LLM 强依赖代码，无 key 无法离线覆盖。
- 旧 zip（v3/v4）已过时，不得作为交付；本报告对应远端 `9e5c5f87`。
