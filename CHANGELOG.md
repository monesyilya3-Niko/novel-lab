# Changelog

本文件记录面向用户的显著变更。1.0.0 起由 [release-please](https://github.com/googleapis/release-please) 按 Conventional Commits 自动维护。

## [0.1.1](https://github.com/monesyilya3-Niko/novel-lab/compare/v0.1.0...v0.1.1) (2026-09-13)


### Miscellaneous

* 三次验证 release-please（JSON body PATCH 后） ([43ded61](https://github.com/monesyilya3-Niko/novel-lab/commit/43ded6124cbf1d1eeca9f85fe1522553a3333243))
* 二次验证 release-please 权限设置 ([d02e5f5](https://github.com/monesyilya3-Niko/novel-lab/commit/d02e5f50ccdd57ea85bbb676a0306a5b988eaa5b))
* 触发 release-please 验证（v0.1.0 基线后首跑） ([d3a8a8a](https://github.com/monesyilya3-Niko/novel-lab/commit/d3a8a8a843a657501f61168067d3a525df199f5d))

## [Unreleased]

### Fixed

- GUI 首页「资产总数」排除报告/语料虚拟类别，消除 69 虚报（实际 55），饼图口径同步对齐
- echarts 5.6.0 → 6.1.0，修复 XSS 漏洞（GHSA-fgmj-fm8m-jvvx）

### Changed

- 根目录 QA 调试产物归档至 `docs/archive/qa-artifacts/`

## [1.0.0-baseline] - 2026-09-13

开源基线。此前的完整变更历史见 `git log`，要点：

- 拆书引擎：五遍扫描 + 蒸馏 + 万字报告 + 版权合规检查（纯标准库）
- 资产体系八类：文风卡 / 笔法卡 / 结构观测 / 商业观测 / 题材包 / 蒸馏 / 文风卡库 / 桥段库
- GUI 工作台：首页 / 分析 / 资产库 / 写作台 / 质检台 / 高级 / 系统（65 个 API 端点）
- 质量体系：章节 12 维检查 + 全书质检 + QC 四层十二维
- 测试基线：353 用例全绿，pre-commit 钩子强制
