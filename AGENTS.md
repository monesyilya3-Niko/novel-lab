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

> 外部桌面智能体（Qoder / Cline / Claude / OpenCode / Antigravity）调用本项目时，
> **优先使用 HTTP API**（CLI 仅作一次性备选），调用手册见 [docs/AGENT_API.md](docs/AGENT_API.md)。

---

## 1. 三条铁律（违反即视为 bug）

### 铁律一：题材隔离
- 不同题材的资产/配置严格隔离，注入时按题材匹配，**禁止跨题材污染**
- 执行机制：聚合题材包时 `source_books` 的 genre 必须全部一致，不一致 → `pass5_aggregate.py` 显式断言 + `sys.exit(1)`，禁止静默跳过
- 执行机制：`craft-card.meta.genre` 必须 ∈ `CORE_GENRES`（完整链题材白名单，`validate.py` 校验；warn 级，不阻断拆书但阻断聚合）
- 执行机制：题材集**不存在人工维护清单**——由 `scripts/genre_registry.py` 扫描 `assets/` 派生（`CORE_GENRES` 完整链 ∪ `PROSE_GENRES` prose 卡 = `KNOWN_GENRES`），磁盘是唯一真相源
- 执行机制：`genre-prose-card.meta.id` 必须符合 `genre-<slug>` 命名规范，且文件名与之严格对应（`tests/test_genre_registry.py` 双向守卫）
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
python run_tests.py          # 全量门禁（用例数只认 §7 的权威口径行，别在此处另写一份）
```

### 隔离要求（血泪教训）
**新增 config 路径常量时，所有 patch 该类路径的测试必须同步审查。**

已发生的事故 ①（2026-09-11）：`gui/config.py` 的 L2 修复新增 `STATE_JSON_DIR` 后，`tests/test_overview_api.py` 与 `tests/test_asset_index.py` 的 `setUpClass` 只 patch 了 `STATE_ROOT`，漏了 `STATE_JSON_DIR`，导致测试夹具数据写进**真实的 `gui/state/`** 并跨轮累积，造成 2 个测试持续失败。

已发生的事故 ②（2026-09-23）：`gui/system_service.py` 把 settings.json 路径写成**模块级常量** `_SETTINGS_FILE = config.STATE_ROOT / "settings.json"`。该赋值在**导入期**执行、路径被固化，因此 `setattr(config, "STATE_ROOT", tmp)` 这类重定向**对它完全无效**，`tests/test_system_service.py` 实际写进了**真实** `gui_state/settings.json`（受控实验：写入哨兵值 → 跑全量测试 → 哨兵被完全抹掉、内容变成测试入参值）。事故 ① 的防线只覆盖 `gui/state/`，故未能拦住。

**规矩**：
- 测试若涉及路径常量，必须 patch **全部**相关常量，不得只 patch 其中一部分
- patch 后必须在 `tearDownClass` 恢复
- 临时目录要覆盖所有被 patch 的路径
- **运行时路径一律在函数内实时求值**（`config.STATE_ROOT / "x.json"`），禁止写成模块级常量——导入期快照无法被 patch 重定向
- 已有防线测试守护此约束（见 `tests/`），**不得删除或弱化**：
  - `tests/test_config_isolation.py`（登记表全覆盖 + 确定性路径跟随）
  - `tests/test_module_config_snapshot.py`（AST 扫描导入期快照，白名单需附理由）
  - `tests/test_zz_state_dir_leak_guard.py`（`gui/state/` 与 `gui_state/` 双目录泄漏守卫）
  - `tests/test_doc_metrics.py`（`AGENTS.md` §7 口径与实测一致）

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
| 项目根（唯一权威工作副本） | `C:\Users\monesy\workspace\projects\novel-lab` |
| 主解释器 | `C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe` |
| 解释器版本 | **实际 3.13.14**（目录名 3.13.12 是历史 artifact，属正常） |
| 项目 venv | `C:/Users/monesy/.niko/binaries/python/envs/default`（3.13.14，含 fontTools / numpy / Pillow，仅番茄抓书用） |
| Node | `C:/Program Files/nodejs`（实测 v24.21.0 + npm 11.19.0） |
| npm 镜像 | 实测 `~/.npmrc` 为 `https://registry.npmjs.org/`（官方源本机 `npm ci` 实测可用；旧的 npmmirror 口径已过时） |
| pip 镜像 | 实测 `pip config list` 为空（未配置镜像，走默认源） |
| GitHub | 直连可用（2026-10-08 实测 `git push` 到 origin 成功）；备用镜像 `ghfast.top` |

