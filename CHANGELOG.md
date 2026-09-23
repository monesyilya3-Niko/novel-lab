# Changelog

本文件记录面向用户的显著变更。版本发布由 `.github/workflows/release.yml` 驱动：推送 `v*` tag 即从 Conventional Commits 自动生成发布说明。

## [Unreleased] - 2026-09-23（总工第二轮：规则体系 + 存量处置 + 铁律一修复）

### Added
- **`docs/internal/PROJECT_LAW.md` 升级 v1 → v2**：从「只有三铁律条文」扩为**完整可执行规则体系**——三条业务铁律（题材隔离 / 万字报告 / 纯标准库）+ 六条工程约束（校验先于副作用 / 路径实时求值 / 索引可对账可收敛 / 规则上线必须回扫存量 / 交付物只经门禁路径产出 / 文档数字单一来源）。每条按**条文 / 适用范围 / 判定标准 / 理由 / 预期作用**五要素书写，判定标准全部落到可执行命令或测试上。
- **`python -m gui.migrate --prune`（含 `--dry-run`）**：删除「文件已不存在」的索引行（assets / reports），补上索引收敛能力。清理前自动 `backup()`，可回滚。
- `gui/platform_service.get_platform` 错误码 400 → **404**：该函数的 `platform_id` 来自**路径**（`GET /api/platform/{id}`），按 `router.py` 约定属「资源不存在」；其余三个平台接口的 platform_id 来自**请求体**，属参数校验，维持 400。前端不区分 400/404，无兼容性风险。
- `gui/style_service._rel_or_name()`：`save_style` 原先直接 `fp.relative_to(config.ROOT_DIR)`，当 ASSETS_ROOT 不在项目根内时抛 `ValueError`（这也是该模块此前**无法被隔离测试**、零覆盖的原因之一）。现与 `gui/migrate.py::_rel_path` 统一为同样的回退语义。
- **CI 新增跨平台作业 `python-cross-platform`**：`ubuntu-latest` × Python 3.11/3.12/3.13。项目对外承诺「纯标准库、跨平台」，而原矩阵只有 windows-latest + 3.13 单点——承诺需要持续验证。首次加入时设 `continue-on-error: true`（本机只有 Windows + 3.13，新腿红绿无法本地预判）；**首轮 CI（run 35884685050）三个 ubuntu 腿全部通过**，日志实测确认 `Ran 909 tests`（与 Windows 同规模）且 `ruff check .` 全绿，跨平台兼容性已获证据 → **同日去掉 `continue-on-error` 升级为门禁**。若日后出现偶发失败，应排查根因而不是改回非阻断。
- 新增测试文件 `tests/test_gui_module_smoke.py`（12 用例）：覆盖此前**零测试引用**的 `gui/launch.py`、`gui/platform_service.py`、`gui/style_service.py`。

### Fixed
- **`同步检查` 对「非流水线产出」的书误报采样漂移**：`corpus/raw/Lord_of_the_Mysteries/` 是**空目录**——该书资产由**会话直接产出**（`novel.py 组装` 会明确报错「缺少 `pass1_structure.json`（AI 会话内应先产出该 pass JSON）」），这是受支持的模式。但旧实现仍拿「后来的采样器 manifest（27 章）」去比「会话当时选的章（19 章）」，报出一条**无法成立**的漂移——两者是两次独立决策，本不可比。
  - 修复：为「采样一致性」比对补上**前提守卫**——只有存在 pass 产出的书才做该比对（「资产过期」同理）。非流水线产出的书**显式打印说明**（`[说明] 非流水线产出…→ 跳过…比对`）而非静默跳过，符合铁律一「禁止静默跳过」。
  - 效果：`novel.py 同步检查` 由 `exit=1 / 1 个问题` 变为 `exit=0 / 全部 6 本资产与报告同步`。
  - 新增 6 条测试，含**反向守护**（有 pass 产出的书必须**仍然**报采样漂移，防止把守卫改成永远通过）；反向验证：仅移除该前提守卫时 1 条用例失败，还原后全绿。
