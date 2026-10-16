import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import PlatformPanel from './PlatformPanel'
import { I18nProvider } from '../state/I18nContext'
import { writeStorage, removeStorage } from '../safeStorage'

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
    parseStatBox: vi.fn().mockResolvedValue({
      stat_boxes: [
        {
          type: 'bracket_window',
          title: 'Status Window',
          fields: { Name: 'Carl', Level: '1', Strength: '14' },
          raw_text: '[Status Window]\nName: Carl\nLevel: 1\nStrength: 14',
          start: 0,
          end: 50,
          char_count: 50,
        },
      ],
      count: 1,
    }),
    formatRoyalRoad: vi.fn().mockResolvedValue({
      formatted: "[b]Author's Note:[/b]\nThanks for reading!\n\n---\n[spoiler=\"Status Window\"]\n[Status Window]\nName: Carl\n[/spoiler]",
      stat_boxes_found: 1,
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

  it('切换到 LitRPG 与海外排版选项卡，能解析属性面板', async () => {
    render(<PlatformPanel />)
    const litrpgTab = screen.getByText(/LitRPG 属性面板与海外排版/)
    fireEvent.click(litrpgTab)

    expect(screen.getByText('LitRPG 属性面板与 Royal Road 格式化工坊')).toBeDefined()

    const parseBtn = screen.getByText('解析属性面板')
    fireEvent.click(parseBtn)

    await waitFor(() => {
      expect(screen.getByText('属性面板识别结果')).toBeDefined()
      expect(screen.getByText('共识别 1 个面板')).toBeDefined()
      expect(screen.getByText('Name: Carl')).toBeDefined()
      expect(screen.getByText('Level: 1')).toBeDefined()
      expect(screen.getByText('Strength: 14')).toBeDefined()
    })
  })

  it('点击 Royal Road 一键排版并生成 BBCode 格式代码及支持复制', async () => {
    render(<PlatformPanel />)
    const litrpgTab = screen.getByText(/LitRPG 属性面板与海外排版/)
    fireEvent.click(litrpgTab)

    const formatBtn = screen.getByText('⚡ Royal Road 一键排版')
    fireEvent.click(formatBtn)

    await waitFor(() => {
      expect(screen.getByText('Royal Road BBCode 排版稿')).toBeDefined()
      expect(screen.getByText(/\[spoiler="Status Window"\]/)).toBeDefined()
    })

    const copyBtn = screen.getByText('复制排版代码')
    fireEvent.click(copyBtn)

    await waitFor(() => {
      expect(screen.getByText('已复制！')).toBeDefined()
    })
  })

  it('在 en-US 语言环境下渲染英文动作按钮与标签', async () => {
    writeStorage('novellab.locale', 'en-US')
    try {
      render(
        <I18nProvider>
          <PlatformPanel />
        </I18nProvider>,
      )
      expect(screen.getByText('Multi-Platform Adaptation & Submission Audit')).toBeDefined()
      expect(screen.getByText('Check Compliance')).toBeDefined()
      expect(screen.getByText('🎯 Submission Readiness Audit')).toBeDefined()
      expect(screen.getByText('LitRPG Stat Box & Formatter')).toBeDefined()
    } finally {
      removeStorage('novellab.locale')
    }
  })
})
