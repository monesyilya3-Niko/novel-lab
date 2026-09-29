# novel-lab 企业级整改 — 最终验收报告

日期：2026-09-28
任务书：`v2__1.md`（唯一有效版本；旧 v2 已作废）
分支：`feat/enterprise-hardening`
说明：本报告是本轮唯一的最终验收报告；此前各轮中间报告（v4、v5 等）已被取代并移除，不再保留。

---

## 1. 基线数据（本轮开工前实测）

| 项 | 基线 |
|---|---|
| Python 测试 | 1074 例通过 / 3 跳过 |
| ruff | 全清 |
| coverage | 62% |
| 前端 | tsc 全清，ESLint 0 警告，vitest 40/40，build 成功 |
| 性能 | 100MB 上传导入服务端 RSS 峰值 **3092MB**（异常） |
| 远端 | `feat/enterprise-hardening` 与本地 HEAD 经 374 文件 tree 对比全一致 |

---

## 2. 本轮发现的问题清单（全部为真实复现，非推测）

| # | 问题 | 复现证据 |
|---|---|---|
| 1 | multipart 解析器内存放大：`email.BytesParser` 解析 100MB body 产生约 10 倍瞬时放大 | 性能套件 T3 断言失败：`100MB 上传 RSS 峰值 3117MB 超过 600MB 回归上限` |
| 2 | `scripts/metrics.py::compute_metrics` 物化：`char_ttr` 为 33M 字符建 list（约 1.6GB），`compute` 物化约 310 万句子 list，`bigram_freq` 逐位置切片 | 100MB 分阶段 tracemalloc 诊断进程被 OOM kill（exit 137）；20MB 样本下旧实现峰值超 300MB |
| 3 | 上传缓冲与导入期内存叠加：`_handle_import_upload` 的 raw+file_bytes（约 2x）与 `import_book` 的 text+chapters（约 2x）同时存活 | T3 峰值 630MB（修复 1、2 后仍超 600MB 哨兵） |
| 4 | 空库 E2E 隔离脚本缺陷：`--exclude='assets/'` 非锚定，误删 `gui/web/dist/assets/`，导致空库模式下前端 JS 404、页面空白 | onboarding E2E 连续 `2 failed`：`getByText('欢迎使用 novel-lab')` 找不到；curl 确认 JS 返回 text/html |
| 5 | 前端竞态：`AppContext.selectChapter` 旧请求回包覆盖新章节；`ResultPanel` 切章时批次状态未归零；`SettingsWorkbench` 输入态与校验缺失 | 定向 race 测试复现 |
| 6 | `QcVisuals` 热力图静默空白：`HeatmapChart` 未在 `BaseChart` 注册 | 代码审查发现（此前轮次已修复，本轮回归确认） |
| 7 | ruff 4 项违规（perf_check import 排序/未用 import/`TimeoutError` 别名；测试文件多余 encoding 参数） | `ruff check` 输出 |
| 8 | 文档口径漂移：`AGENTS.md §7` 测试基线 1103 vs 实测 1109（新增 multipart 测试后未同步） | `test_doc_metrics` 失败：`1103 != 1109` |

---

## 3. 修复记录

| # | 修复 | 验证 |
|---|---|---|
| 1 | `gui/router.py`：multipart 解析器重写为纯 bytes 边界扫描（标准库 only，零新增依赖）；缺 boundary、截断 body 返回 400；支持 quoted/RFC2231/raw UTF-8 中文文件名 | `tests/test_import_upload` 19/19；20MB 解析 tracemalloc 峰值 < body 3 倍 |
| 2 | `scripts/metrics.py` 流式化：`char_ttr` 改唯一字符集+计数器；`_sentence_len_stats` 用 `finditer` 单遍；`bigram_freq` 改 zip 配对；`_paragraph_count` 流式 | 新旧实现对同一混合文本全量 JSON `diff` 无差异（PARITY_OK）；新增 `tests/test_metrics_streaming.py` 7/7（含 10MB/20MB 内存上界回归） |
| 3 | `gui/server.py`：上传缓冲落盘后 `del raw, file_bytes`；`gui/services.py`：metrics 算完后 `del text`（正文保留在 chapters_raw） | T3 峰值 630MB → **431.5MB** |
| 4 | `scripts/e2e_isolated.sh`：空库排除改为根锚定（`/corpus/` `/assets/` `/reports/` `/gui/state/`）；默认模式保留种子数据（smoke 资产库测试需要） | `E2E_EMPTY_LIBRARY=1` 下 onboarding 2/2 |
| 5 | `AppContext` sequence guard、`ResultPanel` 请求序列守卫+切章批次归零、`SettingsWorkbench` 字符串态输入/即时校验/交叉阈值校验/保存重置刷新、Quality/Writing 状态中文化、`ErrorBoundary` 重试恢复 | vitest 51/51（含新增 race/校验/重试测试 11 例） |
| 7 | ruff `--fix` 自动修复 4 项 | `ruff check .` 全清 |
| 8 | `AGENTS.md §7` 基线同步为 1116（后随 metrics 新测试再次同步；16:34 复验轮再同步为 1117） | `test_doc_metrics` 通过 |

