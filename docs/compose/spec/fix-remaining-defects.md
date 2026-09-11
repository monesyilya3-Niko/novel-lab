---
feature: fix-remaining-defects
status: designed
updated: 2026-09-11
branch: fix/remaining-defects
commits: 2d6435c..pending
---

# 修复 GUI 后端剩余 12 项缺陷

## [S1] Problem

进度报告（2026-09-11）审计产出 18 项缺陷，已修 6 项。剩余 12 项（M1/M2/M4/M5/M7/M8-remaining/L1–L6）尚未修复，涉及依赖方向违规、错误响应不一致、内存无界增长、数字口径矛盾、输入健壮性不足等。

## [S2] Design

### M1 — `migrate.py` 绕过 `db.py` 直接 import sqlite3

- **现状**：`migrate.py:230` 用 `__import__("sqlite3").connect(str(dst))` 做备份连接。
- **修复**：在 `db.py` 新增 `backup_to(dst: Path) -> None`，内部用已持有的连接调 `conn.backup()`。`migrate.py` 改调 `db.backup_to(dst)`。
- **契约**：`db.py` 仍是唯一 import sqlite3 的层。

### M2 — `router.py` 分页参数错误返回 HTTP 200

- **现状**：`router.py:138` `return err(400, ...)`，同类错误在别处均为 `raise ServiceError`。
- **修复**：改为 `raise ServiceError("offset/limit 必须为整数", 400)`。
- **契约**：所有 4xx 错误统一走 `ServiceError`，由上层转 HTTP 状态码。

### M4 — SSE broker 队列无界

- **现状**：`sse.py:27` `queue.Queue()` 无 maxsize，注释声称「满则丢弃」永不触发。
- **修复**：`queue.Queue(maxsize=256)`。满时 `put_nowait` 抛 `Full`，已有 `except queue.Full: continue` 生效。
- **契约**：慢客户端最多积压 256 条事件，超出丢弃最旧（FIFO 语义下 put_nowait 失败即丢新事件——可接受，因进度事件幂等）。

### M5 — `get_overview` 的 `total_assets` 两分支口径不一致

- **现状**：SQLite 分支 `total_assets = sum(db.count_by_kind().values())`，但 `assets_by_kind = self.count_by_kind()`（可能回退扫描），两者可不同。扫描分支 `total_assets` 含 book/genre_pack/report。
- **修复**：两分支均改为 `total_assets = sum(assets_by_kind.values())`，先算 `assets_by_kind` 再求和。
- **契约**：`total_assets == sum(assets_by_kind.values())` 恒成立。

### M7 — `get_stats` 混用两套「就绪」判据

- **现状**：`totals` 用 `db._db_ready()`，`by_kind` 用 `asset_index.count_by_kind()`（内部有自己的 `_db_ready` 分支）。
- **修复**：`get_stats` 开头取一次 `ready = db._db_ready()`；`totals` 与 `by_kind` 均基于同一 `ready` 值。库未就绪时 `by_kind` 也返回空 dict（与 totals 一致）。
- **契约**：同一响应内数字自洽。

### M8-remaining — `/api/import` 响应回吐整书正文 + 任意路径

- **现状**：`import_book` 返回的 `batches[].text` 含全文；`path` 参数无范围限制。
- **修复**：
  1. 响应体中 `batches` 只保留元信息（chapter_index/batch_index/char_start/char_end/status），剥离 `text`。
  2. `path` 必须 resolve 后位于项目根（`config.ROOT_DIR`）之内，否则 403。
- **契约**：import 响应不含正文；路径穿越被拦截。

### L1 — `load_task` 不回传 `asset_index`

- **现状**：SQLite 路径返回的 dict 无 `asset_index` 键，`get_status` 读 `state.get("asset_index", {})` 恒空。
- **修复**：`load_task` 的 SQLite 返回 dict 显式加 `"asset_index": {}`。JSON 降级路径已从 load_state 继承该字段。不伪造数据。
- **契约**：`get_status` 响应中 `asset_index` 字段始终存在（可能为空 dict）。

### L2 — `retry_failed` 在分析线程存活时无效