- **铁律一实现过严导致 `聚合` 命令完全不可用**：`pass5_aggregate.main()` 原先把 mismatch 判定放在 `--books` 过滤**之前**，只要 `assets/` 下存在任何异题材 voice-card 就 `sys.exit(1)`——即使用户已显式限定书目。本项目常态就是多题材并存（3 个题材），于是 `聚合` **完全不可用**，`novel.py 状态` 里那句「拆 ≥3 本同题材后跑 'novel 聚合'」成了死路。现判定对象修正为**本次聚合的 source_books**，与 `PROJECT_LAW.md` 铁律一原文对齐：`--books` 显式指定的书必须属于目标题材（否则硬失败，防静默漏掉）；未显式指定时范围外的书**打印列出**但不阻断。
- **索引只增不删（永久漂移）**：`run_migrate()` 只有 UPSERT，从不删除已消失文件的对应行。删除报告后 `reports` 表仍留 8 条指向不存在文件的记录，GUI 会列出幽灵报告，而 `--check` 只能报告差异、**无任何修复手段**。现由 `--prune` 收敛。
- **`MODELS.md` 与配置事实不符**：该文档声称「2026-09-01 起不调用任何外部 LLM API」，但 `config/models.json` 已配置 `workbuddy-deepseek`，且 `config/.secrets.bin` 中实测存有该模型的密钥（`secret_store.load_secrets()` 可读到条目），GUI `/api/overview` 返回 `model_configured: true`。现更正为实测状态，原声明保留为历史沿革。
- **`CHANGELOG` 重复的 `[Unreleased]` 段落**：旧段落排在 `[1.1.0]` 之后、与文件顶部重复，且条目已被 1.1.0/1.1.2 摘要覆盖。改为 `## [历史存档] 1.1.0 发布前的详细条目草稿`，**内容原样保留**（比摘要更详细）。
- `pyproject.toml` 的 `exclude` 移除了两个不存在的目录（`.worktrees`、`指纹拆书`）。
- `gui/web/test-results/.last-run.json` 从版本库移除跟踪（`test-results/` 本就在 `.gitignore` 中，但该文件已被跟踪，导致每次跑 e2e 都弄脏工作区）。

### Changed
- **删除 4 本存量不达标报告**（8 个文件）：`chireng_chosen` / `qingning_chosen` / `sangshi_chosen` / `Lord_of_the_Mysteries` 的拆书报告与笔法分析。合计仅 5612–7024 字 < 10000 字门槛。
  - **定性**：其中 3 本（chireng / qingning / sangshi，提交于 **2026-09-01**）早于铁律二硬校验（**2026-09-07**）6 天，属**规则时间差**，不视为违规；`Lord_of_the_Mysteries`（提交于 **2026-09-21**）晚于铁律 14 天，属**门禁旁路**（会话直接写文件，提交信息 `session-agent reports`，未经过 `novel.py 分析` 与 GUI 两条门禁路径）——两者都按「规则上线必须回扫存量」约束处置，**不判违规**。
  - 同步执行 `gui.migrate --prune` 清理 8 条孤儿索引行；`--check` 现为 `一致: YES`（资产 65/65、报告 4/4）。
  - 可从 git 历史恢复：`git checkout <commit> -- reports/<文件名>`。
  - **未做任何内容填充**（不编造分析）。需要时重跑：`python novel.py 分析 <书名> --genre <题材>`。
- 报告数 12 → **4**；测试基线 881 → **909**（新增 28 用例：prune 5 + 聚合作用域 5 + gui 模块冒烟 12 + 同步检查非流水线产出守卫 6）。
- 文档口径同步（AGENTS §7 / PROJECT_SUMMARY / HANDOFF）；`AGENTS.md §8` 的文档索引标注 `PROJECT_LAW.md` 为**规则单一权威来源，优先于本文件**。
- HEAD 由 detached 状态切回 `master` 分支。

### Known Issues（未修，需业务决策）
- 铁律二存量缺口已通过「删除 + 回扫机制」处置，但 4 本书**当前无报告**；重生成属分析产出工作。
- `Lord_of_the_Mysteries` 采样漂移（manifest 27 章 vs 资产 19 章）——既有已知项，`novel.py 同步检查` 可复现。
- `_sample_words()` 在 `assemble.py` 与 `pipeline.py` 的双份实现：`tests/test_sample_words.py` **有意**锁定两份（用例注释写明「同时锁定两者，防止将来只改一处」），属设计取舍，未合并。
- 超大请求体（>10MB）：服务端确实返回 `413`（仅发头部即可读到），但客户端真发超大 body 时会因服务端提前关闭触发 TCP RST 而读不到该响应。低危，未改。
- `_BOOKS` 为进程内内存字典，不随 SQLite 恢复；重启后 `/api/book/{id}` 对 DB 中已存在的书返回 404。前端有 `.catch(() => {})` 兜底且 `/api/status` 重启后 `book_id` 为 null，实际影响很小。
- 52 个函数 > 60 行（`pipeline.py::main()` 358 行等）；lint 债见 `docs/lint-debt.md`。

## [Unreleased] - 2026-09-23（总工全面检查修复）

