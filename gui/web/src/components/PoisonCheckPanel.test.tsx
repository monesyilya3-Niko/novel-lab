import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import PoisonCheckPanel from './PoisonCheckPanel'

vi.mock('../api/client', () => ({
  toolsApi: {
    checkPoison: vi.fn().mockResolvedValue({
      score: 25,
      verdict: '警告：存在部分憋屈或送人头情节',
      totalIssues: 1,
      findings: [
        {
          line: 3,
          type: 'excessive_suffering',
          typeName: '过度憋屈受辱',
          severity: 'fatal',
          snippet: '低头不敢出声，受尽了百般刁难',
          matched: '低头不敢出声',
          reason: '主角遭受侮辱无反击',
          suggestion: '当场展现反击动作',
        },
      ],
    }),
    getTaboos: vi.fn().mockResolvedValue({
      totalCount: 1,
      taboos: [
        {
          id: 'TB-001',
          name: '长篇憋屈无反击 (Excessive Suffering)',
          severity: 'fatal',
          description: '主角连续2章以上遭遇不公诬陷却隐忍自证。',
          readerReaction: '极度胸闷烦躁，直接弃书。',
          fixSuggestion: '受辱必须在同一章节内完成打脸反击。',
        },
      ],
    }),
  },
  friendlyError: (e: unknown) => String(e),
}))

describe('PoisonCheckPanel', () => {
  it('渲染并执行毒点扫描', async () => {
    render(<PoisonCheckPanel />)
    expect(screen.getByText('毒点快速排查 (本地规则)')).toBeDefined()

    const textarea = screen.getByPlaceholderText('请在此粘贴需要检测的章节正文或剧情草稿...')
    fireEvent.change(textarea, { target: { value: '主角低头不敢出声，受尽了百般刁难。' } })

    const scanBtn = screen.getByText('一键扫描毒点')
    fireEvent.click(scanBtn)

    await waitFor(() => {
      expect(screen.getByText('警告：存在部分憋屈或送人头情节')).toBeDefined()
      expect(screen.getByText('过度憋屈受辱')).toBeDefined()
      expect(screen.getByText(/当场展现反击动作/)).toBeDefined()
    })
  })

  it('切换到弃坑避雷规范库', async () => {
    render(<PoisonCheckPanel />)
    fireEvent.click(screen.getByText('弃坑避雷规范库 (10大红线)'))

    await waitFor(() => {
      expect(screen.getByText('长篇憋屈无反击 (Excessive Suffering)')).toBeDefined()
      expect(screen.getByText(/受辱必须在同一章节内完成打脸反击/)).toBeDefined()
    })
  })
})
