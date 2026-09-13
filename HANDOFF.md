# novel-lab 交接文档

> **用途**：新会话/新协作者的完整上下文。先读本文件 + `PROJECT_SUMMARY.md` + `AGENTS.md` 即可接手。
> **最后更新**：2026-09-11（迁移后重写，基于 git `fb6a3f6` 实测）
> **项目路径**：`C:\Users\monesy\niko\novel-lab`

---

## 一、项目定位

**novel-lab** 是一套网文创作辅助系统，覆盖全链路：

```
导入语料 → 拆书分析(pass1-5) → 多维资产蒸馏 → 万字报告 → 质检 → 题材包/文风卡 → 注入辅助写作
```

双形态交付：**CLI 引擎**（`novel.py`，20+ 子命令）+ **GUI 工作台**（浏览器 `http://127.0.0.1:8000/`）。

---

## 二、当前状态（2026-09-11）

### 已拆书目（4 本，campus-redemption 题材）

| 书名 | 目录名 | 状态 |
|---|---|---|
| 炽炀 | chireng_chosen | 四类资产齐全 |
| 青柠 | qingning_chosen | 四类资产齐全 |
| 桑式 | sangshi_chosen | 四类资产齐全 |
| 溯雨信笺 | suyixinjian_chosen | 四类资产齐全（2026-09-07 实战闭环） |

### 产出统计

- **资产 55 个**：voice 4 / craft 4 / structure 4 / commercial 4 / genre-pack 1 / distilled 4 / prose-card 33 / trope 1
- **报告 8 份**：4 书 × (拆书报告 + 笔法分析)
- **测试 353 用例全绿**

### GUI 功能

| 模块 | 状态 | 端点数 |
|---|---|---|
| 首页概览 | ✅ 可用 | 3 |
| 拆书分析 | ✅ 可用 | 10 |
| 资产库 | ✅ 可用 | 7 |
| **写作台 (M2)** | ✅ 阶段二新增 | 8 |
| **质检台 (M3)** | ✅ 阶段二新增 | 5 |
| **高级 (M1+M4)** | ✅ 阶段三新增 | 7 |
| **系统 (M5)** | ✅ 阶段三新增 | 4 |
| 设置 | 占位（系统 Tab 内已覆盖） | — |

---

## 三、架构与分层

```
前端 (Vite + React + MUI + Tailwind + ECharts)
  HomeDashboard / AnalysisView / AssetLibrary
  WritingWorkbench / QualityWorkbench / SystemWorkbench / AdvancedWorkbench / SettingsWorkbench
        │  HTTP REST + SSE
        ▼
GUI 后端（纯标准库）
  router.py           65 个端点
  services.py         拆书链路服务
  writing_service.py  M2：注入/写作/打分/组装/手动入库
  quality_service.py  M3：检查/全书质检/qc/报告
  engine_adapter.py   唯一 import scripts/ 的层
  db.py               唯一 import sqlite3 的层
  sse.py              事件广播（task_id 过滤）
        │  同进程 import
        ▼
scripts/（32 个纯标准库脚本）
  pipeline / sampler / metrics / normalize / validate / compliance
  inject / write / consistency / chapter_check / book_quality
  qc / logic_check / setting_check / state_tracker
  distill_core / distill / distill_render / retrieve
  report / report_craft / pass5_aggregate / assemble / ...
```

**关键约束**：
- `engine_adapter.py` 是唯一 import `scripts/` 的层
- `db.py` 是唯一 import `sqlite3` 的层
- `scripts/` 与 `gui/` 后端只能用 Python 标准库（铁律三）

---

## 四、CLI 命令速查

```bash
PY="C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe"

# 状态
$PY novel.py 状态

# 拆书
$PY novel.py 拆书 book.txt --genre campus-redemption
$PY novel.py 组装 书名 --genre campus-redemption
$PY novel.py 校验 asset.json
$PY novel.py 合规 asset.json book.txt

# 写作
$PY novel.py 注入 voice.json --craft-card craft.json --genre-pack gp.json
$PY novel.py 写作 voice.json --chapter 1 --task "要点"
$PY novel.py 检查 chapter.txt --voice voice.json
$PY novel.py 质检 chapter_dir/

# 报告
$PY novel.py 报告 voice.json
$PY novel.py 笔法报告 craft.json

# GUI
$PY -m gui.launch
```

---

