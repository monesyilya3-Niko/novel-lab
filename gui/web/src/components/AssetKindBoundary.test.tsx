// Task 7 边界回归：distilled / prose_card_index 必须与 voice / prose_card 分开。
//
// 边界怎么锁定：
// - distilled 不得混进 voice-card 下拉，只能走独立的「蒸馏规则」下拉。
// - prose_card_index 当前 UI 没有 prose_card 选择器（注入面板只暴露 voice / genre-pack /
//   craft / distilled），因此「索引不得被当成 prose_card」由资产库分类间接锁定：
//   索引独立成 kind，点「题材文风卡索引」请求的是 prose_card_index 而不是 prose_card。
// - 高级工作台资产编辑同理：索引不进可编辑下拉，其余 kind 显示中文标签。
//
// 全部走 mock，不触网、不启服务、不调用 LLM。
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WritingWorkbench from './WritingWorkbench'
import AssetLibrary from './AssetLibrary'
import AdvancedWorkbench from './AdvancedWorkbench'

type Row = { id: string; name: string; kind: string }

const ASSETS: Row[] = [
  { id: 'voice-a', name: 'voice-A', kind: 'voice' },
  { id: 'craft-a', name: 'craft-A', kind: 'craft' },
  { id: 'distilled-a', name: 'distilled-A', kind: 'distilled' },
  { id: 'genre-prose-card-index', name: 'genre-prose-card-index', kind: 'prose_card_index' },
]

const { assetListMock, listAssetsMock, injectMock } = vi.hoisted(() => ({
  assetListMock: vi.fn(),
  listAssetsMock: vi.fn(),
  injectMock: vi.fn(),
}))

