// 国际化语言 Context：zh-CN / en-US，localStorage 持久化。
import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { readStorage, writeStorage } from '../safeStorage'
import { TRANSLATIONS, type Locale } from '../i18n/translations'

const STORAGE_KEY = 'novellab.locale'

interface I18nState {
  locale: Locale
  setLocale: (l: Locale) => void
  toggleLocale: () => void
  t: (key: string, fallback?: string) => string
}

const I18nContext = createContext<I18nState | null>(null)

function readStoredLocale(): Locale {
  const v = readStorage(STORAGE_KEY)
  return v === 'en-US' || v === 'zh-CN' ? v : 'zh-CN'
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(readStoredLocale)

  const setLocale = (l: Locale) => {
    setLocaleState(l)
    writeStorage(STORAGE_KEY, l)
  }

  const toggleLocale = () => {
    const next: Locale = locale === 'zh-CN' ? 'en-US' : 'zh-CN'
    setLocale(next)
  }

  const t = (key: string, fallback?: string): string => {
    const entry = TRANSLATIONS[key]
    if (entry && entry[locale]) {
      return entry[locale]
    }
    return fallback ?? key
  }

  const value = useMemo<I18nState>(
    () => ({ locale, setLocale, toggleLocale, t }),
    [locale],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nState {
  const ctx = useContext(I18nContext)
  if (!ctx) {
    // 降级兜底：在未挂载 Provider 的隔离单测中提供安全 fallback
    return {
      locale: 'zh-CN',
      setLocale: () => {},
      toggleLocale: () => {},
      t: (key: string, fallback?: string) => {
        const entry = TRANSLATIONS[key]
        return entry ? entry['zh-CN'] : (fallback ?? key)
      },
    }
  }
  return ctx
}
