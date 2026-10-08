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
- **正文路径准入（`gui/text_access.py`）**：打分 `chapter_path`、合规 `book_path`、投稿导出 `book_dir`、
  质检 `target` 一律**不限目录、只限内容**（`.txt`/`.md`、非符号链接、体积与数量上限）。
  旧实现要求"必须在项目目录或用户数据目录内"，用户的稿子放在别处就直接 403，反馈原话是"有些路径放不进去"。
  **别把目录前缀检查加回来**，也别因为它看起来"删掉了安全校验"就回滚：防护目标没变（仍然读不到正文以外的东西），
  只是判据从路径换成了内容。回归锚点在 `tests/test_text_access.py` + `tests/test_security_fixes.py`。
- **正文解码口径**：UTF-8 优先、失败退 GBK（国内 `.txt` 稿子大量是 GBK）。唯一实现在
  `scripts/chapter_loader.read_text_file`，GUI 侧经 `engine_adapter.read_chapter_text` 出口（铁律二：不直连 scripts）。
  只按 UTF-8 读会让真稿报成"读取章节失败"，措辞像路径被禁，实际是编码——别再往回调 `read_text(encoding="utf-8")`。

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
- 当前实测口径（2026-10-08）：资产 **86** / 报告 **12** / 书 **9**（已拆 7，磁盘语料 2）/ 测试 **1350** / API 端点 **95** / 版本 **2.0.3**
  - ⚠️ "资产 86" 指 `assets/*.json` **文件数**（也是 `assets-manifest.json` 的登记数、桌面打包校验用的数）。UI 首页"资产总数"与 `/api/overview.total_assets` 在干净环境下报的是 **85**：`trope-library.json` 是桥段库**容器**、不是资产卡，`asset_index` 按 `ASSET_KINDS` 计数时有意排除（同口径还排除 report/book 虚拟 kind）。两个数都对，别再互相"纠正"。（版本号 2.0.2→2.0.3；此前括号内全部内容沿用）（新增：写作创作页 14 路由——大纲/人物卡/灵感便签/码字统计/TXT 导出；新增 14 个题材 prose 卡，题材 32→46；新增 102 个题材专属桥段，桥段库 68→170（46 个 prose 题材各 3 条）+ 每题材 3 条不变式回归测试；AI 生成流码字统计异常隔离 + record_words AST 静态回归测试 + record_words 异常行为级测试（AI 生成任务仍进 done、手动入库不受影响）；测试文件直接运行 sys.path 约定修复（test_writing_extra/test_b3_cross_thread_close/test_concurrent_writes/test_deepwater_regressions/test_p2_validation 共 5 文件）+ test_direct_run_convention 行为级守卫；桥段数量徽标 total_count 契约修复；gui/web package-lock 根版本 2.0.1→2.0.2 对齐；102 条新桥段 niko 逐条精读审计完成（修复 11 处元叙事：T-BW-003/T-DT-003/SA-001/KJ-002/DT-002/CY-002/MF-002/ND-003/SA-003/WU-001/WY-003 + T-XN-001 中英混杂；题材漂移/同构 0 问题）；14 张 prose 卡逐张精读审计完成（共修改 7 张卡：其中 5 张真实 IP/人名借用——电竞卡 LGD/娃娃/召唤师峡谷/Pentakill→虚构名、武侠卡沈浪→沈砚、无限流卡寂静岭/无限恐怖台词→原创、盗墓卡王胖子/九龙抬棺→原创、网游卡熔火之心→烈焰深渊；2 张读者指代——美食/历史穿越卡与桥段库标准对齐）；迁移 0002 新增 writing_outlines/characters/notes/daily_stats 四表；新桌面图标；gui/server.py 直接执行兼容（`python3 gui/server.py`）+ test_server_direct_run 回归测试；章节重复入库幂等（record_words 支持带符号增量，import_chapter/_run_generate 落盘前快照旧章节、只记增量不重复累加章节数，返回 overwrote 标记）+ 5 个幂等行为测试；_CHAPTER_WRITE_LOCK 章节写锁（快照→落盘→记账原子化，防并发重复入库竞态）+ 并发 20 线程回归测试；write_manifest 真幂等（无变化重跑不写文件）+ 回归测试；2026-10-08 总工批次：ruff 存量清零（纯净 HEAD 上 19 处：B904×12 / I001×5 / F401×1 / B007×1 → 0）；测试在 Windows 退出时释放 SQLite 连接（消除 tearDown 的 WinError 32）并让跨线程 FD 断言只在 POSIX 分支执行；补齐 desktop/build/python-win 后 6 条桌面打包门禁在本机真跑（此前 setUpClass 跳过，故 "Ran" 只报 1256 而口径为 1262）；AGENTS.md §5 环境表按磁盘实测重写（旧项目根指向迁移前的陈旧克隆，Node/npm 镜像/pip 镜像口径已失效）+ §7 收编发版禁令与安装包 NotSigned 实测；test_doc_metrics 口径行守卫加固（锚定列表项、断言唯一、别处提及不再顶掉解析，+2 用例）；质检 target 支持 novel/corpus 之外的任意本机路径（外部目录按章节加载器规则隔离复制，engine_adapter 新增 chapter_scan_rules() 出口 + 三道上限），外部副本改为按 qc-external-* 整棵回收、qc 任务 scratch 清理改 rmtree，+7 用例；e2e 选择器跟上品牌改名并给 dummy 模型注册加收尾（此前它会写脏被跟踪的 config/models.json）；CI 触发分支扩到 feat/** 且锁死 ruff/coverage 版本，据此查出并修好ubuntu 三条腿（FD 采样顺序）与 e2e 全灭（npx 抓到未锁定的 playwright 版本、三处过期选择器）、登录时序断言改为两路径对照；派生路径常量 patch 守卫 + test_system_service 不再量到用户真实库，+9 用例；docs/AGENT_API.md 新增 §4.6 质检端点手册（此前手册完全没有质检），check/book/qc 三端点经真实 HTTP 验证；测试临时目录回收：`_isolation` 新增 `remove_tree()`（先按 PRAGMA database_list 只关"开在该目录内"的 SQLite 连接再整棵删，Windows 句柄未释放是过去删不掉的根因），`isolate_paths()` 退出时自动回收它接管的临时根，13 个测试模块补上 teardown，`test_config_isolation` 加 3 条回收守卫；A/B 实测旧代码每轮全量在 %TEMP% 留 72 个目录、修复后 0 个，实测累计残留 3453 个，其中 2869 个已删除（30 分钟内新建的 176 个保留、40 个被其它在跑的会话占着句柄删不掉）；安全审计批次：访问日志脱敏从只认 auth= 扩到 auth / handshake / handshake_token——实机证明桌面版握手令牌原本明文落进 gui.log（改前 1 次、改后 0 次），并修掉旧替换串里的 SOH 控制字节与吞掉 ?/& 分隔符的过度匹配；管理员初始密码改为只进数据目录指引文件、不进长期留存的日志（仅当指引文件写不出来才退回日志），文件名收口为 admin.ADMIN_HINT_FILE_NAME 单一来源，+6 用例）；2026-10-08 总工批次②：Electron 握手门禁补回归测试（查询参数豁免只适用于 `/api/events`，普通 API 必须带 `X-Handshake-Token`）；打分 `chapter_path`、合规 `book_path`、投稿导出 `book_dir` 统一接入 `gui/text_access.py`（目录不设界、内容设界，+19 用例；旧“项目根外 403”安全断言按新判据重写而非删除）；投稿标题重复章号修复（“第1章 初见”曾导出为“第1章 第1章 初见”），知乎纯 `{title}` 模板不剥前缀，`chapter_num` 为 0/负数/bool 一律 400（+11 用例）；docs/AGENT_API.md 补 §4.7 平台投稿手册（此前该组端点在本手册里完全没有条目）并订正 `chapter_num` 与正文路径准入口径；`announce_initial_password` try 块缩进对齐；正文读取收口到 `gui/text_access.py`（在同一个 fd 上做 O_NOFOLLOW / fstat / 体积校验，再 UTF-8→GBK 解码），`services._secure_read_text` 改为声明策略后复用同一实现（原有措辞与状态码逐条覆盖保留）；引擎侧新增 `scripts/chapter_loader.read_text_file`，QC 单章、`novel.py 检查`/`打分`/`合规`/`清洗`/`批量`/`采样`/`指标`/`组装`/`写作` 全部改走它——GBK 稿子此前在质检里报"读取章节失败"，措辞像路径被禁，实际是只认 UTF-8；默认参数不再冻结模块常量（`max_bytes=None` 才让上限可调，同 §4 的导入期快照坑）；+11 用例（两种编码分数必须一致、FIFO/目录当文件、GBK 单章质检与整本导出静默丢章）；`POST /api/import` 撤掉"导入路径必须在项目目录内"的墙（M8 遗留，与质检同一句话），任意文件读取的防线由 `services._secure_read_text` 承担（只收 .txt / 不跟随链接 / 常规文件 / 100MB），`path` 非字符串补 400（原来会 TypeError 变 500）；docs/AGENT_API.md 补 §4.0 拆书导入（此前 `/api/import*` 一个条目都没有，并写明路径式=就地引用、上传式=归一化落 corpus 的差别）；+7 用例；`writing_extra` 的码字统计/导出/入库记账改走统一解码（用户按 `chapter-NNN.txt` 摆进 novel/ 的 GBK 稿子此前会变成不带文件名的 500），+3 用例；`.githooks/pre-commit` 补 `ruff check .`（CI 每个分支都跑 lint，本地只跑测试导致一条 F401 推上去把 ubuntu 三条腿同时弄红；本机没有 ruff 时只警告不拦）；桌面版新增原生路径选择器：`desktop/preload.js` 用 contextBridge 只暴露 `pickPath(kind)`（不把 ipcRenderer 交给页面），`main.js` 的 `ipcMain.handle` 只认 `dir`/`file` 两个枚举值，`electron-builder.yml` 的 `files` 白名单补 `preload.js`（漏一行就等于功能装机版上静默消失，已加 4 条打包守卫）；质检三个路径输入框在桌面版出现「选择文件…/选择目录…」，浏览器版不渲染。本机真机验证过完整链路：起 dev 版 Electron → 点按钮 → 系统对话框（标题「选择章节文件」、过滤器「正文」）→ 选项目外的 GBK 章节 → 路径回填 → 「检查」出分（质量 73.7 / 一致性 36.0）；目录分支也实测（对话框标题「选择章节目录」→ 选一份混合编码的整本目录 → 全书质检出 Ch1/Ch2 两条章内重复，GBK 那章的文字解码正确）；文风分析的对白统计改走引擎单一口径 `engine_adapter.dialogue_char_count`（原正则只认 ASCII 引号与直角引号，中文弯引号 `“…”` 整段漏计：实测对白占 17% 的稿子被读成 4%，`apply_style_prompt` 据此给出"对话密度较低、以叙述为主"的反向建议）；风格卡落盘改原子写（tmp + `os.replace`；崩溃留下的半份 JSON 会被 `list_styles` 当坏文件跳过，用户看到的是"卡片凭空消失"）；`analyze`/`save`/`apply` 补请求体类型校验（`text`/`style_card`/`base_prompt` 传脏值此前一律变 500），磁盘风格卡里的指标被手改成非数值时回落默认值而不是崩；+10 用例。同一模块的切句口径也一起收口到 `engine_adapter.split_sentences`（`metrics.SENT_RE`：省略号/分号/换行都算句边界）——旧正则只切 `。！？!?`，实测同一篇稿子 140 句被读成 100 句、平均句长 5.6 读成 8.4，句长阈值（15/40）因此可能给出反向建议；+2 用例；帮助文案同步补选择按钮与编码口径；前端 +7 用例，dist 重建
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

### 发布物溯源与真机实测（2026-10-08，Windows 10 19045）

- **溯源方法（有效，下次发版照做）**：`gh run download <run-id> -n windows-installer` 取 CI artifact，与 Release 资产逐字节比 SHA-256。已用此法证明 v2.0.3 的 Release 资产与 run `37496901677`（提交 `d10cd72`）的构建产物**完全相同**（`78370d75…5e0765`，93,401,448 字节）。
- ⚠️ **安装器不是可复现构建**：`desktop/package-lock.json` 入库后依赖版本已锁定，但同一提交在 CI 上构建两次，产物**字节不同**（2026-10-08 实测：均 93,404,140 字节，SHA-256 分别 `e60dba1c…` 与 `08d5fe94…`）——NSIS / electron-builder 会嵌入时间戳一类的构建期差异。
  因此溯源只能比"**产出该发布物的那一次 run**"的 artifact，**不要**用"重新构建一个来对哈希"的方式去判断发布物有没有被改动，那样必然对不上。
- **产物名 ≠ 上传名**：`desktop/electron-builder.yml` 的 `artifactName` 产出的文件是 `暮冬念春-Setup-<ver>-win64.exe`；v2.0.3 上传时被人工改名成了 `novel-lab-Setup-…`。到 artifact 里找包要按 yml 的名字找，别信历史文档里的文件名（CI 的 `path: desktop/release/*-Setup-*-win64.exe` 两种名字都吃得下）。
- **真机安装实测**：提权安装走 `/allusers` → `C:\Program Files\novel-lab-desktop`；exe `ProductVersion 2.0.3.0`；随包含 `gui/ scripts/ assets/ config/ reports/ python-win/`，`assets-manifest.json` 版本与资产数（86）与 §7 口径一致；`http://127.0.0.1:8000/` 返回 200。**用户数据不在安装目录**，在 `%LOCALAPPDATA%\暮冬念春`（`index.db` + `.lock` + 备份 + `corpus` + `assets`），全用户安装下权限正常。
- **真机卸载实测**：卸载注册表项、公共桌面与开始菜单快捷方式均清除，8000 端口不再监听，`%LOCALAPPDATA%\暮冬念春` 按设计保留（已验证：拷贝该目录后用同一套后端代码起服务，能读出 6 本书 / 25 个资产 / 14 张 prose 卡）。残留两处：安装目录剩**空目录**壳（NSIS 不删根目录，轻微，卸载前后都在）；`%LOCALAPPDATA%\novel-lab-desktop-updater\installer.exe` 89.1 MB（electron-updater 下载的整包，NSIS 卸载原本完全不碰）。
  - 后者已由 `desktop/build/installer.nsh` 的 `customUnInstall` 修掉，并做了真机前后对照：同一台机器上，旧包卸载后该目录仍在（89MB）；用带该脚本的构建产物静默装到 `%LOCALAPPDATA%\Programs\` 再静默卸载 → 目录**已清除**，`%LOCALAPPDATA%\暮冬念春` 仍完整保留 17 项，且程序未被启动过。注意：逐字节搜安装包里的路径字符串是**无效验证**（NSIS 脚本块被压缩，新包只比旧包大 14 字节），只有实跑卸载才算证明。
- **桌面版在跑时跑测试**：`migrate._server_is_running()` 读 `config.LOCK_PATH`（`config.py` 的导入期常量，patch `STATE_ROOT` 带不动它）。任何手工隔离路径的测试都必须一并隔离 `LOCK_PATH`，否则用户的桌面版一开，全量门禁误红（2026-10-08 实修，见提交 `dc2b716`）。

#### 安装包改动的复验方法（不需要用户点 UAC）

`perMachine: false` + 不提权时，NSIS 会**静默装进当前用户目录**，Agent 可以自己跑完整装卸循环：

```bash
"<安装包路径>" /S                      # 装到 %LOCALAPPDATA%\Programs\novel-lab-desktop
"%LOCALAPPDATA%\Programs\novel-lab-desktop\Uninstall 暮冬念春.exe" /S   # 卸载
```

卸载后必查三项：`%LOCALAPPDATA%\暮冬念春`（用户数据，必须完整保留）、
`%LOCALAPPDATA%\novel-lab-desktop-updater`（缓存，应被清掉）、`tasklist` 里程序是否被误启动（不应有）。
测完把测试留下的空目录删掉即可；**绝不要**在这条路径上点版本号、打 tag、发 Release。
（上面两条命令已按原样实跑验证：仅 `/S` 即可静默装到用户目录，卸载清掉 updater 缓存，用户数据 17 项无损。）

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
