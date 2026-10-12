/**
 * safeStorage 的回归测试（2026-10-12）。
 *
 * 背景：项目有 4 处直接访问 window.localStorage。隐私模式 / 禁用站点数据 /
 * 配额耗尽时，访问会抛 SecurityError 或 QuotaExceededError——
 * 其中 ThemeModeProvider 的 readStored() 是 useState 初始化器，在渲染期间执行，
 * 抛出会导致整个应用白屏（该 Provider 包住所有组件）。
 *
 * 本测试通过 mock localStorage 抛异常来复现这些场景。
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { readStorage, removeStorage, writeStorage } from './safeStorage'

/** 造一个"访问即抛"的 localStorage（模拟隐私模式）。 */
function installThrowingStorage() {
  const throwing = {
    getItem: () => {
      throw new DOMException('denied', 'SecurityError')
    },
    setItem: () => {
      throw new DOMException('denied', 'SecurityError')
    },
    removeItem: () => {
      throw new DOMException('denied', 'SecurityError')
    },
  }
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    get: () => throwing,
  })
}

/** 造一个"setItem 抛 QuotaExceededError"的存储（读正常）。 */
function installQuotaExceededStorage() {
  const store = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    get: () => ({
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string) => {
        // 探活用的 probe 允许通过，真实写入抛配额错误
        if (k === '__novel_lab_probe__') return
        throw new DOMException('quota', 'QuotaExceededError')
      },
      removeItem: (k: string) => {
        store.delete(k)
      },
    }),
  })
}

/** 造一个"探活通过、但 getItem/setItem 之后才抛"的存储。
 *
 * 为什么需要这个 mock：getStore() 的探活会拦住"访问即抛"的存储，
 * 使 getItem/setItem 各自的 try/catch 成为第二层防御——如果只测
 * "访问即抛"，那层防御被删掉也不会让测试变红（变异测试验证过）。
 * 真实场景：存储可用但读某个键时抛（某些浏览器的键名限制），
 * 或探活与真实调用之间状态改变。
 */
function installSelectivelyThrowingStorage() {
  const store = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    get: () => ({
      getItem: (k: string) => {
        if (k === '__novel_lab_probe__') return null
        throw new DOMException('read failed', 'SecurityError')
      },
      setItem: (k: string) => {
        if (k === '__novel_lab_probe__') return
        throw new DOMException('write failed', 'SecurityError')
      },
      removeItem: (k: string) => {
        store.delete(k)
      },
    }),
  })
}

const originalStorage = window.localStorage

afterEach(() => {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    get: () => originalStorage,
  })
  vi.restoreAllMocks()
})

describe('safeStorage', () => {
  it('正常环境读写', () => {
    expect(writeStorage('k1', 'v1')).toBe(true)
    expect(readStorage('k1')).toBe('v1')
    removeStorage('k1')
    expect(readStorage('k1')).toBeNull()
  })

  it('读不到时返回 fallback', () => {
    expect(readStorage('missing-key', 'default')).toBe('default')
    expect(readStorage('missing-key')).toBeNull()
  })

  it('存储被禁用（抛 SecurityError）时读返回 fallback，不抛出', () => {
    installThrowingStorage()
    expect(() => readStorage('k', 'fallback')).not.toThrow()
    expect(readStorage('k', 'fallback')).toBe('fallback')
  })

  it('存储被禁用时写返回 false，不抛出', () => {
    installThrowingStorage()
    expect(() => writeStorage('k', 'v')).not.toThrow()
    expect(writeStorage('k', 'v')).toBe(false)
  })

  it('存储被禁用时删不抛出', () => {
    installThrowingStorage()
    expect(() => removeStorage('k')).not.toThrow()
  })

  it('配额耗尽时写返回 false，读仍可用', () => {
    installQuotaExceededStorage()
    expect(writeStorage('k', 'v')).toBe(false)
    expect(() => readStorage('k', 'x')).not.toThrow()
  })

  it('真实 localStorage 在探活失败时不被误判为可用', () => {
    // 探活写 probe 就抛 → getStore 返回 null → 所有操作走 fallback 路径
    installThrowingStorage()
    expect(readStorage('anything')).toBeNull()
  })

  // --- 第二层防御：探活通过后单次操作仍可能抛 ---------------------------
  // 下面两个用例专门覆盖 getItem/setItem 各自的 try/catch。缺了它们，
  // 把这两处 try/catch 删掉测试也不会变红（变异测试实证）。

  it('探活通过但 getItem 抛时返回 fallback（第二层防御）', () => {
    installSelectivelyThrowingStorage()
    expect(() => readStorage('k', 'fb')).not.toThrow()
    expect(readStorage('k', 'fb')).toBe('fb')
  })

  it('探活通过但 setItem 抛时返回 false（第二层防御）', () => {
    installSelectivelyThrowingStorage()
    expect(() => writeStorage('k', 'v')).not.toThrow()
    expect(writeStorage('k', 'v')).toBe(false)
  })
})