### Fixed
- **报告「先写盘、后校验」→ 改为「校验通过才落盘」**：`gui/services.py::_generate_reports` 此前先把两份 Markdown 写进 `reports/`，再调铁律二合计校验；校验失败**只抑制 `report_ready` 事件，不删已落盘的文件**。实测后果：6 本书里 **4 本**（chireng/qingning/sangshi/Lord_of_the_Mysteries）合计仅 5612–7024 字，全部低于 10000 字门槛，用项目自身的 `report.check_combined_report_length()` 判定均为 `ok=False`，却一直躺在交付目录里冒充合格品。现改为在内存中生成两份 Markdown → 先判定 → 通过才落盘，不通过**一个字节都不写**。
- **`novel.py 质检` 抛裸 `KeyError` 崩栈**：`book_quality.book_quality_check` 在无法质检时返回 `{"error": ..., "error_type": ...}`（目录不存在 / 空目录 / 同章号命中多个物理文件），该返回**没有** `total_chapters` 等字段，而 CLI 直接索引它 → 用户看到的是 traceback 而不是「目录不存在」。全仓 grep 显示 `error_type` 契约此前**没有任何调用方消费**。现先判 `error`，给可读信息并非零退出；`--json` 模式仍输出机器可读错误对象。
- **测试污染真实运行态（隔离漏洞）**：`gui/system_service.py` 的 `_SETTINGS_FILE = config.STATE_ROOT / "settings.json"` 是**导入期快照**，测试用 `setattr(config, "STATE_ROOT", tmp)` 重定向时它**不会跟随**，导致 `tests/test_system_service.py` 写进**真实** `gui_state/settings.json`（受控实验：写入哨兵值 → 跑测试 → 哨兵被完全抹掉）。这与 AGENTS.md §4 记录的 R1 事故同类，但 config patch 对它完全无效；既有 `test_zz_state_dir_leak_guard` 只覆盖 `gui/state/`，因此漏网。现改为函数内实时求值；同类隐患 `gui/style_service.py::STYLES_DIR` 一并修复。
- **资产库显示陈旧文件体积**：`AssetIndex` 走 SQLite 路径时直接回吐 `assets.size/mtime` 缓存列，而这些列停留在上次索引时刻（2026-09-21）。文件此后被批量重写，实测 65 个资产中 **24 个**体积不符，最严重的「暮冬念春-structure-obs」显示 28593 而实际 74875（差 2.6 倍）。现以实时 `stat()` 为准，仅在文件不可读时退回缓存值（对齐 AGENTS.md §7「所有数字以实测磁盘为准」）。
- **`_generate_reports` 虚报 `report_ids`**：craft-card 缺失时「笔法分析」并未生成，事件里却仍列出 `report:{book_id}-笔法分析`。现只列**实际写出**的报告。

### Added
- **`novel.py 同步检查` 覆盖报告铁律二**：此前只查资产（缺失/过期/采样漂移），报告**没有任何回头复核手段**——而合计校验只发生在生成时，这正是上述 4 本不达标报告能潜伏至今的结构性原因。新增第 4 项检查，实测直接抓出 4 本不达标 + 1 处已知采样漂移。
- **三道回归防线**（均做过反向验证：把 bug 放回去必须失败）：
  - `tests/test_module_config_snapshot.py`：AST 静态扫描「模块级 `X = config.<路径常量>` 导入期快照」，新增即失败（白名单仅 `logging_setup`，附理由）。
  - `tests/test_config_isolation.py::TestRuntimePathFollowsConfig`：**确定性**行为测试——重定向 config 后断言真实 `gui_state/settings.json` 指纹（存在性+sha256+mtime）不变。仅靠内容哈希会因「覆写成同值」漏报。
  - `tests/test_zz_state_dir_leak_guard.py::TestRealGuiStateLeakGuard`：泄漏守卫从 `gui/state/` 扩展到 `gui_state/`。
  - 另：`tests/test_report_write_gate.py`（4 用例，锁「低于门槛不得落盘」）、`tests/test_cli_qc_error_path.py`（3 用例，锁「不得崩栈 + 非零退出」）。
- `scripts/report.py::combined_report_ok(book_chars, craft_chars)`：纯长度判定（不读盘），供写盘前校验与 `check_combined_report_length` 共用，门槛与口径仍是单一来源。
- `tests/test_doc_metrics.py`：守住 `AGENTS.md` §7「当前实测口径」的确定性指标（测试数 / 端点数 / 版本号）与实测一致，并禁止 README 再写死测试基线（改为指向单一权威来源）。起因：文档口径长期漂移，同一时期 README 写 782、AGENTS 写 853、PROJECT_SUMMARY 正文写 782/55 而页脚写 853/65、HANDOFF 写 780/801/55/60。

