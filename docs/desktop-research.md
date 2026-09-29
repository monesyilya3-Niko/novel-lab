# novel-lab Windows 桌面交付调研报告

- 日期：2026-09-29
- 性质：**纯调研，不写代码、不做修改**。所有"未验证"标注均为诚实标注：没有在真实 Windows 环境实测过的内容不写成定论。
- 目标形态：用户在 Windows 10 Professional 上双击图标启动的桌面软件，含完整管理员系统（管理员系统已在 Web UI 内，无需单独形态）。

---

## 0. 项目基线事实（本机实测，非推测）

| 项 | 实测值 |
|---|---|
| 后端 | `gui/` 纯 Python，**只用标准库**（仓库规约），源码共约 425 KB |
| 后端入口 | `python gui/launch.py` / `python -m gui.launch`；`gui/launch.py::main()`、`gui/server.py::main()` 均存在 |
| 端口策略 | 默认 8000，占用自动 +1（上限 8099）；环境变量 `NOVEL_LAB_GUI_PORT` 可覆盖（`gui/config.py:165`） |
| 前端 | `gui/web/dist/` 已构建，**1.9 MB** |
| 用户数据目录 | 已实现跨平台：`%LOCALAPPDATA%\暮冬念春`（Win）/ `~/Library/Application Support/暮冬念春`（macOS）（`gui/config.py:28-41`） |
| 内置资产同步 | `gui/builtin_sync.py` 启动时把随包资产补齐到用户目录（缺失复制、冲突只警告不覆盖）——已为"只读安装包 + 可写用户目录"模型做好准备 |
| 就绪探针 | **缺失**：`gui/router.py` 中无 `/health` / `/ping` 端点（grep 确认无）。Electron 主进程需要新增一个（见 §4） |
| 本机 Python | 3.12.3（Linux）。Windows 打包需用 Windows 版 Python 3.12（见 §1） |

---

## 1. Python 后端随包方案：PyInstaller vs 内嵌 python-embed

这是整个方案最关键的分叉点。两条路线都必须产出 **Windows 原生可执行物**，因为：

> **PyInstaller 不是交叉编译器**：在 Linux 上跑 PyInstaller 只能产出 Linux 可执行文件，Windows 的 `.exe` 必须在 Windows 上构建。
> 来源：PyInstaller 官方文档（经多篇实战文章复述）——
> - https://github.com/brentvollebregt/nitrate.net（nitratine.net 文章页，引用 PyInstaller v5.7.0 文档原文）
> - https://github.com/tfd-42/proc_map_analyzer（实战总结："PyInstaller does not cross-compile"）
> - https://github.com/zhaoweny/clear-record/blob/HEAD/packaging/pyinstaller/README.md（"Build on each target OS"）

### 路线 A：PyInstaller 打包成 exe（`--onedir` 模式）

做法：在 Windows 构建机（GitHub Actions `windows-latest`）上 `pip install pyinstaller`，对 `gui/launch.py` 跑 `--onedir --noconfirm`，产出 `novel-lab-backend/novel-lab-backend.exe + _internal/` 目录，随 Electron 的 `extraResources` 打进安装包。主进程 spawn 这个 exe。

- **体积**：PyInstaller 会把整个 CPython 运行时打进去。novel-lab 后端只用标准库、**无第三方二进制依赖**，这是巨大优势：不需要 `--collect-all` 处理 numpy/scipy 之类，无 hidden-import 地雷（`gui/` 的 import 均为显式标准库导入）。纯标准库应用的 PyInstaller 体积量级一般在 **15–40 MB**（未验证：需真实构建测量；hello-world 级约 tens of MB，见 https://github.com/simonschubert/linuxcommandlibrary/blob/HEAD/assets/commands/pyinstaller.md）。
- **启动速度**：`--onedir` 模式无解包步骤，启动快；**不要用 `--onefile`**——每次启动都要自解压到临时目录，慢，且杀毒软件误报重灾区（同上来源）。
- **杀毒软件误报**：PyInstaller（尤其 onefile）的自解压 stub 行为像恶意软件加壳器，Windows Defender/国产杀毒误报常见；onedir 相对好一些。代码签名（ Authenticode 证书）是正规解法（同上来源）。
- **优点**：单目录、用户侧零 Python 概念；构建脚本成熟，文档多。
- **缺点**：必须在 Windows 上构建（CI 解决）；每次后端改动都要重新跑 PyInstaller（约 1–3 分钟，可接受）。

