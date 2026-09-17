# Git 钩子（提交前自动测试守卫）

本目录纳入版本控制，保证「提交前必须跑通全量回归测试」这条纪律随仓库一起分发。

## 启用（每个新克隆执行一次）

```sh
git config core.hooksPath .githooks
```

Git 会把钩子查找路径从默认的 `.git/hooks/` 改为仓库内的 `.githooks/`。
之后每次 `git commit` 都会先执行 `.githooks/pre-commit`。

> 说明：`core.hooksPath` 属于本地仓库配置，不会被提交，所以需要每人手动启用一次。

## 行为

1. 运行 `python run_tests.py`（全量约 3 秒）。
   - **测试失败 → 非零退出，提交被阻止**，并打印「测试未通过，提交已阻止」及绕过方式。
2. 测试通过后，校验本次**暂存**的 `assets/*.json`（`python scripts/validate.py <资产>`）。
   - 无暂存资产 → 打印「无变更资产，跳过 schema 校验。」并正常放行（不增加耗时）。
   - 全部 PASS（返回码 0）→ 打印「资产 schema 校验通过（N 个）。」并放行。
   - 出现 WARN（返回码 2）→ 打印警告，**不阻止提交**。
   - 出现 REJECT（返回码 1）→ 打印该资产完整校验输出，**阻止提交**并列出不合规清单。
   - 校验脚本异常返回码 → 同样视为失败并阻止提交。

## 绕过

仅在确知要临时跳过时使用：

```sh
git commit --no-verify
```

## 解释器选择（健壮降级）

按以下顺序解析，任一步命中即用；**都不会因「指定解释器不存在」而崩溃**：

1. 环境变量 `NOVEL_LAB_PYTHON`（若设置但不可执行，打印警告后继续）。
2. 项目约定解释器 `C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe`。
3. 项目内 venv：`.venv/Scripts/python.exe`、`.venv/bin/python`、`venv/...`。
4. 回退到 `PATH` 的 `python3` / `python`（打印警告）。
5. 全部找不到 → 明确报错并提示绕过方式（非静默崩溃）。

示例：

```sh
NOVEL_LAB_PYTHON=/c/Python313/python.exe git commit -m "..."
```

## 停用

```sh
git config --unset core.hooksPath
```
