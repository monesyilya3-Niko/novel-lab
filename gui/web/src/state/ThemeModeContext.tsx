// 主题模式 Context：light / dark / system（跟随系统），localStorage 持久化。
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { readStorage, writeStorage } from '../safeStorage'

export type ThemeMode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'novellab.theme-mode'
const systemPrefersDark = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-color-scheme: dark)').matches

interface ThemeModeState {
  mode: ThemeMode
  setMode: (m: ThemeMode) => void
  /** 解析后的实际是否暗色（system → 查询系统） */
  isDark: boolean
}

const ThemeModeContext = createContext<ThemeModeState | null>(null)

function readStored(): ThemeMode {
  // 走 safeStorage：本函数是 useState 的初始化器，在**渲染期间**执行。
  // 直接访问 localStorage 在隐私模式/禁用站点数据时抛 SecurityError，
  // 异常会冒泡出渲染，导致整个应用白屏（本 Provider 包住所有组件）。
  const v = readStorage(STORAGE_KEY)
  return v === 'light' || v === 'dark' || v === 'system' ? v : 'system'
}

export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(readStored)
  const [systemDark, setSystemDark] = useState(systemPrefersDark)

  // 跟随系统：监听系统偏好变化
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e: MediaQueryListEvent) => setSystemDark(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const setMode = (m: ThemeMode) => {
    setModeState(m)
    writeStorage(STORAGE_KEY, m)
  }

  const value = useMemo<ThemeModeState>(
    () => ({ mode, setMode, isDark: mode === 'dark' || (mode === 'system' && !!systemDark) }),
    [mode, systemDark],
  )

  return <ThemeModeContext.Provider value={value}>{children}</ThemeModeContext.Provider>
}

export function useThemeMode(): ThemeModeState {
  const ctx = useContext(ThemeModeContext)
  if (!ctx) throw new Error('useThemeMode 必须在 ThemeModeProvider 内使用')
  return ctx
}
