// novel-lab 桌面版主进程。
// 职责：启动内嵌 Python 后端 → 等待服务就绪 → 打开原生窗口 → 退出时回收后端。
// 后端零依赖（纯标准库），随包携带 Windows embeddable Python，用户机器无需装 Python。
'use strict'

const { app, BrowserWindow, dialog, shell } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')

let backend = null
let mainWindow = null
let backendUrl = null
let handshakeToken = null

const isPackaged = app.isPackaged
// 打包后：resources/backend/{gui,scripts,python-win}；开发时：项目根目录。
const BACKEND_DIR = isPackaged
  ? path.join(process.resourcesPath, 'backend')
  : path.join(__dirname, '..')
const PYTHON_EXE = isPackaged
  ? path.join(BACKEND_DIR, 'python-win', 'python.exe')
  : 'python3'

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })
}

function parseUrlFromOutput(text) {
  const m = /\[GUI\] 暮冬念春 服务已启动:\s*(http:\/\/[^\s]+)/.exec(text)
  if (!m) return null
  const url = m[1].replace(/\/$/, '')
  const tm = /\[GUI\] 握手令牌:\s*([A-Za-z0-9_-]+)/.exec(text)
  return { url, token: tm ? tm[1] : null }
}

function waitForHttp(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const headers = handshakeToken ? { 'X-Handshake-Token': handshakeToken } : {}
      const req = http.get(url + '/api/overview', { headers }, (res) => {
        res.resume()
        if (res.statusCode === 200) return resolve()
        retry()
      })
      req.on('error', retry)
      req.setTimeout(2000, () => { req.destroy(); retry() })
      function retry() {
        if (Date.now() > deadline) return reject(new Error('后端服务启动超时'))
        setTimeout(attempt, 400)
      }
    }
    attempt()
  })
}

function startBackend() {
  return new Promise((resolve, reject) => {
    let out = ''
    try {
      backend = spawn(PYTHON_EXE, ['-u', 'gui/launch.py', '--no-browser'], {
        cwd: BACKEND_DIR,
        windowsHide: true,
        // PYTHONUNBUFFERED=1：Windows 管道下 stdout 块缓冲会导致启动 URL
        // 长时间刷不出来，-u 与环境变量双保险。
        env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' },
      })
    } catch (e) {
      return reject(e)
    }
    backend.on('error', (e) => reject(e))
    const onData = (d) => {
      out += d.toString()
      const parsed = parseUrlFromOutput(out)
      // 必须 URL 和 token 都到齐才继续：两行 print 可能分属不同管道
      // 数据块，若只拿到 URL 就摘监听，token 会永远收不到导致 403。
      if (parsed && parsed.url && parsed.token) {
        backendUrl = parsed.url
        handshakeToken = parsed.token
        backend.stdout.off('data', onData)
        backend.stderr.off('data', onData)
        waitForHttp(parsed.url, 30000).then(resolve).catch(reject)
      }
    }
    backend.stdout.on('data', onData)
    backend.stderr.on('data', onData)
    backend.on('exit', (code) => {
      if (!backendUrl) reject(new Error(`后端启动失败，退出码 ${code}\n${out.slice(-500)}`))
    })
    setTimeout(() => { if (!backendUrl) reject(new Error('后端启动超时（60s）')) }, 60000)
  })
}

const fs = require('fs')

function windowStatePath() {
  return path.join(app.getPath('userData'), 'window-state.json')
}

function loadWindowState() {
  const defaults = { width: 1440, height: 900, x: undefined, y: undefined }
  try {
    const raw = fs.readFileSync(windowStatePath(), 'utf-8')
    const s = JSON.parse(raw)
    // 校验数值合法性，损坏的配置回退默认值。
    if (typeof s.width === 'number' && s.width >= 1024) defaults.width = s.width
    if (typeof s.height === 'number' && s.height >= 640) defaults.height = s.height
    if (typeof s.x === 'number') defaults.x = s.x
    if (typeof s.y === 'number') defaults.y = s.y
  } catch (_) { /* 首次启动或配置损坏，用默认值 */ }
  return defaults
}