### Changed
- 测试基线 **853 → 881**（新增 24 用例：报告写盘门禁 4 + CLI 错误路径 3 + 隔离防线 8 + 文档口径 5 + 同步检查报告项 5，另有既有用例调整）
- 文档口径统一为实测值（资产 65 / 报告 12 / 书 8（已拆 6）/ 测试 881 / API 端点 65 / 版本 1.1.2）
- README 不再写死测试基线数字，改指向 `AGENTS.md` §7

### Known Issues（本次未修，需业务决策或后续排期）
- **4 本存量报告仍不达标**（合计 5612–7024 字 < 10000）：代码层门禁已修复，但这 4 份报告的内容补齐属于分析产出工作，**未做任何内容填充**（不编造分析）。请对 chireng_chosen / qingning_chosen / sangshi_chosen / Lord_of_the_Mysteries 重新跑 `novel.py 分析`。
- `Lord_of_the_Mysteries` 采样漂移（manifest 27 章 vs 资产 19 章）——既有已知项，`同步检查` 现可复现。
- 超大请求体（>10MB）契约差异：服务端**确实**返回 `413 Content Too Large`（仅发头部即可读到）；但客户端在真正流式发送超大 body 时，会因服务端提前关闭连接触发 TCP RST 而**读不到**该响应。低危（本地单机、前端不会发这么大的包），未改。
- `_BOOKS` 为进程内内存字典，不随 SQLite 恢复：重启 GUI 后 `/api/book/{id}` 对 DB 中已存在的书返回 404「未导入」。前端对该调用有 `.catch(() => {})` 兜底且 `/api/status` 重启后 `book_id` 为 null，实际影响很小。

## [1.1.2] - 2026-09-21

### Added
- 题材 **realistic-romance**：`KNOWN_GENRES` 白名单 + 种子题材包 +《暮冬念春》四卡/报告入库
- `docs/detection-authority.md` 补全：钩子/开头/对话带/entities 别名与属性写入红线