---

## 4. 门禁结果（均为本轮最终代码上的真实工具输出）

### Python
- `python3 -m unittest discover -s tests`：**1117 例，OK（3 跳过）**——3 跳过为 2 个 Windows-only + 1 个缺 corpus，与基线一致（16:34 复验轮新增守卫用例 1 例，基线 1116→1117）
- `ruff check .`：**All checks passed**
- `coverage report --fail-under=60`：**62%，通过**

### 前端
- `npx tsc --noEmit`：通过
- `npx eslint src`（不加 `--quiet`）：**exit 0，0 警告 0 错误**
- `npx vitest run`：**11 文件 51/51 通过**
- `npm run build`：成功（产物已提交入库，CI 另有 dist freshness 校验）

### E2E（均为隔离服务实测，`scripts/e2e_isolated.sh`）
- 普通模式：**12 通过 / 2 跳过**（2 个 onboarding 用例按设计在非空库跳过）
- 空库模式（`E2E_EMPTY_LIBRARY=1`）：**onboarding 2/2 通过**（三步走完/跳过，刷新不再出现）
- journey 新增真 UI 一键分析链路：导入 → `/api/genres` 取合法题材 → 选定题材 → 一键分析 → `/api/analyze/full` 200 且 `task_id` 非空

### 性能（隔离复测，`docs/internal/perf_2026-09-28.json`）
- T1 20 并发读：p99 1035.6ms（nearest-rank，含最大值）
- T2 10 并发上传：10 本全入库
- T3 100MB 上传：34.4s，**服务端 RSS 峰值 431.5MB**（基线 30.2MB；旧实现 3092MB）
- T4 超限：413 立即拒绝
- T5 模型超时：熔断正常，`timeout_observed=true`
- verdict：**ALL_PASS**
- 注：600MB 为内部回归哨兵（旧 3.1GB 病态放大的量级对照），不是任务书阈值（任务书无性能数值要求）

### 第 4 节规则复核（每次提交前执行）
- 三铁律：题材隔离 / 万字报告 / 纯标准库零第三方依赖（`test_stdlib_only` 全绿）——均未触及红线
- 六约束：校验先于副作用（multipart 400 在写盘前）；无新增模块级路径常量；未直接写 `assets/`/`reports/`；CHANGELOG 数字为带日期历史快照（约束六明确豁免）；`AGENTS.md §7` 为唯一实测口径来源
- 架构硬约束：import 方向未变；服务仅绑 `127.0.0.1`；测试零污染真实状态（隔离脚本 + `_isolation.py`）

---

## 5. 未实测链路声明

- **外部模型链路未实测**：项目 secret store 无可用 LLM key，按任务书 §5 以 mock/离线路径完成端到端验证。受影响的验证项：真实模型调用的拆书/写作/质检全链路、模型超时重试的真实延迟特征。T5 超时熔断用的是黑洞 TCP + `timeout=2` 的模拟模型。
- **npm audit 未完成**：`npm audit` 被环境代理策略拒绝（`POST /-/npm/v1/security/audits/quick` → `policy_denied`）。**不记为通过**，留待可联网环境补跑。

---

## 6. 遗留事项

| 事项 | 状态 |
|---|---|
| npm audit | 未完成（见 §5），需在可联网环境补跑 |
| 外部模型链路 | 未实测（见 §5），有 key 后需补真实调用验证 |
| echarts chunk 610KB | vite 构建警告（>500KB）；已按需拆分为独立 chunk，前端门禁通过；是否进一步拆分由后续迭代决定 |
| 分支策略 | 代码已推送至 `feat/enterprise-hardening`；是否合并至 `master` 由总负责人（monesy）决定 |

---

## 7. Definition of Done 逐项验收结论

