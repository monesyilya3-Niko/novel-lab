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
import { systemApi } from '../api/client'

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

  // 初始化错误（P1-F8：不再静默吞错，UI 可展示）
  initError: string | null

  // 系统设置阈值（P1-F3/F4：QC 合格线/写书目标分统一口径，不再硬编码）
  qualityPassLine: number
  consistencyTarget: number
  // 设置页保存后刷新阈值（避免 QC/写作面板沿用旧值直到整页刷新）
  refreshThresholds: () => Promise<void>

  // actions
  importBook: (path: string) => Promise<void>
  uploadBook: (file: File) => Promise<void>
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
  const [initError, setInitError] = useState<string | null>(null)
  const [qualityPassLine, setQualityPassLine] = useState(75)
  const [consistencyTarget, setConsistencyTarget] = useState(90)

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

  // 竞态守卫：只让最后一次请求的响应写入全局 bookResults
  const bookResultsSeq = useRef(0)
  const loadBookResults = useCallback(async (bookId: string) => {
    const seq = ++bookResultsSeq.current
    const r = await api.getBookResults(bookId)
    if (seq === bookResultsSeq.current) setBookResults(r)
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

  const applyImportedBook = useCallback(async (b: Book) => {
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

  const importBook = useCallback(async (path: string) => {
    const b = await api.importBook(path)
    await applyImportedBook(b)
  }, [applyImportedBook])

  // P0-3：浏览器文件上传导入（拿不到 file.path 时走这里）。
  const uploadBook = useCallback(async (file: File) => {
    const b = await api.uploadBook(file)
    await applyImportedBook(b)
  }, [applyImportedBook])

  // 竞态守卫（与 loadBookResults 同模式）：A→B 快速切换时，A 的迟到响应
  // 不得覆盖 B。只让最后一次 selectChapter 的响应写入 currentChapter。
  const selectChapterSeq = useRef(0)
  const selectChapter = useCallback(async (idx: number) => {
    if (!bookIdRef.current) return
    const seq = ++selectChapterSeq.current
    setSelectedChapter(idx)
    const ch = await api.getChapter(bookIdRef.current, idx)
    if (seq === selectChapterSeq.current) setCurrentChapter(ch)
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

  // P1-F3/F4：加载系统阈值设置（失败则用默认值，不阻断初始化）。
  // 抽出为独立回调：设置页保存阈值后可调用 refreshThresholds() 即时刷新，
  // 否则 QC 合格线/写书目标分会沿用旧值直到整页刷新。
  const refreshThresholds = useCallback(async () => {
    try {
      const d = await systemApi.settings()
      const th = (d as Record<string, unknown>).thresholds as
        | { qualityPassLine?: number; consistencyTarget?: number }
        | undefined
      if (typeof th?.qualityPassLine === 'number') setQualityPassLine(th.qualityPassLine)
      if (typeof th?.consistencyTarget === 'number') setConsistencyTarget(th.consistencyTarget)
    } catch {
      /* 保持旧值 */
    }
  }, [])

  // 初始加载：恢复会话 + 加载概览（P1-F8：错误写入 initError，不再静默吞掉）。
  /* eslint-disable react-hooks/set-state-in-effect -- 本 effect 内所有 setState
     均在异步回调（.then/.catch）中触发，非 effect 同步体；这是标准的数据加载模式。 */
  useEffect(() => {
    let cancelled = false
    const fail = (e: unknown) => {
      if (!cancelled) setInitError(e instanceof Error ? e.message : String(e))
    }
    refreshStatus()
      .then(() => {
        const bid = bookIdRef.current
        if (bid) return api.getBook(bid).then((b) => { if (!cancelled) setBook(b) })
      })
      .catch(fail)
    refreshOverview().catch(fail)
    refreshThresholds()
    return () => { cancelled = true }
  }, [refreshStatus, refreshOverview, refreshThresholds])
  /* eslint-enable react-hooks/set-state-in-effect */

  const value = useMemo<AppState>(
    () => ({
      book,
      initError,
      qualityPassLine,
      consistencyTarget,
      refreshThresholds,
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
      uploadBook,
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
      initError, qualityPassLine, consistencyTarget,
      workbench, overview, bookResults,
      importBook, uploadBook, selectChapter, refreshStatus, startAnalysis, runFullAnalysis,
      pauseAnalysis, resumeAnalysis, retryFailed, refreshThresholds, refreshOverview, loadBookResults, refreshBookResults,
    ],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp(): AppState {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp 必须在 AppProvider 内使用')
  return ctx
}
