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
  const m = /\[GUI\] novel-lab 书籍分析服务已启动:\s*(http:\/\/[^\s]+)/.exec(text)
  return m ? m[1].replace(/\/$/, '') : null
}

function waitForHttp(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(url + '/api/overview', (res) => {
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
      backend = spawn(PYTHON_EXE, ['gui/launch.py', '--no-browser'], {
        cwd: BACKEND_DIR,
        windowsHide: true,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      })
    } catch (e) {
      return reject(e)
    }
    backend.on('error', (e) => reject(e))
    const onData = (d) => {
      out += d.toString()
      const url = parseUrlFromOutput(out)
      if (url) {
        backendUrl = url
        backend.stdout.off('data', onData)
        backend.stderr.off('data', onData)
        waitForHttp(url, 30000).then(resolve).catch(reject)
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

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    title: 'xuan',
    autoHideMenuBar: true,
    backgroundColor: '#FAF7F0',
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  })
  mainWindow.loadURL(backendUrl + '/')
  mainWindow.once('ready-to-show', () => mainWindow.show())
  // 外部链接用系统浏览器打开，不在应用窗口内跳转。
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(backendUrl)) {
      shell.openExternal(url)
      return { action: 'deny' }
    }
    return { action: 'allow' }
  })
  mainWindow.on('closed', () => { mainWindow = null })
}

function stopBackend() {
  if (backend && !backend.killed) {
    try {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', String(backend.pid), '/T', '/F'])
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

app.on('before-quit', stopBackend)

app.whenReady().then(async () => {
  try {
    await startBackend()
    createWindow()
  } catch (e) {
    dialog.showErrorBox(
      'novel-lab 启动失败',
      `后端服务未能启动：\n${e.message}\n\n请尝试重新安装，或联系开发者。`
    )
    stopBackend()
    app.quit()
  }
})
