import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import PlatformPanel from './PlatformPanel'

vi.mock('../api/client', () => ({
  platformApi: {
    list: vi.fn().mockResolvedValue({
      platforms: [
        {
          id: 'qidian',
          name: '起点中文网',
          chapterMinChars: 2000,
          chapterMaxChars: 4000,
          supportsSerialization: true,
          genreCount: 12,
        },
        {
          id: 'fanqie',
          name: '番茄小说',
          chapterMinChars: 1500,
          chapterMaxChars: 3000,
          supportsSerialization: true,
          genreCount: 15,
        },
      ],
    }),
    check: vi.fn().mockResolvedValue({
      platform: 'qidian',
      charCount: 2200,
      compliant: true,
      issues: [],
    }),
    diagnose: vi.fn().mockResolvedValue({
      platform: '起点中文网',
      platformId: 'qidian',
      chapterNum: 1,
      charCount: 2200,
      score: 92,
      grade: 'A',
      signingProb: '极高',
      dialogueRatio: 0.28,
      vetoRisks: [],
      actionableFixes: ['黄金三章节奏建议：在第二章进一步抛出悬念'],
    }),
  },
  friendlyError: (e: unknown) => String(e),
}))

describe('PlatformPanel', () => {
  it('渲染平台列表并展示平台字数要求', async () => {
    render(<PlatformPanel />)
    expect(screen.getByText('多平台适配与签约诊断')).toBeDefined()
    await waitFor(() => {
      expect(screen.getByText('2000-4000字/章')).toBeDefined()
    })
  })

  it('点击检查合规性展示结果', async () => {
    render(<PlatformPanel />)
    const textareas = screen.getAllByRole('textbox')
    // textareas[0] 是标题，textareas[1] 是正文
    const contentInput = textareas[1]
    fireEvent.change(contentInput, { target: { value: '这是两千多字的测试章节正文。' } })

    const checkBtn = screen.getByText('检查合规性')
    fireEvent.click(checkBtn)

    await waitFor(() => {
      expect(screen.getByText('合规检查结果')).toBeDefined()
      expect(screen.getByText('合规')).toBeDefined()
    })
  })

  it('点击签约过稿深度诊断展示评级与建议', async () => {
    render(<PlatformPanel />)
    const textareas = screen.getAllByRole('textbox')
    const contentInput = textareas[1]
    fireEvent.change(contentInput, { target: { value: '这是测试章节正文，主角拔剑出鞘。' } })

    const diagnoseBtn = screen.getByText('🎯 签约过稿深度诊断')
    fireEvent.click(diagnoseBtn)

    await waitFor(() => {
      expect(screen.getByText('签约过稿诊断报告')).toBeDefined()
      expect(screen.getByText(/评级 A/)).toBeDefined()
      expect(screen.getByText(/签约潜力分: 92/)).toBeDefined()
      expect(screen.getByText('黄金三章节奏建议：在第二章进一步抛出悬念')).toBeDefined()
    })
  })
})