#### ⚠️ 本机有第二个 novel-lab 克隆（2026-10-08 实测确认）

`C:\Users\monesy\niko\novel-lab` 是**迁移前的旧副本**：分支 `master`、最后提交 `edfae04`（2026-09-23）、
工作区停留在 2026-09-24，68 个文件未提交。它的已提交历史已完整包含于权威副本（`git cat-file -e edfae04` 可验），
但工作区里留着**从未进过任何分支的草稿**（`APP_PLAN.md`、`electron/`、`skills/`，以及 6 个未入库的 React 组件：
AssetEditor / ChapterManager / ExportImportPanel / GlobalSearch / NotificationCenter / QuickStartLoop）。

规矩：
- **只在权威副本开发**。旧副本里改文件、提交，会得到一份 2026-09-23 的陈旧产物。
- **不要删除旧副本**。上述草稿未受版本控制保护，删掉即永久丢失；要清理必须先确认它们已被取代。
- 旧副本的组件草稿若日后需要，从磁盘取回并在新前端结构下重写，不要整目录覆盖 `gui/web/src`。

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
- 当前实测口径（2026-10-03）：资产 **86** / 报告 **12** / 书 **9**（已拆 7，磁盘语料 2）/ 测试 **1262** / API 端点 **95** / 版本 **2.0.3**（版本号 2.0.2→2.0.3；此前括号内全部内容沿用）（新增：写作创作页 14 路由——大纲/人物卡/灵感便签/码字统计/TXT 导出；新增 14 个题材 prose 卡，题材 32→46；新增 102 个题材专属桥段，桥段库 68→170（46 个 prose 题材各 3 条）+ 每题材 3 条不变式回归测试；AI 生成流码字统计异常隔离 + record_words AST 静态回归测试 + record_words 异常行为级测试（AI 生成任务仍进 done、手动入库不受影响）；测试文件直接运行 sys.path 约定修复（test_writing_extra/test_b3_cross_thread_close/test_concurrent_writes/test_deepwater_regressions/test_p2_validation 共 5 文件）+ test_direct_run_convention 行为级守卫；桥段数量徽标 total_count 契约修复；gui/web package-lock 根版本 2.0.1→2.0.2 对齐；102 条新桥段 niko 逐条精读审计完成（修复 11 处元叙事：T-BW-003/T-DT-003/SA-001/KJ-002/DT-002/CY-002/MF-002/ND-003/SA-003/WU-001/WY-003 + T-XN-001 中英混杂；题材漂移/同构 0 问题）；14 张 prose 卡逐张精读审计完成（共修改 7 张卡：其中 5 张真实 IP/人名借用——电竞卡 LGD/娃娃/召唤师峡谷/Pentakill→虚构名、武侠卡沈浪→沈砚、无限流卡寂静岭/无限恐怖台词→原创、盗墓卡王胖子/九龙抬棺→原创、网游卡熔火之心→烈焰深渊；2 张读者指代——美食/历史穿越卡与桥段库标准对齐）；迁移 0002 新增 writing_outlines/characters/notes/daily_stats 四表；新桌面图标；gui/server.py 直接执行兼容（`python3 gui/server.py`）+ test_server_direct_run 回归测试；章节重复入库幂等（record_words 支持带符号增量，import_chapter/_run_generate 落盘前快照旧章节、只记增量不重复累加章节数，返回 overwrote 标记）+ 5 个幂等行为测试；_CHAPTER_WRITE_LOCK 章节写锁（快照→落盘→记账原子化，防并发重复入库竞态）+ 并发 20 线程回归测试；write_manifest 真幂等（无变化重跑不写文件）+ 回归测试）
- 第三方衍生资产必须携带 `provenance.source / license / copyright` 三要素，并在 `THIRD_PARTY_NOTICES.md` 逐张登记（`validate.py` 硬校验 + `tests/test_third_party_notices.py` 守卫）；许可证原文须以逐字副本存于 `LICENSES/<上游>/`
- ⚠️ 历史文档中的「17 资产 / 33 测试 / 3 本书 / 68 资产 / 272 测试 / 353/373/648 测试 / 44 端点」等均为**过时或错误口径**
- 用户数据（财务等）永远留空待用户填写，**AI 不得代填**
- Git Data API 推送教训（2026-09-30）：blob 创建后必须用 GET 验证内容再建 tree（曾推送过根版本仍为 2.0.1 的错误 blob）；tree 必须基于远端最新 commit 的 tree；推送后 fetch + reset --hard 对齐本地（API 创建的 commit SHA 与本地不同但 tree 一致属正常）

