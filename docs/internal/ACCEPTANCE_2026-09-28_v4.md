# novel-lab 企业出版级优化 — 最终验收报告（2026-09-28）

> 本报告替代 `docs/internal/ACCEPTANCE_2026-09-28.md` 旧版中的过度结论。
> 所有"已验证"断言均有本轮真实工具结果支撑；未验证项明确标注。

## 一、本轮工作范围

用户指令："模型这里先不管"、"你来接手，向企业出版级进行优化"。
分支：`feat/enterprise-hardening`。
远端：`f6de4cb5`（已验证与本地 HEAD 内容一致，抽查 3 文件 blob SHA 全匹配）。

## 二、安全审计（只读审计 + 5 项修复，已验证）

| # | 问题 | 修复 | 回归测试 |
|---|---|---|---|
| 1 | `get_book_results` 未校验 book_id（路径穿越/文件探测） | 开头调 `_get_book_or_raise` | ✅ |
| 2 | `export_book_for_platform` book_dir 未约束项目根 | resolve 后要求位于 ROOT_DIR 内 | ✅ |
| 3 | CORS 放行 `Origin: null` | 不再把空 hostname 视为本机 | ✅ |
| 4 | `distill_status` genre 拼入 glob | 加 `[A-Za-z0-9_-]+` 白名单 | ✅ |
| 5 | secrets 先写后 chmod（TOCTOU） | 改用 `os.open(..., 0o600)` 原子创建 | ✅ |

`tests/test_security_fixes.py`：10 例，定向通过。

**诚实说明**：
- `npm audit` 因环境代理 403 未执行，**不能声称**依赖漏洞扫描通过。
- 审计确认：无 `shell=True`/`os.system`；无 `dangerouslySetInnerHTML`；上传文件名已有 basename+控制字符过滤+100MB 上限；服务硬编码绑定 127.0.0.1。

## 三、测试补强（+89 例，全部通过）

| 文件 | 例数 | 覆盖内容 |
|---|---|---|
| test_normalize_coverage.py | 31 | normalize.py 纯函数 |
| test_batch_dryrun.py | 4 | batch.py dry-run |
| test_report_assemble.py | 15 | report/assemble 纯函数 |
| test_inject_render.py | 16 | inject 渲染 |
| test_model_service.py | 13 | 模型 ID/协议/URL 校验 |
| test_security_fixes.py | 10 | 安全回归 |

**全量**：`Ran 1069 tests`，`OK (skipped=3)`（3 跳过为 Windows-only/缺语料，属预期）。

**覆盖率**：60% → 61%。**未达 80%**，原因诚实说明：
剩余低覆盖模块（`write.py` 18%、`pipeline.py` 17%、`model_service.py` 部分）核心逻辑依赖真实 LLM API 调用，无 key 无法离线测试。已达 offline 可测上限，不用浅断言凑数字。

## 四、前端优化（已验证）

- **ECharts 懒加载**：BarChart/RadarChart/PieChart/BaseChart 改 `React.lazy + Suspense`。
- 构建产物：`echarts` 604KB 独立 chunk（按需加载），`vendor` 451KB，主 `index` 27KB。
- `npx tsc --noEmit` 通过；ESLint 0 警告；vitest 40/40；`npm run build` 成功。

## 五、E2E（隔离服务实测，未污染真实状态）

- 冒烟 4/4 通过（既有）。
- 新增旅程 2/2 通过：
  1. 分析页上传导入 → API 验证书入库（`total_books` +1）。
  2. 未选题材时"一键分析"按钮禁用（P0-4）。
- 方法：在 `~/workspace/.tmp` 解压 git archive 副本，独立端口启动服务，跑完即删。真实 `gui_state/` 零写入。

## 六、性能压测（实测数据）

- 20 并发 `/api/overview`：平均 10–115ms，最大 ~1s（单线程 http.server 排队，属预期；localhost 场景可接受）。
- 3.6MB 文件（50 章）上传导入：1.5s，`code=0`。

## 七、门禁汇总（本轮实测）

| 门禁 | 结果 |
|---|---|
| Python 1069 例 | ✅ 全绿（3 跳过） |
| ruff | ✅ 全清 |
| coverage | 61%（offline 上限，见 §三） |
| tsc | ✅ 全清 |
| ESLint | ✅ 0 警告 |
| vitest | ✅ 40/40 |
| Playwright 冒烟+旅程 | ✅ 6/6 |
| npm run build | ✅ 成功 |

## 八、旧报告纠正

1. 旧报告称"本地 HEAD 与远端同步"——当时远端为 `f8a1089`，本地已有未推送提交，**不成立**。现远端 `f6de4cb5` 已验证一致。
2. 旧报告称"P0-2 原子发布真正关闭"——测试复制了发布逻辑未调生产函数，**证据不足**，本轮未重验，**不声称**已关闭。
3. 旧 zip（`...-v3.zip`，SHA `319d2262...`）已过时，不得作为交付。

## 九、未验证项（明确声明）

- **外部模型链路未实测**（无可用 LLM key，仅 mock/离线验证）。
- `npm audit` 未执行（代理 403）。
- P0-2 原子发布、P1-F5 竞态等历史项本轮未重验，不沿用旧结论。

## 十、交付物

- GitHub：`monesyilya3-Niko/novel-lab` 分支 `feat/enterprise-hardening` @ `f6de4cb5`。
- 本地：`~/workspace/projects/novel-lab`，7 个本地提交（squash 为 1 个远端 commit）。
