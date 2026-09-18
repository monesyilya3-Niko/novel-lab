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

- **资产 55 个**：0 WARN / 0 REJECT（sangshi `common_mistakes` 已由本卡观察汇总补齐）
- **报告 8 份**：4 书 × (拆书报告 + 笔法分析)
- **测试 780 用例 OK**（`python -B run_tests.py`，2026-09-18）
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
$PY -B run_tests.py    # 全量（当前 751 OK）
```

- `.githooks/pre-commit`：全量测试 + 暂存资产 schema 校验
- `git config core.hooksPath .githooks` 启用
- 新增路径常量必须登记 `tests/_isolation.py::DATA_PATH_CONSTANTS`

---

## 六、交付物

| 产物 | 路径 |
|---|---|
| 便携包 | `build/dist/novel-lab-portable-v1.1.1/` + `.zip` |
| 安装器 | `build/dist/novel-lab-setup-v1.1.1.exe`（Inno Setup，per-user） |
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
| — | GitHub Release：当前 **v1.1.1**（tag + 本机 `gh release upload` 附加安装包） |
| P2 | 服务常驻 autostart 为可选项，未默认安装 |
| P3 | lint 债：`docs/lint-debt.md`（ruff ignore 基线，重构时顺手清） |
| — | 连续打分后若扩充语料，需重算了字密度分位数常量 |
| — | 检测口径权威说明：`docs/detection-authority.md` |
| — | 章内碎片重复已接入 n-gram 检测（2026-09-18） |

---

## 九、优化轮次索引

| 轮次 | 计划 | 状态 |
|---|---|---|
| 2026-09-16 高优修复 | `docs/superpowers/plans/2026-09-16-*.md` | 完成 |
| 2026-09-17 第二轮 | `docs/superpowers/plans/2026-09-17-*.md` | 完成 |
| 2026-09-18 第三轮 + 连续打分 + 发布 | `docs/superpowers/plans/2026-09-18-*.md` | 完成 |
| 2026-09-18 GUI 实机 + v1.1.1 | 本会话 | 完成 |

---

*本交接文档基于 2026-09-18 实测数据更新（782 tests OK / 55 资产 0 WARN 0 REJECT / v1.1.1）。*
