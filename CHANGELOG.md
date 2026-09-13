# Changelog

本文件记录面向用户的显著变更。版本发布由 `.github/workflows/release.yml` 驱动：推送 `v*` tag 即从 Conventional Commits 自动生成发布说明。

## [Unreleased]

### Fixed

- GUI 首页「资产总数」排除报告/语料虚拟类别，消除 69 虚报（实际 55），饼图口径同步对齐
- echarts 5.6.0 → 6.1.0，修复 XSS 漏洞（GHSA-fgmj-fm8m-jvvx）

### Changed

- 根目录 QA 调试产物归档至 `docs/archive/qa-artifacts/`
- 根目录 Agent 协作文档（HANDOFF / RULES / PROJECT_LAW / PROJECT_SUMMARY）归档至 `docs/internal/`；无许可第三方参考内容与本地拆书实验产物移出版本库（仅本地留存，已加入 `.gitignore`）
- README 新增 CI / License 徽章；截图区移除「暗色首页」（首页暂不响应暗色模式，修复后补回）

## [1.0.0-baseline] - 2026-09-13

开源基线。此前的完整变更历史见 `git log`，要点：

- 拆书引擎：五遍扫描 + 蒸馏 + 万字报告 + 版权合规检查（纯标准库）
- 资产体系八类：文风卡 / 笔法卡 / 结构观测 / 商业观测 / 题材包 / 蒸馏 / 文风卡库 / 桥段库
- GUI 工作台：首页 / 分析 / 资产库 / 写作台 / 质检台 / 高级 / 系统（65 个 API 端点）
- 质量体系：章节 12 维检查 + 全书质检 + QC 四层十二维
- 测试基线：353 用例全绿，pre-commit 钩子强制
