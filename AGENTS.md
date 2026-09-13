# AGENTS.md — novel-lab 项目规约（AI 协作者必读）

> 本文件是**可执行的硬约束**，面向所有 AI 协作者。任何违反即视为 bug。
> 生成日期：2026-09-11 ｜ 项目已从另一套 niko 实例迁移至 niko 工作区

---

## 0. 项目定位

**novel-lab** 是一套网文创作辅助系统，覆盖全链路：

```
导入语料 → 拆书分析(pass1-4) → 多维资产蒸馏 → 万字报告 → 质检 → 题材包/文风卡 → 注入辅助写作
```

双形态交付：**CLI 引擎**（`novel.py`，20+ 子命令）+ **GUI 工作台**（浏览器访问 `http://127.0.0.1:8000/`，Python 标准库常驻 + 预构建前端）。

---

## 1. 三条铁律（违反即视为 bug）

### 铁律一：题材隔离
- 不同题材的资产/配置严格隔离，注入时按题材匹配，**禁止跨题材污染**
- 执行机制：聚合题材包时 `source_books` 的 genre 必须全部一致，不一致 → `pass5_aggregate.py` 显式断言 + `sys.exit(1)`，禁止静默跳过
- 执行机制：`craft-card.meta.genre` 必须 ∈ `KNOWN_GENRES` 白名单（`validate.py` 校验）
- 执行机制：桥段库每个 trope 必须标注 `genre_scope`（universal / 题材专属 id）

### 铁律二：万字报告硬校验
- 拆书报告 + 笔法分析**合计**字符数 ≥ **10000**（硬门槛）
- 执行机制：`novel.py 分析` 收尾做合计校验，不足 `sys.exit(1)` 阻断交付
- `report.py` / `report_craft.py` 各自单份 < 10000 仅 soft warning，不阻断
- 最终以「分析」命令的合计校验为准

### 铁律三：纯标准库零第三方依赖
- **`scripts/` 与 `gui/` 后端只能用 Python 标准库**（sqlite3 / json / urllib / http.server / ctypes 等）
- 前端层（Vite + React）不受此约束
- 已用 `ctypes` 实现 Windows 进程探活——**禁止引入 psutil** 等替代

---

## 2. 依赖方向禁令（不可倒置）

| 约束 | 说明 |
|---|---|
| `gui/engine_adapter.py` | **唯一** import `scripts/` 的层 |
| `gui/db.py` | **唯一** import sqlite3 的层 |

其他任何模块都不得直接 import `scripts/` 或 `sqlite3`。

---

## 3. 路径常量（唯一来源：`gui/config.py`）

```python
ROOT_DIR       = novel-lab/
SCRIPTS_DIR    = novel-lab/scripts/
WEB_DIR        = novel-lab/gui/web/
DIST_DIR       = novel-lab/gui/web/dist/
ASSETS_ROOT    = novel-lab/assets/
STATE_ROOT     = novel-lab/gui_state/     # 运行时产物：index.db + WAL + .lock + 备份
STATE_JSON_DIR = novel-lab/gui/state/     # 状态 JSON 降级副本（不入库·SQLite 派生镜像）
DB_PATH        = gui_state/index.db       # ← 注意不是 gui/state/
LOCK_PATH      = gui_state/.lock
REPORTS_DIR    = novel-lab/reports/
CORPUS_DIR     = novel-lab/corpus/
CONFIG_DIR     = novel-lab/config/
NOVEL_DIR      = novel-lab/novel/
```

### ⚠️ 路径易混淆点
- **DB 在 `gui_state/index.db`**，状态 JSON 在 `gui/state/`——两者已分离，勿混淆
- `gui_state/` 被 `.gitignore` **整目录**忽略（纯运行时产物）
- `gui/state/` 同样**不入库**（`.gitignore` 整目录忽略）：它是 SQLite 的派生镜像，SQLite 才是唯一权威来源（§6 已裁决）

---

## 4. 测试规范（关键：隔离）

### 运行方式
```bash
python run_tests.py          # 全量（基线 353 用例）
```

### 隔离要求（血泪教训）
**新增 config 路径常量时，所有 patch 该类路径的测试必须同步审查。**

