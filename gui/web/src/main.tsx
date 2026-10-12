import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { installGlobalErrorHandlers } from './globalErrorHandlers'
import { ThemeModeProvider } from './state/ThemeModeContext'
import './index.css'

// 全局错误兜底：ErrorBoundary 只能捕获渲染期同步错误，捕获不到 Promise
// 拒绝与事件回调异常——桌面版里那类错误完全静默（点按钮没反应却无提示）。
// 仅生产构建启用，见模块注释。
installGlobalErrorHandlers()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeModeProvider>
      <App />
    </ThemeModeProvider>
  </React.StrictMode>,
)
