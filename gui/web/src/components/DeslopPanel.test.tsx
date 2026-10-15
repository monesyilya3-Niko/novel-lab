import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import DeslopPanel from './DeslopPanel'

const mockDeslop = vi.fn()

vi.mock('../api/client', () => ({
  writingApi: {
    deslop: (...args: unknown[]) => mockDeslop(...args),
  },
  friendlyError: (e: unknown) => String(e),
}))

vi.mock('../state/ThemeModeContext', () => ({
  useThemeMode: () => ({ isDark: false }),
}))

describe('DeslopPanel 去 AI 味诊断面板', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('初始渲染包含标题、输入框与诊断按钮', () => {
    render(<DeslopPanel />)
    expect(screen.getByText('去 AI 味全维度诊断与润色')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/粘贴待检测的章节/)).toBeInTheDocument()
    expect(screen.getByText('开始去 AI 味诊断')).toBeInTheDocument()
  })

  it('输入文本后调用诊断并展示诊断报告', async () => {
    mockDeslop.mockResolvedValueOnce({
      aiScore: 42.5,
      verdict: 'NOTICEABLE',
      verdictCn: 'AI 腔明显（存在高频模板与直陈宣泄）',
      stats: {
        wordCount: 850,
        sentenceCount: 36,
        issuesCount: 2,
        rangDensity: 3.5,
      },
      issues: [
        {
          type: 'hollow_rhetoric',
          label: '时间凝固模板',
          snippet: '这一刻时间仿佛凝固了',
          index: 0,
          weight: 12,
          suggestion: '改为描写周围人物动作的戛然而止。',
        },
      ],
      suggestions: ['警惕玄虚修辞，网文需要的是落地的动作与环境反馈。'],
    })

    render(<DeslopPanel />)
    const textarea = screen.getByPlaceholderText(/粘贴待检测的章节/)
    fireEvent.change(textarea, { target: { value: '这一刻时间仿佛凝固了。' } })

    const btn = screen.getByText('开始去 AI 味诊断')
    fireEvent.click(btn)

    await waitFor(() => {
      expect(mockDeslop).toHaveBeenCalledWith('这一刻时间仿佛凝固了。')
      expect(screen.getByText('42.5')).toBeInTheDocument()
      expect(screen.getByText(/AI 腔明显/)).toBeInTheDocument()
      expect(screen.getByText(/时间凝固模板/)).toBeInTheDocument()
    })
  })

  it('切换到 Exoscribe 英文模式并展示副词占比报告', async () => {
    mockDeslop.mockResolvedValueOnce({
      aiScore: 38.0,
      verdict: 'MILD',
      verdictCn: '轻度模式化（个别英文模板与修辞冗余）',
      stats: {
        wordCount: 320,
        sentenceCount: 18,
        issuesCount: 1,
        rangDensity: 0.0,
        adverbDensity: 5.2,
      },
      issues: [
        {
          type: 'hollow_rhetoric',
          label: 'A testament to 虚辞',
          snippet: 'a testament to',
          index: 0,
          weight: 12,
          suggestion: 'Anchor in concrete actions.',
        },
      ],
      suggestions: ['Cut abstract LLM metaphors.'],
    })

    render(<DeslopPanel />)
    const enToggle = screen.getByText('Exoscribe 英文')
    fireEvent.click(enToggle)

    const textarea = screen.getByPlaceholderText(/粘贴待检测的章节/)
    fireEvent.change(textarea, { target: { value: 'His bravery was a testament to courage.' } })

    const btn = screen.getByText('开始去 AI 味诊断')
    fireEvent.click(btn)

    await waitFor(() => {
      expect(mockDeslop).toHaveBeenCalledWith('His bravery was a testament to courage.', 'en')
      expect(screen.getByText('38')).toBeInTheDocument()
      expect(screen.getByText(/A testament to 虚辞/)).toBeInTheDocument()
      expect(screen.getByText(/5.2%/)).toBeInTheDocument()
    })
  })
})
