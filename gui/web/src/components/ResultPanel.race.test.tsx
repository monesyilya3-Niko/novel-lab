// ResultPanel P2-F9 回归：
// 1) 章节切换时批次归零，且只请求 (新章节, 0)，不发出"新章节+旧批次"的误请求；
// 2) 迟到的旧资产响应不得覆盖新请求的结果。
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import ResultPanel from './ResultPanel'

const mockGetAsset = vi.fn()

vi.mock('../api/client', () => ({
  getAsset: (...args: unknown[]) => mockGetAsset(...args),
  friendlyError: (e: unknown) => String(e),
}))

// 可变的 useApp mock：通过改对象 + rerender 模拟章节切换
const appState: Record<string, unknown> = {
  book: { bookId: 'b1', name: '测试书' },
  selectedChapter: 1,
  currentChapter: { chapterIndex: 1, batchCount: 3 },
  batchStates: {},
}
vi.mock('../state/AppContext', () => ({
  useApp: () => appState,
}))

function deferred<T>() {
  let resolve!: (v: T) => void
  const promise = new Promise<T>((r) => { resolve = r })
  return { promise, resolve }
}

type Call = [string, number, number, string]

describe('ResultPanel 章节/批次竞态', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    appState.selectedChapter = 1
    appState.currentChapter = { chapterIndex: 1, batchCount: 3 }
    mockGetAsset.mockImplementation(() => Promise.resolve({ ok: true }))
  })

  it('章节切换：批次归零，只请求(新章节,0)，无"新章节+旧批次"误请求', async () => {
    const { rerender } = render(<ResultPanel />)
    await waitFor(() => expect(mockGetAsset).toHaveBeenCalledTimes(1))
    expect(mockGetAsset.mock.calls[0].slice(0, 3)).toEqual(['b1', 1, 0])

    // 用户先把批次切到 2
    const batchSelect = screen.getByRole('combobox')
    fireEvent.mouseDown(batchSelect)
    const opt2 = await screen.findByRole('option', { name: /第 2 批/ })
    fireEvent.click(opt2)
    await waitFor(() => expect(mockGetAsset).toHaveBeenCalledTimes(2))
    expect(mockGetAsset.mock.calls[1].slice(0, 3)).toEqual(['b1', 1, 2])

    // 章节 1 → 2：应只发起 (b1,2,0)，绝不能出现 (b1,2,2)
    appState.selectedChapter = 2
    appState.currentChapter = { chapterIndex: 2, batchCount: 3 }
    rerender(<ResultPanel />)
    await waitFor(() => expect(mockGetAsset).toHaveBeenCalledTimes(3))
    const calls = mockGetAsset.mock.calls as unknown as Call[]
    expect(calls[2].slice(0, 3)).toEqual(['b1', 2, 0])
    expect(calls.some((c) => c[1] === 2 && c[2] === 2)).toBe(false)
    // 章节切换只产生一次新请求（无双请求）
    expect(calls.filter((c) => c[1] === 2).length).toBe(1)
  })

  it('迟到的旧资产响应不覆盖新请求结果', async () => {
    const dOld = deferred<Record<string, unknown>>()
    const dNew = deferred<Record<string, unknown>>()
    let n = 0
    mockGetAsset.mockImplementation(() => (++n === 1 ? dOld.promise : dNew.promise))

    const { rerender } = render(<ResultPanel />)
    await waitFor(() => expect(mockGetAsset).toHaveBeenCalledTimes(1))

    // 章节 1 → 2，旧请求迟迟不返回
    appState.selectedChapter = 2
    appState.currentChapter = { chapterIndex: 2, batchCount: 3 }
    rerender(<ResultPanel />)
    await waitFor(() => expect(mockGetAsset).toHaveBeenCalledTimes(2))

    // 新请求先返回，旧请求后返回（迟到）
    dNew.resolve({ tag: 'new' })
    await waitFor(() => expect(screen.getByText(/"tag": "new"/)).toBeInTheDocument())
    dOld.resolve({ tag: 'old' })
    // 给迟到响应一点时间，若它覆盖了 UI 这里会失败
    await new Promise((r) => setTimeout(r, 50))
    expect(screen.getByText(/"tag": "new"/)).toBeInTheDocument()
    expect(screen.queryByText(/"tag": "old"/)).not.toBeInTheDocument()
  })
})
