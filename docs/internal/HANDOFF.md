# novel-lab 交接文档

> **用途**：新会话/新协作者的完整上下文。先读本文件 + `PROJECT_SUMMARY.md` + `AGENTS.md` 即可接手。
> **最后更新**：2026-09-18（总工收尾第三轮优化 + 连续打分后实测）
> **项目路径**：`C:\Users\monesy\niko\novel-lab`

---

## 一、项目定位

**novel-lab** 是一套网文创作辅助系统，覆盖全链路：

```
导入语料 → 拆书分析(pass1-5) → 多维资产蒸馏 → 万字报告 → 质检 → 题材包/文风卡 → 注入辅助写作
```

双形态交付：**CLI 引擎**（`novel.py`，20+ 子命令）+ **GUI 工作台**（浏览器 `http://127.0.0.1:8000/`）。

---

## 二、当前状态（2026-09-18 实测）

### 已拆书目（campus-redemption）

| 书名 | 目录名 | 状态 |
|---|---|---|
| 炽炀 | chireng_chosen | 四类资产齐全 |
| 青柠 | qingning_chosen | 四类资产齐全 |
| 桑式 | sangshi_chosen | 四类资产齐全 |
| 溯雨信笺 | suyixinjian_chosen | 四类资产齐全 |

### 产出统计（以磁盘为准）

- **资产 65 个**：0 WARN / 0 REJECT（含 distilled 4 + genre-prose-card-index 1）
- **报告 4 份**：2 书 × (拆书报告 + 笔法分析)（2026-09-23 删除 4 本不达标存量报告，见 CHANGELOG）
- **测试 909 用例 OK**（`python run_tests.py`，2026-09-23）
- **git**：本地 `master`；远程 `monesyilya3-Niko/novel-lab`

### 评分语义（2026-09-18 变更，必读）

- 章节 12 维中多处硬档位已改为 **连续打分**（`scripts/chapter_check.py` 的 `_ramp`）
- 满分区与权重不变；分数可带 1 位小数；**历史章节分会与旧口径不同**
- 「了」字密度：语料 p75=27.0 / p90=31.2，其间线性扣分 0→3
- QC D9 同时消费跨章重复与章内碎片重复
- **对话占比满分区可按题材配置**：默认 (0.15, 0.40)；campus-redemption = (0.07, 0.35)（`docs/detection-authority.md`）

### GUI 功能

| 模块 | 状态 | 说明 |
|---|---|---|
| 首页概览 | ✅ | 资产口径已校正 |
| 拆书分析 | ✅ | 五遍扫描 + 万字报告 |
| 资产库 | ✅ | 含 distilled / prose_card_index 独立分类 |
| 写作台 (M2) | ✅ | 注入含蒸馏规则可选下拉 |
| 质检台 (M3) | ✅ | 问题列表可展开；截断有提示 |
| 高级 (M1+M4) | ✅ | 蒸馏/批量/资产编辑 |
| 系统 (M5) | ✅ | 状态与模型配置（含 fallback） |

---

## 三、架构与分层

```
前端 (Vite + React + MUI + Tailwind + ECharts)
  HomeDashboard / AnalysisView / AssetLibrary
  WritingWorkbench / QualityWorkbench / SystemWorkbench / AdvancedWorkbench
        │  HTTP REST + SSE
        ▼
GUI 后端（纯标准库）
  router.py           API 端点
  services.py         拆书链路 + detect/assert_asset_kind
  writing_service.py  M2：注入/写作/打分/组装/手动入库
  quality_service.py  M3：检查/全书质检/qc/报告
  engine_adapter.py   唯一 import scripts/ 的层
  db.py               唯一 import sqlite3 的层
        │
        ▼
scripts/（纯标准库：pipeline / chapter_check / qc / distill / llm_client …）
```

**关键约束**：见 `AGENTS.md` 三条铁律（题材隔离 / 万字报告 / 纯标准库）。

---

## 四、CLI 命令速查

```bash
PY="C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe"

$PY novel.py 状态
$PY novel.py 拆书 book.txt --genre campus-redemption
$PY novel.py 注入 voice.json --craft-card craft.json --genre-pack gp.json
$PY novel.py 检查 chapter.txt --voice voice.json
$PY novel.py 质检 chapter_dir/
$PY novel.py qc chapter_dir/
$PY -m gui.launch
```

模型配置：`$PY scripts/model_config.py list|fallback <id> [备用...]`

---

## 五、测试与质量守卫

```bash
$PY run_tests.py       # 全量（当前 909 OK）
```

- `.githooks/pre-commit`：全量测试 + 暂存资产 schema 校验
- `git config core.hooksPath .githooks` 启用
- 新增路径常量必须登记 `tests/_isolation.py::DATA_PATH_CONSTANTS`

---

## 六、交付物

| 产物 | 路径 |
|---|---|
| 便携包 | `build/dist/novel-lab-portable-v1.1.2/` + `.zip` |
| 安装器 | `build/dist/novel-lab-setup-v1.1.2.exe`（Inno Setup，per-user） |
| 构建脚本 | `build/build_portable.py` → 再 `ISCC.exe build/installer.iss` |

