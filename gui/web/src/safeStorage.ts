/**
 * 安全的 localStorage 访问（2026-10-12）。
 *
 * 为什么不能直接调 window.localStorage：
 * - **隐私模式 / 禁用站点数据**：Safari 无痕、部分企业策略下，访问 localStorage
 *   会直接抛 SecurityError（不是返回 null）。
 * - **配额耗尽**：setItem 在 QuotaExceededError 时抛出。
 * - **SSR / 测试环境**：window 或 localStorage 可能不存在。
 *
 * 后果分级：普通交互处抛出只是打断一次点击；但若发生在 **useState 初始化器**
 * 里（如 ThemeModeProvider 的 readStored），异常会在渲染期间冒泡，
 * 导致整个应用白屏——主题 Provider 包住所有组件。
 *
 * 因此统一走本模块：读失败返回默认值，写失败静默忽略（存储不可用时，
 * 应用仍应能正常使用，只是不记忆偏好）。
 */

function getStore(): Storage | null {
  try {
    // 先探活：某些环境 window.localStorage 存在但访问即抛。
    const s = window.localStorage
    const probe = '__novel_lab_probe__'
    s.setItem(probe, '1')
    s.removeItem(probe)
    return s
  } catch {
    return null
  }
}

/** 读取字符串；不可用或不存在时返回 fallback。 */
export function readStorage(key: string, fallback: string | null = null): string | null {
  const s = getStore()
  if (!s) return fallback
  try {
    const v = s.getItem(key)
    return v === null ? fallback : v
  } catch {
    return fallback
  }
}

/** 写入字符串；不可用时静默忽略（返回是否成功，供调用方需要时判断）。 */
export function writeStorage(key: string, value: string): boolean {
  const s = getStore()
  if (!s) return false
  try {
    s.setItem(key, value)
    return true
  } catch {
    return false
  }
}

/** 删除键；不可用时静默忽略。 */
export function removeStorage(key: string): void {
  const s = getStore()
  if (!s) return
  try {
    s.removeItem(key)
  } catch {
    /* 忽略 */
  }
}
