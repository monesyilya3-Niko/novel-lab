import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import WritingExtras from './WritingExtras'

const mockOutlines = vi.fn()
const mockCharacters = vi.fn()
const mockNotes = vi.fn()
const mockStats = vi.fn()
const mockProjects = vi.fn()
const mockExport = vi.fn()

vi.mock('../api/client', () => ({
  writingApi: {
    projects: () => mockProjects(),
    outlines: (proj: string) => mockOutlines(proj),
    characters: (proj: string) => mockCharacters(proj),
    notes: (proj: string) => mockNotes(proj),
    stats: (proj: string) => mockStats(proj),
    export: (proj: string, fmt: string) => mockExport(proj, fmt),
  },
  friendlyError: (e: unknown) => String(e),
}))

vi.mock('../state/ThemeModeContext', () => ({
  useThemeMode: () => ({ isDark: false }),
}))

vi.mock('./charts/CreationRateChart', () => ({
  default: () => <div data-testid="creation-rate-chart">CreationRateChart</div>,
}))
vi.mock('./charts/EmotionWaveChart', () => ({
  default: () => <div data-testid="emotion-wave-chart">EmotionWaveChart</div>,
}))
vi.mock('./charts/RhythmRadarChart', () => ({
  default: () => <div data-testid="rhythm-radar-chart">RhythmRadarChart</div>,
}))

describe('WritingExtras 创作扩展工作台', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockProjects.mockResolvedValue([
      { id: 'p1', name: 'test-project', readOnly: false },
    ])
    mockOutlines.mockResolvedValue([
      { id: 1, project: 'test-project', kind: 'chapter', title: '第1章 惊变', summary: '主角觉醒', status: 'planned', sortOrder: 0, createdAt: '', updatedAt: '' },
    ])
    mockCharacters.mockResolvedValue([
      { id: 1, project: 'test-project', name: '林凡', role: '主角', description: '坚毅勇敢', extra: '{}', createdAt: '', updatedAt: '' },
    ])
    mockNotes.mockResolvedValue([
      { id: 1, project: 'test-project', title: '金手指伏笔', content: '古玉在第三章激活', createdAt: '', updatedAt: '' },
    ])
    mockStats.mockResolvedValue({
      totalWords: 5200,
      todayWords: 1200,
      streakDays: 3,
      totalChapters: 3,
      todayChapters: 1,
      history: [],
    })
  })

  it('无项目时提示先在写作页签新建项目', async () => {
    mockProjects.mockResolvedValueOnce([])
    render(<WritingExtras />)
    await waitFor(() => {
      expect(screen.getByText('请先在「写作」页签新建写作项目')).toBeInTheDocument()
    })
  })

  it('有项目时默认渲染项目标签页及大纲列表', async () => {
    render(<WritingExtras />)
    await waitFor(() => {
      expect(screen.getByText('大纲架构')).toBeInTheDocument()
      expect(screen.getByText('人物卡与关系')).toBeInTheDocument()
      expect(screen.getByText('灵感便签')).toBeInTheDocument()
      expect(screen.getByText('创作者仪表盘')).toBeInTheDocument()
      expect(screen.getByText('规范导出')).toBeInTheDocument()
    })

    // 默认展示大纲列表
    await waitFor(() => {
      expect(screen.getByText('第1章 惊变')).toBeInTheDocument()
    })
  })

  it('切换标签页到人物卡、便签、仪表盘与规范导出', async () => {
    render(<WritingExtras />)
    await waitFor(() => {
      expect(screen.getByText('大纲架构')).toBeInTheDocument()
    })

    // 切换到人物卡与关系
    fireEvent.click(screen.getByText('人物卡与关系'))
    await waitFor(() => {
      expect(screen.getByText('林凡')).toBeInTheDocument()
      expect(screen.getByText('坚毅勇敢')).toBeInTheDocument()
    })

    // 切换到灵感便签
    fireEvent.click(screen.getByText('灵感便签'))
    await waitFor(() => {
      expect(screen.getByText('金手指伏笔')).toBeInTheDocument()
      expect(screen.getByText('古玉在第三章激活')).toBeInTheDocument()
    })

    // 切换到创作者仪表盘
    fireEvent.click(screen.getByText('创作者仪表盘'))
    await waitFor(() => {
      expect(screen.getByText('全书总字数')).toBeInTheDocument()
      expect(screen.getByTestId('creation-rate-chart')).toBeInTheDocument()
      expect(screen.getByTestId('emotion-wave-chart')).toBeInTheDocument()
      expect(screen.getByTestId('rhythm-radar-chart')).toBeInTheDocument()
    })

    // 切换到规范导出
    fireEvent.click(screen.getByText('规范导出'))
    await waitFor(() => {
      expect(screen.getByText('导出全书作品')).toBeInTheDocument()
      expect(screen.getByText('导出 Word (.docx)')).toBeInTheDocument()
      expect(screen.getByText('导出 Markdown (.md)')).toBeInTheDocument()
    })
  })
})