打包基于 `git archive HEAD`，**必须先提交再打包**。

---

## 七、环境

| 项 | 值 |
|---|---|
| 项目根 | `C:\Users\monesy\niko\novel-lab` |
| Python | `C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe`（实际 3.13.14） |
| Node | `C:/Users/monesy/.niko/binaries/node/versions/22.22.2-2` |
| Inno Setup | `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe` |
| pip 镜像 | 阿里云 |
| npm 镜像 | `registry.npmmirror.com` |

---

## 八、已知限制与待办

| 优先级 | 事项 |
|---|---|
| — | GitHub Release：当前 **v1.1.2**（tag + 本机 `gh release upload` 附加安装包） |
| P2 | 服务常驻 autostart：**已启用**（2026-09-21）— 计划任务 `novel-lab-gui-autostart`（ONLOGON，用户 monesy）+ Startup 快捷方式双通道 |
| P3 | lint 债：`docs/lint-debt.md`（ruff ignore 基线，重构时顺手清） |
| P3 | 语料就绪未拆：`corpus/autumn_chosen.txt`、`corpus/duwo_chosen.txt`（books.status=idle） |
| — | 连续打分后若扩充语料，需重算了字密度分位数常量 |
| — | 检测口径权威说明：`docs/detection-authority.md` |
| — | 章内碎片重复已接入 n-gram 检测（2026-09-18） |

### 2026-09-21 锁与 autostart 实测（worktree `chore/autostart-lock-verify`）

| 项 | 结果 |
|---|---|
| `python -m gui.launch --check` | 全模块 import + engine_adapter 自检 **OK**；`gui/web/dist` 存在 |
| `start_gui.bat` 根路径 | `%~dp0..\..` 解析到项目根，`gui/server.py` 可定位 |
| 计划任务 `novel-lab-gui-autostart` | **已注册**（提权 schtasks：ONLOGON / LIMITED / IT，Status=Ready，Run As=monesy，指向主仓 `start_gui.bat`） |
| Startup 自启 | `%APPDATA%\...\Startup\novel-lab-gui-autostart.lnk` → `cmd /c start_gui.bat`，WorkDir=项目根 — **已验证存在** |
| stale 锁（内容为死 PID） | 启动时自动清理并改写为新进程 PID — **通过** |
| 单实例二次启动 | 锁被存活进程持有时拒绝启动 — **通过** |
| 优雅关停 | `_release_lock` 删除 `.lock` — **通过** |
| 关停后重启 | 可再次获取锁并启动 — **通过** |
| 边界现象 | 存活进程仍持有锁文件句柄时，即使锁内容被改成死 PID，`os.replace` 会 WinError 32，`_clear_stale_lock` 返回 False → 维持「已在运行中」拒绝（fail-closed，正确） |
| worktree 测试 skip=1 | `test_split_chapters_on_real_corpus` 因 worktree 无本地 `corpus/`（未入库语料）跳过；主仓同用例 **ok** |

### 2026-09-21 总工审计（生产 `gui_state/index.db`）

| 项 | 结果 |
|---|---|
| schema | 7 表齐备（books/assets/reports/analysis_tasks/genres/schema_migrations/sqlite_sequence）；迁移仅 `0001_init.sql`，无欠账 |
| 磁盘对齐 | assets **60** · reports **10** · books **7**（与 `novel.py 状态` 一致） |
| 发现 1 | 全部 `books.genre` 为空 → 已按资产回填：4 本 campus-redemption + 暮冬念春 realistic-romance |
| 发现 2 | 暮冬念春四卡 `book_id` 为 NULL → 已回填 `暮冬念春`（voice/craft/structure/commercial） |
| 发现 3 | `analysis_tasks` 残留 `qa_leak_probe`（2026-09-10）→ **已删除** |
| 未做 | lint 大扫除（项目原则：触及再清）；autumn/duwo 未拆（业务选择，非缺陷） |
| 备份 | `gui_state/index.db.bak-20260921-105415-chief` |

---

## 九、优化轮次索引

| 轮次 | 计划 | 状态 |
|---|---|---|
| 2026-09-16 高优修复 | `docs/superpowers/plans/2026-09-16-*.md` | 完成 |
| 2026-09-17 第二轮 | `docs/superpowers/plans/2026-09-17-*.md` | 完成 |
| 2026-09-18 第三轮 + 连续打分 + 发布 | `docs/superpowers/plans/2026-09-18-*.md` | 完成 |
| 2026-09-18 GUI 实机 + v1.1.1 | 本会话 | 完成 |
| 2026-09-21 锁/autostart 实测 | worktree 验证 + master 同步 | 完成（计划任务 + Startup 双通道已启用） |
| 2026-09-21 总工审计 | 生产 DB 卫生 + books.genre 回填 | 完成 |
| 2026-09-21 infer_book_id 根因修复 | 去掉 `_chosen` 硬约束，中文书名可归属 | 见 fix 分支 |

---

*本交接文档基于 2026-09-23 实测数据更新（909 tests OK / 65 资产 / 报告 4 / Release v1.1.2；锁/autostart 与总工审计见第八节）。*
