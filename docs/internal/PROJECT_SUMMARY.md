# novel-lab 项目总结文档

> **版本**：2026-09-21（v1.1.2，检测口径重标定 + realistic-romance 入库）
> **项目路径**：`C:\Users\monesy\niko\novel-lab`
> **用途**：新会话直接参考本文件即可了解全部结构与用法；历史沿革见 HANDOFF.md
> **诚实声明**：本文件数字基于 2026-09-18 实测（测试 782 OK / 资产 55）；未实测部分明确标注

---

## 一、项目定位与核心功能

**一句话**：把优秀小说拆成可复用的结构化资产，再用这些资产驱动 AI 创作。

| 核心功能 | 说明 |
|---|---|
| 拆书引擎 | TXT 全本 → 分层采样 → 量化 → 五遍扫描 → 归一化 → 结构化资产 |
| 资产体系 | voice-card / craft-card / structure-obs / commercial-obs / genre-pack / distilled / prose-card / trope-library |
| 资产驱动写作 | 资产注入 → system prompt → 生成 → 三维度改写循环 |
| 质量体系 | 章节检查（12 维 **连续打分**）+ 全书质检 + QC 四层十二维 + 版权合规 |
| GUI 工作台 | `http://127.0.0.1:8000/`：首页/分析/资产库/写作/质检/高级/系统 |
| CLI 引擎 | `novel.py`（20+ 子命令） |
| 发布 | GitHub Release **v1.1.2**（setup.exe + portable zip） |

**LLM 层模式**：可配置外部模型（当前 1 个 openai 协议模型）；失败时显式降级并列出不可用能力。无模型时拆书/写作走会话内接管清单；采样/量化/校验/合规/打分全部本地 Python 计算。支持 **fallback 备用模型链**。

**评分语义（2026-09-18）**：章节维度连续打分（消除悬崖档位）；「了」字密度按语料 p75/p90；对话占比满分区可按题材包 `dialogue_optimal` 配置（campus-redemption = 0.07–0.35）。

---

## 二、整体架构