function saveWindowState(win) {
  if (!win || win.isDestroyed()) return
  try {
    const [width, height] = win.getSize()
    const [x, y] = win.getPosition()
    // 最大化状态下不保存位置（恢复时位置无意义），只记大小。
    const state = win.isMaximized() ? { width, height } : { width, height, x, y }
    fs.writeFileSync(windowStatePath(), JSON.stringify(state))
  } catch (_) { /* 保存失败不影响运行 */ }
}

function createWindow() {
  // 窗口状态持久化：记住用户调整后的大小/位置，下次启动恢复。
  const winState = loadWindowState()
  mainWindow = new BrowserWindow({
    width: winState.width,
    height: winState.height,
    x: winState.x,
    y: winState.y,
    minWidth: 1024,
    minHeight: 640,
    title: '暮冬念春',
    autoHideMenuBar: true,
    backgroundColor: '#FAF7F0',
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  })
  // 关闭/退出前保存窗口状态（防崩溃丢失：resize/move 即时保存）。
  const saveState = () => saveWindowState(mainWindow)
  mainWindow.on('resize', saveState)
  mainWindow.on('move', saveState)
  mainWindow.on('close', saveState)
  const frontUrl = handshakeToken ? backendUrl + '/?handshake=' + encodeURIComponent(handshakeToken) : backendUrl + '/'
  mainWindow.loadURL(frontUrl)
  mainWindow.once('ready-to-show', () => mainWindow.show())
  // 外部链接用系统浏览器打开，不在应用窗口内跳转。
  // setWindowOpenHandler 只拦截 window.open() 弹窗；will-navigate 拦截
  // 同窗口导航（链接点击、重定向、location.href），否则外部页面会在
  // 应用窗口内加载。
  // 安全：用 URL origin 严格比较，不用字符串前缀（前缀可被绕过，
  // 如 backendUrl=http://127.0.0.1:8000 时 http://127.0.0.1:8000.evil.com 也会通过）。
  const backendOrigin = new URL(backendUrl).origin
  const isInternalUrl = (url) => {
    try {
      return new URL(url).origin === backendOrigin
    } catch (_) {
      return false
    }
  }
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!isInternalUrl(url)) {
      event.preventDefault()
      shell.openExternal(url)
    }
  })
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!isInternalUrl(url)) {
      shell.openExternal(url)
      return { action: 'deny' }
    }
    return { action: 'allow' }
  })
  mainWindow.on('closed', () => { mainWindow = null })
}

function stopBackend() {
  app.quitting = true
  if (backend && !backend.killed) {
    try {
      if (process.platform === 'win32') {
        // B5：同步等待 taskkill 完成，避免后端变孤儿导致下次启动报"已在运行"。
        const { spawnSync } = require('child_process')
        spawnSync('taskkill', ['/pid', String(backend.pid), '/T', '/F'])
      } else {
        backend.kill('SIGTERM')
      }
    } catch (_) { /* 忽略回收失败 */ }
    backend = null
  }
}

app.on('window-all-closed', () => {
  stopBackend()
  if (process.platform !== 'darwin') app.quit()
})

// B6：macOS 点击 Dock 图标时重建窗口（window-all-closed 后 app 未退出）。
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    // 后端已随窗口关闭而停止，需重启
    startBackend().then(createWindow).catch((e) => {
      dialog.showErrorBox('启动失败', `后端重启失败：${e.message}`)
    })
  }
})

app.on('before-quit', stopBackend)

app.whenReady().then(async () => {
  try {
    await startBackend()
    createWindow()
    // B4：窗口创建后监听后端退出，崩溃时弹窗提示而非白屏卡死。
    backend.on('exit', (code) => {
      if (app.quitting) return
      dialog.showErrorBox(
        '暮冬念春 后端已停止',
        `后端服务意外退出（退出码 ${code}）。\n\n请重启应用恢复。如频繁出现，请联系开发者。`
      )
    })
  } catch (e) {
    dialog.showErrorBox(
      '暮冬念春 启动失败',
      `后端服务未能启动：\n${e.message}\n\n请尝试重新安装，或联系开发者。`
    )
    stopBackend()
    app.quit()
  }
})
