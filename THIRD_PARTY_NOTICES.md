# 第三方资产与许可证声明

本文件记录本项目引入的第三方内容、其许可证、版权声明与修改情况，
满足 MIT「副本或实质部分须同时包含版权声明与许可声明」的要求。

**同步要求**：下方资产清单必须与 `assets/genre-prose-card-*.json` 逐张对应，
由 `tests/test_third_party_notices.py` 守卫；新增/删除卡片而未更新本文件，测试即失败。

## 1. 摘要

| 上游项目 | 许可证 | 版权持有人 | 衍生资产 | 许可证副本 |
| --- | --- | --- | --- | --- |
| `zenstory-ai/oh-story-claudecode` | MIT | oh-story-claudecode (2025-2026) | genre-prose-card × 32 | `LICENSES/oh-story-claudecode/LICENSE` |

## 2. oh-story-claudecode

- **上游仓库**：https://github.com/zenstory-ai/oh-story-claudecode（同名仓库 `worldwonderer/oh-story-claudecode` 内容一致）
- **许可证**：MIT License
- **版权声明**：Copyright (c) 2025-2026 oh-story-claudecode
- **许可证副本**：`LICENSES/oh-story-claudecode/LICENSE`（逐字保留上游文本，未作修改）
- **核实方式与时间**：2026-09-27 分别抓取两个 owner 的 `raw .../main/LICENSE`，返回同一 1081 字节文件，内容与本仓库副本一致；非依据资产内自报字段推定

### 2.1 衍生资产清单

共 32 张题材文风卡，全部满足 `provenance.source/license/copyright` 齐备（`validate.py` 硬校验）。

| 资产文件 | meta.id | 题材 | 转换时间 |
| --- | --- | --- | --- |
| `assets/genre-prose-card-genre-dushi-gaowu.json` | `genre-dushi-gaowu` | 都市高武 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-dushi-naodong.json` | `genre-dushi-naodong` | 都市脑洞 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-dushi-richang.json` | `genre-dushi-richang` | 都市日常 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-dushi-xiuzhen.json` | `genre-dushi-xiuzhen` | 都市修真 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-dushi-zhongtian.json` | `genre-dushi-zhongtian` | 都市种田 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-gongdou.json` | `genre-gongdou` | 宫斗宅斗 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-gufeng-shiqing.json` | `genre-gufeng-shiqing` | 古风世情 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-guyan-naodong.json` | `genre-guyan-naodong` | 古言脑洞 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-haomen-zongcai.json` | `genre-haomen-zongcai` | 豪门总裁 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-kangzhan-diezhan.json` | `genre-kangzhan-diezhan` | 抗战谍战 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-kehuan-moshi.json` | `genre-kehuan-moshi` | 科幻末世 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-kuaichuan.json` | `genre-kuaichuan` | 快穿 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-lishi-naodong.json` | `genre-lishi-naodong` | 历史脑洞 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-lishi.json` | `genre-lishi` | 历史古代 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-minguo-yanqing.json` | `genre-minguo-yanqing` | 民国言情 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-niandai.json` | `genre-niandai` | 年代 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-nvpin-xuanyi.json` | `genre-nvpin-xuanyi` | 女频悬疑 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-nvpin-zhongtian.json` | `genre-nvpin-zhongtian` | 女频种田 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-qingchun-tianchong.json` | `genre-qingchun-tianchong` | 青春甜宠 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-shuangnan.json` | `genre-shuangnan` | 双男主 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-xianxia.json` | `genre-xianxia` | 东方仙侠 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-xianyan-naodong.json` | `genre-xianyan-naodong` | 现言脑洞 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-xifang-qihuan.json` | `genre-xifang-qihuan` | 西方奇幻 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-xingguang.json` | `genre-xingguang` | 星光璀璨 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-xuanhuan-naodong.json` | `genre-xuanhuan-naodong` | 玄幻脑洞 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-xuanhuan-yanqing.json` | `genre-xuanhuan-yanqing` | 玄幻言情 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-xuanhuan.json` | `genre-xuanhuan` | 传统玄幻 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-xuanyi-lingyi.json` | `genre-xuanyi-lingyi` | 悬疑灵异 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-xuanyi-naodong.json` | `genre-xuanyi-naodong` | 悬疑脑洞 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-youxi-tiyu.json` | `genre-youxi-tiyu` | 游戏体育 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-zhanshen-zhuixu.json` | `genre-zhanshen-zhuixu` | 战神赘婿 | 2026-09-09T06:21:51+00:00 |
| `assets/genre-prose-card-genre-zhichang-hunlian.json` | `genre-zhichang-hunlian` | 职场婚恋 | 2026-09-09T06:21:51+00:00 |

## 3. 修改说明

上游内容进入本仓库时经过结构与语义转换，非原样复制：

- 包装为本仓库资产契约：补齐 `meta.kind = "genre-prose-card"`、`meta.confidence`、`meta.upgrade_status`、`meta.source_books`
- 新增 `meta.provenance`（source / license / verified / evidence / converted_at）
- 2026-09-27 补写 `meta.provenance.copyright`（本次 MIT 归因整改）
- 题材文风卡在本仓库定位为**软约束种子**：不套用 genre-pack 的量化硬校验，仅要求 `meta.kind`、`meta.id` 命名规范、`language_rules`、`prose.sections` 存在

## 4. `provenance.verified` 为何仍为 false

`verified` 的语义是**逐条内容级事实核验**（该题材统计是否成立、指导是否准确），不是「许可证是否核验」。许可证已于 2026-09-27 完成核验（见第 2 节），但内容级核验尚未逐张完成，因此 `verified` 保持 false。
`validate.py` 对该字段有约束：genre-prose-card 的 `verified` 若为 true 会触发警告，防止把「许可证已核实」误读为「内容已核实」而放松质量门禁。

## 5. 未纳入第三方声明的内容及理由

- **拆书产物**（`*-craft-card.json` / `voice-card` / `structure-obs` / `commercial-obs` / `distilled`）：由用户自有本地书样本统计派生，上游归属见各资产自身 `meta`
- **`prose.sections` 各节**：为原创性写作指导文本（实测每节 37–84 字的提示性描述），不含第三方小说的逐字原文片段，因此不触发小说版权面
- **`provenance.evidence`**：仅为样本量与统计特征描述（可用本数、抽样数、段落中位字数、对话占比），属事实性数据，不构成受版权保护的表达

## 6. 责任声明

本文件为合规归因记录，不构成法律意见。若上游许可证发生变更，或计划对外分发并需逐文件标注版权，应重新评估归因方式。
