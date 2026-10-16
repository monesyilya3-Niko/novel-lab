import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import DiffReviewView from './DiffReviewView'
import { I18nProvider } from '../state/I18nContext'
import { writeStorage, removeStorage } from '../safeStorage'

vi.mock('../state/ThemeModeContext', () => ({
  useThemeMode: () => ({ isDark: false }),
}))

describe('DiffReviewView 双栏对比审校组件', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('默认渲染原稿与润色稿双栏内容及段落统计', () => {
    const orig = '第一段原稿内容。\n第二段原稿内容。'
    const polished = '第一段润色后内容。\n第二段原稿内容。'

    render(<DiffReviewView originalText={orig} polishedText={polished} />)

    expect(screen.getByText('双栏对比审校')).toBeInTheDocument()
    expect(screen.getByText(/原稿 2 段 \/ 润色稿 2 段/)).toBeInTheDocument()
    expect(screen.getByText('原稿（修改前）')).toBeInTheDocument()
    expect(screen.getByText('AI 润色 / 去味优化稿')).toBeInTheDocument()
    expect(screen.getByText('第一段原稿内容。')).toBeInTheDocument()
    expect(screen.getByText('第一段润色后内容。')).toBeInTheDocument()
  })

  it('点击采纳与放弃按钮触发回调', () => {
    const handleAccept = vi.fn()
    const handleReject = vi.fn()
    const orig = '原稿文字'
    const polished = '润色文字'

    render(
      <DiffReviewView
        originalText={orig}
        polishedText={polished}
        onAccept={handleAccept}
        onReject={handleReject}
      />
    )

    const acceptBtn = screen.getByText('采纳润色稿')
    fireEvent.click(acceptBtn)
    expect(handleAccept).toHaveBeenCalledWith('润色文字')

    const rejectBtn = screen.getByText('放弃改动')
    fireEvent.click(rejectBtn)
    expect(handleReject).toHaveBeenCalledTimes(1)
  })

  it('点击复制润色稿按钮能调用剪贴板并变更状态文本', () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    })

    const orig = '原稿文字'
    const polished = '润色文字'

    render(<DiffReviewView originalText={orig} polishedText={polished} />)

    const copyBtn = screen.getByText('复制润色稿')
    fireEvent.click(copyBtn)

    expect(writeTextMock).toHaveBeenCalledWith('润色文字')
    expect(screen.getByText('已复制！')).toBeInTheDocument()
  })

  it('在 en-US 语言环境下渲染纯正英文标签与动作按钮', () => {
    writeStorage('novellab.locale', 'en-US')
    try {
      const orig = 'Original paragraph 1.\nOriginal paragraph 2.'
      const polished = 'Polished paragraph 1.\nOriginal paragraph 2.'

      render(
        <I18nProvider>
          <DiffReviewView
            originalText={orig}
            polishedText={polished}
            onAccept={vi.fn()}
            onReject={vi.fn()}
          />
        </I18nProvider>
      )

      expect(screen.getByText('Side-by-Side Review')).toBeInTheDocument()
      expect(screen.getByText(/Original 2 paras \/ Polished 2 paras/)).toBeInTheDocument()
      expect(screen.getByText('Original Draft (Before)')).toBeInTheDocument()
      expect(screen.getByText('AI Polish / Anti-Slop Revision (After)')).toBeInTheDocument()
      expect(screen.getByText('Copy Polished')).toBeInTheDocument()
      expect(screen.getByText('Discard')).toBeInTheDocument()
      expect(screen.getByText('Accept Polish')).toBeInTheDocument()
    } finally {
      removeStorage('novellab.locale')
    }
  })
})
