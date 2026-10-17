import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AdvancedWorkbench from './AdvancedWorkbench'
import { I18nProvider } from '../state/I18nContext'
import { advancedApi, assetApi } from '../api/client'

vi.mock('../api/client', () => ({
  advancedApi: {
    distillStatus: vi.fn(),
    distillRun: vi.fn(),
    batchStatus: vi.fn(),
  },
  assetApi: {
    list: vi.fn(),
    detail: vi.fn(),
    update: vi.fn(),
  },
  friendlyError: vi.fn((e) => String(e)),
}))

describe('AdvancedWorkbench 高级功能工坊双语支持', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(advancedApi.distillStatus).mockResolvedValue({
      canDistill: true,
      books: ['book-A', 'book-B'],
      distilledAssets: ['distilled-A'],
    })
    vi.mocked(advancedApi.batchStatus).mockResolvedValue({
      books: [
        {
          name: 'Book-1',
          passCount: 5,
          hasAssets: true,
          passes: { pass1_structure: true, pass2_character: true },
        },
      ],
    })
    vi.mocked(assetApi.list).mockResolvedValue({
      items: [
        { id: 'v1', name: 'voice-1', kind: 'voice' },
      ],
    })
  })

  it('zh-CN 默认环境下渲染中文顶层 Tabs 与四大子面板', async () => {
    render(
      <I18nProvider initialLocale="zh-CN">
        <AdvancedWorkbench />
      </I18nProvider>
    )

    // 四大 Tab 标签
    expect(screen.getByRole('tab', { name: '蒸馏' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '批量状态' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '资产编辑' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '平台适配' })).toBeInTheDocument()

    // 默认处于蒸馏页签
    expect(screen.getByRole('heading', { name: '题材蒸馏' })).toBeInTheDocument()
    expect(screen.getByLabelText('题材')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '执行蒸馏' })).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText(/可蒸馏书目：/)).toBeInTheDocument()
      expect(screen.getByText('可蒸馏')).toBeInTheDocument()
    })

    // 切换到批量状态
    fireEvent.click(screen.getByRole('tab', { name: '批量状态' }))
    expect(await screen.findByRole('heading', { name: '批量拆书状态' })).toBeInTheDocument()
    expect(screen.getByText('已有资产')).toBeInTheDocument()
    expect(screen.getByText('P1 结构')).toBeInTheDocument()

    // 切换到资产编辑
    fireEvent.click(screen.getByRole('tab', { name: '资产编辑' }))
    expect(await screen.findByRole('heading', { name: '资产编辑' })).toBeInTheDocument()
    expect(screen.getByLabelText('选择资产')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '加载' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '保存' })).toBeInTheDocument()
    expect(screen.getByLabelText('资产 JSON 内容')).toBeInTheDocument()
  })

  it('en-US 语言环境下全量渲染英文 Tabs 与子面板文案', async () => {
    render(
      <I18nProvider initialLocale="en-US">
        <AdvancedWorkbench />
      </I18nProvider>
    )

    // 英文四大 Tab
    expect(screen.getByRole('tab', { name: 'Distillation' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Batch Status' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Asset Editor' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Platform Adaptation' })).toBeInTheDocument()

    // 英文蒸馏面板
    expect(screen.getByRole('heading', { name: 'Genre Distillation' })).toBeInTheDocument()
    expect(screen.getByLabelText('Genre')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Execute Distillation' })).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText(/Available Books:/)).toBeInTheDocument()
      expect(screen.getByText('Ready to Distill')).toBeInTheDocument()
    })

    // 切换到英文批量状态面板
    fireEvent.click(screen.getByRole('tab', { name: 'Batch Status' }))
    expect(await screen.findByRole('heading', { name: 'Batch Deconstruction Status' })).toBeInTheDocument()
    expect(screen.getByText('Assets Present')).toBeInTheDocument()
    expect(screen.getByText('P1 Structure')).toBeInTheDocument()

    // 切换到英文资产编辑面板
    fireEvent.click(screen.getByRole('tab', { name: 'Asset Editor' }))
    expect(await screen.findByRole('heading', { name: 'Asset Editor' })).toBeInTheDocument()
    expect(screen.getByLabelText('Select Asset')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Load' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument()
    expect(screen.getByLabelText('Asset JSON Content')).toBeInTheDocument()
  })
})
