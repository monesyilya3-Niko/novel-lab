# 贡献指南

感谢关注 novel-lab。动手之前请先读完本文——这个项目有几条不太常见的硬约束。

## 环境准备

- Windows 10/11 + Git Bash（开发环境按此假设；代码本身跨平台）
- Python 3.10+（开发机实际使用 3.13）
- Node 22 + npm（仅前端开发需要；`gui/web/dist` 预构建产物入库，纯后端开发免装）

```bash
git clone https://github.com/monesyilya3-Niko/novel-lab.git
cd novel-lab
git config core.hooksPath .githooks   # 启用提交前自动测试（强烈建议）
python run_tests.py                    # 确认基线全绿
```

## 三条铁律（违反即视为 bug）

1. **题材隔离**：不同题材的资产/配置严格隔离。聚合题材包时 `source_books` 的 genre 必须全部一致，不一致显式 `sys.exit(1)`，禁止静默跳过。
2. **万字报告硬校验**：拆书报告 + 笔法分析合计字符数 ≥ 10000。判定单一来源在 `scripts/report.py::check_combined_report_length`，禁止另立口径。
3. **纯标准库**：`scripts/` 与 `gui/` 后端只能 import Python 标准库（sqlite3 / json / urllib / http.server / ctypes 等）。前端（Vite + React）不受此约束。CI 会自动扫描违规 import。

## 架构约束

- `gui/engine_adapter.py` 是**唯一** import `scripts/` 的层
- `gui/db.py` 是**唯一** import `sqlite3` 的层
- 路径常量唯一来源：`gui/config.py`；新增路径常量必须同步登记 `tests/_isolation.py::DATA_PATH_CONSTANTS`，否则测试隔离防线会 FAIL
- `gui_state/`（SQLite）是运行时唯一权威数据源；`gui/state/` 只是派生镜像，均不入库

## 测试纪律

- 提交前 pre-commit 钩子会跑全量测试，红测试阻止提交（绕过：`--no-verify`，仅限紧急且需在提交信息中说明）
- 新功能必须带测试；测试涉及路径常量时必须 patch **全部**相关常量并在 tearDown 恢复（历史血泪教训见 `AGENTS.md` §4）
- 数据真实性红线：文档中的数字以实测磁盘为准，不得臆造或沿用旧口径

## 提交规范

[Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：

```
feat|fix|docs|refactor|test|chore: 摘要

正文说明动机（可选）。
```

一次提交只做一件事。版本与 CHANGELOG 由 release-please 自动维护，不要手改 `CHANGELOG.md`。

## 提交什么、绝不提交什么

- 绝不提交：API 密钥（`config/.secrets.json`）、范文语料（`corpus/`，版权材料）、运行时数据（`gui_state/`、`gui/state/`、`novel/`）——`.gitignore` 已覆盖，但请自觉
- 发现密钥疑似泄露：**立即**按 [SECURITY.md](SECURITY.md) 报告，不要先开 issue

## Pull Request

- 描述写清楚：改了什么、为什么、如何验证（贴测试输出）
- 保持提交历史整洁（squash 或按功能分组）
- CI 全绿是合并前提