- **现状**：线程存活时 `resume` 会抛 409，但 `retry_failed` 已先把 failed→pending 并 save，返回 `retried: N` 却不重跑。
- **修复**：`retry_failed` 先检查 `_runtime` 中线程是否存活。存活时：只重置状态为 pending 并返回 `{"retried": N, "note": "线程运行中，将在当前循环内重扫"}`，不调 resume。不存活时：走现有 resume 路径。
- **契约**：返回值语义准确，不假装触发了新线程。

### L3 — `start_analysis`/`resume` 不持久化 `running`（已由 H3 修复）

- **现状核实**：H3 修复已在 `start_analysis` 中加入 `state["status"] = "running"` + `save_state`；`resume` 委托 `start_analysis`。
- **处理**：标记为 PRE-FIXED，不重复修改。验证测试确认 `/api/status` 在 start 后返回 running。

### L4 — `read_body` 对非法 Content-Length 抛 500

- **现状**：`router.py:234` `int(handler.headers.get("Content-Length", "0") or "0")`，非数字抛 ValueError → 500。
- **修复**：try/except ValueError → `raise ServiceError("Content-Length 非法", 400)`。另加 body 上限 10 MB，超限返回 413。
- **契约**：非法 Content-Length 返回 400；超大 body 返回 413。

### L5 — `resolve_port` 不校验端口范围

- **现状**：`config.py:58` 直接 `int(preferred)` 或读环境变量，无范围检查。
- **修复**：校验结果在 1–65535，否则 `raise ValueError`。
- **契约**：非法端口在启动前即报错，不进入绑定循环。

### L6 — `_CORPUS_EXCLUDE_DIRS` 死代码

- **现状**：`asset_index.py:52` 定义后从未使用。
- **修复**：删除该常量。
- **契约**：无未使用常量。

## [S3] Out of Scope

- CLI / scripts/ 静态审计（P0 另一项，不在本次范围）
- W10–W18 阶段三功能实现
- 前端代码修改
- 文档纠偏（PROJECT_SUMMARY/HANDOFF 重写）

## Tasks

- [ ] T1: 修 M1 — db.backup_to 封装 + migrate 调用 — acceptance: `__import__` 不再出现在 migrate.py；测试通过 (covers: S2-M1)
- [ ] T2: 修 M2 — router 分页错误改 raise ServiceError — acceptance: 非整数 offset 返回 HTTP 400 (covers: S2-M2)
- [ ] T3: 修 M4 — SSE 队列加 maxsize=256 — acceptance: Queue 有界；Full 时不阻塞 (covers: S2-M4)
- [ ] T4: 修 M5 — total_assets = sum(assets_by_kind) — acceptance: 两分支口径一致 (covers: S2-M5)
- [ ] T5: 修 M7 — get_stats 统一就绪判据 — acceptance: 空库时 totals 与 by_kind 均为 0 (covers: S2-M7)
- [ ] T6: 修 M8 — import 响应剥离 text + 路径限制 — acceptance: 响应无正文；项目外路径 403 (covers: S2-M8)
- [ ] T7: 修 L1 — load_task 补 asset_index 键 — acceptance: get_status 响应含 asset_index 字段 (covers: S2-L1)
- [ ] T8: 修 L2 — retry_failed 线程存活时不假调 resume — acceptance: 存活时返回 note；不存活时正常 resume (covers: S2-L2)
- [ ] T9: 验证 L3 已修 — acceptance: start 后 /api/status 返回 running (covers: S2-L3)
- [ ] T10: 修 L4 — read_body 健壮性 — acceptance: 非法 Content-Length→400；超大 body→413 (covers: S2-L4)
- [ ] T11: 修 L5 — resolve_port 范围校验 — acceptance: 端口 0 或 70000 抛 ValueError (covers: S2-L5)
- [ ] T12: 修 L6 — 删除 _CORPUS_EXCLUDE_DIRS — acceptance: 常量不存在且测试通过 (covers: S2-L6)
- [ ] T13: 全量测试 + 提交 — acceptance: 272+ 新增用例全绿；工作区干净 (covers: 全部)
