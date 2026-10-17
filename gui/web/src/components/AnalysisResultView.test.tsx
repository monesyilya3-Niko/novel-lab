import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import AnalysisResultView from './AnalysisResultView'
import { I18nProvider } from '../state/I18nContext'
import type { BookResults } from '../types'

const mockSampleResults: BookResults = {
  bookId: 'b1',
  title: '天道神尊',
  voiceCard: { tone: '热血', pace: '紧凑' },
  structure: { arc: '三段式' },
  commercial: { sellingPoint: '系统逆袭' },
  craftCard: { style: '白描' },
  chapterScores: [
    { chapterIndex: 1, title: '初入仙途', consistency: 92, quality: 88 },
    { chapterIndex: 2, title: '初露锋芒', consistency: 95, quality: 90 },
  ],
  reportIds: ['summary-report-1'],
}

const mockUseApp = vi.fn()

vi.mock('../state/AppContext', () => ({
  useApp: () => mockUseApp(),
}))

vi.mock('../api/client', () => ({
  getReport: vi.fn().mockResolvedValue({ id: 'summary-report-1', name: '全书总结', markdown: '# 全书总结报告' }),
  friendlyError: (e: unknown) => String(e),
}))

// Mock lazy-loaded chart components to avoid canvas issues in jsdom
vi.mock('./charts/BarChart', () => ({
  default: () => <div data-testid="mock-bar-chart">Bar Chart</div>,
}))

vi.mock('./charts/RadarChart', () => ({
  default: () => <div data-testid="mock-radar-chart">Radar Chart</div>,
}))

describe('AnalysisResultView 拆书结果视图双语与交互', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('zh-CN 默认环境下渲染资产卡、打分图与报告标签页', async () => {
    mockUseApp.mockReturnValue({
      book: { bookId: 'b1', title: '天道神尊' },
      bookResults: mockSampleResults,
      loadBookResults: vi.fn().mockResolvedValue(undefined),
    })

    render(<AnalysisResultView />)

    expect(screen.getByText('天道神尊')).toBeInTheDocument()
    expect(screen.getByText('拆书结果')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '资产卡' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '章节打分' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '报告' })).toBeInTheDocument()

    // 资产卡四个维度
    expect(screen.getByText('声线卡')).toBeInTheDocument()
    expect(screen.getByText('结构观测')).toBeInTheDocument()
    expect(screen.getByText('商业观测')).toBeInTheDocument()
    expect(screen.getByText('笔法卡')).toBeInTheDocument()

    // 切换到章节打分
    fireEvent.click(screen.getByRole('tab', { name: '章节打分' }))
    expect(screen.getByText('章节打分对比')).toBeInTheDocument()
    expect(screen.getByText('综合能力雷达')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByTestId('mock-bar-chart')).toBeInTheDocument()
      expect(screen.getByTestId('mock-radar-chart')).toBeInTheDocument()
    })

    // 切换到报告
    fireEvent.click(screen.getByRole('tab', { name: '报告' }))
    expect(screen.getByText(/报告 · summary-report-1/)).toBeInTheDocument()
  })

  it('en-US 环境下渲染全量英文标签与卡片标题', async () => {
    mockUseApp.mockReturnValue({
      book: { bookId: 'b1', title: 'Celestial Divinity' },
      bookResults: {
        ...mockSampleResults,
        title: 'Celestial Divinity',
      },
      loadBookResults: vi.fn().mockResolvedValue(undefined),
    })

    render(
      <I18nProvider initialLocale="en-US">
        <AnalysisResultView />
      </I18nProvider>,
    )

    expect(screen.getByText('Celestial Divinity')).toBeInTheDocument()
    expect(screen.getByText('Analysis Result')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Asset Cards' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Chapter Scores' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Reports' })).toBeInTheDocument()

    // 4 Asset Cards
    expect(screen.getByText('Voice Card')).toBeInTheDocument()
    expect(screen.getByText('Structure Observation')).toBeInTheDocument()
    expect(screen.getByText('Commercial Observation')).toBeInTheDocument()
    expect(screen.getByText('Craft Card')).toBeInTheDocument()

    // Switch to Scores
    fireEvent.click(screen.getByRole('tab', { name: 'Chapter Scores' }))
    expect(screen.getByText('Chapter Score Comparison')).toBeInTheDocument()
    expect(screen.getByText('Comprehensive Ability Radar')).toBeInTheDocument()

    // Switch to Reports
    fireEvent.click(screen.getByRole('tab', { name: 'Reports' }))
    expect(screen.getByText(/Report · summary-report-1/)).toBeInTheDocument()
  })

  it('未选择书籍时双语空状态提示', () => {
    mockUseApp.mockReturnValue({
      book: null,
      bookResults: null,
      loadBookResults: vi.fn(),
    })

    const { rerender } = render(<AnalysisResultView />)
    expect(screen.getByText('请先在首页/控制栏导入并拆书，完成后在此查看结果')).toBeInTheDocument()

    rerender(
      <I18nProvider initialLocale="en-US">
        <AnalysisResultView />
      </I18nProvider>,
    )
    expect(screen.getByText('Please import and analyze a book first to view results here')).toBeInTheDocument()
  })
})