### Fixed
- **章末钩子计分悬崖**：旧「每命中 +3、收束 +2」使「3 类钩子 + 有效收束」永远 11 分；改为 hits 主导（≥3+收束=12），补充转折/设问词表
- **开头检测词表/窗口**：现实场景（会议室/巷口/车厢等）与动作词补齐；开头窗口先 `lstrip`
- realistic-romance **对话带** 0.08–0.30 → **0.06–0.45**（157 章分位数实测，避免对峙/自白章误伤）
- **`commercial-obs.common_mistakes` 组装时静默丢失**：该字段不来自 `pass4_commercial.json`，而是人工后补进资产文件的，`assemble_obs` 只搬运 pass 字段，因此每次重新组装都会丢掉它（sangshi_chosen 与 暮冬念春 各踩一次，两次都靠人工从备份补回）。现按同一口径兜底：优先取 `opening_analysis.common_mistakes`，否则由本卡 `retention_risk_points` 汇总为**字符串列表**（非新造观察）。回归见 `tests/test_assemble_commercial_common_mistakes.py`（8 用例）
- **语料缺章无法被发现**：`sampler.split_chapters` 只按标题行切分，语料少章它看不出来——《暮冬念春》的语料曾静默缺掉第 154 章（156/157），直到人工逐章比对才发现。`pipeline.py` 现于采样前做**章号连续性校验**，缺号时明确告警并给出替换建议
- **CLI 退出码全线丢失（严重）**：`scripts/` 下 **20 个**脚本的入口都写成 `if __name__ == "__main__": main()`，`main()` 里的 `return 1` 被直接丢弃，进程退出码恒为 0。而 `novel.py` 的 `run_script()` 正是靠返回码判断成败（如 `分析` 命令的 `if rc1 != 0: return rc1`），因此**所有失败分支从未触发过**——实测组装因 schema REJECT 失败时退出码仍为 0。现全部改为 `sys.exit(main())`（无 `import sys` 的用 `raise SystemExit(main())`），并加契约测试 `tests/test_cli_exit_code.py` 锁定
- **组装在校验前就写盘**：原流程是「组装一个写一个」，校验发生在写盘之后——一旦 REJECT，磁盘上的旧资产已被覆盖，只能靠 git / 备份找回。现改为**先组装到内存 → 全部校验 → 通过才落盘**；失败时明确提示「已阻止写盘」，旧资产保持原样
- **`consistency.py` 无退出码语义**：作为风格一致性质检脚本，此前只打印诊断、进程恒返回 0，无法用于 CI 或上层脚本判断。现按阈值给判定（默认 75，与 `chapter_check` / `qc` 的 PASS 线一致，可用 `--threshold` 覆盖），并补 `import sys`
- **新增 `novel.py 同步检查`**：拆书是「pass 产出 → 组装」两段式，改了 pass 忘了组装会让资产**静默过期**，此前无任何检测手段。新命令查三项：资产缺失 / 资产过期 / 采样索引（`manifest.selected_indices`）与资产记录（`meta.sample_chapters`）不一致。实测抓出 `Lord_of_the_Mysteries` 采样漂移（manifest 27 章 vs 资产 19 章）
- **资产加来源指纹**：资产此前只记 `extracted_at`（日期），无法判断「这份资产是从哪一版 pass 组装来的」，同步检查只能用 mtime 做启发式判断——**内容未变但文件被重写就会误报**（实测撞到过一次）。现组装时把来源 pass 的 sha256 前 16 位写入 `meta.source_fingerprint`，判定升级为**内容级确定性**（实测：内容改动后准确报「指纹 x → y，已过期」）；老资产无指纹时自动退回 mtime 并明确标注是启发式
- **`total_sample_words` 名实不符（报告在说谎）**：该字段一律填 `metrics.total_chars`（**全书**字数），但字段名与两个消费方（`report.py` 写「**采样范围**：… 共 N 字」、`report_craft.py` 取 `words`）都要求它是**采样**字数。实测症状：《暮冬念春》报告写着「采样范围：第 1-2 章 等 27 章（共 **328658** 字）」——27 章采样不可能有 32.8 万字，自相矛盾。现 `pipeline` 生成 manifest 时算好 `sample_words`（采样章实际字数），`_sample_words()` 优先取它（修复后报告为 **61189** 字）；老 manifest 无该字段时退回旧行为。⚠ `assemble.py` 与 `pipeline.py` 各有一份该 helper（历史重复实现），已同时修正并由 `tests/test_sample_words.py` 锁定两处
- **新增 `novel.py 回填元数据`**：`meta.source_fingerprint` 是新增字段，此前产出的资产没有它（只能退回 mtime 判据）。新命令一次性补齐 —— **只动该字段，不碰任何分析内容**（实测：16 个资产回填后，除 `source_fingerprint` 外**零差异**），避免重新组装覆盖既有产出。对纯会话产出的资产（`corpus/raw/<书>/` 为空，如 `Lord_of_the_Mysteries`）如实提示「无来源 pass 文件，无法计算指纹」，不伪造
- **注入时角色顺序随机**：`inject.render_voices` 按 pass2 产出顺序渲染 ——《暮冬念春》13 个角色里配角「白汐」被排在 4 个工具人之后，主角也可能排在末尾。注入产物是喂给写作 LLM 的 **system prompt**，靠前内容注意力更高。现按 `_ROLE_ORDER`（主角 0 / 配角 1 / 工具人·龙套 2 / 未知 3）做**稳定排序**，同权重角色保持原有相对顺序

### Changed
- 测试基线 **801 → 853 OK**（common_mistakes 8 + CLI 退出码契约 2 + 资产同步检查 9 + 采样字数语义 5 + 元数据回填 6 + 注入角色排序 6）
- 资产 **65** · 报告 **10** · 已拆书 **6**（campus-redemption×4 + realistic-romance×1 + xuanhuan×1）
- 口径变更后分数与历史分不可横比；详见 `docs/detection-authority.md`

## [1.1.1] - 2026-09-18

### Fixed
- GUI 写作台项目列表：`novel/` 不存在时不再返回空，**恒含只读 `default`**
- GUI 系统页模型列表：正确显示模型 `id`（此前误读 `model_id` 导致空白）
- 文档口径刷新：README / AGENTS / PROJECT_SUMMARY 测试基线对齐 **782 OK**

### Note
- 相对 v1.1.0：连续打分、题材对话带、碎片检测、LLM 备用/降级等能力已在 1.1.0；本版为 GUI 热修 + 文档对齐

## [1.1.0] - 2026-09-18

### Added
- 对话占比满分区题材可配（`dialogue_optimal`）；campus-redemption = 0.07–0.35
- LLM 备用模型路由与显式降级提示
- 章内无标点碎片重复检测（20 字 n-gram）
- `docs/detection-authority.md` 检测口径权威说明
- 安装器/便携包版本 **v1.1.0**

### Changed
- 章节评分：悬崖档位 → 连续打分；「了」字密度按语料 p75/p90 标定
- QC D9 接入章内重复；payoff_types 蒸馏口径归一为占比
- 全量测试基线 **780 OK**；55 资产 **0 WARN / 0 REJECT**

## [历史存档] 1.1.0 发布前的详细条目草稿