| DoD | 结论 |
|---|---|
| 1. P0 缺陷清零；P1 缺口关闭或有书面裁决 | 本轮未发现 P0；发现的 P1（内存放大、空库 E2E 隔离缺陷、前端竞态）已全部修复并回归验证；16:34 复验轮又发现 2 个测试隔离泄漏（P1）+ 1 个守卫缺口，见 §9，已全部修复并回归验证 |
| 2. 自主全量审计发现的真实 bug 全部修复 | §2 的 8 项 + §9 复验轮的 3 项已全部修复，无剩余 |
| 3. 第 7 节门禁全部落地且通过 | Python 1117 全绿 / ruff 全清 / coverage 62%（fail-under=60）/ ESLint 0 警告 / tsc 全清 / build 成功 / E2E 通过 / 提交前 §4 复核执行——**全部通过** |
| 4. UI 达到高级感/企业级水准 | 本轮涉及前端竞态、中文化、Onboarding 向导；最终视觉验收由总负责人确认 |
| 5. 交付总验收报告 | 本报告即是（唯一一份） |
| 6. 最终代码同步到 GitHub | 已推送 `feat/enterprise-hardening`；远端 386 文件经路径/blob SHA/mode 完整 recursive tree 对比，与本地 HEAD **全一致**（验证方法见推送脚本 `push_v*.py`，报告内不硬编码追逐 SHA）；分支策略见 §6 |
| 7. zip 成品包 + 仓库说明交付 | `novel-lab-enterprise-hardening-20260928-v7.zip`（由最终 Git HEAD 经 `git archive` 生成，解压复验通过，无压缩错误；SHA-256 见交付时的 `SHA256SUMS.txt` 与交付记录，不在版本化报告内硬编码追逐） |

---

## 8. 交付物

- GitHub：`monesyilya3-Niko/novel-lab` / `feat/enterprise-hardening`（386 文件与本地 HEAD 全一致，已复验）
- zip：`~/workspace/your_files/novel-lab-enterprise-hardening-20260928-v7.zip`（由最终 Git HEAD 经 `git archive` 生成；安装器 `novel-lab-installer-20260928-v7.sh` 内嵌同一 zip，经 SHA-256 校验）
- SHA-256：见同目录 `SHA256SUMS.txt`（交付时生成）
- 原始备份（禁止修改/删除，未动）：`~/workspace/user/files/novel-lab-backup-2026-09-27_2_37wf.zip`

---

## 9. 复验轮（2026-09-28 16:34，用户指令"再检查一遍…安装测试一下"）

本轮不测工作树，测**交付物本身**：从 v6 zip 全新解压一套干净安装，跑全量测试。结果抓到 2 个真实隔离泄漏 + 1 个守卫缺口——在工作树里因残留文件已存在而被掩盖，正是"换真实审计角度"的价值。

| # | 问题 | 根因 | 修复 | 验证 |
|---|---|---|---|---|
| 1 | `test_genre_validation.py` 在真实 `gui/state/` 写下 `gui_state_b.json` | `test_known_genre_passes_validation` 未 mock `state_store`，`start_analysis` 走过题材校验后用真实双写（JSON + SQLite）落盘 | 该用例补 `mock.patch.object(services, "state_store")`（与同文件 `_call` 一致） | 干净安装复测不再产生该文件 |
| 2 | `test_p2_hardening.py` 在真实 `gui_state/` 落下 `index.db` | `TestServerAuth.setUpClass` 起真实 `GuiServer`，`start()` 调 `db.init_schema()`，但只隔离了 `LOCK_PATH`/`API_TOKEN`，未隔离 `STATE_ROOT` | `setUpClass`/`tearDownClass` 加 `STATE_ROOT` + `STATE_JSON_DIR` 成对隔离（沿用 `test_gui_backend.py` 既有模式） | 同上 |
| 3 | 守卫缺口：`TestRealGuiStateLeakGuard` 从未比对 `files` 集合 | `_isolation.snapshot_real_gui_state()` 拍了 `files` 快照，但守卫只断言 `settings.json` 内容/mtime 与 `.tmp` 残留——问题 2 的 `index.db` 长期漏网 | 新增 `test_no_new_files_in_real_gui_state`：比对 `files` 集合（排除 SQLite `-wal`/`-shm` 边车，见快照函数注释） | 反向验证：基线后建 `fake_leak.db`，新守卫 FAIL 捕获；删除后通过 |

修复后：工作树全量 **1117 例 OK（3 跳过）**；远端重新推送并 384 文件完整 recursive tree 复验一致；v7 zip（`git archive`）重新打包，`unzip -t` 通过；**从 v7 zip 干净安装再跑全量：1117 例 OK，`gui/state/` 与 `gui_state/` 零新增文件**；另从干净安装起真实服务冒烟：`GET /` 200、`/api/overview` 200、`POST /api/import-upload`（中文文件名 multipart）200 并正确入库 1 本书。

本轮未发现生产代码缺陷；P0 仍为零。测试基线 `AGENTS.md §7` 已同步 1116→1117。

**后续（同日）：** 新增 `packaging/`（单文件自解压安装器模板 + 构建脚本），用户指令"搞成安装包，然后安装测试一下"。安装器经完整实测：全新安装→`novel-lab --check` 自检通过→真实服务中文文件名上传入库→安装版全量 1117 通过→`--uninstall` 干净卸载→篡改 payload 被 SHA-256 拦截。远端文件数 384→386（新增 2 个 packaging 文件），已重新推送并完整 recursive tree 复验一致；v7 zip 与安装器均从最新 HEAD 重建。