## 五、测试与质量守卫

```bash
$PY run_tests.py    # 全量 353 用例
```

- `.githooks/pre-commit` 提交前自动跑全量测试，红测试阻止提交
- `tests/_isolation.py::DATA_PATH_CONSTANTS` 登记所有需隔离的路径常量
- **新增 config 路径常量时必须同步登记**，否则 `test_config_isolation` FAIL

---

## 六、阶段二新增能力（2026-09-11）

### 写作台 (M2)

| 能力 | API | 说明 |
|---|---|---|
| 资产注入 | `POST /api/writing/inject` | voice+可选资产 → system prompt |
| 写作 | `POST /api/writing/generate` | 长任务：改写循环 + SSE 进度；无模型降级 |
| 手动入库 | `POST /api/writing/chapters` | 贴回正文 → 落盘 + 双维度打分 |
| 打分 | `POST /api/writing/score` | 一致性五维 + 章节质量十二维 |
| 组装 | `POST /api/writing/assemble` | pass1-5 → 4 类资产入库 |
| 项目列表 | `GET /api/writing/projects` | 含 default 只读项目 |

### 质检台 (M3)

| 能力 | API | 说明 |
|---|---|---|
| 单章检查 | `POST /api/quality/check` | 质量+一致性双维度 |
| 全书质检 | `POST /api/quality/book` | 重复/连贯/凑字数/乱编/AI味 |
| QC 综合 | `POST /api/quality/qc` | 四层十二维，报告落盘 `reports/qc/` |
| 报告列表 | `GET /api/quality/reports` | 历史报告 |

### 关键设计决策

- **D1**：写入路径唯一 `novel/<project>`，`default` 只读
- **D3**：scratch 结束即删 + 启动自清理
- **D6**：并发上限 2 写作 + 2 质检，超限 429
- **D7**：assemble genre 必填（铁律一）

---

## 七、环境

| 项 | 值 |
|---|---|
| 项目根 | `C:\Users\monesy\niko\novel-lab` |
| Python | `C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe` |
| Node | `C:/Users/monesy/.niko/binaries/node/versions/22.22.2-2` |
| pip 镜像 | 阿里云（清华源 403） |
| npm 镜像 | `registry.npmmirror.com` |

---

## 八、已知限制与待办

| 优先级 | 事项 |
|---|---|
| ~~P1~~ | ~~前端主包 1.7MB 代码分割~~ **已完成**（2026-09-12 实测：主入口 `index-*.js` 仅 20KB，echarts 隔离为独立 chunk，按视图分块加载） |
| ~~P2~~ | ~~npm audit echarts/esbuild 漏洞~~ **已清零**（2026-09-13：echarts 6.1.0 + vite 7 升级后 `npm audit` 0 vulnerabilities） |
| P2 | 服务常驻实测（`gui/autostart/install_task.bat`；安装器/绿色版已提供正式启动方式，此项降级为可选） |
| ~~P2~~ | ~~备份/回滚演练~~ **已加固**（2026-09-13：启动 + 每日首次请求自动备份，`gui/auto_backup.py`；备份/回滚 CLI 原有） |
| — | 番茄抓书工具链未实测 |
| — | lint 债治理清单：`docs/lint-debt.md`（ruff/ESLint 基线豁免项与治理时机） |

## 九、开发期工具链（2026-09-13 起）

- **Python 侧**：ruff（`pyproject.toml`，本地 `uvx ruff check .`；CI 强制）+ coverage；铁律三由 `tests/test_stdlib_only.py` 自动守护（第三方 import 任何层级禁止；gui 层模块级 import scripts/ 仅 engine_adapter）
- **前端侧**：ESLint 9（typescript-eslint + react-hooks）+ Prettier + vitest（`npm run lint/test:run/coverage`）；vite 7 + vitest 5
- **CI**：`.github/workflows/ci.yml`（Python 3.13 windows-latest：ruff + 全量测试 + coverage；Node 22：lint + vitest + 构建 + **dist 新鲜度校验**）+ Release 工作流（推 v* tag 自动从 Conventional Commits 生成发布说明并创建 Release）
- **本地安装工具**：`uvx --default-index https://mirrors.aliyun.com/pypi/simple/ ruff check .`（pypi 直连不稳时走阿里云镜像）

---

*本交接文档基于 2026-09-11 实测数据重写，确保新会话零信息损失接手。*