> 2026-09-23（总工排查）说明：本段落原标题为 `## [Unreleased]`，位置排在 `[1.1.0]` **之后**，
> 与文件顶部的当前 `[Unreleased]` 重复，且其条目已被 1.1.0 / 1.1.2 的摘要覆盖。
> 为避免与「尚未发布」混淆，改为历史存档标题。**内容原样保留**（它比摘要更详细，
> 是当时修复的完整记录）。

### Added

- **对话占比满分区题材可配（P1-4）**：题材包 `quality_thresholds.dialogue_optimal`（或 `commercial.quality_thresholds.dialogue_optimal`）可覆盖默认 (0.15, 0.40)；campus-redemption 按语料 voice-card 实测（0.0737–0.3016）标定为 **0.07–0.35**，慢热抒情不再被 15% 硬线征税
- `docs/detection-authority.md`：同类检测「以谁为准」权威口径（重复 / 矛盾 / 章节分 / 资产校验）
- `llm_client.describe_llm_degradation`：LLM 额度/网络失败时显式列出「不可用能力 / 仍然可用能力」；pipeline 与 write 在 chat 失败时输出该提示（评估报告 item 10）
- **章内无标点碎片重复漏报**：`check_intra_chapter_repeats` 在句读切分外并入 20 字 n-gram 区间并集覆盖检测；句读侧有发现时仍以句读占比定档（避免二次抬档），句读漏报时才启用碎片占比；`source` 标明主因
- **sangshi commercial-obs 缺顶层 `common_mistakes`**：由本卡 opening_analysis / retention_risk_points 汇总补齐（非新造观察）；55 资产现 **0 WARN / 0 REJECT**
- P2-2 模块冒烟：sampler / clean_verbatim / state_tracker / convert_genre_card / import_genre_prose_cards / pipeline 补导入与纯函数回归
- `tests/test_dialogue_band_and_setting.py`：对话带解析/题材包实装/setting_check 检测行为（世界观禁词、属性矛盾、别名）/LLM 降级文案
- `tests/test_logic_check.py`：24 个用例，为下列三处修复建立回归护栏
- `tests/test_model_config.py`：4 个用例，守住 `model_config` 可导入底线
- 前端新增 `assetKindLabels.test.ts` 与 `HomeDashboard.test.tsx`（共 7 个用例），锁定「同一张标签表同时服务 snake_case 与 camelCase 键、首页饼图不出现原始英文 kind / undefined」
- `tests/test_asset_contract_e2e.py`：18 个用例，把蒸馏卡与题材文风卡索引的契约串成端到端护栏——内存四维蒸馏输出 → 专用校验 → 渲染 → 注入写作 prompt → 服务边界拒绝「蒸馏当单书卡打分」；索引判为独立 kind；部分覆盖题材（某维度无贡献书）仍写出四个文件；章节加载诊断结构（`files` / `ignored` / `duplicates` / `aliases`）。全部使用内存对象或临时目录，不读写真实资产
- 资产体系新增两个独立 kind：`distilled`（跨书题材蒸馏卡）与 `genre-prose-card-index`（题材文风卡寻址索引），各有专用校验契约；GUI 资产库把两者列为独立分类（「蒸馏规则」「题材文风卡索引」），写作台新增「蒸馏规则（可选）」独立下拉
- `tests/test_llm_fallback.py`：LLM 备用模型路由 31 用例（余额/权限类不重试立即切换、全链路失败汇总原因、`test_model` 强制 `allow_fallback=False`）
- `tests/test_fatigue_calibration.py`：「了」字密度按语料分位数（p75/p90）标定的回归护栏
- `tests/test_qc_intra_repeat.py`：QC D9 接入章内重复后的分数与 `cross_chapter`/`intra_chapter` 计数契约
- `tests/test_scoring_continuity.py`：章节评分连续化回归（边界无悬崖、单调性、锚点、了字密度 p75→p90 线性扣分）
- `scripts/model_config.py` 新增 `fallback` 子命令，可为模型写入备用链
- GUI 质检台问题列表支持展开/收起完整清单，并提示截断条数

### Fixed