```
┌─ 拆书层 ─────────────────────────────────────────────────────┐
│ novel.py 拆书 book.txt --genre campus-redemption             │
│   sampler.py → metrics.py → 五遍扫描 → normalize.py → validate.py
├─ 聚合层 ─────────────────────────────────────────────────────┤
│ pass5_aggregate.py  ≥3本同题材 → genre-pack 题材包            │
│ distill.py          跨书蒸馏 → *-distilled.json              │
├─ 写作层 ─────────────────────────────────────────────────────┤
│ inject.py    资产 → 写作 system prompt                       │
│ write.py     生成+三维度改写循环                              │
│ consistency.py / chapter_check.py / book_quality.py          │
├─ 质检层 ─────────────────────────────────────────────────────┤
│ qc.py           四层十二维统一质检                            │
│ logic_check.py  逻辑合理性检测                                │
│ setting_check.py 设定一致性检测                               │
│ state_tracker.py 状态追踪                                     │
├─ GUI 工作台（纯标准库后端 + Vite/React 前端）─────────────────┤
│ 阶段一：首页 / 分析 / 资产库（20 端点）                       │
│ 阶段二：写作台(M2) + 质检台(M3)（13 端点）                    │
│   writing_service.py  注入/写作/打分/组装/手动入库            │
│   quality_service.py  检查/全书质检/qc/报告                   │
├─ 产出层 ─────────────────────────────────────────────────────┤
│ report.py / report_craft.py  拆书报告 / 笔法分析报告           │
│ novel.py                     CLI 统一入口                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、实测数据（2026-09-11）

| 指标 | 数值 |
|---|---|
| 资产文件 | **55**（0 WARN / 0 REJECT；含 distilled 4 + prose-card-index 1） |
| 可交付报告 | **8** 份 |
| 已拆书目 | **4** 本（炽炀 / 青柠 / 桑式 / 溯雨信笺，campus-redemption） |
| API 端点 | **65** 个（router.py 路由表） |
| 测试 | **782** 用例全绿（2026-09-18） |
| 版本 | **1.1.2**（GitHub Releases 附安装包） |

---

## 四、使用指南

### 4.1 环境

```bash
PY="C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe"
cd "C:/Users/monesy/niko/novel-lab"
```

### 4.2 CLI 常用命令

```bash
$PY novel.py 状态                          # 查看项目状态
$PY novel.py 拆书 book.txt --genre xxx     # 拆一本新书
$PY novel.py 组装 书名 --genre xxx         # 组装 pass1-5 → 资产
$PY novel.py 校验 asset.json               # schema 校验
$PY novel.py 合规 asset.json book.txt      # 版权合规
$PY novel.py 注入 voice.json --craft-card craft.json --genre-pack gp.json
$PY novel.py 写作 voice.json --chapter 1 --task "要点"
$PY novel.py 检查 chapter.txt --voice voice.json
$PY novel.py 质检 chapter_dir/
$PY novel.py 报告 voice.json
$PY novel.py 笔法报告 craft.json
```

### 4.3 GUI 工作台

```bash
$PY -m gui.launch                          # 启动 GUI（http://127.0.0.1:8000/）
```

**阶段一**：首页概览 / 拆书分析 / 资产库浏览
**阶段二**：
- **写作台**：资产注入 → 写作（改写循环/无模型降级+手动入库）→ 双维度打分 → pass 组装
- **质检台**：单章检查（质量+一致性）→ 全书质检 → QC 四层十二维（报告落盘 `reports/qc/`）
- **高级**：题材蒸馏 / 批量拆书状态 / 资产编辑（M4 写入）
- **系统**：系统状态 / 版权合规扫描 / 模型配置 / 设置

### 4.4 测试

```bash
$PY run_tests.py    # 全量 782 用例（2026-09-18）
```

---

## 五、三条铁律（违反即视为 bug）

1. **题材隔离**：不同题材资产/配置严格隔离，聚合时 genre 必须全一致，不一致 `sys.exit(1)`
2. **万字报告硬校验**：拆书报告 + 笔法分析合计 ≥ 10,000 字符（`scripts/report.py::check_combined_report_length` 单一来源）
3. **纯标准库零第三方依赖**：`scripts/` 与 `gui/` 后端只能用 Python 标准库

---

## 六、依赖方向（不可倒置）

| 约束 | 说明 |
|---|---|
| `gui/engine_adapter.py` | **唯一** import `scripts/` 的层 |
| `gui/db.py` | **唯一** import `sqlite3` 的层 |

---

## 七、路径常量（唯一来源：`gui/config.py`）

```
ROOT_DIR       = novel-lab/
ASSETS_ROOT    = novel-lab/assets/
STATE_ROOT     = novel-lab/gui_state/     # SQLite + WAL + 锁
STATE_JSON_DIR = novel-lab/gui/state/     # 派生镜像（不入库）
DB_PATH        = gui_state/index.db
REPORTS_DIR    = novel-lab/reports/
CORPUS_DIR     = novel-lab/corpus/
NOVEL_DIR      = novel-lab/novel/         # 写作产出
PROMPTS_DIR    = novel-lab/prompts/generated/
```

---

## 八、环境约束

| 项 | 值 |
|---|---|
| Python | `C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe`（实际 3.13.14） |
| Node | v22.22.2 + npm 10.9.7 |
| pip 镜像 | 阿里云（清华源 403） |
| npm 镜像 | `registry.npmmirror.com` |
| 测试隔离 | 新增 config 路径常量必须登记 `tests/_isolation.py::DATA_PATH_CONSTANTS` |
| 提交守卫 | `.githooks/pre-commit` 自动跑全量测试 |

---

## 九、已知限制

1. **无外部模型**：写作改写循环需 AI 会话内接管，GUI 提供降级指引+手动入库；有模型时支持 fallback 链
2. **前端 echarts**：独立按需加载 chunk
3. **番茄抓书**：依赖 venv 的 fontTools/numpy/Pillow，探针曾通过，非日常路径
4. **服务常驻**：已启用（2026-09-21）— 计划任务 `novel-lab-gui-autostart`（ONLOGON）+ Startup 快捷方式；stale 锁 / 单实例 / 关停重启实测通过

---

*文档更新时间：2026-09-21 ｜ 数据基准：测试 801 OK / 资产 60 / 报告 10 / Release v1.1.2*
