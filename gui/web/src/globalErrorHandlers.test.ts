/**
 * 全局错误兜底的回归测试（2026-10-12）。
 *
 * 覆盖两条链路：unhandledrejection 与 error 事件。
 * 注意：installGlobalErrorHandlers 只在 PROD 构建启用（开发交给 Vite overlay），
 * 故测试里用 vi.stubEnv 或直接 mock import.meta.env.PROD。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { installGlobalErrorHandlers } from './globalErrorHandlers'

const NOTICE_ID = '__novel_lab_error_notice__'

/** 让 import.meta.env.PROD 为 true（模块内部检查它）。 */
function withProdEnv() {
  vi.stubEnv('PROD', true)
}

let cleanup: (() => void) | null = null

beforeEach(() => {
  withProdEnv()
  document.getElementById(NOTICE_ID)?.remove()
})

afterEach(() => {
  cleanup?.()
  cleanup = null
  document.getElementById(NOTICE_ID)?.remove()
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

describe('installGlobalErrorHandlers', () => {
  it('开发环境不安装（交给 Vite overlay）', () => {
    vi.stubEnv('PROD', false)
    const spy = vi.spyOn(window, 'addEventListener')
    cleanup = installGlobalErrorHandlers()
    const calls = spy.mock.calls.map((c) => c[0])
    expect(calls).not.toContain('unhandledrejection')
    expect(calls).not.toContain('error')
  })

  it('Promise 拒绝时记录到 console 并显示提示', () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    cleanup = installGlobalErrorHandlers()

    const evt = new Event('unhandledrejection') as Event & { reason?: unknown }
    evt.reason = new Error('后端连接失败')
    window.dispatchEvent(evt)

    expect(errSpy).toHaveBeenCalled()
    const notice = document.getElementById(NOTICE_ID)
    expect(notice).not.toBeNull()
    expect(notice!.textContent).toContain('后端连接失败')
  })

  it('非 Error 的 rejection 值也能转成可读文本', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    cleanup = installGlobalErrorHandlers()

    const evt = new Event('unhandledrejection') as Event & { reason?: unknown }
    evt.reason = '字符串原因'
    window.dispatchEvent(evt)

    expect(document.getElementById(NOTICE_ID)!.textContent).toContain('字符串原因')
  })

  it('未捕获的 error 事件同样被捕获', () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    cleanup = installGlobalErrorHandlers()

    const evt = new ErrorEvent('error', { message: '脚本崩了' })
    window.dispatchEvent(evt)

    expect(errSpy).toHaveBeenCalled()
    expect(document.getElementById(NOTICE_ID)!.textContent).toContain('脚本崩了')
  })

  it('卸载后不再响应（清理函数有效）', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const uninstall = installGlobalErrorHandlers()
    uninstall()
    cleanup = null

    const evt = new Event('unhandledrejection') as Event & { reason?: unknown }
    evt.reason = new Error('卸载后不该出现')
    window.dispatchEvent(evt)

    expect(document.getElementById(NOTICE_ID)).toBeNull()
  })

  it('提示条可点击关闭', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    cleanup = installGlobalErrorHandlers()

    const evt = new Event('unhandledrejection') as Event & { reason?: unknown }
    evt.reason = new Error('点我关闭')
    window.dispatchEvent(evt)

    const notice = document.getElementById(NOTICE_ID)!
    notice.click()
    expect(document.getElementById(NOTICE_ID)).toBeNull()
  })
})
