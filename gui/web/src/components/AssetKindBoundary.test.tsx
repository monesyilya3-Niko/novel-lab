// Task 7 边界回归：distilled / prose_card_index 不得混进 voice-card 与 prose_card 选择器。
//
// 只锁前端选择器边界（后端已按内容拒绝错配 kind），因此全部走 mock，不触网、不启服务。
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WritingWorkbench from './WritingWorkbench'
import AssetLibrary from './AssetLibrary'

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
}))

/** 打开指定 MUI Select 并返回其当前渲染的 option 文本（每个用例只开一个，避免菜单叠加）。 */
function openSelectOptions(label: string): string[] {
  fireEvent.mouseDown(screen.getByLabelText(label))
  return screen.getAllByRole('option').map((o) => o.textContent ?? '')
}

const lastKindArg = () => {
  const calls = listAssetsMock.mock.calls
  return calls[calls.length - 1]?.[0]
}

beforeEach(() => {
  assetListMock.mockReset()
  listAssetsMock.mockReset()
  injectMock.mockReset()
  assetListMock.mockResolvedValue({ total: ASSETS.length, items: ASSETS })
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

  it('默认选中第一张 distilled 并随 body 一起注入', async () => {
    render(<WritingWorkbench />)
    await screen.findByLabelText('蒸馏规则（可选）')

    fireEvent.click(screen.getByRole('button', { name: '生成 Prompt' }))
    await waitFor(() => expect(injectMock).toHaveBeenCalledTimes(1))
    expect(injectMock.mock.calls[0][0]).toMatchObject({ voice: 'voice-a', distilled: 'distilled-a' })
  })

  it('无 distilled 资产时 body 传 distilled: undefined', async () => {
    assetListMock.mockResolvedValue({ total: 1, items: [ASSETS[0]] })
    render(<WritingWorkbench />)
    await screen.findByLabelText('蒸馏规则（可选）')

    fireEvent.click(screen.getByRole('button', { name: '生成 Prompt' }))
    await waitFor(() => expect(injectMock).toHaveBeenCalledTimes(1))
    expect(injectMock.mock.calls[0][0]).toMatchObject({ voice: 'voice-a', distilled: undefined })
  })
})

describe('资产库 kind 标签边界', () => {
  it('distilled / prose_card_index 各有独立分类，文风卡筛选仍只请求 prose_card', async () => {
    render(<AssetLibrary />)

    fireEvent.click(screen.getByText('蒸馏规则'))
    await waitFor(() => expect(lastKindArg()).toBe('distilled'))

    fireEvent.click(screen.getByText('题材文风卡索引'))
    await waitFor(() => expect(lastKindArg()).toBe('prose_card_index'))

    fireEvent.click(screen.getByText('文风卡'))
    await waitFor(() => expect(lastKindArg()).toBe('prose_card'))
  })
})