### 发布与版本禁令（用户下达，长期有效；2026-10-08 从桌面交接文档收编进本文件）

- **未经用户明确点头，不得**：改版本号、打 tag、建 Release、发版。v2.0.3 是用户批准后才做的。
- 版本号单一真相源是 `gui/__init__.py::__version__`，`tests/test_version_consistency.py` 强制 7 处一致；改版本后必须重建前端 dist（`cd gui/web && npm run build`）。
- 打 tag / 建 Release 会触发 `release.yml` 直接产出对外发布物，属**不可逆的对外动作**，一律等用户点头，不得以"流程已跑通"为由自行执行。
- 以下两件事此前只写在桌面《novel-lab-项目交接文档》里，仓库内没有副本，故收编于此（文档丢失即等于约束丢失）：
  - Release 资产上传曾遇到 `custom.github` 凭证对 `uploads.github.com` 返回 401（对 `api.github.com` 正常），当时改用浏览器网页端上传成功。**本机实测状态**：`gh auth status` 已通过（账号 monesyilya3-Niko，token scopes 含 `repo`/`workflow`），下次发版可先试 `gh release upload`；该路径**尚未实机验证**（验证需真实 Release，不在授权范围内）。
  - 桌面安装产物**未做代码签名**（2026-10-08 对 v2.0.3 资产实测 `Get-AuthenticodeSignature` = `NotSigned`），Windows SmartScreen 必然弹"未知发布者"，用户侧需要手动"更多信息 → 仍要运行"。

---

## 8. 相关文档索引

| 文件 | 用途 | 可信度 |
|---|---|---|
| `docs/internal/PROJECT_LAW.md` | **规则单一权威来源**（v2：三铁律 + 六条工程约束，含判定标准与事故依据） | ✅ 权威，优先于本文件 |
| `docs/internal/RULES.md` | 可执行规则全集（操作层细则） | ✅ 大体可用 |
| `AGENTS.md` | 本文件（AI 协作者入口 + 当前实测口径） | ✅ 权威 |
| `docs/internal/PROJECT_SUMMARY.md` | 项目总结 | ✅ 已重写（2026-09-11，基于实测） |
| `docs/internal/HANDOFF.md` | 交接文档 | ✅ 已重写（2026-09-11，基于实测） |
| `docs/DESIGN_gui_phase2_writing_quality.md` | 阶段二设计（W10-W18） | ✅ 权威 |
| `docs/compose/spec/` | Compose Next 特性文档 | ✅ 按需 |