### 路线 B：python-embed（python.org 官方 embeddable zip）+ 源码

做法：从 python.org 下载 Windows embeddable 包（zip，**约 7–10 MB 下载 / 约 12 MB 解压**，来源：https://github.com/zooba/zooba.github.io/blob/HEAD/_posts/2016-11-06-why-so-many-python-installers.md ；https://github.com/philr7919/yt-dlp-gui），解压到 Electron `extraResources/python-embed/`，把 `gui/` 源码一并打进包。主进程 spawn `python-embed/python.exe`，用 `-c "import sys; sys.path.insert(0, APP_DIR); from gui import launch; ..."` 或 `runpy` 启动（embed 包的 `._pth` 文件强制隔离模式，会忽略 `PYTHONPATH` 环境变量，见 https://michlstechblog.info/blog/python-install-python-with-pip-on-windows-by-the-embeddable-zip-file/ ——因此不要依赖环境变量传路径，用 `-c` 内改 `sys.path` 或改 `._pth` 文件本身；`._pth` 是否支持相对路径**未验证**，需实测）。

- **体积**：约 12 MB（embed）+ 0.5 MB（源码）+ 1.9 MB（前端）= **约 15 MB 增量**，是三条路线里最小的。
- **启动速度**：等同于原生 Python 启动（约 100–200 ms 量级，未验证）+ 后端 `serve_forever` 初始化。
- **杀毒软件误报**：`python.exe` 是 python.org 官方签名二进制，误报概率远低于 PyInstaller 产物（此为合理推断，非实测，标注为**未验证**）。
- **优点**：
  - **可在 Linux 上完成组装**：embed zip 是普通下载文件，Linux 构建机也能下载解压；配合 electron-builder 的 `zip` 目标（见 §2），**理论上可以全程在 Linux 上产出 Windows 免安装包**，不需要 Wine、不需要 Windows 构建机（未验证：需真实跑通一次）。
  - 后端是纯标准库：embed 包**不需要装 pip、不需要装任何第三方包**（`get-pip.py` 步骤可省），这是 novel-lab 独有的红利——换作有 numpy/fastapi 依赖的项目这条路线会复杂一个数量级。
  - 后端热修复容易：源码是明文 .py，紧急修复可直接替换文件（双刃剑：也被用户/杀毒更容易误删）。
- **缺点**：
  - 源码明文分发（PyInstaller 至少是 .pyc 打包；novel-lab 是自用/小众工具，源码可见不是实质风险，但要知晓）。
  - `._pth` 隔离语义是小坑，需一次真实验证。
  - embed 包的大版本号要与开发测试的 Python 对齐（建议锁定 3.12.x，与仓库一致）。

### 路线对比

| | A. PyInstaller onedir | B. python-embed + 源码 |
|---|---|---|
| 增量体积 | 约 15–40 MB（未验证） | 约 15 MB |
| 启动速度 | 快（无解包） | 快（原生 Python） |
| 杀毒误报风险 | 中（onedir 好于 onefile） | 低（官方 python.exe，未验证） |
| 构建机要求 | **必须 Windows**（CI） | Linux 可组装（zip 目标时） |
| 后端改动后重建成本 | 重新跑 PyInstaller（分钟级） | 拷贝 .py（秒级） |
| 源码是否明文 | 否（.pyc） | 是 |

**推荐：路线 B（python-embed + 源码）为一期首选**，理由：novel-lab 纯标准库让这条路线异常干净（无 pip/无依赖地狱）；体积最小；Linux 可组装降低构建门槛；后端迭代时重建成本最低。PyInstaller 作为备选（若实测中 embed 的 `._pth`/杀毒/启动出现意外）。

---

## 2. electron-builder 在 Linux 上构建 Windows 目标的可行性

