# novel-lab 项目规约（硬性要求，任何违反即视为 bug）

## 铁律一：写作技巧严格按题材分类隔离
- 每个题材包（genre-pack）独立，技法不得跨题材混用
- 【执行机制】聚合题材包时，source_books 的 genre 必须全部一致；
  不一致 → pass5_aggregate.py 显式断言 + sys.exit(1)，禁止静默跳过
- 【执行机制】craft-card.meta.genre 必须 ∈ KNOWN_GENRES 白名单（validate.py 校验）
- 【执行机制】桥段库每个 trope 必须标注 genre_scope（universal / 题材专属 id）

## 铁律二：每本书拆解必须产出 ≥1 万字分析报告
- 拆书报告 + 笔法分析 合计字符数 ≥ 10000（硬门槛，字符数口径）
- 【执行机制】report.py / report_craft.py 生成后自动校验
  MIN_REPORT_CHARS=10000，不足 → sys.exit(1) 阻断交付，不产出半成品
- 【执行机制】深度内容由 Pass5 LLM 生成 + deep_analyze.py 校验，缺段即标记

## 铁律三：纯标准库、零第三方依赖
- import 白名单仅限 Python 标准库
- 新增模块（deep_analyze.py）同样遵守