已发生的事故：`gui/config.py` 的 L2 修复新增 `STATE_JSON_DIR` 后，`tests/test_overview_api.py` 与 `tests/test_asset_index.py` 的 `setUpClass` 只 patch 了 `STATE_ROOT`，漏了 `STATE_JSON_DIR`，导致测试夹具数据写进**真实的 `gui/state/`** 并跨轮累积，造成 2 个测试持续失败。

**规矩**：
- 测试若涉及路径常量，必须 patch **全部**相关常量，不得只 patch 其中一部分
- patch 后必须在 `tearDownClass` 恢复
- 临时目录要覆盖所有被 patch 的路径
- 已有防线测试守护此约束（见 `tests/`），**不得删除或弱化**

### 提交前自动测试守卫
仓库内 `.githooks/pre-commit` 会在每次提交前跑 `python run_tests.py`，失败则阻止提交。
新克隆后启用一次：

```bash
git config core.hooksPath .githooks
```

临时绕过：`git commit --no-verify`。详见 `.githooks/README.md`。

---

## 5. 环境（迁移后）

| 项 | 值 |
|---|---|
| 项目根 | `C:\Users\monesy\niko\novel-lab` |
| 主解释器 | `C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe` |
| 解释器版本 | **实际 3.13.14**（目录名 3.13.12 是历史 artifact，属正常） |
| 项目 venv | `C:/Users/monesy/.niko/binaries/python/envs/default`（3.13.14，含 fontTools / numpy / Pillow，仅番茄抓书用） |
| Node | `C:/Users/monesy/.niko/binaries/node/versions/22.22.2-2`（v22.22.2 + npm 10.9.7） |
| npm 镜像 | `https://registry.npmmirror.com`（官方源慢） |
| pip 镜像 | `https://mirrors.aliyun.com/pypi/simple/`（**清华源当前 403 不可用**） |
| GitHub | 直连可用；备用镜像 `ghfast.top` |

### Windows / Git Bash 坑（来自 RULES.md 第七节）
1. **路径**：`/c/xxx` 传给 Python 会被当字面路径 → 用 `C:/xxx` 或先 `cd`
2. **删除**：本机沙箱回收站不可用，`shutil.rmtree` 会失败 → 项目内测试数据用逐文件 `unlink` + `rmdir`
3. **tail -c 按字节截断 UTF-8** 会显示乱码 → 用 Python 读文件验证内容
4. **路径叠加**：`cd novel` 后再 init 会创建 `novel/novel` 嵌套 → 统一在项目根操作

---

## 6. 已裁决事项

| # | 事项 | 裁决 |
|---|---|---|
| 1 | `gui/state/` 是否入 git | **不入库**（2026-09-11 裁决）。它是 SQLite（`gui_state/index.db`）的派生镜像，SQLite 才是唯一权威来源；跟踪派生数据会造成双真相源漂移与提交噪声，与「长期稳定可维护」相悖。`.gitignore` 已改为整目录忽略；备份由 `gui_state/*.bak-*` 与 migrate CLI 的 backup 机制承担。 |

---

## 7. 数据真实性红线

- 所有资产/报告数字**以实测磁盘为准**，不得臆造或沿用旧口径
- 当前实测口径：资产 **55** / 报告 **8** / 书 **6**（已拆 4）/ 题材 **33** / 测试 **373** / API 端点 **65** / git 提交 **84**
- ⚠️ 历史文档中的「17 资产 / 33 测试 / 3 本书 / 68 资产 / 272 测试 / 44 端点」等均为**过时或错误口径**
- 用户数据（财务等）永远留空待用户填写，**AI 不得代填**

---

## 8. 相关文档索引

| 文件 | 用途 | 可信度 |
|---|---|---|
| `docs/internal/PROJECT_LAW.md` | 三铁律条文 | ✅ 权威 |
| `docs/internal/RULES.md` | 可执行规则全集 | ✅ 大体可用 |
| `AGENTS.md` | 本文件 | ✅ 权威 |
| `docs/internal/PROJECT_SUMMARY.md` | 项目总结 | ✅ 已重写（2026-09-11，基于实测） |
| `docs/internal/HANDOFF.md` | 交接文档 | ✅ 已重写（2026-09-11，基于实测） |
| `docs/DESIGN_gui_phase2_writing_quality.md` | 阶段二设计（W10-W18） | ✅ 权威 |
| `docs/compose/spec/` | Compose Next 特性文档 | ✅ 按需 |