官方文档（https://github.com/kdroidfilter/electron-builder/blob/HEAD/website/docs/features/multi-platform-build.md）：

> ### Build for Windows on Linux
> - Install Wine 2.0+
> - Install Mono 4.2+ if you want to use Squirrel.Windows (**NSIS, default target, doesn't require mono**).

逐目标结论：

| 目标 | Linux 构建是否需要 Wine | 说明 |
|---|---|---|
| `nsis`（安装器） | **需要** | NSIS 本体不需要 Mono，但 electron-builder 在构建过程中会**用 Wine 运行 NSIS 安装器 stub**（即使只构建 nsis 也会触发）；且 32 位 stub 需要 `wine32` 先于 `wineboot --init` 安装，否则 exit 123。来源：https://github.com/unn-devotek/fcm-fallout-chat-mod/blob/HEAD/docs/testing/windows-nsis-ci-fixes.md（2026-09 实战记录） |
| `portable`（免安装单 exe） | **需要** | portable 目标内部是从 NSIS 安装器里提取文件，同样走 Wine（同上来源） |
| `zip`（免安装压缩包） | **不需要** | 纯归档操作。多篇实战确认 zip 可在 Linux/Docker 无 Wine 产出，见 https://github.com/blackbelttechnology/pi-agent-dashboard/blob/HEAD/docs/electron-build-methods.md（"Local + Docker emit ZIP only. NSIS Setup.exe CI-only"） |

**结论**：
- 要 NSIS 安装器（用户要的"双击安装、开始菜单/桌面图标"体验）：要么在 Linux 装 Wine（2.0+，注意 wine32 顺序坑），要么用 Docker `electronuserland/builder:wine` 镜像，要么直接上 **GitHub Actions `windows-latest`** 原生构建。
- **最省事且最可靠的是 GitHub Actions `windows-latest`**：仓库是 public（`monesyilya3-Niko/novel-lab`），Actions 免费；Windows 原生构建同时解决 §1 中 PyInstaller 的"必须在 Windows 构建"问题（若选路线 A）。多篇实战一致推荐 CI 矩阵按 OS 分 runner：https://github.com/unn-devotek/fcm-fallout-chat-mod/blob/HEAD/cross-platform-overlay/BUILD.md
- 若选路线 B + `zip` 目标，可先在 Linux 本机快速产出免安装包用于冒烟测试，零 Wine 依赖（未验证，需真实跑通）。

代码签名（ Authenticode ）：一期可不做。未签名包 Windows SmartScreen 会弹"未知发布者"警告（"更多信息 → 仍要运行"可过）。签名证书约 $200–500/年（OV），或 SignPath 免费开源计划（有项目在用，见下 §5）。**未验证**：未实际购买/申请过，不写流程细节。

---

## 3. 体积量级估计（诚实版）

| 组件 | 量级 | 依据 |
|---|---|---|
| Electron 运行时（win32-x64） | 下载约 115 MB；安装后约 100–300 MB | 115 MB 为 electron v33.2.1 真实构建日志数字（https://github.com/basemax/electron-censor-app/blob/HEAD/README.md）；100–300 MB 为"typical-range estimates"（https://github.com/wixely/cupriface/blob/HEAD/comparisons/electron.md，非单次实测） |
| 后端（路线 B） | 约 15 MB | embed 解压约 12 MB（§1 来源）+ 源码 0.5 MB（实测） |
| 后端（路线 A） | 约 15–40 MB | **未验证**，需真实 PyInstaller 构建测量 |
| 前端 dist | 1.9 MB | **实测** |
| NSIS 安装包（压缩后下载体积） | 约 60–100 MB | 估算：Electron 主体压缩率高；**未验证**，需真实构建测量 |
| 安装后磁盘占用 | 约 150–350 MB | 估算（Electron 解压后 + 后端）；**未验证** |

Electron 是体积的绝对大头（Chromium 打包），这是选 Electron 必须接受的代价。备选 Tauri 体积可小一个数量级，但**需要把前端/后端全部重写为 Rust 架构**，与"封装现有资产"的目标相悖，一期不考虑。

---

## 4. Electron 主进程需要做的事（设计清单）

以下基于项目实测事实（§0）列出，无需猜测：

1. **启动后端子进程**
   - 路线 B：`spawn(pythonEmbedExe, ['-c', <bootstrap>])`；`bootstrap` 内把 `gui/` 所在目录插入 `sys.path` 后调 `gui.launch.main(['--port', port])`。**不要**依赖 `PYTHONPATH`（embed 隔离模式忽略它）。
   - 路线 A：`spawn(backendExe, ['--port', port])`。
   - 端口：主进程用 Node `net` 先占一个空闲端口（或直接从 8000 试到 8099，与后端 `_bind_port` 同规则），通过 `--port` / `NOVEL_LAB_GUI_PORT` 传给后端。**不要**让后端自己选了再解析 stdout——多一处脆弱解析。
   - `windowsHide: true`，避免弹出 Python 控制台黑窗口。
2. **等待后端就绪再开窗口**
   - 后端现状**无 `/health` 端点**（已验证缺失）。需新增 `GET /api/health` 返回 `{"service": "novel-lab", "version": ...}`（0.5 天工作量，含测试）。
   - 主进程轮询该端点（带 service 字段校验，防止误认本机其他占用端口的服务——此模式见 https://github.com/krishivseth/orchard/blob/HEAD/ELECTRON_GUIDE.md 的 readiness probe 设计）；就绪前显示 splash/loading 窗口，超时（约 15 s）则报错退出。
3. **退出时杀掉后端**
   - `app.on('before-quit')` / `window-all-closed` 时 kill 子进程；用 `tree-kill` 之类库杀进程树，防止残留（模式见 https://github.com/aryansingh0777raghav/arch 的 README："Closing the Electron window automatically kills the Python process tree using tree-kill"）。
4. **单实例锁**
   - `app.requestSingleInstanceLock()`；第二个实例启动时聚焦已有窗口（Electron 标准 API，无坑）。
5. **用户数据目录与内置资产分离**
   - 已天然分离：`gui/config.py` 的用户数据目录是 `%LOCALAPPDATA%\暮冬念春`，与安装目录无关；`builtin_sync` 启动时把随包资产复制过去。**卸载时不要删用户数据**（NSIS `deleteAppDataOnUninstall: false`，参考 https://github.com/engasnm111/lnwjud/blob/HEAD/docs/development/PACKAGING_WINDOWS.md 的打包契约）。
   - 注意：打包后"随包资产"的读取路径是 `process.resourcesPath`，`builtin_sync` 的"随包目录"解析逻辑需适配 Electron 路径（`app.isPackaged` 分支），这是实现时要改的一处（未验证具体代码量，估计小）。
   - 升级场景：NSIS 覆盖安装只替换程序文件，用户数据目录不动；`builtin_sync` 的"冲突只警告不覆盖"策略天然保护用户修改过的资产（但官方旧版本升级问题仍在，见主线 TODO）。
6. **前端加载**
   - `win.loadFile(resourcesPath/frontend/dist/index.html)` 或 `loadURL('http://127.0.0.1:PORT/')`。二选一：若后端本身 serve 前端静态文件（现状 `launch.py` 就是这么干的——后端 + 浏览器 UI），则直接 `loadURL` 后端地址，**前端 dist 甚至不需要单独进 Electron 包**（后端已会 serve）。需确认后端生产模式是否 serve `gui/web/dist/`（**未验证**，实现前确认；若不 serve，则把 dist 打进 `extraResources` 并由主进程起一个静态文件服务，或让后端加静态路由——以后端加路由为优，改动最小）。
7. **安全基线**
   - `contextIsolation: true`、`nodeIntegration: false`、preload 脚本只暴露最小 IPC（如需）。前端现状是纯 Web 应用，无 Electron API 依赖，改动面小。

---

## 5. 自动升级：electron-updater 是否一期就做

实测依据（均为真实项目的公开文档/提交）：

- **Windows 上 unsigned 也可工作**：多个项目在未签名状态下跑通 electron-updater（NSIS 目标），更新包用 `latest.yml` 里的 sha512 校验；SmartScreen 只在首次安装时警告。
  - https://github.com/kaiscommitted/musicflow-/blob/HEAD/musicflow-electron/README.md（"Works unsigned — NSIS auto-update doesn't require a code-signing cert"）
  - https://github.com/hlt83595685-cmyk/veridian/commit/bae200c8c00c458a1c87dc3a9b49efd4e5c85635（"No self-hosted server and no code-signing cert required. Windows unsigned updates work"）
  - https://github.com/malpractis/materia-core-releases（公开 release feed 实物：Setup exe + `.exe.blockmap` + `latest.yml`）
- **差分更新**：NSIS blockmap 支持只下载变化块；有人为避坑主动关掉差分用全量（https://github.com/kaiscommitted/musicflow-/blob/HEAD/musicflow-electron/README.md）。
- **zip 目标不能自动更新**：`quitAndInstall()` 对 zip 无能为力，必须是 `nsis` 目标（https://github.com/amirlehmam/wmux/pull/97，issue #96 的真实教训）。
- **更新源免费**：`publish: { provider: 'github' }`，feed 就是 GitHub Releases 上的静态文件，零服务器成本（https://github.com/zenineasa/konjugate/blob/HEAD/docs/proposals/autoUpdates.md）。
- **一个反例**：若把 `win.publisherName` 钉到签名机构（如 SignPath），electron-updater 会去做 Authenticode 校验，未签名包反而**更新失败**——所以一期 unsigned 就不要配 publisherName（https://github.com/amirlehmam/wmux/pull/97）。

**建议**：一期**接线但不强依赖**。electron-updater 的接线成本很低（主进程约 30 行：`autoUpdater.checkForUpdates()` + 用户确认对话框 + `quitAndInstall`；`package.json` 加 `publish.provider=github`），且与"手动覆盖安装"不冲突：
- 一期交付：NSIS 安装器手动下载覆盖安装（`deleteAppDataOnUninstall: false` 保数据）。
- electron-updater 作为"有新版本提醒 → 用户点确认 → 后台下载 → 重启安装"的增强，unsigned 可用；若实测中 SmartScreen/权限出现幺蛾子，可随时降级为纯手动（删几行代码的事）。
- macOS 自动更新需要签名暂不考虑（当前只做 Windows）。

---

## 6. 推荐路线（一期最小可用）与工作量

### 推荐：一期 = Electron + python-embed + NSIS，GitHub Actions 构建

```
GitHub Actions (windows-latest)
  1. npm ci && 前端已构建(dist 现成)
  2. 下载 python-3.12.x-embed-amd64.zip → extraResources/python-embed/
  3. 拷贝 gui/ 源码 → extraResources/backend/
  4. electron-builder --win nsis （zip 目标顺手一起出，用于冒烟测试）
  5. 产物上传到 GitHub Release（手動下载安装）
```

为什么是这条：
- novel-lab 纯标准库 → embed 路线无依赖地狱，体积最小（约 15 MB 后端增量）。
- NSIS 安装器是用户要的"双击安装、桌面图标"体验；zip 目标可先在 Linux 本机验证大部分逻辑。
- Actions 原生 Windows 构建，绕开 Wine 全部坑；若将来切回路线 A（PyInstaller），构建机不变。

### 工作量估计（人天，含测试，均为估计非承诺）

| 步骤 | 内容 | 估计 |
|---|---|---|
| E1 | Electron 脚手架：`electron/` 目录、main.ts（窗口/splash/菜单）、preload.ts、双 tsconfig（main DOM 分离，参考 https://github.com/alexishida/dalhe-cli/blob/HEAD/src/template/skills/dl-electron-react/references/build-and-packaging.md） | 1–2 天 |
| E2 | 后端生命周期：spawn（windowsHide）、端口选择与传递、`/api/health` 轮询就绪、单实例锁、退出杀进程树 | 1–1.5 天 |
| E3 | 新增 `GET /api/health`（service 字段防误认）+ Python 单测 | 0.5 天 |
| E4 | 打包配置：electron-builder.yml（nsis per-user、icon.ico、extraResources、artifactName）、`builtin_sync` 适配 `process.resourcesPath` | 1–1.5 天 |
| E5 | 构建脚本：embed 下载解压脚本（Linux/Win 通用）、`.ico` 图标生成 | 0.5–1 天 |
| E6 | GitHub Actions `windows-latest` 工作流：构建 → 产物 → Release | 0.5–1 天 |
| E7 | electron-updater 接线（GitHub provider）+ 更新提示 UI | 0.5–1 天 |
| E8 | Windows 10 真机验证：安装/卸载/覆盖升级/用户数据保留/端口冲突/杀毒误报/开机自启（如需） | 2–3 天（需用户配合或 Windows VM） |
| **合计** | | **约 8–13 人天** |

### 风险清单（诚实版）

1. **未签名 SmartScreen 警告**：unsigned NSIS 安装时 Windows 会弹"未知发布者"。一期可接受（用户点"仍要运行"），长期需 OV 证书或 SignPath。**未验证** SignPath 申请流程。
2. **embed `._pth` 隔离语义**：需一次真实 Windows 验证启动链路（E2 覆盖）。
3. **后端 serve 前端 dist 的确认**（§4.6）：实现前必须确认，否则打包结构要调整。
4. **杀毒误报**：路线 B 预期低，但**未在真实 Windows + 国产杀毒环境测过**，E8 必须覆盖。
5. **Python 版本锁定**：embed 包用 3.12.x（与仓库一致）；`gui/` 代码避免用 3.13+ 语法（现状 3.12，无问题）。
6. **Wine 路线已放弃**：若将来要在 Linux 本机构建 NSIS，需回头踩 §2 的 wine32 坑；一期走 Actions 不踩。

---

## 7. 参考链接（全部为本报告实际引用的真实页面）

**PyInstaller 与跨平台构建**
- https://github.com/brentvollebregt/nitrate.net（nitratine.net：PyInstaller 常见问题，含官方"not a cross-compiler"原文引用、onefile 杀毒误报）
- https://github.com/simonschubert/linuxcommandlibrary/blob/HEAD/assets/commands/pyinstaller.md（PyInstaller caveats 速查：跨编译不支持、杀毒误报、onefile 启动慢）
- https://github.com/tfd-42/proc_map_analyzer（实战："PyInstaller does not cross-compile"）
- https://github.com/zhaoweny/clear-record/blob/HEAD/packaging/pyinstaller/README.md（"Build on each target OS"，CI 矩阵实践）
- https://github.com/ranipdx-glitch/bvid-fe/blob/HEAD/docs/BUILD.md（PyInstaller 体积实测：scipy/matplotlib 栈 >500 MB ——反衬 novel-lab 纯标准库的优势）

**Electron + Python 封装实战**
- https://github.com/aryansingh0777raghav/arch（Electron + PyInstaller 后端 + tree-kill，extraResources 配置范例）
- https://github.com/krishivseth/orchard/blob/HEAD/ELECTRON_GUIDE.md（PyInstaller onedir + readiness probe 要求 `/health` 返回 service 名 + 按 arch 分目录）
- https://github.com/lunaburg/star_manager/blob/HEAD/apps/docs/packaging-windows.md（`electron-builder --win dir` + 后端 exe 进 resources 的完整三阶段脚本）
- https://github.com/djdistraction/htxpunk-mv-generator/blob/HEAD/electron-app/README.md（NSIS + portable + Windows 签名配置范例）

**Linux 构建 Windows 目标 / Wine**
- https://github.com/kdroidfilter/electron-builder/blob/HEAD/website/docs/features/multi-platform-build.md（官方：Linux 构建 Windows 需 Wine 2.0+；NSIS 不需要 Mono）
- https://github.com/unn-devotek/fcm-fallout-chat-mod/blob/HEAD/docs/testing/windows-nsis-ci-fixes.md（2026-09 实战：nsis/portable 在 Linux 构建时 electron-builder 内部用 Wine 跑安装器 stub；wine32 必须先于 wineboot 安装）
- https://github.com/unn-devotek/fcm-fallout-chat-mod/blob/HEAD/cross-platform-overlay/BUILD.md（CI 矩阵：windows-latest / macos / ubuntu 分 runner）
- https://github.com/blackbelttechnology/pi-agent-dashboard/blob/HEAD/docs/electron-build-methods.md（本地/Docker 只出 ZIP；NSIS 只走 CI 的 Windows runner）
- https://github.com/djascendance/wrlforge/blob/HEAD/AGENTS.md（"portable .exe + NSIS installer, needs wine when cross-building from Linux — or builds natively on Windows"）
- https://github.com/tembalanco/roku-dev-studio/blob/HEAD/INSTALLATION.md（"Cross-building Windows artifacts from macOS/Linux requires Wine… run npm run build:win on Windows"）

**python-embed**
- https://github.com/zooba/zooba.github.io/blob/HEAD/_posts/2016-11-06-why-so-many-python-installers.md（CPython Windows 发布负责人 Steve Dower：embed 包约 7 MB 下载 / 12 MB 解压，`._pth` 强制隔离）
- https://github.com/9mtm/agent-player/blob/HEAD/docs/PYTHON_ENVIRONMENT.md（embed 约 10 MB，免安装、免管理员、隔离；`._pth` 配 pip 的做法）
- https://github.com/philr7919/yt-dlp-gui（各 OS 内嵌 Python 体积表：Windows embed zip 约 10 MB）
- https://github.com/g4m3rm1k3/upskillos/blob/HEAD/desktop/README.md（Electron 应用内下载 embed zip 到 userData、补 `._pth` 的实战）
- https://michlstechblog.info/blog/python-install-python-with-pip-on-windows-by-the-embeddable-zip-file/（`._pth` 覆盖 PYTHONPATH 的坑）

**自动更新**
- https://github.com/kaiscommitted/musicflow-/blob/HEAD/musicflow-electron/README.md（unsigned NSIS 自动更新可行；差分下载可主动关闭避坑）
- https://github.com/hlt83595685-cmyk/veridian/commit/bae200c8c00c458a1c87dc3a9b49efd4e5c85635（electron-updater + GitHub Releases 零成本方案，无需签名）
- https://github.com/malpractis/materia-core-releases（公开 release feed 实物：Setup exe + blockmap + latest.yml）
- https://github.com/amirlehmam/wmux/pull/97（zip 目标无法被 updater 安装，必须用 nsis；publisherName 钉签名后 unsigned 包更新会失败）
- https://github.com/zenineasa/konjugate/blob/HEAD/docs/proposals/autoUpdates.md（GitHub Releases 做更新源零服务器成本；Windows/Linux unsigned 可行，macOS 需签名）
- https://github.com/azure/configforge/blob/HEAD/apps/desktop/UPDATING.md（unsigned 构建的更新行为边界：首次安装 SmartScreen，更新靠 sha512 校验）
- https://github.com/tsiger/widgetizer/blob/HEAD/docs-llms/core-electron.md（本地 Windows 更新链路测试方法：`--updater-url` 指到本地 http-server）

**体积参考**
- https://github.com/basemax/electron-censor-app/blob/HEAD/README.md（electron-v33.2.1-win32-x64.zip 下载 115 MB，真實构建日志）
- https://github.com/wixely/cupriface/blob/HEAD/comparisons/electron.md（Electron 典型值：安装器 80–150 MB，安装后 100–300 MB，标注为 typical-range estimates）
- https://github.com/ipfizz/bunmaska/blob/HEAD/website/src/content/docs/compare/bunmaska-vs-electron.md（Electron 下载 150 MB+ / 安装约 220 MB，第三方对比页，量级参考）
- https://github.com/engasnm111/lnwjud/blob/HEAD/docs/development/PACKAGING_WINDOWS.md（NSIS per-user 打包契约：`deleteAppDataOnUninstall: false`、`portable.yml` 独立更新通道）

**构建模板**
- https://github.com/alexishida/dalhe-cli/blob/HEAD/src/template/skills/dl-electron-react/references/build-and-packaging.md（electron-vite 模板：双 tsconfig、electron-builder.yml 范例、asar 说明）
- https://github.com/two-steps-studio/two-steps-studio/blob/HEAD/tss-website/ELECTRON_DESKTOP_GUIDE.md（NSIS + portable 双产物、release 流程、latest.yml 上传清单）
