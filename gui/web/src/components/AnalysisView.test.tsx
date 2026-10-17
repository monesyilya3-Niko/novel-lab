import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import AnalysisView from './AnalysisView'
import { I18nProvider } from '../state/I18nContext'

const mockGetGenres = vi.fn()
const mockListSamples = vi.fn()

vi.mock('../api/client', () => ({
  getGenres: (...args: unknown[]) => mockGetGenres(...args),
  listSamples: (...args: unknown[]) => mockListSamples(...args),
  getReport: vi.fn().mockResolvedValue({ id: 'r1', name: '总报告', markdown: '# 报告' }),
  friendlyError: (e: unknown) => String(e),
}))

const mockAppState = {
  book: { bookId: 'b1', title: '绝世剑神', totalChapters: 10, chapters: [] },
  selectedChapter: null,
  selectChapter: vi.fn(),
  batchStates: {},
  status: { status: 'idle', done: 0, total: 0, cursor: '' },
  runFullAnalysis: vi.fn(),
  uploadBook: vi.fn(),
  importSampleBook: vi.fn(),
  bookResults: null,
  loadBookResults: vi.fn().mockResolvedValue(undefined),
}

vi.mock('../state/AppContext', () => ({
  useApp: () => mockAppState,
  useAppOptional: () => mockAppState,
}))

describe('AnalysisView 拆书分析工作台双语渲染与标签页切换', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetGenres.mockResolvedValue(['xuanhuan', 'dushi'])
    mockListSamples.mockResolvedValue([])
  })

  it('zh-CN 默认环境下渲染中文顶栏与子标签页', async () => {
    render(<AnalysisView />)
    await waitFor(() => {
      expect(mockGetGenres).toHaveBeenCalled()
    })

    expect(screen.getByRole('tab', { name: '导入' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '进度' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '结果' })).toBeInTheDocument()
    expect(screen.getByLabelText('查看拆书指南')).toBeInTheDocument()
  })

  it('点击切换到进度与结果子标签页', async () => {
    render(<AnalysisView />)
    await waitFor(() => {
      expect(mockGetGenres).toHaveBeenCalled()
    })

    const progressTab = screen.getByRole('tab', { name: '进度' })
    fireEvent.click(progressTab)
    expect(screen.getByText('分析进度')).toBeInTheDocument()

    const resultTab = screen.getByRole('tab', { name: '结果' })
    fireEvent.click(resultTab)
    expect(screen.getByText('尚未生成拆书结果，请先运行「一键分析」')).toBeInTheDocument()
  })

  it('en-US 环境下渲染英文顶栏、子标签页及空状态提示', async () => {
    render(
      <I18nProvider initialLocale="en-US">
        <AnalysisView />
      </I18nProvider>,
    )
    await waitFor(() => {
      expect(mockGetGenres).toHaveBeenCalled()
    })

    expect(screen.getByRole('tab', { name: 'Import' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Progress' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Results' })).toBeInTheDocument()
    expect(screen.getByLabelText('View Deconstruction Guide')).toBeInTheDocument()

    const progressTab = screen.getByRole('tab', { name: 'Progress' })
    fireEvent.click(progressTab)
    expect(screen.getByText('Analysis Progress')).toBeInTheDocument()

    const resultTab = screen.getByRole('tab', { name: 'Results' })
    fireEvent.click(resultTab)
    expect(screen.getByText(/No analysis results generated yet/i)).toBeInTheDocument()
  })
})
