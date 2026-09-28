// AppContext.selectChapter 竞态回归：A→B 快速切换时，A 的迟到响应不得覆盖 B。
import { render, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { useEffect } from 'react'
import { AppProvider, useApp } from './AppContext'

type Ctx = ReturnType<typeof useApp>

const mockGetStatus = vi.fn()
const mockGetBook = vi.fn()
const mockGetOverview = vi.fn()
const mockGetChapter = vi.fn()

vi.mock('../api/client', () => ({
  getStatus: (...args: unknown[]) => mockGetStatus(...args),
  getBook: (...args: unknown[]) => mockGetBook(...args),
  getOverview: (...args: unknown[]) => mockGetOverview(...args),
  getChapter: (...args: unknown[]) => mockGetChapter(...args),
  subscribeEvents: () => () => {},
  systemApi: { settings: () => Promise.resolve({}) },
  friendlyError: (e: unknown) => String(e),
}))

function deferred<T>() {
  let resolve!: (v: T) => void
  const promise = new Promise<T>((r) => { resolve = r })
  return { promise, resolve }
}

let probeCtx: Ctx | null = null
function Probe() {
  const ctx = useApp()
  // 测试探针：经 effect 捕获 context，避免 render 期副作用。
  useEffect(() => { probeCtx = ctx })
  return null
}

describe('selectChapter 竞态守卫', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    probeCtx = null
    mockGetStatus.mockResolvedValue({ bookId: 'b1', status: 'idle', cursor: '', done: 0, total: 0 })
    mockGetBook.mockResolvedValue({ bookId: 'b1', name: '测试书' })
    mockGetOverview.mockResolvedValue({ totalBooks: 1 })
  })

  it('A→B 快切：A 的迟到响应不覆盖 B', async () => {
    const d1 = deferred<unknown>()
    const d2 = deferred<unknown>()
    mockGetChapter.mockImplementation((_bid: unknown, idx: unknown) =>
      idx === 1 ? d1.promise : d2.promise,
    )
    render(<AppProvider><Probe /></AppProvider>)
    // 等初始化完成（bookIdRef 已由 refreshStatus 写入）
    await waitFor(() => expect(probeCtx?.book).not.toBeNull())

    const p1 = probeCtx!.selectChapter(1)
    const p2 = probeCtx!.selectChapter(2)
    // B 先返回，A 后返回（迟到）
    d2.resolve({ chapterIndex: 2, title: '第二章' })
    await p2
    d1.resolve({ chapterIndex: 1, title: '第一章' })
    await p1

    await waitFor(() => {
      expect(probeCtx!.currentChapter).toMatchObject({ chapterIndex: 2 })
    })
    // 最终选中的章节索引仍是 B
    expect(probeCtx!.selectedChapter).toBe(2)
  })

  it('串行选择：后一次正常覆盖前一次', async () => {
    mockGetChapter.mockImplementation((_bid: unknown, idx: unknown) =>
      Promise.resolve({ chapterIndex: idx as number }),
    )
    render(<AppProvider><Probe /></AppProvider>)
    await waitFor(() => expect(probeCtx?.book).not.toBeNull())

    await probeCtx!.selectChapter(1)
    await waitFor(() => {
      expect(probeCtx!.currentChapter).toMatchObject({ chapterIndex: 1 })
    })
    await probeCtx!.selectChapter(2)
    await waitFor(() => {
      expect(probeCtx!.currentChapter).toMatchObject({ chapterIndex: 2 })
    })
  })
})