- **悬崖式档位导致假性掉分与刷分空间（P1-2）**：章节 12 维中字数/对话占比/情绪密度/段落节奏/了字密度/让字密度/直陈式情绪词/旁白情绪标签等改为**分段线性连续打分**（`chapter_check._ramp`），满分区与权重不变；1499→1500、14.9%→15.0%、27.0→27.1 等边界不再整档跳 2–4 分。分数可带 1 位小数；历史章节分会变化
- **「了」字密度阈值与语料脱节**：旧 `>5`/`>8` 使语料 100% 章扣满、维度零区分度；改为 corpus p75=27.0 / p90=31.2，并在 p75→p90 间连续扣分（0→3）
- **QC 与 `novel 质检` 双命令不对称**：章内碎片重复此前只进 `book_quality` 不进 `qc`；现 D9（句子重复）并行消费跨章句与章内重复，`raw` 分列 `cross_chapter`/`intra_chapter`
- **payoff_types 四种单位混加成 103**：蒸馏聚合前按书内归一为占比再跨书中位数；`sources` 保留原始值；dashboard 按实际量纲渲染
- **LLM 无备用路由**：`chat()` 支持 `resolve_fallback_chain` + `allow_fallback`；余额/权限类错误不重试立即切换；`test_model` 显式关闭回退以免误报连通成功
- **蒸馏/index 资产被套用单书卡校验（整份 REJECT）**：`validate.py` 此前没有 distilled 与题材文风卡索引的校验器，`auto_kind` 兜底把它们判成 `voice-card`，于是「缺少 narration / dialogue / emotion_handling / banned」等单书卡硬错误全部报在蒸馏卡与索引上，四个 `*-distilled.json` 与题材文风卡索引均无法通过校验。现新增 `validate_distilled` 与 `validate_genre_prose_card_index`（并注册进 `DISPATCH`），`auto_kind` 支持按文件名线索识别索引、按 `meta.dimension` 或 `rules`/`blindspots`/`stats` 三元组识别蒸馏卡；`validate_asset_data(kind, data)` 提供纯数据校验结果，且不污染全局 `ERRORS`/`WARNS`
- **蒸馏写盘无结构门禁**：`distill.py` 曾直接 `json.dump` 四维结果落盘，残缺 payload 会安静写进 `assets/`。现 `write_distilled_outputs` 在**任何 mkdir/写文件之前**对四个维度全量校验（维度齐备、`meta.dimension` 与输出维度一致、`meta.genre` 白名单、distilled 专用契约），任一硬错误即抛 `ValueError` 且不留半成品；警告不阻断写盘
- **部分覆盖题材的蒸馏被门禁判死（零文件写出）**：写盘门禁要求 `meta.source_books` 至少 1 项，而某维度**无任何贡献书**时蒸馏产物天然是 `source_books: []`（`books_count: 0`、`rules: []`），于是「3 本书只有 voice-card」这类部分覆盖题材从「可蒸馏」变成整体失败、一个文件都不写。现空维度（无来源书 / 书数为 0 / 无规则三者同时成立）豁免该要求，其余情况仍要求非空；同时 GUI 服务层把门禁的 `ValueError` 转成 400 可读错误（原先冒到路由层变成 500，用户只看到「服务器内部错误」）
- **单文件重索引破坏资产 key 口径**：`gui/migrate.py` 的 `sync_asset` 用 `asset_key=stem` 重索引，而迁移与详情定位都用 `kind:stem`（`get_asset_by_key(f"{kind}:{name}")`）——写盘后重索引会另插一行重复资产，或在 path 冲突时把既有行的 `asset_key` 静默改写掉，详情查询随即落空。现统一为 `f"{kind}:{stem}"` 且 path 用 `_rel_path`（与 `run_migrate` 同口径）
- GUI 首页资产类型分布的标签改为复用共享表 `assetKindLabels.ts`（原先首页另有一份本地表，键为 camelCase 且缺 `distilled` / `prose_card_index`，「蒸馏规则」「题材文风卡索引」在饼图里显示成原始英文 kind）
- **章节加载污染与静默覆盖**：`book_quality` / `qc` / `logic_check` 各自递归扫 `*.txt` 并 `texts[num] = read_text()` 直接赋值，导致 `_备份/`、`备份/`、`backup/`、`.git/`、`build/`、`dist/` 下的旧稿被当正文参与质检；同一章号命中多个文件时又按遍历顺序静默覆盖、结果不可复现。现统一委托 `chapter_loader`：排除备份/构建目录（大小写不敏感）、文件名取不到章号记入 `ignored`、同一章号命中多个**不同物理文件**抛 `ChapterLoadError`、同一物理文件被多个章号引用（别名）抛 `ChapterAliasError`，并保留 `novel_dir` 与其 `chapters/` 的双根语义（外部符号链接补扫、同一物理文件只加载一次）
- **章节评分与量化指标漏算四角引号**：对白统计只认 `"` 与 `“”`，以 `「」`、`『』` 成文的章节对白占比被算成 0，连带影响节奏类维度。现 `metrics.dialogue_char_count` 统一四类引号口径，`chapter_check` 与 `metrics` 共用同一分子
- **单书评分/注入接受错配 kind**：资产引用只给文件名，而蒸馏卡历史上落成 `*-voice-card-distilled.json` 这类基础卡后缀，服务层会把它当单书 voice 卡打分、把索引当文风卡注入。现服务层按**内容**自证 kind（`assert_asset_kind`），蒸馏卡当 voice、索引当 prose-card 传入一律以 400 拒绝；GUI 侧两者独立成 kind 与独立分类，不再与 `voice` / `prose_card` 混用
- **`novel 模型` 完全不可用**：`model_config.py` 写的是 `from llm_client import (..., secret_store)`，但 `llm_client.py` 里的 `secret_store` 是**函数内延迟 import**（`load_secrets`/`save_secrets` 各自 `import secret_store`），并非模块级属性，因此该 import 必然抛 `ImportError: cannot import name 'secret_store' from 'llm_client'`——连 `list` 都进不去，模型配置在加载阶段就被拦死。现改为独立 `import secret_store`
- **时间线检测误报（严重）**：旧实现把「昨天/今天/明天」当作时间锚点，并以**全书不回落的最高水位线**逐章比较，导致任何不含前瞻时间词的章节都被判「时间线倒退」。在一本 157 章中文长篇上实测产生 **33 条误报（占 21% 章节）**，直接把「逻辑合理」维度打到 0 分、连带 `novel qc` 判定 FAIL。根因是把**相对指代**当成了**绝对位置**，且不区分对白与比喻。现改为：剥离引号内对白与比喻（「好像昨天才见过」）后，只在**同一场景窗口（1000 字）内**校验「句首第N天」的日序单调性——同一段叙述里出现「第三天…第二天…第三天」才报「编号错误」
- **数值类矛盾检测零覆盖**：正则只认阿拉伯数字，而中文小说的年龄/天数/金额普遍写作汉字数字，实测全书「阿拉伯数字+岁」为 0 处——报「0 问题」并非一致，而是读不到数据。现同时接受汉字数字（含「十八」「一百二十」），并用实体名粗筛（剔除「已经不是」「我那时候」这类非人名片段）控制误报；「十八」与「18」视为同一取值
- **`qc` 空声线卡未走兜底**：声线卡存在但 `dialogue.character_voices` 为空列表时，`check_voices` 恒返回 0——「人物弧线」被直接打到 0 分（而卡片为 `None` 时反而按「无法评估」记 100，两条分支不一致）；「手法运用」的 35 分声线子项同样恒为 0，使该维度凭空被压到 65 分。现统一按「无法评估」跳过（人物弧线），并按可评估子项（情绪 20 + 叙述 15 + 禁忌 20 + 意象 10 = 65）重归一（手法运用）
- **质检问题列表静默截断**：`total_issues=61` 却只展示 50 条且无提示；现上报 `issues_truncated`/`issues_limit`，CLI/GUI 均提示可见条数，质检台可展开全量
- GUI 首页「资产总数」排除报告/语料虚拟类别，消除 69 虚报（实际 55），饼图口径同步对齐
- echarts 5.6.0 → 6.1.0，修复 XSS 漏洞（GHSA-fgmj-fm8m-jvvx）
- `dashboard/smoke-test.js` 曾硬编码另一套 WorkBuddy 实例路径，导致冒烟测试测的是陈旧快照；已改为读本仓库产物
- `.githooks/pre-commit` 索引模式 `100644→100755`，POSIX 克隆上钩子不再被静默跳过；并校验暂存资产 schema

