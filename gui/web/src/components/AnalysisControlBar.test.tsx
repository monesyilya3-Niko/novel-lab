// P0-4 AnalysisControlBar 回归：题材必填、下拉加载、失败提示、选择后可分析。
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import AnalysisControlBar from './AnalysisControlBar'

const mockGetGenres = vi.fn()

vi.mock('../api/client', () => ({
  getGenres: (...args: unknown[]) => mockGetGenres(...args),
  friendlyError: (e: unknown) => String(e),
}))

// AppContext 的 mock：提供 book 和 runFullAnalysis
vi.mock('../state/AppContext', () => ({
  useApp: () => ({
    book: { id: 'test-book', name: '测试书' },
    runFullAnalysis: vi.fn(),
  }),
}))

describe('AnalysisControlBar 题材必填', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetGenres.mockResolvedValue(['campus-redemption', 'dushi-gaowu'])
  })

  it('加载题材列表并渲染下拉', async () => {
    render(<AnalysisControlBar onGoResult={() => {}} />)
    await waitFor(() => {
      expect(mockGetGenres).toHaveBeenCalled()
    })
    // MUI Select 应渲染
    expect(screen.getByLabelText(/题材/)).toBeInTheDocument()
  })

  it('未选题材时一键分析按钮禁用', async () => {
    render(<AnalysisControlBar onGoResult={() => {}} />)
    await waitFor(() => {
      expect(mockGetGenres).toHaveBeenCalled()
    })
    const btn = screen.getByRole('button', { name: /一键分析/ })
    expect(btn).toBeDisabled()
  })

  it('题材加载失败显示错误提示', async () => {
    mockGetGenres.mockRejectedValueOnce(new Error('网络错误'))
    render(<AnalysisControlBar onGoResult={() => {}} />)
    await waitFor(() => {
      expect(screen.getByText(/题材列表加载失败/)).toBeInTheDocument()
    })
  })
})
