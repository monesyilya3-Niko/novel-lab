// 全局状态 Context：书/章节/批次/任务进度 + 工作台/资产索引缓存。
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { Book, BookResults, Chapter, Overview, ProgressEvent, StatusInfo } from '../types'
import type { WorkbenchKey } from '../layout/WorkbenchNav'
import * as api from '../api/client'

interface AppState {
  // 当前导入的书
  book: Book | null
  // 当前选中的章节索引（1 起）
  selectedChapter: number | null
  // 当前章节全文（含批次）
  currentChapter: Chapter | null
  // 任务状态
  status: StatusInfo | null
  // 进度事件（最近一次）
  lastEvent: ProgressEvent | null
  // 各批次状态映射（key = c{ch}-b{batch}）
  batchStates: Record<string, { status: string; asset?: string }>

  // 阶段一：工作台 + 概览 + 拆书结果缓存
  workbench: WorkbenchKey
  setWorkbench: (k: WorkbenchKey) => void
  overview: Overview | null
  refreshOverview: () => Promise<void>
  bookResults: BookResults | null
  loadBookResults: (bookId: string) => Promise<void>
  refreshBookResults: () => Promise<void>

  // actions
  importBook: (path: string) => Promise<void>
  selectChapter: (idx: number) => Promise<void>
  refreshStatus: () => Promise<void>
  startAnalysis: (genre: string) => Promise<void>
  runFullAnalysis: (genre: string) => Promise<void>
  pauseAnalysis: () => Promise<void>
  resumeAnalysis: () => Promise<void>
  retryFailed: () => Promise<void>
}

const AppContext = createContext<AppState | null>(null)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [book, setBook] = useState<Book | null>(null)
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null)
  const [currentChapter, setCurrentChapter] = useState<Chapter | null>(null)
  const [status, setStatus] = useState<StatusInfo | null>(null)
  const [lastEvent, setLastEvent] = useState<ProgressEvent | null>(null)
  const [batchStates, setBatchStates] = useState<Record<string, { status: string; asset?: string }>>({})

  // 阶段一新增状态。
  const [workbench, setWorkbench] = useState<WorkbenchKey>('home')
  const [overview, setOverview] = useState<Overview | null>(null)
  const [bookResults, setBookResults] = useState<BookResults | null>(null)

  const bookIdRef = useRef<string | null>(null)

  const refreshStatus = useCallback(async () => {
    const s = await api.getStatus(bookIdRef.current ?? undefined)
    setStatus(s)
    if (s.bookId) bookIdRef.current = s.bookId
  }, [])

  const refreshOverview = useCallback(async () => {
    const ov = await api.getOverview()
    setOverview(ov)
  }, [])

  const loadBookResults = useCallback(async (bookId: string) => {
    const r = await api.getBookResults(bookId)
    setBookResults(r)
  }, [])

  const refreshBookResults = useCallback(async () => {
    const bid = bookIdRef.current
    if (!bid) return
    try {
      await loadBookResults(bid)
    } catch {
      // 无结果时静默（前端显示空态）。
    }
  }, [loadBookResults])

  // 订阅 SSE 进度。
  useEffect(() => {
    const close = api.subscribeEvents(bookIdRef.current, (e) => {
      setLastEvent(e)
      if (e.status === 'success' || e.status === 'failed' || e.status === 'running') {
        const key = e.cursor
        setBatchStates((prev) => ({ ...prev, [key]: { status: e.status } }))
      }
      // 任务结束/完成时刷新一次状态。
      if (e.status === 'done') {
        refreshStatus()
        refreshBookResults()
        refreshOverview()
      }
      // 报告生成完成（拆书 done 后异步回调）→ 刷新拆书结果以显示 report_ids。
      if ((e.status as string) === 'report_ready') {
        refreshBookResults()
        refreshOverview()
      }
    })
    return close
  }, [refreshStatus, refreshBookResults, refreshOverview])

  const importBook = useCallback(async (path: string) => {
    const b = await api.importBook(path)
    setBook(b)
    bookIdRef.current = b.bookId
    setSelectedChapter(null)
    setCurrentChapter(null)
    // 初始化批次状态
    const states: Record<string, { status: string }> = {}
    for (const ch of b.chapters) {
      for (const bt of ch.batches) {
        states[`c${bt.chapterIndex}-b${bt.batchIndex}`] = { status: bt.status }
      }
    }
    setBatchStates(states)
    await refreshStatus()
  }, [refreshStatus])

  const selectChapter = useCallback(async (idx: number) => {
    if (!bookIdRef.current) return
    setSelectedChapter(idx)
    const ch = await api.getChapter(bookIdRef.current, idx)
    setCurrentChapter(ch)
  }, [])

  const startAnalysis = useCallback(async (genre: string) => {
    if (!bookIdRef.current) return
    await api.startAnalysis(bookIdRef.current, genre)
    await refreshStatus()
  }, [refreshStatus])

  const runFullAnalysis = useCallback(async (genre: string) => {
    if (!bookIdRef.current) return
    await api.runFullAnalysis(bookIdRef.current, genre)
    await refreshStatus()
  }, [refreshStatus])

  const pauseAnalysis = useCallback(async () => {
    if (!bookIdRef.current) return
    await api.pauseAnalysis(bookIdRef.current)
    await refreshStatus()
  }, [refreshStatus])

  const resumeAnalysis = useCallback(async () => {
    if (!bookIdRef.current) return
    await api.resumeAnalysis(bookIdRef.current)
    await refreshStatus()
  }, [refreshStatus])

  const retryFailed = useCallback(async () => {
    if (!bookIdRef.current) return
    await api.retryFailed(bookIdRef.current)
    await refreshStatus()
  }, [refreshStatus])

  // 初始加载：恢复会话 + 加载概览。
  useEffect(() => {
    refreshStatus().then(() => {
      const bid = bookIdRef.current
      if (bid) {
        api.getBook(bid).then((b) => setBook(b)).catch(() => {})
      }
    })
    refreshOverview().catch(() => {})
  }, [refreshStatus, refreshOverview])

  const value = useMemo<AppState>(
    () => ({
      book,
      selectedChapter,
      currentChapter,
      status,
      lastEvent,
      batchStates,
      workbench,
      setWorkbench,
      overview,
      refreshOverview,
      bookResults,
      loadBookResults,
      refreshBookResults,
      importBook,
      selectChapter,
      refreshStatus,
      startAnalysis,
      runFullAnalysis,
      pauseAnalysis,
      resumeAnalysis,
      retryFailed,
    }),
    [
      book, selectedChapter, currentChapter, status, lastEvent, batchStates,
      workbench, overview, bookResults,
      importBook, selectChapter, refreshStatus, startAnalysis, runFullAnalysis,
      pauseAnalysis, resumeAnalysis, retryFailed, refreshOverview, loadBookResults, refreshBookResults,
    ],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp(): AppState {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp 必须在 AppProvider 内使用')
  return ctx
}