### Changed

- 根目录 QA 调试产物归档至 `docs/archive/qa-artifacts/`
- 根目录 Agent 协作文档（HANDOFF / RULES / PROJECT_LAW / PROJECT_SUMMARY）归档至 `docs/internal/`；无许可第三方参考内容与本地拆书实验产物移出版本库（仅本地留存，已加入 `.gitignore`）
- README 新增 CI / License 徽章；截图区移除「暗色首页」（首页暂不响应暗色模式，修复后补回）
- 全量测试基线：**780 tests OK**（2026-09-18）；55 资产 **0 WARN / 0 REJECT**
- 检测口径权威说明见 `docs/detection-authority.md`

## [1.0.0-baseline] - 2026-09-13

开源基线。此前的完整变更历史见 `git log`，要点：

- 拆书引擎：五遍扫描 + 蒸馏 + 万字报告 + 版权合规检查（纯标准库）
- 资产体系八类：文风卡 / 笔法卡 / 结构观测 / 商业观测 / 题材包 / 蒸馏 / 文风卡库 / 桥段库
- GUI 工作台：首页 / 分析 / 资产库 / 写作台 / 质检台 / 高级 / 系统（65 个 API 端点）
- 质量体系：章节 12 维检查 + 全书质检 + QC 四层十二维
- 测试基线：353 用例全绿，pre-commit 钩子强制