vi.mock('../api/client', () => ({
  friendlyError: (e: unknown) => String(e),
  assetApi: {
    list: (...args: unknown[]) => assetListMock(...args),
    detail: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  listAssets: (...args: unknown[]) => listAssetsMock(...args),
  getAssetDetail: vi.fn(),
  subscribeTaskEvents: vi.fn(() => () => {}),
  writingApi: {
    inject: (...args: unknown[]) => injectMock(...args),
    projects: vi.fn().mockResolvedValue([]),
    generate: vi.fn(),
    taskState: vi.fn(),
    importChapter: vi.fn(),
    score: vi.fn(),
    assemble: vi.fn(),
    assembleCandidates: vi.fn().mockResolvedValue([]),
  },
  advancedApi: {
    distillStatus: vi.fn().mockResolvedValue({ books: [], distilledAssets: [], canDistill: false }),
    distillRun: vi.fn(),
    batchStatus: vi.fn().mockResolvedValue({ books: [] }),
  },
  styleApi: {
    list: vi.fn().mockResolvedValue({ styles: [] }),
    get: vi.fn(),
    analyze: vi.fn(),
    save: vi.fn(),
    delete: vi.fn(),
    apply: vi.fn(),
  },
  platformApi: {
    list: vi.fn().mockResolvedValue([]),
    get: vi.fn(),
    check: vi.fn(),
    format: vi.fn(),
    export: vi.fn(),
  },
}))

/** 打开指定 MUI Select 并返回其当前渲染的 option 文本（每个用例只开一个，避免菜单叠加）。 */
function openSelectOptions(label: string): string[] {
  fireEvent.mouseDown(screen.getByLabelText(label))
  return screen.getAllByRole('option').map((o) => o.textContent ?? '')
}

/** 让 assetApi.list 像真实后端那样按 kind 过滤：不带 kind 返回全量（受 limit 限制）。 */
function mockAssetList(rows: Row[]) {
  assetListMock.mockImplementation(async (args?: { kind?: string }) => {
    const items = args?.kind ? rows.filter((a) => a.kind === args.kind) : rows
    return { total: items.length, items }
  })
}

const lastKindArg = () => {
  const calls = listAssetsMock.mock.calls
  return calls[calls.length - 1]?.[0]
}

beforeEach(() => {
  assetListMock.mockReset()
  listAssetsMock.mockReset()
  injectMock.mockReset()
  mockAssetList(ASSETS)
  listAssetsMock.mockResolvedValue({ total: 0, items: [] })
  injectMock.mockResolvedValue({
    prompt: 'p', charCount: 1, injectedKinds: ['voice'], meta: { sourceTitle: '', genre: '', savedPath: null },
  })
})

describe('注入面板 kind 边界', () => {
  it('voice-card 下拉只含 voice 资产', async () => {
    render(<WritingWorkbench />)
    await screen.findByLabelText('蒸馏规则（可选）')

    expect(openSelectOptions('voice-card（必选）')).toEqual(['voice-A'])
  })

  it('蒸馏卡走独立的「蒸馏规则」下拉', async () => {
    render(<WritingWorkbench />)
    await screen.findByLabelText('蒸馏规则（可选）')

    expect(openSelectOptions('蒸馏规则（可选）')).toEqual(['无', 'distilled-A'])
  })

  it('蒸馏卡按 kind 拉取：首页列表被 limit 截断时仍能选中第一张蒸馏卡', async () => {
    // 模拟资产总数超 100：不带 kind 的首页只回 voice，蒸馏卡只能靠 kind 过滤拿到。
    assetListMock.mockImplementation(async (args?: { kind?: string }) => {
      const items = args?.kind === 'distilled' ? ASSETS.filter((a) => a.kind === 'distilled') : [ASSETS[0]]
      return { total: items.length, items }
    })
    render(<WritingWorkbench />)
    await screen.findByLabelText('蒸馏规则（可选）')

    expect(openSelectOptions('蒸馏规则（可选）')).toEqual(['无', 'distilled-A'])
  })

  it('默认选中第一张 distilled 并随 body 一起注入', async () => {
    render(<WritingWorkbench />)
    await screen.findByLabelText('蒸馏规则（可选）')

    fireEvent.click(screen.getByRole('button', { name: '生成 Prompt' }))
    await waitFor(() => expect(injectMock).toHaveBeenCalledTimes(1))
    expect(injectMock.mock.calls[0][0]).toMatchObject({ voice: 'voice-a', distilled: 'distilled-a' })
  })

  it('无 distilled 资产时 body 传 distilled: undefined', async () => {
    mockAssetList([ASSETS[0]])
    render(<WritingWorkbench />)
    await screen.findByLabelText('蒸馏规则（可选）')

    fireEvent.click(screen.getByRole('button', { name: '生成 Prompt' }))
    await waitFor(() => expect(injectMock).toHaveBeenCalledTimes(1))
    expect(injectMock.mock.calls[0][0]).toMatchObject({ voice: 'voice-a', distilled: undefined })
  })
})

describe('资产库分类与 kind 标签边界', () => {
  it('蒸馏规则 / 题材文风卡索引各有独立分类，文风卡筛选只请求 prose_card', async () => {
    render(<AssetLibrary />)

    fireEvent.click(screen.getByText('蒸馏规则'))
    await waitFor(() => expect(lastKindArg()).toBe('distilled'))

    fireEvent.click(screen.getByText('题材文风卡索引'))
    await waitFor(() => expect(lastKindArg()).toBe('prose_card_index'))

    fireEvent.click(screen.getByText('文风卡'))
    await waitFor(() => expect(lastKindArg()).toBe('prose_card'))
  })
})

describe('资产编辑面板 kind 标签边界', () => {
  it('下拉与选中态 Chip 显示中文标签，索引不进可编辑列表', async () => {
    render(<AdvancedWorkbench />)
    fireEvent.click(screen.getByRole('tab', { name: '资产编辑' }))
    const select = await screen.findByLabelText('选择资产')

    fireEvent.mouseDown(select)
    expect(screen.getAllByRole('option').map((o) => o.textContent ?? '')).toEqual([
      'voice-A（声线卡）',
      'craft-A（笔法卡）',
      'distilled-A（蒸馏规则）',
    ])

    fireEvent.click(screen.getByRole('option', { name: 'distilled-A（蒸馏规则）' }))
    // 选中态 Chip 同样走中文标签，不再显示原始 kind
    expect(await screen.findByText('蒸馏规则')).toBeInTheDocument()
    expect(screen.queryByText('distilled')).not.toBeInTheDocument()
    // 索引被排除在可编辑列表外，只给只读提示
    expect(screen.getByText(/只读寻址表/)).toBeInTheDocument()
  })
})
