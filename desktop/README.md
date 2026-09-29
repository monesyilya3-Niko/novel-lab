# novel-lab 桌面版（Electron）

Windows 桌面应用：Electron 原生窗口 + 内嵌 Python 后端（Windows embeddable），
用户机器无需安装 Python、无需浏览器。

## 目录结构

- `main.js` — 主进程：启动后端 → 解析服务 URL → 打开窗口 → 退出时回收后端
- `package.json` — electron + electron-builder 依赖
- `electron-builder.yml` — 打包配置（win NSIS 安装器；须在 Windows 上构建，见下）
- `build/` — 图标（icon.ico/png）、Python embeddable 原始包
- `backend/` — 打包用的后端资源：`gui/`（含 web/dist）、`scripts/`、`python-win/`

## 构建

```sh
cd desktop
npm install
npm run dist        # 产物在 release/；predist 会自动准备后端资源
```

- 正式交付为 NSIS `.exe` 安装器（用户要求，禁用 zip 冒充安装器）。
- 须在 Windows 机器上构建：Linux 下打 NSIS 包需 wine，本机无 wine。
  在 Windows 上 `cd desktop && npm install && npm run dist`，产物在 `release/`。
- `npm run dist` 的 `predist` 钩子会自动做两件事（构建机需装一份
  [python.org](https://www.python.org/downloads/windows/) Python，
  仅构建时用，用户机器不需要）：
  1. `python fetch-python-win.py` — 准备 `build/python-win/`
     （Windows embeddable Python，已存在则跳过；缺失时自动从 python.org
     下载最新 3.12.x embed-amd64 包解压）；
  2. `python sync_backend.py` — 同步 `backend/`（gui/、scripts/、assets/、
     corpus/、reports/、assets-manifest.json、python-win/、前端 dist）。
  任一步失败都会中断构建，不会产出缺少后端/缺少 Python 运行时的坏安装包。

## 运行逻辑

1. 主进程 spawn `resources/backend/python-win/python.exe gui/launch.py --no-browser`
2. 从 stdout 正则解析 `[GUI] 暮冬念春 服务已启动: http://...` 与 `[GUI] 握手令牌: ...`
3. HTTP 轮询 `/api/overview` 确认就绪后打开 BrowserWindow
4. 窗口关闭/退出时 taskkill 回收后端进程树；单实例锁防多开
5. 未签名：Windows SmartScreen 会提示未知发布者，属预期（个人分发无证书）
