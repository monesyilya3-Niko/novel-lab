# Lint 债治理清单

> ruff / ESLint 基线建立时（2026-09-13）有意豁免的存量风格债。
> 原则：新代码不允许新增此类问题；存量在对应模块重构时顺手清零。

## ruff（pyproject.toml `[tool.ruff.lint] ignore`）

| 规则 | 数量（基线） | 分布 | 治理时机 |
|---|---|---|---|
| E402 模块级 import 不在顶部 | 19 | gui/ 函数级延迟 import 依赖 sys.path 引导（engine_adapter 既有设计） | **豁免项**：架构意图，不治理；新增文件遵守顶部 import |
| E701/E702 单行多语句 | 22 | scripts/ CLI 短分支 | 重构触及该文件时展开为标准块 |
| E741 歧义单字符变量名 | 7 | scripts/ 量化循环（l/I 混用风险低，中文字面量场景） | 同上 |
| F841 赋值未使用 | 15 | 部分（a, b = ...）元组解包占位 | 同上；真正的死赋值直接删 |

## ESLint（eslint.config.js）

| 规则 | 数量（基线） | 分布 | 治理时机 |
|---|---|---|---|
| react-hooks/set-state-in-effect | 4 | AppContext/ResultPanel 等 effect 内初始加载 | P3 状态管理重构时改为事件驱动/条件加载模式 |

## 已修复（ruff --fix 自动基线清理）

- F401 死 import ×48（含 write.py 的历史遗留 `import re`，见 test_regressions.py 类注释）
- F541 空 f-string ×15
