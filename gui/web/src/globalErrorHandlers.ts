/**
 * 全局错误兜底（2026-10-12）。
 *
 * 背景：React 的 ErrorBoundary 只能捕获**渲染期间**的同步错误。它捕获不到：
 * - Promise 拒绝（unhandledrejection）——最常见：事件处理器里的 await 失败
 * - 事件回调里的同步异常（onerror）
 *
 * 后果：桌面应用中这类错误完全静默——用户点了按钮没反应，界面无任何提示；
 * 开发者也无从知晓（生产构建没有 devtools 常开）。本模块把这类错误
 * 统一记录到控制台并给出一次可见提示，把"静默失败"变成"可诊断失败"。
 *
 * 设计取舍：
 * - **只在生产构建启用**（import.meta.env.PROD）：开发时 Vite 的 HMR overlay
 *   已经处理了这些，重复弹提示反而干扰。
 * - **不吞错误**：仍然 console.error，保留原始堆栈供排查。
 * - **不弹 alert**：用轻量 DOM 提示条，避免阻塞（且 Electron 里 alert 体验差）。
 */

const NOTICE_ID = '__novel_lab_error_notice__'

/** 显示一次性错误提示条（同一条消息不重复弹）。 */
function showNotice(message: string): void {
  if (typeof document === 'undefined') return
  try {
    const existing = document.getElementById(NOTICE_ID)
    if (existing) {
      // 已有一条提示：更新文本即可，避免叠加
      existing.textContent = message
      return
    }
    const bar = document.createElement('div')
    bar.id = NOTICE_ID
    bar.textContent = message
    bar.setAttribute('role', 'alert')
    // 内联样式：不依赖 MUI（此时 React 树可能已损坏，主题上下文不可用）
    bar.style.cssText = [
      'position:fixed', 'left:50%', 'bottom:16px', 'transform:translateX(-50%)',
      'max-width:90vw', 'padding:10px 16px', 'border-radius:6px',
      'background:#b3261e', 'color:#fff', 'font-size:13px', 'line-height:1.5',
      'box-shadow:0 4px 12px rgba(0,0,0,.25)', 'z-index:2147483647',
      'white-space:pre-wrap', 'word-break:break-word',
    ].join(';')
    // 点击可关闭，避免常驻遮挡
    bar.style.cursor = 'pointer'
    bar.title = '点击关闭'
    bar.addEventListener('click', () => bar.remove())
    document.body.appendChild(bar)
    // 8 秒后自动消失（用户已看到即可）
    setTimeout(() => bar.remove(), 8000)
  } catch {
    /* 提示失败不应再抛（否则递归） */
  }
}

/** 把任意 rejection 值转为可读消息。 */
function describe(reason: unknown): string {
  if (reason instanceof Error) return reason.message || reason.name
  if (typeof reason === 'string') return reason
  try {
    return JSON.stringify(reason)
  } catch {
    return String(reason)
  }
}

/**
 * 安装全局处理器。在 main.tsx 中调用一次。
 * 返回卸载函数（测试用）。
 */
export function installGlobalErrorHandlers(): () => void {
  // 开发环境交给 Vite overlay，避免重复提示
  if (!import.meta.env.PROD) return () => {}

  const onRejection = (e: PromiseRejectionEvent) => {
    console.error('[未处理的 Promise 拒绝]', e.reason)
    showNotice(`操作未完成：${describe(e.reason)}`)
  }
  const onError = (e: ErrorEvent) => {
    console.error('[未捕获的错误]', e.error ?? e.message)
    showNotice(`发生错误：${e.message}`)
  }

  window.addEventListener('unhandledrejection', onRejection)
  window.addEventListener('error', onError)
  return () => {
    window.removeEventListener('unhandledrejection', onRejection)
    window.removeEventListener('error', onError)
  }
}
